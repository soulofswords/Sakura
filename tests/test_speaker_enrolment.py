import json
import pytest
from unittest.mock import patch
from speaker_profiles import SpeakerProfiles, accepts_microphone


def test_rename_preserves_embedding_and_rejects_collision(tmp_path):
    saved={'Alice':[1.,0.],'Bob':[0.,1.]}
    def write(key,value):
        saved.clear();saved.update(json.loads(value))
    with patch('credentials.get_cloud_key',side_effect=lambda key:json.dumps(saved)),patch('credentials.set_cloud_key',side_effect=write):
        profiles=SpeakerProfiles(tmp_path)
        profiles.rename('Alice','Owner')
        assert saved=={'Owner':[1.,0.],'Bob':[0.,1.]}
        with pytest.raises(ValueError):profiles.rename('Owner','Bob')
        with pytest.raises(ValueError):profiles.rename('Owner',' ')
        assert len(saved)==2


def test_enrolment_limit_and_filter_fail_closed(tmp_path):
    with patch('credentials.get_cloud_key',return_value=json.dumps({str(i):[1.] for i in range(5)})),patch.object(SpeakerProfiles,'vector',return_value=[1.]):
        with pytest.raises(ValueError,match='five'):SpeakerProfiles(tmp_path).enroll('Six',b'clip')
    with patch.object(SpeakerProfiles,'_profiles',return_value={'Owner':[1.]}),patch.object(SpeakerProfiles,'identify',side_effect=ValueError('offline')):
        assert accepts_microphone(b'clip') is False
    with patch.object(SpeakerProfiles,'_profiles',return_value={}):
        assert accepts_microphone(b'clip') is True


def test_companion_profile_routes_block_tracking_and_validate_rename():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from companion_speakers import install
    app=FastAPI();allow=[False];install(app,lambda:allow[0]);client=TestClient(app)
    assert client.get('/api/companion/speakers').status_code==409
    assert client.post('/api/companion/speakers/install',json={'consent':True}).status_code==409
    allow[0]=True
    assert client.post('/api/companion/speakers/install',json={}).status_code==400
    assert client.post('/api/companion/speakers/rename',json={'name':'x','new_name':None}).status_code==400
