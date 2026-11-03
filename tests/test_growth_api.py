import re
from unittest.mock import Mock,patch
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from personal_features import PersonalFeatures


def test_guest_blocks_owner_routes_and_uses_stateless_brain(tmp_path,monkeypatch):
    import app,personal_features
    from local_client import TestClient as LocalClient
    features=PersonalFeatures(tmp_path);features.configure({'guest':True});monkeypatch.setattr(personal_features,'_instance',features)
    monkeypatch.setattr(app.app.state,'tracking_only',False,raising=False);monkeypatch.setattr(app,'EDITION','companion')
    model=Mock();model._request_raw.return_value='Guest reply';monkeypatch.setattr(app,'llm',model)
    client=LocalClient(app.app)
    assert client.post('/api/chat',json={'text':'What do you know about my owner?'}).json()['guest']
    model.chat.assert_not_called()
    for path in ('/api/agent/state','/api/memory-archaeology/recall','/api/personas','/api/settings'):
        assert client.get(path).status_code==409
    assert client.get('/api/features/status').json()['guest'] is True
    with patch('native_consent.confirm',return_value=False):
        assert client.post('/api/features/guest',json={'enabled':False}).status_code==403
    assert features.guest()


def test_sdk_token_is_required_and_never_grants_owner_tools(tmp_path,monkeypatch):
    from companion_features import router
    import personal_features
    monkeypatch.setattr(personal_features,'_instance',PersonalFeatures(tmp_path))
    model=Mock();model._request_raw.return_value='SDK reply'
    app=FastAPI();app.include_router(router(lambda request:True,lambda:True,lambda:model))
    client=TestClient(app)
    with patch('credentials.get_cloud_key',return_value='expected'):
        assert client.post('/api/sdk/chat',json={'text':'Hello'}).status_code==401
        reply=client.post('/api/sdk/chat',headers={'authorization':'Bearer expected'},json={'text':'Hello'})
        assert reply.json()=={'reply':'SDK reply','stateless':True}
    model.chat.assert_not_called()


def test_growth_routes_are_token_gated_and_use_native_approval(tmp_path,monkeypatch):
    import agent_api,personal_features
    from agent_runtime import AgentRuntime
    from agent_connections import Connections
    from agent_api import agent_router
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'));monkeypatch.setattr(agent_api,'runtime',runtime)
    monkeypatch.setattr(personal_features,'_instance',PersonalFeatures(tmp_path))
    routes=agent_router(lambda *args:Mock())
    app=FastAPI();app.include_router(routes)
    client=TestClient(app,base_url='http://127.0.0.1:8790',client=('127.0.0.1',35000))
    token=re.search(r"const token='([^']+)'",client.get('/agent').text)[1];headers={'X-Sakura-Agent':token}
    assert client.get('/api/agent/knowledge/folders').status_code==403
    root=tmp_path/'docs';root.mkdir();(root/'notes.md').write_text('Acme review notes')
    with patch('agent_api.native_confirm',return_value=False):
        assert client.post('/api/agent/knowledge/folders',headers=headers,json={'folder':str(root)}).status_code==403
    assert client.get('/api/agent/knowledge/folders',headers=headers).json()['folders']==[]
    with patch('agent_api.native_confirm',return_value=True):
        result=client.post('/api/agent/knowledge/folders',headers=headers,json={'folder':str(root)})
        assert result.status_code==200,result.text
        assert result.json()['indexed']==1
        result=client.post('/api/agent/expenses',headers=headers,json={'day':'2026-11-03','amount':'12.50','currency':'INR'})
        assert result.status_code==200,result.text
        result=client.post('/api/agent/features',headers=headers,json={'phone_memory':True})
        assert result.status_code==200,result.text
    assert client.post('/api/agent/knowledge/search-folders',headers=headers,json={'query':'Acme'}).json()['results']
    assert client.get('/api/agent/expenses',headers=headers).json()['totals_by_currency']['INR']=='12.50'
    # Exactly one compare route; the helper must never become a route itself.
    matches=[route for route in routes.routes if getattr(route,'path',None)=='/api/agent/speakers/compare']
    assert len(matches)==1


def test_paired_phone_context_requires_explicit_pc_opt_in(tmp_path,monkeypatch):
    from mobile_link import MobileLink
    import personal_features,memory_archaeology
    from memory_archaeology import MemoryArchaeology
    features=PersonalFeatures(tmp_path/'features');monkeypatch.setattr(personal_features,'_instance',features)
    archive=MemoryArchaeology(tmp_path/'memory');archive.configure(True);archive.record_save('document','notes.md','Acme','','')
    monkeypatch.setattr(memory_archaeology,'_service',archive)
    link=MobileLink(tmp_path/'devices.json');link.enabled=True;link.edition='companion';link.state={'edition':'companion'};link.tokens={'paired'}
    client=TestClient(link.api,client=('127.0.0.1',30100));headers={'authorization':'Bearer paired'}
    assert client.get('/memory/context',headers=headers).status_code==409

    features.configure({'phone_memory':True})
    packet=client.get('/memory/context',headers=headers).json();assert packet['saves'][0]['topic']=='Acme'
    assert client.get('/memory/context').status_code==401
    features.configure({'guest':True})
    assert client.get('/memory/context',headers=headers).status_code==409


def test_sdk_client_headers_pass_real_app_origin_guard(tmp_path,monkeypatch):
    import app,personal_features,gui_server
    from sakura_sdk import Sakura
    monkeypatch.setattr(personal_features,'_instance',PersonalFeatures(tmp_path))
    monkeypatch.setattr(app.app.state,'tracking_only',False,raising=False)
    monkeypatch.setattr(app,'EDITION','companion');model=Mock();model._request_raw.return_value='SDK hello';monkeypatch.setattr(app,'llm',model)
    client=TestClient(app.app,base_url=f'http://127.0.0.1:{gui_server.port}')
    class Opener:
        def open(self,request,timeout):
            assert request.get_header('Origin')==f'http://127.0.0.1:{gui_server.port}'
            response=client.post('/api/sdk/chat',content=request.data,headers=dict(request.header_items()))
            assert response.status_code==200,response.text
            import io
            return io.BytesIO(response.content)
    with patch('credentials.get_cloud_key',return_value='test-token'),patch('sakura_sdk.build_opener',return_value=Opener()):
        assert Sakura(f'http://127.0.0.1:{gui_server.port}',token='test-token').chat('Hi')['reply']=='SDK hello'
    model.chat.assert_not_called()
