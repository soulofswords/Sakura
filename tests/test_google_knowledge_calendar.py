from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from agent_connections import Connections
from agent_runtime import AgentRuntime
from agent_knowledge import _doc_text
from memory_archaeology import MemoryArchaeology
import memory_archaeology
import assistant_reminders

DOC={'body':{'content':[{'paragraph':{'elements':[{'textRun':{'content':'Acme proposal'}}]}}]}}


def test_approved_google_index_is_searchable_and_uses_bound_adapter(tmp_path):
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'))
    run=runtime.new_run('Index my document',str(tmp_path),False)
    with patch('agent_service_mcp.binding',return_value='account-A'),patch('agent_google.request',return_value=DOC) as request:
        step=runtime.propose(run['id'],'knowledge.index.google',{'file_id':'doc1'})['steps'][-1]
        assert step['status']=='pending'
        request.assert_not_called()
        assert runtime.actions[step['id']]['bindings']['google_account']=='account-A'
        executed=runtime.decide(step['id'],True)['action']
        assert executed['status']=='completed'
        request.assert_called_once_with('docs','GET','/documents/doc1')
    assert runtime.knowledge.search(tmp_path,'Acme')['results']
    assert not (tmp_path/'knowledge.sqlite3').exists()
    assert runtime.knowledge.search(tmp_path/'other','Acme')['results']==[]


def test_google_account_swap_blocks_execution_before_read(tmp_path):
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'))
    run=runtime.new_run('Index my document',str(tmp_path),False)
    with patch('agent_service_mcp.binding',return_value='A'):
        step=runtime.propose(run['id'],'knowledge.index.google',{'file_id':'doc1'})['steps'][-1]
    with patch('agent_service_mcp.binding',return_value='B'),patch('agent_google.request') as request:
        executed=runtime.decide(step['id'],True)['action']
    assert executed['status']=='failed'
    assert 'connection changed' in executed['result']['error']
    request.assert_not_called()


def test_sheet_requires_reviewed_range_and_correct_encoded_url(tmp_path):
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'))
    run=runtime.new_run('Index spreadsheet',str(tmp_path),False)
    with patch('agent_service_mcp.binding',return_value='A'):
        with pytest.raises(ValueError,match='range'):
            runtime.propose(run['id'],'knowledge.index.google',{'file_id':'sheet1','service':'sheets'})
        step=runtime.propose(run['id'],'knowledge.index.google',{'file_id':'sheet1','service':'sheets','range':'Revenue!A1:B2'})['steps'][-1]
        with patch('agent_google.request',return_value={'values':[['Acme',20]]}) as request:
            assert runtime.decide(step['id'],True)['action']['status']=='completed'
            assert request.call_args.args==('sheets','GET','/spreadsheets/sheet1/values/Revenue%21A1%3AB2')
    assert runtime.knowledge.search(tmp_path,'Acme')['results']


def test_docs_extract_tables_tabs_and_plain_text():
    data={'tabs':[{'documentTab':{'body':{'content':[
        {'table':{'tableRows':[{'tableCells':[{'content':[{'paragraph':{'elements':[{'textRun':{'content':'Table text'}}]}}]}]}]}}
    ]}}}]}
    assert _doc_text(data)=='Table text'
    assert _doc_text(DOC)=='Acme proposal'


@pytest.fixture
def archive(tmp_path,monkeypatch):
    now=[datetime(2026,11,3,12,tzinfo=timezone.utc).timestamp()]
    archive=MemoryArchaeology(tmp_path,clock=lambda:now[0])
    archive.configure(True)
    archive.record_save('document','proposal.md','Acme','meeting preparation','')
    monkeypatch.setattr(memory_archaeology,'_service',archive)
    return archive,now


def event_result(now):
    return {'ok':True,'events':[{'id':'event1','summary':'Acme meeting','start':{'dateTime':datetime.fromtimestamp(now+3600,timezone.utc).isoformat()}}]}


def test_calendar_separate_opt_in_hourly_read_and_daily_dedup(archive):
    store,now=archive
    with patch('agent_service_mcp.binding',return_value='A'),patch('agent_service_mcp.execute',return_value=event_result(now[0])) as execute:
        assert assistant_reminders.calendar_context_nudge() is None
        execute.assert_not_called()
        store.configure(True,True)
        offer=assistant_reminders.calendar_context_nudge()
        assert 'Acme meeting' in offer['message']
        assert execute.call_args.args[2]['account_binding']=='A'
        assert execute.call_args.args[2]['max_results']==20
        assert assistant_reminders.calendar_context_nudge() is None
        assert execute.call_count==1
        now[0]+=3601
        assert assistant_reminders.calendar_context_nudge() is None
        assert execute.call_count==2
        store.configure(False)
        assert assistant_reminders.calendar_context_nudge() is None
        assert execute.call_count==2


def test_calendar_failures_and_missing_start_are_safe(archive):
    store,now=archive;store.configure(True,True)
    assert assistant_reminders._event_start({})==0
    assert assistant_reminders._event_start({'start':123})==123
    assert assistant_reminders._event_start({'start':{'date':'2026-11-04'}})>0
    assert assistant_reminders._event_start({'start':{'dateTime':'bad'}})==0
    with patch('agent_service_mcp.binding',side_effect=ValueError('disconnected')):
        assert assistant_reminders.calendar_context_nudge() is None
    now[0]+=3601
    with patch('agent_service_mcp.binding',side_effect=['A','B']),patch('agent_service_mcp.execute',return_value=event_result(now[0])):
        assert assistant_reminders.calendar_context_nudge() is None


def test_diary_context_read_requires_approval_and_rechecks_opt_in(archive,tmp_path):
    store,now=archive
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'))
    run=runtime.new_run('Weekly recap',str(tmp_path),False)
    step=runtime.propose(run['id'],'knowledge.saved_context',{'days':7})['steps'][-1]
    assert step['status']=='pending'
    result=runtime.decide(step['id'],True)['action']['result']
    assert result['timeline'][0]['saves'][0]['topic']=='Acme'
    step=runtime.propose(run['id'],'knowledge.saved_context',{'query':'Acme','days':7})['steps'][-1]
    store.configure(False)
    assert runtime.decide(step['id'],True)['action']['status']=='failed'


def test_starter_upgrade_keeps_existing_skill_and_installs_diary(tmp_path):
    from agent_skills import AgentSkills
    (tmp_path/'desktop-profile').mkdir()
    profile=tmp_path/'desktop-profile'
    (profile/'starter-skills-v3.json').write_text('{}')
    profile_skills=AgentSkills(profile/'agent-skills.json')
    profile_skills.save('custom','User authored instructions')
    with patch('agent_runtime.BASE_DIR',tmp_path),patch('agent_runtime.Connections',return_value=Connections(profile/'connections.json')):
        runtime=AgentRuntime()
    assert (profile/'starter-skills-v5.json').exists()
    assert 'sakura-diary' in [item['name'] for item in runtime.skills.list()]
    assert runtime.skills.get('custom')['instructions']=='User authored instructions'


def test_calendar_route_requires_companion_and_persists_opt_in(tmp_path,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from unittest.mock import Mock
    from gui_server import archaeology_router
    import gui_server
    monkeypatch.setattr(gui_server,'__file__',str(tmp_path/'gui_server.py'))
    monkeypatch.setattr(memory_archaeology,'_service',None)
    active=[True];app=FastAPI()
    app.include_router(archaeology_router(lambda:Mock(),lambda request:request.headers.get('origin')=='http://testserver',lambda:active[0]))
    client=TestClient(app);headers={'origin':'http://testserver'}
    with patch('agent_service_mcp.execute') as execute:
        assert client.get('/api/memory-archaeology/calendar-context',headers=headers).json()=={'nudge':None}
        execute.assert_not_called()
    assert client.post('/api/memory-archaeology/configure',headers=headers,json={'enabled':True,'calendar_context_enabled':'yes'}).status_code==400
    assert client.post('/api/memory-archaeology/configure',headers=headers,json={'enabled':True,'calendar_context_enabled':True}).status_code==200
    assert client.get('/api/memory-archaeology/status',headers=headers).json()['calendar_context_enabled'] is True
    assert client.get('/api/memory-archaeology/calendar-context').status_code==403
    active[0]=False
    assert client.get('/api/memory-archaeology/calendar-context',headers=headers).status_code==409
