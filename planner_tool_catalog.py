"""Bound untrusted MCP metadata before it enters a planner's context."""
import json
import re


def planner_tools(catalog, query='', *, max_tools=80, max_bytes=24000):
    words=set(re.findall(r'[a-z0-9]{3,}', query.lower()))
    def relevance(item):
        name=str(item.get('name',''))
        tokens=set(re.findall(r'[a-z0-9]{3,}',(name+' '+str(item.get('description',''))).lower()))
        return (-len(words & tokens), not name.startswith('mcp:'), name)
    result=[];used=2
    for item in sorted(catalog,key=relevance):
        schema=item.get('inputSchema') or {}
        properties={}
        for key,value in list((schema.get('properties') or {}).items())[:40]:
            if not isinstance(value,dict):continue
            enum=value.get('enum')
            properties[str(key)[:100]]=[str(x)[:80] for x in enum[:20]] if isinstance(enum,list) else str(value.get('type','string'))[:30]
        entry={'name':str(item.get('name',''))[:180], 'description':str(item.get('description',''))[:180]}
        # Called takes rather than arguments: the reply the planner owes has a key named arguments,
        # and a small model that sees a catalog key with the same name can hand back that list of
        # names as its own arguments object instead of a set of values.
        if properties:entry['takes']=properties
        if isinstance(schema.get('required'),list):entry['required']=[str(key)[:100] for key in schema['required'][:40]]
        cost=len(json.dumps(entry,ensure_ascii=False).encode('utf-8'))+2
        if used+cost>max_bytes:continue
        result.append(entry);used+=cost
        if len(result)>=max_tools:break
    return result
