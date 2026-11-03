with open('F:/AI/assistant/Sakura/agent_runtime.py', 'r', errors='ignore') as f:
    content = f.read()
old = "    {'name':'calendar.events.create',"
new = "    {'name':'process.list','description':'List agent-related processes. Read-only; approval needed.', 'inputSchema':{'type':'object','properties':{},'additionalProperties':False}},\n    {'name':'process.kill','description':'Kill a process by PID with approval.', 'inputSchema':{'type':'object','properties':{'pid':{'type':'integer'}},'required':['pid'],'additionalProperties':False}},\n    {'name':'calendar.events.create',"
if old in content:
    content = content.replace(old, new)
    with open('F:/AI/assistant/Sakura/agent_runtime.py', 'w') as f:
        f.write(content)
    print('Registered process tools in agent_runtime LOCAL_TOOLS')
else:
    print('Target not found — agent_runtime may already have them or needs manual edit.')
