import importlib.util
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock,patch
import pytest
from agent_usage import capture_usage,record_usage,summarize,merge
from agent_loop_guard import inspect as loop_check
from agent_connections import Connections
from agent_runtime import AgentRuntime
from agent_skills import AgentSkills
from agent_knowledge import Knowledge
from sandbox_mount_policy import validate_mount


def test_usage_reports_unknown_prices_and_preserves_cache_independent_estimate():
    messages=[{'role':'user','content':'long private query '*100}]
    with capture_usage() as rows:
        record_usage('ollama','qwen',messages,{'prompt_eval_count':1,'eval_count':10})
        record_usage('gemini','test',messages,{'usageMetadata':{'promptTokenCount':100,'candidatesTokenCount':20,'thoughtsTokenCount':30}})
    assert rows[0]['prompt_estimated_tokens']>rows[0]['input_tokens']
    assert rows[1]['output_tokens']==50
    assert 'private' not in json.dumps(rows)
    assert summarize(rows)['cost_usd_estimate'] is None
    priced=summarize(rows,{'ollama/qwen':{'input':0,'output':0},'gemini/test':{'input':1,'output':2}})
    assert priced['cost_usd_estimate']==.0002
    assert merge(priced,summarize(rows))['cost_usd_estimate'] is None
    assert priced['budget_tokens']>priced['input_tokens']+priced['output_tokens']


def test_usage_context_isolated_between_threads():
    def work(n):
        with capture_usage() as rows:record_usage('ollama',str(n),[],{'eval_count':n})
        return rows
    with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(work,[3,8]))
    assert [x[0]['output_tokens'] for x in rows]==[3,8]


def test_planner_loops_warn_then_block_and_allow_real_progress():
    a={'tool':'files.read','arguments':{'path':'a.txt'},'status':'completed'}
    b={**a,'arguments':{'path':'b.txt'}}
    assert not loop_check([a],a['tool'],a['arguments'])['warning']
    assert loop_check([a,a],a['tool'],a['arguments'])['warning']
    assert not loop_check([a,a],a['tool'],a['arguments'])['blocked']
    assert loop_check([a,a,a],a['tool'],a['arguments'])['blocked']
    assert loop_check([a,b,a,b,a],b['tool'],b['arguments'])['blocked']
    assert not loop_check([a,a,a],'files.read',{'path':'new.txt'})['blocked']


def test_skill_import_provenance_aliases_dependencies_and_no_execution(tmp_path):
    skills=AgentSkills(tmp_path/'skills.json');skills.save('base','Read current sources and verify the answer.')
    item=skills.import_markdown('---\nname: research\ndescription: Research a topic\nallowed-tools: ["Read", "WebSearch"]\ndependencies: ["base"]\n---\nRead the source and search for confirming evidence.','reviewed.md')
    assert item['required_tools']==['files.read','web.search'] and item['script_execution'] is False
    assert len(item['provenance']['sha256'])==64
    assert skills.resolve('research',['files.read','web.search'])['dependency_guidance'][0]['name']=='base'
    with pytest.raises(ValueError,match='unavailable'):skills.resolve('research',['files.read'])
    with pytest.raises(ValueError,match='cycle'):skills.import_markdown('---\nname: cycle\ndependencies: ["cycle"]\n---\nRead the current source and verify it.')
    with pytest.raises(ValueError):skills.import_markdown('---\nname: unsafe\nname: other\n---\nRead the source and verify it.')


def test_knowledge_is_workspace_scoped_and_reindexes_without_duplicates(tmp_path):
    index=Knowledge(tmp_path/'knowledge.db');one=tmp_path/'one';two=tmp_path/'two'
    first=index.index(one,'report.md','Electric motor efficiency is 92 percent.\n'*100)
    assert first['chunks']>1
    assert index.index(one,'report.md','Electric motor efficiency is 92 percent.\n'*100)['unchanged']
    found=index.search(one,'motor efficiency');assert found['results'] and found['results'][0]['source']=='report.md'
    assert index.search(two,'motor efficiency')['results']==[]
    index.index(one,'report.md','Hydraulic pump measurements only.')
    assert index.search(one,'electric motor')['results']==[]
    index.clear(one);assert index.search(one,'hydraulic')['results']==[]


def test_index_tools_use_approval_and_recheck_source(tmp_path):
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'));file=tmp_path/'notes.md';file.write_text('Read and index these facts.')
    run=runtime.new_run('Index my notes',str(tmp_path),False)
    step=runtime.propose(run['id'],'knowledge.index',{'path':'notes.md'})['steps'][-1]
    assert step['status']=='pending'
    file.write_text('Changed after review.')
    result=runtime.decide(step['id'],True)['action']
    assert result['status']=='failed'
    assert runtime.knowledge.search(tmp_path,'changed')['results']==[]


@pytest.mark.parametrize('filename',['.env','.npmrc','private.pem','.git/config','.ssh/id_ed25519','settings.json'])
def test_container_mount_blocks_credentials(tmp_path,filename):
    file=tmp_path/filename;file.parent.mkdir(parents=True,exist_ok=True);file.write_text('private')
    with pytest.raises(ValueError,match='protected|credential'):validate_mount(tmp_path)


def test_usage_budget_stops_next_planner_call(tmp_path):
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'));run=runtime.new_run('Read notes',str(tmp_path))
    runtime.usage_config({'prices':{},'max_tokens':1,'max_cost_usd':0})
    runtime.runs[run['id']]['usage']={'budget_tokens':5,'calls':1,'input_tokens':5,'output_tokens':0}
    model=Mock();state=runtime.plan(run['id'],model)
    assert state['status']=='blocked';model._request_raw.assert_not_called()


def test_cost_budget_requires_known_prices_before_first_paid_call(tmp_path):
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'));run=runtime.new_run('Read notes',str(tmp_path))
    runtime.usage_config({'prices':{},'max_tokens':0,'max_cost_usd':1})
    model=Mock(provider='gemini',gemini_model='unknown-price')
    result=runtime.plan(run['id'],model)
    assert result['status']=='blocked';model._request_raw.assert_not_called()


def test_two_skill_stores_do_not_lose_concurrent_updates(tmp_path):
    path=tmp_path/'skills.json';one=AgentSkills(path);two=AgentSkills(path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=[pool.submit(store.save,name,'Read the current source and verify it.') for store,name in [(one,'first'),(two,'second')]]
        for result in results:result.result()
    assert {x['name'] for x in one.list()}=={'first','second'}


def test_planning_persists_reported_usage_on_real_runtime(tmp_path):
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'));run=runtime.new_run('Read notes',str(tmp_path),False)
    class Model:
        provider='ollama';model='test';base_url='http://127.0.0.1:11434'
        def _request_raw(self,messages,**kwargs):
            record_usage('ollama','test',messages,{'prompt_eval_count':10,'eval_count':7})
            return json.dumps({'tool':'files.list','arguments':{'path':str(tmp_path)}})
    result=runtime.plan(run['id'],Model())
    assert result['status']=='awaiting_approval' and result['usage']['output_tokens']==7
    assert runtime.metrics()['summary']['inference']['calls']==1
    assert AgentRuntime(Connections(tmp_path/'connections.json')).state(run['id'])['usage']['input_tokens']==10


def test_doctor_never_contacts_cloud_and_runs_local_probes_in_parallel(tmp_path):
    from sakura_doctor import diagnose,local_health
    with patch('requests.get') as request:
        result=diagnose(Path(__file__).resolve().parents[1]);assert result['cloud_probed'] is False;request.assert_not_called()
        assert local_health({'cloud':'https://example.com/health'})[0]['ready'] is False;request.assert_not_called()
    import threading
    barrier=threading.Barrier(2)
    def respond(*args,**kwargs):barrier.wait(timeout=2);return Mock(status_code=200)
    with patch('requests.Session.get',side_effect=respond):
        states=local_health({'one':'http://127.0.0.1:11434/api/tags','two':'http://127.0.0.1:1234/health'})
    assert all(x['ready'] for x in states)


def test_real_benchmark_runner_is_resumable_and_does_not_execute_tools(tmp_path):
    path=Path(__file__).resolve().parents[1]/'tools/benchmark-assistant.py'
    spec=importlib.util.spec_from_file_location('assistant_bench',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    model=Mock(provider='ollama',model='test');model._request_raw.return_value='I cannot do that without evidence.'
    output=tmp_path/'bench.jsonl';module.run(model,output)
    assert model._request_raw.call_count==len(module.CASES)
    module.run(model,output);assert model._request_raw.call_count==len(module.CASES)
    assert all('usage' in json.loads(line) for line in output.read_text().splitlines())
    assert 'cannot do that' not in output.read_text()


def test_new_agent_api_routes_require_local_token_and_return_real_data(tmp_path,monkeypatch):
    import re
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import agent_api
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'))
    monkeypatch.setattr(agent_api,'runtime',runtime)
    router=agent_api.agent_router(lambda *args:Mock(conversation_mode='teacher'))
    app=FastAPI();app.include_router(router)
    client=TestClient(app,base_url='http://127.0.0.1:8790',client=('127.0.0.1',35000))
    token=re.search(r"const token='([^']+)'",client.get('/agent').text)[1];headers={'X-Sakura-Agent':token}
    assert client.get('/api/agent/doctor').status_code==403
    assert client.post('/api/agent/skills/import',json={'markdown':'test'}).status_code==403
    assert client.get('/api/agent/usage-config',headers=headers).json()['prices']=={}
    saved=client.post('/api/agent/usage-config',headers=headers,json={'prices':{'gemini/test':{'input':1,'output':2}},'max_tokens':5000,'max_cost_usd':0})
    assert saved.status_code==200 and saved.json()['max_tokens']==5000
    invalid=client.post('/api/agent/usage-config',headers=headers,json={'prices':{},'max_tokens':-1})
    assert invalid.status_code==400
    imported=client.post('/api/agent/skills/import',headers=headers,json={'markdown':'---\nname: tested-import\n---\nRead actual sources and verify the result.','source':'SKILL.md'})
    assert imported.status_code==200 and runtime.skills.get('tested-import')['provenance']['label']=='SKILL.md'
    health=client.get('/api/agent/doctor',headers=headers)
    assert health.status_code==200 and health.json()['cloud_probed'] is False


def test_docker_mount_is_rechecked_after_approval(tmp_path):
    from agent_backends import prepare,execute
    args={'backend':'docker','image':'sha256:'+'a'*64,'command':'pwd','cwd':str(tmp_path)}
    run={'workspace':str(tmp_path)}
    with patch('agent_backends.shutil.which',return_value=sys.executable):bindings,_=prepare(args,run,tmp_path)
    (tmp_path/'.env').write_text('private settings appeared after review')
    process=Mock()
    with pytest.raises(ValueError,match='protected'):execute(args,run,bindings,process)
    process.assert_not_called()
