"""Explicitly configured MCP transports; connecting never grants tool approval."""
import asyncio
import copy
import json
import os
import re
import threading
import uuid
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

from config import BASE_DIR


def secret_get(slot):
    from credentials import get_cloud_key
    value=get_cloud_key('agent:'+slot)
    return json.loads(value) if value else {}


def secret_set(slot,value):
    from credentials import set_cloud_key
    set_cloud_key('agent:'+slot,json.dumps(value) if value else '')


def bounded_schema(schema):
    if not isinstance(schema,dict) or len(json.dumps(schema))>64000:raise ValueError('The MCP tool schema exceeds the supported size.')
    def visit(value,depth=0):
        if depth>40:raise ValueError('The MCP schema nesting is too deep.')
        if isinstance(value,dict):
            for key,item in value.items():
                if key in ('$ref','$dynamicRef') and (not isinstance(item,str) or not item.startswith('#')):
                    raise ValueError('External schema references are not permitted; the MCP server must supply self-contained tool schemas.')
                visit(item,depth+1)
        elif isinstance(value,list):
            for item in value:visit(item,depth+1)
    visit(schema)
    return schema


class Connections:
    def __init__(self,path=None):
        self.path=Path(path or BASE_DIR/'agent-connections.json');self.lock=threading.RLock()
        self.tools={}
    def all(self):
        with self.lock:
            try:value=json.loads(self.path.read_text(encoding='utf-8'))
            except (OSError,ValueError):value={}
        return value if isinstance(value,dict) else {}
    def get(self,identifier):
        item=self.all().get(identifier)
        if not item:raise ValueError('MCP connection not found.')
        return copy.deepcopy(item)
    def save(self,payload):
        name=payload.get('name','').strip()
        if not name or len(name)>80:raise ValueError('Give the connection a name of up to 80 characters.')
        kind=payload.get('transport','http')
        identifier=payload.get('id') or uuid.uuid4().hex
        if not re.fullmatch(r'[a-f0-9]{32}',identifier):raise ValueError('Invalid connection ID.')
        config={'id':identifier,'name':name,'transport':kind,'revision':uuid.uuid4().hex}
        if kind=='http':
            url=payload.get('url','');parsed=urlparse(url)
            if (parsed.scheme not in ('https','http') or not parsed.hostname or parsed.username or parsed.password
                    or parsed.query or parsed.fragment or (parsed.scheme=='http' and parsed.hostname not in ('localhost','127.0.0.1','::1'))):
                raise ValueError('Use an HTTPS MCP URL, or HTTP on localhost. Put credentials in the token field, not the URL.')
            config['url']=url
        elif kind=='stdio':
            command=payload.get('command','');args=payload.get('args',[])
            if not isinstance(command,str) or not command or len(command)>500:raise ValueError('Enter the MCP server executable.')
            if not isinstance(args,list) or len(args)>50 or any(not isinstance(x,str) or len(x)>2000 for x in args):raise ValueError('MCP arguments must be an array of strings.')
            config.update(command=command,args=args)
        else:raise ValueError('Choose http or stdio.')
        env=payload.get('env',{})
        if not isinstance(env,dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in env.items()):raise ValueError('Environment variables must be string key/value pairs.')
        old=secret_get('mcp:'+identifier)
        if payload.get('token'):old['token']=payload['token']
        if env:old['env']=env
        config['credential_set']=bool(old.get('token') or old.get('env'))
        config['environment_keys']=list(old.get('env',{}))
        secret_set('mcp:'+identifier,old)
        with self.lock:
            data=self.all();data[identifier]=config
            temp=self.path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2),encoding='utf-8');temp.replace(self.path)
            self.tools.pop(identifier,None)
        return config
    def remove(self,identifier):
        with self.lock:
            data=self.all();data.pop(identifier,None)
            temp=self.path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2),encoding='utf-8');temp.replace(self.path)
            self.tools.pop(identifier,None)
        secret_set('mcp:'+identifier,{})
    def public(self):return list(self.all().values())


async def _mcp_request(config,operation,tool=None,arguments=None,schema_hash=None):
    from contextlib import AsyncExitStack
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.client.streamable_http import streamablehttp_client
    from jsonschema import validate
    from agent_runtime import digest
    secrets=secret_get('mcp:'+config['id'])
    async with AsyncExitStack() as stack:
        if config['transport']=='stdio':
            env={key:os.environ[key] for key in ('PATH','SYSTEMROOT','WINDIR','TEMP','TMP','USERPROFILE','HOME') if key in os.environ}
            env.update(secrets.get('env',{}))
            streams=await stack.enter_async_context(stdio_client(StdioServerParameters(command=config['command'],args=config['args'],env=env)))
        else:
            headers={'Authorization':'Bearer '+secrets['token']} if secrets.get('token') else {}
            streams=await stack.enter_async_context(streamablehttp_client(config['url'],headers=headers,timeout=timedelta(seconds=20),sse_read_timeout=timedelta(seconds=30)))
        session=await stack.enter_async_context(ClientSession(streams[0],streams[1],read_timeout_seconds=timedelta(seconds=30)))
        await session.initialize()
        listing=await session.list_tools()
        tools=[{'name':item.name,'description':(item.description or '')[:1200],'inputSchema':bounded_schema(item.inputSchema)} for item in listing.tools[:80]]
        if operation=='discover':return tools
        selected=next((item for item in tools if item['name']==tool),None)
        if not selected:raise ValueError('The connected server no longer exposes this tool. Discover its tools again.')
        if digest(selected['inputSchema'])!=schema_hash:raise ValueError('The tool schema changed. Review a new proposal before execution.')
        validate(arguments,selected['inputSchema'])
        result=await session.call_tool(tool,arguments)
        # Keep image/audio blobs out of planner history and bound remote output.
        content=[];budget=64000;truncated=False
        for block in result.content[:40]:
            kind=getattr(block,'type','unknown')
            if kind=='text':
                raw=block.text;portion=raw[:budget];budget-=len(portion)
                content.append({'type':'text','text':portion});truncated|=len(raw)>len(portion)
            else:content.append({'type':kind,'note':'Non-text tool output is not supplied to the planner.'})
            if budget<=0:truncated=True;break
        structured=getattr(result,'structuredContent',None)
        if structured:
            raw=json.dumps(structured,ensure_ascii=False)
            content.append({'type':'text','text':raw[:budget]});truncated|=len(raw)>budget
        return {'is_error':bool(result.isError),'content':content,'output_truncated':truncated or len(result.content)>40}


def mcp_request(config,operation,**kwargs):
    async def bounded():
        async with asyncio.timeout(45):return await _mcp_request(config,operation,**kwargs)
    return asyncio.run(bounded())
