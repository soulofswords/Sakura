import json
from agent_learning import AgentLearning

def run(identifier='one',status='completed'):
 return {'id':identifier,'goal':'Summarize confidential document for Alice api_key=SECRET','status':status,'steps':[{'tool':'files.list','status':'completed','arguments':{'path':'private'},'result':{'ok':True}},{'tool':'files.read','status':'completed','arguments':{'path':'secret.txt'},'result':{'ok':True,'text':'PASSWORD PRIVATE CONTENT'}}]}

def test_learning_persists_only_verified_sequences_and_matches_new_task(tmp_path):
 path=tmp_path/'memory.json';memory=AgentLearning(path)
 assert memory.learn(run())
 raw=path.read_text();assert 'Alice' not in raw and 'SECRET' not in raw and 'PASSWORD' not in raw and 'secret.txt' not in raw
 assert not memory.learn(run())
 memory=AgentLearning(path);context=memory.context('Summarize a report')
 assert context['successful_tool_sequences'][0]['tools']==['files.list','files.read']
 assert not memory.context('Schedule my meeting')['successful_tool_sequences']
 assert memory.learn(run('two'));assert memory.status()['procedures'][0]['successes']==2

def test_failed_cancelled_or_claim_only_tasks_do_not_create_memory(tmp_path):
 m=AgentLearning(tmp_path/'memory.json')
 for state in ['failed','ready','cancelled','pending']:assert not m.learn(run(status=state))
 r=run();r['steps'][1]['status']='rejected';assert not m.learn(r)
 r=run();r['steps'][1]['result']['ok']=False;assert not m.learn(r)
 r=run();r['steps']=[];assert not m.learn(r)
 assert m.status()['procedures']==[]

def test_settings_disabled_delete_clear_and_skill_procedure(tmp_path):
 import pytest
 m=AgentLearning(tmp_path/'memory.json');m.configure(False,'Project notes','Keep replies brief')
 assert not m.learn(run()) and m.context('document')=={}
 m.configure(True,'Project notes','Keep replies brief');m.learn(run())
 item=m.status()['procedures'][0];assert 'fresh approval' in m.skill(item['id'])
 m.delete(item['id']);assert m.status()['procedures']==[]
 m.clear();assert m.status()['notes']=='' and m.status()['profile']==''
 with pytest.raises(ValueError):m.configure(True,'x'*2201,'')
 with pytest.raises(ValueError):m.configure(True,'api_key=do-not-store-this','')

def test_runtime_completion_reuses_learning_in_next_plan(tmp_path):
 from agent_connections import Connections
 from agent_runtime import AgentRuntime
 from unittest.mock import Mock
 runtime=AgentRuntime(Connections(tmp_path/'connections.json'))
 current=runtime.new_run('Summarize my report',str(tmp_path));source=tmp_path/'notes.txt';source.write_text('Actual source')
 for tool,args in [('files.list',{'path':str(tmp_path)}),('files.read',{'path':'notes.txt'})]:
  action=runtime.propose(current['id'],tool,args)['steps'][-1]
  runtime.decide(action['id'],True)
 model=Mock();model._request_raw.return_value='{"done":true,"summary":"Reviewed the source document."}'
 result=runtime.plan(current['id'],model)
 assert result['status']=='completed'
 fresh=AgentRuntime(Connections(tmp_path/'connections.json'))
 next_run=fresh.new_run('Summarize another document',str(tmp_path))
 model._request_raw.return_value='{"tool":"files.write","arguments":{"path":"new.md","content":"Verified draft"},"reason":"Prepare new output."}'
 planned=fresh.plan(next_run['id'],model)
 context=json.loads(model._request_raw.call_args.args[0][1]['content'])
 assert context['remembered_guidance']['successful_tool_sequences'][0]['tools']==['files.list','files.read']
 assert planned['steps'][-1]['status']=='pending'
 assert not planned['steps'][-1].get('result')
