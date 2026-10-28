import re
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import agent_api
from agent_connections import Connections
from agent_runtime import AgentRuntime


@pytest.fixture
def client(tmp_path,monkeypatch):
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'));monkeypatch.setattr(agent_api,'runtime',runtime)
    monkeypatch.setattr('agent_messaging.get_cloud_key',lambda name:'')
    app=FastAPI();app.include_router(agent_api.agent_router(lambda choice='current':Mock()))
    client=TestClient(app,base_url='http://127.0.0.1:8790',client=('127.0.0.1',30000))
    token=re.search(r"const token='([^']+)'",client.get('/agent').text)[1]
    return client,{'X-Sakura-Agent':token},runtime


def test_new_routes_require_local_authorization(client):
    api,headers,runtime=client
    for endpoint in ('history/search?q=sample','history/id','gateways'):
        assert api.get('/api/agent/'+endpoint).status_code==403
        assert api.get('/api/agent/'+endpoint,headers={**headers,'Origin':'https://outside.test'}).status_code==403
    for endpoint in ('imports/preview','imports/id/confirm','voice/transcribe','gateways/discord','tasks/id/delegate'):
        assert api.post('/api/agent/'+endpoint,json={}).status_code==403
        assert api.post('/api/agent/'+endpoint,headers={**headers,'Origin':'https://outside.test'},json={}).status_code==403
    assert api.delete('/api/agent/permissions/id').status_code==403


def test_history_search_and_read_are_readonly(client,tmp_path):
    api,headers,runtime=client
    run=runtime.new_run('Archive test needle',str(tmp_path))
    response=api.get('/api/agent/history/search?q=needle',headers=headers)
    assert response.status_code==200 and response.json()['results'][0]['id']==run['id']
    assert api.get('/api/agent/history/'+run['id'],headers=headers).json()['archived'] is True
    assert api.get('/api/agent/history/search?q=',headers=headers).status_code==400


def test_import_preview_cannot_be_mutated_at_confirmation(client):
    api,headers,runtime=client
    preview=api.post('/api/agent/imports/preview',headers=headers,json={'filename':'SKILL.md','text':'---\nname: my-skill\n---\nRead and check the selected files.'}).json()
    assert api.post('/api/agent/imports/'+preview['id']+'/confirm',headers=headers,json={'approved':True,'items':[]}).status_code==400
    assert not runtime.skills.list()
    assert api.post('/api/agent/imports/'+preview['id']+'/confirm',headers=headers,json={'approved':True}).status_code==200


def test_webhook_is_not_a_second_desktop_approval_path(client):
    api,headers,runtime=client
    assert api.get('/api/messaging/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=wrong&hub.challenge=1').status_code==403
    assert api.post('/api/messaging/whatsapp/webhook',json={'approve':True,'tool':'shell.run'}).status_code==403
    assert api.post('/api/agent/gateways/unknown',headers=headers,json={'enabled':False}).status_code==400
    assert not runtime.actions
