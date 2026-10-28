import json
from unittest.mock import Mock,patch

import pytest

from agent_connections import Connections
from agent_history import AgentHistory,MAX_RECORD_BYTES
from agent_runtime import AgentRuntime


def test_text_credentials_are_removed_from_json_and_fts(runtime,tmp_path):
    run=runtime.new_run('Credential cleanup',str(tmp_path))
    runtime.runs[run['id']]['steps']=[{'result':{'output':'password=canarypassword123 api_key=canarykey456 Bearer canarybearer789 safe diagnostic'}}]
    runtime._save_runs()
    for needle in ('canarypassword123','canarykey456','canarybearer789'):
        assert needle not in runtime.store_path.read_text(encoding='utf-8')
        assert runtime.history.search(needle)['results']==[]
        assert needle not in json.dumps(runtime.history.read(run['id']))
    assert runtime.history.search('safe diagnostic')['results']


def test_existing_archive_is_scrubbed_before_search(tmp_path):
    import sqlite3
    path=tmp_path/'legacy.sqlite'
    record={'id':'legacy','goal':'old task','workspace':str(tmp_path),'steps':[{'result':'password=legacycanary123'}]}
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE sessions (id TEXT PRIMARY KEY, created REAL, workspace TEXT, goal TEXT, status TEXT, record TEXT)')
        db.execute('CREATE VIRTUAL TABLE session_search USING fts5(id UNINDEXED,text)')
        db.execute('INSERT INTO sessions VALUES (?,?,?,?,?,?)',('legacy',1,str(tmp_path),'old task','done',json.dumps(record)))
        db.execute('INSERT INTO session_search VALUES (?,?)',('legacy',json.dumps(record)))
    history=AgentHistory(path)
    assert history.search('legacycanary123')['results']==[]
    assert 'legacycanary123' not in json.dumps(history.read('legacy'))
    assert b'legacycanary123' not in path.read_bytes()


@pytest.fixture
def runtime(tmp_path):
    return AgentRuntime(Connections(tmp_path/'connections.json'))


def test_archive_survives_live_eviction_and_restart(runtime,tmp_path):
    first=runtime.new_run('Unique telescope observations',str(tmp_path))
    for number in range(31):runtime.new_run('Other task '+str(number),str(tmp_path))
    assert first['id'] not in runtime.runs
    restored=AgentRuntime(Connections(tmp_path/'connections.json'))
    assert restored.history.search('telescope')['results'][0]['id']==first['id']
    archived=restored.history.read(first['id'])
    assert archived['archived'] is True
    assert first['id'] not in restored.runs


def test_archive_excludes_authority_and_secret_fields(runtime,tmp_path):
    run=runtime.new_run('private record',str(tmp_path))
    action=runtime.propose(run['id'],'files.list',{'path':'.'})['steps'][-1]
    runtime.runs[run['id']]['steps'][-1]['result']={'token':'secret-needle','env':{'KEY':'private'},'output':'safe result'}
    runtime._save_runs()
    record=runtime.history.read(run['id'])
    assert 'bindings' not in record['steps'][0]
    assert 'secret-needle' not in json.dumps(record)
    assert 'approval_digest' not in json.dumps(record)
    assert runtime.history.search('secret-needle')['results']==[]
    assert runtime.history.search('safe result')['results']
    runtime.cancel(run['id'])
    with pytest.raises(ValueError):runtime.decide(action['id'],True)


def test_literal_queries_and_workspace_scope(runtime,tmp_path):
    run=runtime.new_run('alpha quotation café',str(tmp_path))
    assert runtime.history.search('café')['results'][0]['id']==run['id']
    assert runtime.history.search('alpha OR missing')['results']==[]
    assert runtime.history.search('"() *')['results']==[]
    assert runtime.history.search('alpha',str(tmp_path/'other'))['results']==[]
    with pytest.raises(ValueError):runtime.history.read(run['id'],str(tmp_path/'other'))
    with pytest.raises(ValueError):runtime.history.search('x'*301)


def test_clear_removes_archive_and_refuses_active_work(runtime,tmp_path):
    runtime.new_run('erase needle',str(tmp_path))
    with runtime.operation_lock:
        with pytest.raises(ValueError,match='running'):runtime.clear_history()
    assert runtime.history.search('needle')['results']
    assert runtime.clear_history()=={'ok':True}
    assert runtime.history.search('needle')['results']==[]
    assert not runtime.store_path.exists()


def test_archive_is_bounded_and_search_index_tracks_updates(runtime,tmp_path):
    run=runtime.new_run('oldword',str(tmp_path))
    stored=runtime.runs[run['id']]
    stored['goal']='newword'
    stored['steps']=[{'tool':'files.read','result':{'text':'x'*50000}} for _ in range(40)]
    runtime._save_runs()
    assert runtime.history.search('oldword')['results']==[]
    assert len(json.dumps(runtime.history.read(run['id'])).encode())<MAX_RECORD_BYTES+100
    with patch('agent_history.MAX_RECORDS',2):
        for number in range(3):runtime.new_run('limited '+str(number),str(tmp_path))
    assert len(runtime.history.search('limited')['results'])==2


def test_forget_removes_exactly_one_session_from_both_tables(tmp_path):
    history=AgentHistory(tmp_path/'sessions.sqlite')
    for identifier in ('keep-me','drop-me'):
        history.save([{'id':identifier,'goal':'Quarterly report work','workspace':str(tmp_path),'status':'completed','steps':[]}])
    assert history.forget('drop-me')=={'ok':True,'id':'drop-me'}
    assert {row['id'] for row in history.search('quarterly')['results']}=={'keep-me'}
    with pytest.raises(ValueError):history.read('drop-me')
    assert history.forget('drop-me')['ok'] is False


def test_planner_context_gets_source_links_without_archived_bodies(tmp_path):
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'))
    run=runtime.new_run('Summarize the quarterly report',str(tmp_path))
    with patch.object(runtime.history,'search',return_value={'results':[
        {'id':run['id'],'goal':'current task','status':'ready','created_at':3},
        {'id':'old-1','goal':'Earlier quarterly report work','status':'completed','created_at':2,'snippet':'full archived body'}]}) as search:
        model=Mock();model._request_raw.return_value=json.dumps({'done':True,'summary':'Ready.'})
        runtime.plan(run['id'],model)
        context=json.loads(model._request_raw.call_args_list[0].args[0][1]['content'])
        search.assert_called_once_with('Summarize the quarterly report',run['workspace'])
        assert [item['id'] for item in context['related_sessions']]==['old-1']
        assert 'full archived body' not in json.dumps(context['related_sessions'])
