from unittest.mock import patch,Mock
from pathlib import Path
import re
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from agent_runtime import AgentRuntime
from agent_connections import Connections
import agent_api


def test_modes_distinguish_public_reads_writes_and_unknown_tools(tmp_path):
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'))
    assert runtime.approval_policy()['mode']=='ask'
    assert not runtime._auto_allowed({'tool':'web.fetch'})
    assert not runtime._auto_allowed({'tool':'shell.run','arguments':{'command':'whoami'},'schema_hash':'test','bindings':{}})
    runtime.set_approval_mode('balanced')
    assert runtime._auto_allowed({'tool':'web.fetch'})
    assert not runtime._auto_allowed({'tool':'files.write'})
    assert not runtime._auto_allowed({'tool':'mcp:provider:unknown'})
    runtime.set_approval_mode('full')
    assert runtime._auto_allowed({'tool':'files.write'})
    runtime.set_approval_mode('ask')
    assert not runtime._auto_allowed({'tool':'files.write'})
    with pytest.raises(ValueError):runtime.set_approval_mode('unrecognised')
    assert AgentRuntime(Connections(tmp_path/'other.json')).approval_policy()['mode']=='ask'


def test_full_access_does_not_remove_workspace_validation(tmp_path):
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'));runtime.set_approval_mode('full')
    workspace=tmp_path/'workspace';workspace.mkdir();outside=tmp_path/'outside.txt';outside.write_text('outside')
    run=runtime.new_run('Read a file',str(workspace))
    with pytest.raises(ValueError,match='workspace'):runtime.propose(run['id'],'files.read',{'path':str(outside)})


def test_planner_executes_a_write_only_under_explicit_full_access(tmp_path):
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'))
    run=runtime.new_run('Create a draft',str(tmp_path));model=Mock()
    def proposed(*args):return runtime.propose(run['id'],'files.write',{'path':'out.md','content':'# Written under full access'},'Save the requested draft')
    with patch.object(runtime,'_plan_once',side_effect=proposed):
        result=runtime.plan(run['id'],model)
    assert result['status']=='awaiting_approval' and not (tmp_path/'out.md').exists()
    runtime.decide(result['steps'][-1]['id'],False)
    runtime.set_approval_mode('full')
    count=0
    def advance(*args):
        nonlocal count
        count+=1
        return proposed() if count==1 else runtime.state(run['id'])
    with patch.object(runtime,'_plan_once',side_effect=advance):
        result=runtime.plan(run['id'],model)
    assert result['steps'][-1]['status']=='completed'
    assert (tmp_path/'out.md').read_text()=='# Written under full access'
    next_action=runtime.propose(run['id'],'files.write',{'path':'next.md','content':'# Not allowed'},'Next draft')['steps'][-1]
    runtime.set_approval_mode('ask')
    with pytest.raises(ValueError):runtime._decide(next_action['id'],True,auto=True)
    assert not (tmp_path/'next.md').exists()


def test_full_access_uses_panel_choice_without_duplicate_native_prompts(tmp_path,monkeypatch):
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'));monkeypatch.setattr(agent_api,'runtime',runtime)
    app=FastAPI();app.include_router(agent_api.agent_router(lambda *args:Mock()))
    client=TestClient(app,base_url='http://127.0.0.1:8790',client=('127.0.0.1',3333))
    token=re.search(r"const token='([^']+)'",client.get('/agent').text)[1];headers={'X-Sakura-Agent':token}
    with patch('agent_api.native_confirm',return_value=False) as prompt:
        assert client.post('/api/agent/approval-policy',json={'mode':'full'}).status_code==403
        assert client.post('/api/agent/approval-policy',headers={**headers,'Origin':'https://outside.example'},json={'mode':'full'}).status_code==403
        assert runtime.approval_policy()['mode']=='ask'
        assert client.post('/api/agent/approval-policy',headers=headers,json={'mode':'full'}).json()['mode']=='full'
        run=runtime.new_run('Write a draft',str(tmp_path),False)
        step=runtime.propose(run['id'],'files.write',{'path':'draft.md','content':'Draft'},'Requested draft')['steps'][-1]
        assert client.post('/api/agent/actions/'+step['id']+'/decision',headers=headers,json={'approve':True}).status_code==200
        assert (tmp_path/'draft.md').read_text()=='Draft'
        prompt.assert_not_called()
        assert client.post('/api/agent/approval-policy',headers=headers,json={'mode':'ask'}).json()['mode']=='ask'
        assert client.post('/api/agent/approval-policy',headers=headers,json={'mode':'balanced'}).status_code==403
        prompt.assert_called_once()
    assert AgentRuntime(Connections(tmp_path/'restart.json')).approval_policy()['mode']=='ask'
