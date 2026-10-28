"""Hold the MCP session open while the owner consents in Google's browser page."""
import argparse
import asyncio
import os
import json
from pathlib import Path
import re
import sys
import webbrowser


async def authorize(app, email):
    sys.path.insert(0,str(app))
    from agent_connections import Connections, secret_get, secret_set
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    config=next(item for item in Connections().public() if item['name']=='Google Workspace MCP')
    secret=secret_get('mcp:'+config['id'])
    secret['env']['USER_GOOGLE_EMAIL']=email
    secret_set('mcp:'+config['id'],secret)
    env={key:os.environ[key] for key in ('PATH','SYSTEMROOT','WINDIR','TEMP','TMP','USERPROFILE','HOME') if key in os.environ}
    env.update(secret['env'])
    folder=Path(env['WORKSPACE_MCP_CREDENTIALS_DIR'])
    before={p:p.stat().st_mtime_ns for p in folder.rglob('*.json')}
    # Server logs can contain OAuth URLs. Keep them out of chat/tool output.
    with (folder/'authorization.log').open('a',encoding='utf-8') as log:
        async with stdio_client(StdioServerParameters(command=config['command'],args=config['args'],env=env),errlog=log) as streams:
            async with ClientSession(streams[0],streams[1]) as session:
                await session.initialize()
                result=await session.call_tool('list_calendars',{'user_google_email':email})
                text='\n'.join(getattr(block,'text','') for block in result.content)
                if not result.isError and 'ACTION REQUIRED' not in text:
                    print('Google authorization already works. Calendar MCP check: succeeded.',flush=True)
                    return
                match=re.search(r'https://accounts\.google\.com/[^\s<>]+',text)
                if not match:
                    print('Google did not return a consent URL. Check the private authorization log.',flush=True)
                    log.write(text+'\n')
                    return
                if 'automatically opened' not in text:
                    webbrowser.open(match.group(0).rstrip(')\"'))
                print('Opened Google consent. Waiting for your approval in the browser.',flush=True)
                for _ in range(300):
                    await asyncio.sleep(1)
                    saved=False
                    for p in folder.rglob('*.json'):
                        if p.stat().st_mtime_ns==before.get(p):continue
                        try:
                            record=json.loads(p.read_text(encoding='utf-8'))
                            saved=isinstance(record,dict) and bool(record.get('refresh_token') or record.get('token'))
                        except (OSError,ValueError):continue
                        if saved:break
                    if saved:
                        print('Google authorization saved locally. Checking Calendar access.',flush=True)
                        listing=await session.list_tools()
                        tool=next((t for t in listing.tools if t.name=='list_calendars'),None)
                        if tool:
                            checked=await session.call_tool(tool.name,{'user_google_email':email})
                            print('Calendar MCP check: '+('failed; see private log' if checked.isError else 'succeeded'),flush=True)
                            if checked.isError:log.write(str(checked)+'\n')
                        return
                print('Google consent was not completed within five minutes. No connection was claimed.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app',type=Path,required=True)
    parser.add_argument('--email',required=True)
    args=parser.parse_args()
    asyncio.run(authorize(args.app,args.email))
