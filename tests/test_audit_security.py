from pathlib import Path
from fastapi.testclient import TestClient
import app
from command_approval import propose,consume

def test_all_mutations_require_same_origin_and_bound_host():
    client=TestClient(app.app,base_url='http://127.0.0.1:8766')
    for path in ['/api/virtual-camera/configure','/api/tracking/mode','/api/collab/import','/api/models/texture-material','/api/vtuber/connect','/api/tts/speak']:
        for headers in [{},{'origin':'http://localhost:3000'},{'origin':'https://evil.example'},{'host':'attacker.example','sec-fetch-site':'same-origin'}]:
            assert client.post(path,json={},headers=headers).status_code==403

def test_other_localhost_port_cannot_read_settings():
    response=TestClient(app.app,base_url='http://127.0.0.1:8766').get('/api/settings',headers={'origin':'http://localhost:3000'})
    assert response.status_code==403
    assert 'access-control-allow-origin' not in response.headers

def test_messaging_webhook_exception_stays_inert_without_provider_secrets():
    """The one path allowed past the origin guard must refuse everything until it is configured."""
    client=TestClient(app.app,base_url='http://127.0.0.1:8766')
    for headers in [{},{'origin':'https://evil.example'},{'content-type':'text/plain'}]:
        refused=client.post('/api/messaging/whatsapp/webhook',content='{"object":"whatsapp_business_account"}',headers=headers)
        assert refused.status_code==403 and 'delivery refused' in refused.text
        assert client.get('/api/messaging/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=x&hub.challenge=1',headers=headers).status_code==403
    # The exemption is path-exact: a foreign Host still cannot reach it, and neighbours keep the guard.
    spoofed=TestClient(app.app,base_url='http://rebind.example:8766').post('/api/messaging/whatsapp/webhook',json={})
    assert spoofed.status_code==403 and 'Only this computer' in spoofed.text
    assert client.post('/api/agent/tasks',json={'goal':'x','workspace':'.'},headers={'origin':'https://evil.example'}).status_code==403
    assert client.get('/api/settings',headers={'host':'rebind.example'}).status_code==403

def test_action_approval_is_single_use_and_rejection_consumes_it():
    import pytest
    identifier=propose('open chrome','desktop')
    assert consume(identifier,True)==('open chrome','desktop',{'processes':{}})
    with pytest.raises(ValueError):consume(identifier,True)
    identifier=propose('open chrome','desktop');assert consume(identifier,False) is None
    with pytest.raises(ValueError):consume(identifier,True)

def test_process_approval_binds_identity_until_execution(monkeypatch):
    from command_approval import propose,consume
    identity={'pid':12345,'name':'safe-test.exe','username':'owner','created':12.5}
    monkeypatch.setattr('process_tools.inspect_target',lambda pid:identity)
    identifier=propose('kill process 12345','desktop')
    text,channel,bindings=consume(identifier,True)
    assert (text,channel)==('kill process 12345','desktop')
    assert bindings=={'processes':{'12345':identity}}

def test_process_kill_passes_approved_identity_to_termination(monkeypatch):
    import assistant_tools
    expected={'pid':12345,'name':'safe-test.exe','username':'owner','created':12.5}
    seen={}
    def terminate(pid, approved):
        seen.update(pid=pid,approved=approved)
        return {'ok':True,'message':'Terminated safe-test.exe (12345).'}
    monkeypatch.setattr('process_tools.terminate',terminate)
    result=assistant_tools.execute('process.kill',{'pid':12345},{'processes':{'12345':expected}})
    assert result['ok'] and seen=={'pid':12345,'approved':expected}

def test_android_refuses_missing_pin_before_network():
    source=(Path(__file__).parents[1]/'android/src/app/sakura/mobile/PcTls.java').read_text()
    assert 'if(!pin.matches("[0-9a-f]{64}")||!pin.equals(fingerprint(chain[0])))' in source


def test_semicolon_sequence_cannot_bypass_effect_approval():
    from command_approval import required
    assert required('pc status; set volume to 30%')
    assert required('set volume to 30%; pc status')
    assert required('pc status then set volume to 30%')
    assert not required('pc status; cpu usage')


def test_spoken_prefix_cannot_skip_review_for_a_write():
    from command_approval import required
    # run_command normalises "can u" before acting, so the review gate must read that form too.
    assert required('can u increase the volume a bit')
    assert required('can you set the volume to 30%')
    assert required('could u make the volume 30 percent')
    assert not required('can u tell me the volume')


def test_direct_execution_still_reviews_the_screen_and_the_process_table():
    from command_approval import required
    direct = {'pc_action_review_required': False}
    assert not required('set volume to 30%', direct)
    assert not required('set brightness to 40%', direct)
    assert not required('pc status; set volume to 30%', direct)
    assert required('click save', direct)
    assert required('kill process 1234', direct)
    assert required('click save then press enter', direct)
    assert required('set volume to 30%') is True
