import hashlib
import hmac
import json
import threading
import time
from unittest.mock import Mock,patch

import pytest

from agent_messaging import MessagingGateway


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr('agent_messaging.requests.request',Mock(side_effect=AssertionError('External messaging is disabled in tests')))


def gateway(tmp_path,name='discord'):
    item=MessagingGateway(name,tmp_path/(name+'.json'),lambda text:'AI '+text)
    item.enabled=True;item.channels=['123456'];item.users=['654321']
    return item


def test_discord_skips_backlog_bots_outsiders_and_mentions(tmp_path):
    item=gateway(tmp_path)
    old={'id':'100001','author':{'id':'654321'},'content':'old message'}
    new=[{'id':'100002','author':{'id':'654321'},'content':'hello'},
         {'id':'100003','author':{'id':'999999'},'content':'outsider'},
         {'id':'100004','author':{'id':'654321','bot':True},'content':'bot reply'}]
    with patch.object(item,'_request',side_effect=[[old],new,{}]) as request:
        item.poll_once();assert request.call_count==1
        item.poll_once();assert request.call_count==3
    assert request.call_args.args[2]['allowed_mentions']=={'parse':[]}
    assert request.call_args.args[2]['content']=='AI hello'
    assert item.offsets['123456']=='100004'


def test_slack_escapes_mentions_and_rejects_other_users(tmp_path):
    item=gateway(tmp_path,'slack');item.channels=['C123456'];item.users=['U123456']
    with patch.object(item,'_request',return_value={}) as request:
        item._reply('C123456','OTHER','hi');request.assert_not_called()
        item._reply('C123456','U123456','<!channel>')
    payload=request.call_args.args[2]
    assert payload['text']=='AI &lt;!channel&gt;' and payload['mrkdwn'] is False
    assert payload['unfurl_links'] is False


def test_gateway_secret_config_never_writes_credentials_to_json(tmp_path):
    item=gateway(tmp_path);item.enabled=False
    with patch('agent_messaging.get_cloud_key',return_value=''),patch('agent_messaging.set_cloud_key') as protected,patch.object(item,'start'):
        status=item.configure({'enabled':True,'channels':['123456'],'users':['654321'],'token':'private-token'})
    protected.assert_called_once_with('agent_discord','private-token')
    assert 'private-token' not in item.path.read_text()
    assert 'private-token' not in json.dumps(status)
    with pytest.raises(ValueError):item.configure({'enabled':True,'channels':[],'users':[]})
    with pytest.raises(ValueError):item.configure({'enabled':False,'users':['display name']})


def test_stop_during_model_generation_prevents_late_reply(tmp_path):
    item=gateway(tmp_path)
    def handler(text):item.stop_event.set();return 'late reply'
    item.handler=handler
    with patch.object(item,'_send') as send:item._reply('123456','654321','hello')
    send.assert_not_called()


def test_whatsapp_requires_signature_phone_sender_and_deduplicates(tmp_path):
    item=gateway(tmp_path,'whatsapp');item.phone_id='123456'
    body=json.dumps({'object':'whatsapp_business_account','entry':[{'changes':[{'value':{'metadata':{'phone_number_id':'123456'},'messages':[{'id':'message-one','from':'654321','timestamp':str(int(time.time())),'type':'text','text':{'body':'hello'}}]}}]}]}).encode()
    signature='sha256='+hmac.new(b'app-secret',body,hashlib.sha256).hexdigest()
    with patch.object(item,'_secret',return_value='app-secret'):
        with pytest.raises(ValueError):item.accept_webhook(body,'bad')
        assert item.accept_webhook(body,signature)['accepted']==1
        assert item.accept_webhook(body,signature)['accepted']==0
        assert item.queue.get_nowait()==('654321','654321','hello')
        item.users=[]
        changed=body.replace(b'message-one',b'message-two')
        assert item.accept_webhook(changed,'sha256='+hmac.new(b'app-secret',changed,hashlib.sha256).hexdigest())['accepted']==0
    assert 'hello' not in item.path.read_text()
    assert 'app-secret' not in item.path.read_text()


def test_whatsapp_challenge_needs_local_configuration(tmp_path):
    item=gateway(tmp_path,'whatsapp')
    with patch.object(item,'_secret',return_value='verify-secret'):
        assert item.verify_challenge('subscribe','verify-secret','123')=='123'
        with pytest.raises(ValueError):item.verify_challenge('subscribe','wrong','123')
        with pytest.raises(ValueError):item.verify_challenge('subscribe','verify-secret','<script>')


def test_a_stalled_gateway_worker_cannot_wedge_or_outlive_a_reconfigure(tmp_path):
    item=gateway(tmp_path)
    release=threading.Event();holding=threading.Event()
    def stalled():
        holding.set();release.wait(timeout=30)
        item._reply('123456','654321','late from the stopped worker')
    item._loop=stalled
    first=threading.Thread(target=item._guarded,args=(item.stop_event,),daemon=True)
    item.thread=first;first.start()
    # The worker has to be inside its slow reply before stop() runs, or the stall is not tested.
    assert holding.wait(timeout=10),'the gateway worker never reached its slow reply'
    assert item.stop() is False,'a reply still inside the model should report a stall'
    assert item.thread is None,'holding the reference would make every later start() a no-op'
    item._loop=lambda:None
    with patch.object(item,'_send') as send:
        item.start(restore=False)
        assert item.thread is not None and item.thread is not first,'reconfiguring left the gateway dark'
        release.set();first.join(timeout=10);item.thread.join(timeout=10)
        send.assert_not_called(),'the superseded worker replied after it was stopped'


def test_a_non_ascii_webhook_token_is_refused_rather_than_raising(tmp_path):
    item=gateway(tmp_path,'whatsapp');item.enabled=True
    with patch('agent_messaging.get_cloud_key',return_value='sécrit'),pytest.raises(ValueError):
        item.verify_challenge('subscribe','tökén','123')
    with patch('agent_messaging.get_cloud_key',return_value='secret'),pytest.raises(ValueError):
        item.accept_webhook(b'{"object":"whatsapp_business_account"}','sha256=nön-ascii')
