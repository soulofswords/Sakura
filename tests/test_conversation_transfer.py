import threading
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from conversation_transfer import snapshot,preview


def test_only_raw_dialogue_and_preview_has_no_message_contents():
    model=SimpleNamespace(_lock=threading.RLock(),history=[{'role':'system','content':'owner secrets'},{'role':'user','content':'Hello'},{'role':'assistant','content':'Hi'}],trusted_memory={'secret':'not exported'})
    data=snapshot(model,'pc-123');assert data['messages']==model.history[1:]
    assert 'trusted_memory' not in data
    meta=preview(model,'pc-123');assert meta['message_count']==2 and 'messages' not in meta
    model.history.append({'role':'user','content':'Changed'});assert snapshot(model,'pc-123')['snapshot_id']!=data['snapshot_id']


def test_export_requires_opt_in_and_fresh_preview(tmp_path,monkeypatch):
    import personal_features
    from personal_features import PersonalFeatures
    from companion_features import router
    features=PersonalFeatures(tmp_path);monkeypatch.setattr(personal_features,'_instance',features)
    model=SimpleNamespace(history=[{'role':'user','content':'My retained question'}])
    app=FastAPI();app.include_router(router(lambda request:True,lambda:True,lambda:model));client=TestClient(app)
    assert client.get('/api/features/conversation-export').status_code==409
    features.configure({'phone_history':True})
    data=client.get('/api/features/conversation-export').json();assert data['message_count']==1
    assert client.post('/api/features/conversation-export',json={'snapshot_id':'old'}).status_code==409
    exported=client.post('/api/features/conversation-export',json={'snapshot_id':data['snapshot_id']});assert exported.status_code==200
    features.configure({'guest':True});assert client.get('/api/features/conversation-export').status_code==409


def test_camera_delivery_requires_consent_and_is_not_emotion_recognition(tmp_path,monkeypatch):
    import personal_features
    from personal_features import PersonalFeatures
    from companion_features import router
    from camera_style import describe
    features=PersonalFeatures(tmp_path);monkeypatch.setattr(personal_features,'_instance',features)
    app=FastAPI();app.include_router(router(lambda request:True,lambda:True,lambda:None));client=TestClient(app)
    with patch('native_consent.confirm',return_value=False):assert client.post('/api/features/camera-style',json={'enabled':True}).status_code==403
    with patch('native_consent.confirm',return_value=True):assert client.post('/api/features/camera-style',json={'enabled':True}).json()['camera_style']
    assert not client.post('/api/features/camera-style',json={'enabled':False}).json()['camera_style']
    assert describe({'mouthSmileLeft':float('nan'),'eyeBlinkLeft':True,'identity':'owner'})==''
    assert 'warmer' in describe({'mouthSmileLeft':.8,'mouthSmileRight':.9})
    assert 'mood' in describe({'eyeBlinkLeft':1})
