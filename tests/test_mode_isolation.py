from unittest.mock import Mock,AsyncMock
import pytest
import app
from local_client import TestClient

@pytest.mark.parametrize('edition',['companion','vtuber'])
def test_tracking_denies_assistant_state_tools_and_provider_calls(monkeypatch,edition):
    monkeypatch.setattr(app,'EDITION',edition);monkeypatch.setattr(app.app.state,'tracking_only',True,raising=False)
    model=Mock();monkeypatch.setattr(app,'llm',model)
    client=TestClient(app.app)
    for method,path in [('post','/api/llm/test'),('post','/api/refresh-memory'),('get','/api/long-term-memory'),
                        ('post','/api/long-term-memory/search'),('get','/api/personas'),('post','/api/personas/activate'),
                        ('get','/api/relationship'),('post','/api/assistant-tools/device'),('get','/api/assistant-tools/status'),
                        ('get','/api/agent/audit'),('post','/api/chat'),('post','/api/stt')]:
        response=getattr(client,method)(path,**({'json':{}} if method=='post' else {}))
        assert response.status_code==409,(edition,path,response.text)
    assert not model.mock_calls
    if edition=='vtuber':
        assert client.post('/api/tracking/mode',json={'enabled':False}).status_code==409

@pytest.mark.parametrize('edition',['companion','vtuber'])
def test_tracking_keeps_character_library_voice_preview_and_twitch_reader(monkeypatch,edition):
    monkeypatch.setattr(app,'EDITION',edition);monkeypatch.setattr(app.app.state,'tracking_only',True,raising=False)
    voice=Mock();voice.speak_to_file_async=AsyncMock(return_value='preview.wav')
    monkeypatch.setattr(app,'tts',voice);monkeypatch.setattr(app,'speech_notice',lambda path:'local')
    client=TestClient(app.app)
    assert client.get('/api/local-model-library/folder-names').status_code==200
    assert client.post('/api/tts/test',json={'voice':'kokoro_af_heart'}).status_code==200
    connect=Mock(return_value='channel');monkeypatch.setattr('live_chat.chat.connect',connect)
    monkeypatch.setattr('screen_audio.listener.set_computer_only',lambda value:None)
    result=client.post('/api/chat-reader/connect',json={'link':'https://twitch.tv/channel','twitch_username':'reader','twitch_token':'not-real'})
    assert result.status_code==200;connect.assert_called_once_with('https://twitch.tv/channel','reader','not-real',None,'')

def test_companion_provider_test_still_works_outside_tracking(monkeypatch):
    monkeypatch.setattr(app,'EDITION','companion');monkeypatch.setattr(app.app.state,'tracking_only',False,raising=False)
    model=Mock(provider='gemini');model.test_gemini_connection.return_value='Connected locally in test';monkeypatch.setattr(app,'llm',model)
    assert TestClient(app.app).post('/api/llm/test',json={}).status_code==200
    model.test_gemini_connection.assert_called_once()

@pytest.mark.parametrize('action',[None,[],object(),{'seconds':'bad'},{'arguments':{'not-json':{1,2}}}])
def test_audit_never_raises_for_malformed_action(tmp_path,action):
    from agent_audit import AuditLog
    assert AuditLog(tmp_path/'audit.sqlite3').record('run',action) is False
