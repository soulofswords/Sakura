import json
import threading
from unittest.mock import Mock,patch

import pytest
import requests

from telegram_bot import TelegramGateway,parse_chat_ids

TEST_TOKEN='123456789:'+('aB_cD-eF'*4)+'xyz'


@pytest.fixture(autouse=True)
def no_external_telegram_requests():
    with patch('telegram_bot.requests.post',side_effect=AssertionError('Tests must not contact Telegram.')):
        yield


def make(tmp_path,handler=None):
    return TelegramGateway(store_path=tmp_path/'telegram.json',handler=handler or (lambda text:'local: '+text))


def test_reconfiguration_waits_for_a_slow_worker_instead_of_running_two(tmp_path):
    """Two pollers would acknowledge updates the retired one never answers."""
    bot=make(tmp_path);bot.STOP_TIMEOUT=0.02
    entered=threading.Event();release=threading.Event()
    old_event=bot.stop_event
    def delayed():
        entered.set();release.wait(2)
    bot.thread=threading.Thread(target=delayed,daemon=True);old=bot.thread;old.start()
    assert entered.wait(1)
    try:
        with patch('credentials.get_cloud_key',return_value=TEST_TOKEN),patch('credentials.set_cloud_key') as saved:
            with pytest.raises(ValueError,match='still stopping'):
                bot.configure(False,'42',token=TEST_TOKEN)
        assert not bot.store_path.exists() and not saved.called
        assert old_event.is_set() and bot.thread is old
    finally:
        release.set();old.join(2)
        assert bot.configure(False,'42',token=TEST_TOKEN)['enabled'] is False


def update(chat_id=42,text='hello'):
    return {'update_id':7,'message':{'chat':{'id':chat_id},'text':text}}


def test_chat_id_parsing_accepts_numbers_and_rejects_other_input():
    assert parse_chat_ids('123, -456')=={123,-456}
    assert parse_chat_ids(['123',456])=={123,456}
    assert parse_chat_ids(None)==set()
    for bad in ('not-a-number',['0'],['1']*21,{'a':1}):
        with pytest.raises(ValueError):parse_chat_ids(bad)


def test_strangers_only_learn_their_chat_id(tmp_path):
    bot=make(tmp_path);bot.chat_ids={42}
    chat_id,reply=bot.reply_for(update(chat_id=99))
    assert chat_id==99
    assert '99' in reply and 'Agent panel' in reply
    assert bot.received==0


def test_allowed_chat_reaches_the_local_handler_and_nothing_else(tmp_path):
    seen=[]
    bot=make(tmp_path,handler=lambda text:seen.append(text) or 'reply')
    bot.chat_ids={42}
    assert bot.reply_for(update())==(42,'reply')
    assert seen==['hello']
    assert bot.received==1 and bot.last_message_at is not None


def test_start_and_help_do_not_call_the_model(tmp_path):
    bot=make(tmp_path,handler=lambda text:pytest.fail('model must not run for /start'))
    bot.chat_ids={42}
    assert 'Sakura is connected' in bot.reply_for(update(text='/start'))[1]


def test_non_text_and_empty_updates_are_ignored(tmp_path):
    bot=make(tmp_path);bot.chat_ids={42}
    assert bot.reply_for({'update_id':1,'message':{'chat':{'id':42},'photo':[{}]}}) is None
    assert bot.reply_for({}) is None
    assert bot.reply_for(update(text='   ')) is None


def test_model_failure_is_reported_without_a_traceback(tmp_path):
    def boom(text):raise RuntimeError('model not loaded; secret='+TEST_TOKEN)
    bot=make(tmp_path,handler=boom);bot.chat_ids={42}
    assert bot.reply_for(update())[1]=='The AI reply failed. Check the model connection in Sakura on the PC.'


def test_long_replies_are_split_into_telegram_sized_messages(tmp_path):
    bot=make(tmp_path);sent=[]
    bot._request=lambda method,payload,timeout:sent.append((method,payload))
    bot.send(42,'x'*9000)
    assert [len(payload['text']) for _,payload in sent]==[4000,4000,1000]
    assert all(method=='sendMessage' for method,_ in sent)


def test_poll_advances_the_offset_and_answers_each_message(tmp_path):
    bot=make(tmp_path);bot.chat_ids={42};calls=[]
    def fake(method,payload,timeout):
        calls.append(method)
        if method=='getUpdates':return [update(),{**update(chat_id=99),'update_id':8}]
        return {'message_id':1}
    bot._request=fake
    assert bot.poll_once()==2
    assert bot.offset==9
    assert calls.count('sendMessage')==2


def test_token_is_never_written_to_the_settings_file(tmp_path):
    bot=make(tmp_path)
    with patch('credentials.get_cloud_key',return_value=TEST_TOKEN),patch('credentials.set_cloud_key') as saved,patch.object(bot,'restart'):
        status=bot.configure(True,'42',token=TEST_TOKEN)
    saved.assert_called_once_with('telegram',TEST_TOKEN)
    assert json.loads((tmp_path/'telegram.json').read_text())=={'version':1,'enabled':True,'chat_ids':[42],'voice_enabled':False}
    assert status['token_set'] is True and status['enabled'] is True
    assert TEST_TOKEN not in json.dumps(status)


def test_enabling_without_a_token_keeps_the_gateway_stopped(tmp_path):
    bot=make(tmp_path)
    with patch('credentials.get_cloud_key',return_value=''):
        with pytest.raises(ValueError,match='before enabling'):bot.configure(True,'42')
        assert not bot.status()['running']
    assert not bot.store_path.exists()


def test_bad_tokens_are_refused_before_any_network_call(tmp_path):
    bot=make(tmp_path)
    with pytest.raises(ValueError):bot.configure(True,'42',token='not a token')


def test_restore_reads_ids_but_requires_the_saved_token(tmp_path):
    (tmp_path/'telegram.json').write_text(json.dumps({'version':1,'enabled':True,'chat_ids':[42]}))
    bot=make(tmp_path)
    with patch('credentials.get_cloud_key',return_value=''):
        bot.restore()
    assert bot.chat_ids=={42} and bot.enabled is False


@pytest.mark.parametrize('value',[True,123,{},[], '123:abc', '123:abc/redirect', 'not:numeric'+('a'*30)])
def test_invalid_token_types_and_syntax_are_rejected(tmp_path,value):
    with patch('credentials.set_cloud_key') as save:
        with pytest.raises(ValueError):make(tmp_path).configure(True,'42',token=value)
    save.assert_not_called()


def test_reconfigure_keeps_credentials_while_a_poller_is_still_live(tmp_path):
    """Clearing the token beside a live loop would leave it polling with a stale
    offset while the new configuration starts a second poller beside it."""
    bot=make(tmp_path);bot.token=TEST_TOKEN;bot.chat_ids={42}
    worker=Mock();worker.is_alive.return_value=True;bot.thread=worker
    with patch('credentials.get_cloud_key',return_value=TEST_TOKEN),patch('credentials.set_cloud_key') as save:
        with pytest.raises(ValueError,match='still stopping'):
            bot.configure(False,'99',clear_token=True)
    assert not save.called and not bot.store_path.exists()
    assert bot.token==TEST_TOKEN and bot.chat_ids=={42} and bot.thread is worker
    assert bot.stop_event.is_set()


def test_stopped_long_poll_does_not_dispatch_or_send(tmp_path):
    bot=make(tmp_path,handler=Mock());bot.chat_ids={42};stop=threading.Event()
    def response(*args):
        stop.set()
        return [update()]
    bot._request=Mock(side_effect=response)
    assert bot.poll_once(stop)==0
    bot.handler.assert_not_called()
    assert bot._request.call_count==1


def test_stop_during_generation_discards_the_reply(tmp_path):
    stop=threading.Event()
    bot=make(tmp_path,handler=lambda text:stop.set() or 'Do not deliver this')
    bot.chat_ids={42};bot._request=Mock(return_value=[update()])
    assert bot.poll_once(stop)==0
    assert bot._request.call_count==1


def test_network_errors_never_expose_the_token(tmp_path):
    bot=make(tmp_path);stop=threading.Event()
    def fail(*args):
        raise requests.ConnectionError('Connection failed for https://api.telegram.org/bot'+TEST_TOKEN+'/getUpdates')
    bot._request=fail
    with patch.object(stop,'wait',side_effect=lambda seconds:stop.set()):bot._poll(stop)
    assert 'connection failed' in bot.last_error
    assert TEST_TOKEN not in bot.last_error


def test_invalid_credentials_stop_polling_without_exposing_url(tmp_path):
    bot=make(tmp_path);bot.enabled=True;response=Mock(status_code=401)
    bot._request=Mock(side_effect=requests.HTTPError(TEST_TOKEN,response=response))
    bot._poll(threading.Event())
    assert bot.last_error=='Telegram returned HTTP 401.' and not bot.enabled
    assert bot._request.call_count==1


def test_request_uses_fixed_https_destination_and_no_redirects(tmp_path):
    bot=make(tmp_path);bot.token=TEST_TOKEN
    response=Mock();response.json.return_value={'ok':True,'result':[]}
    context=Mock();context.__enter__=Mock(return_value=response);context.__exit__=Mock(return_value=False)
    with patch('telegram_bot.requests.post',return_value=context) as post:
        assert bot.poll_once()==0
    assert post.call_args.args[0]=='https://api.telegram.org/bot'+TEST_TOKEN+'/getUpdates'
    assert post.call_args.kwargs['allow_redirects'] is False


def test_duplicate_updates_are_not_sent_again(tmp_path):
    bot=make(tmp_path);bot.chat_ids={42}
    bot._request=Mock(return_value=[update(),update()])
    assert bot.poll_once()==1
    assert bot.offset==8


def test_gateway_uses_raw_model_requests_without_desktop_chat(tmp_path):
    from agent_api import agent_router
    bot=make(tmp_path);model=Mock();model._request_raw.return_value='isolated reply'
    with patch('telegram_bot.gateway',bot):agent_router(lambda choice:model)
    bot.chat_ids={42,99}
    assert bot.reply_for(update(text='cancel all timers'))==(42,'isolated reply')
    assert bot.reply_for(update(chat_id=99,text='read my desktop history'))==(99,'isolated reply')
    model.chat.assert_not_called()
    model.remember_exchange.assert_not_called()
    messages=model._request_raw.call_args.args[0]
    assert len(messages)==2 and messages[-1]['content']=='read my desktop history'
    assert 'cancel all timers' not in json.dumps(messages)


def test_paused_ai_does_not_reach_the_telegram_model(tmp_path):
    from agent_api import agent_router
    bot=make(tmp_path);getter=Mock()
    with patch('telegram_bot.gateway',bot):agent_router(getter,enabled=lambda:False)
    bot.chat_ids={42}
    assert 'AI reply failed' in bot.reply_for(update())[1]
    getter.assert_not_called()


def test_polling_worker_receives_and_sends_with_simulated_telegram(tmp_path):
    from agent_api import agent_router
    bot=make(tmp_path);model=Mock();model._request_raw.return_value='Sakura integration test reply'
    with patch('telegram_bot.gateway',bot):agent_router(lambda choice:model)
    delivered=threading.Event();sent=[]
    class Response:
        def __init__(self,result):self.result=result
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def raise_for_status(self):pass
        def json(self):return {'ok':True,'result':self.result}
    def transport(url,*,json,timeout,allow_redirects):
        assert url.startswith('https://api.telegram.org/bot'+TEST_TOKEN+'/')
        assert allow_redirects is False
        if url.endswith('/getUpdates'):return Response([update(text='Say hello')])
        assert url.endswith('/sendMessage')
        sent.append(json);bot.stop_event.set();delivered.set()
        return Response({'message_id':1})
    with patch('credentials.get_cloud_key',return_value=TEST_TOKEN),patch('credentials.set_cloud_key'),patch('telegram_bot.requests.post',side_effect=transport):
        try:
            bot.configure(True,'42',token=TEST_TOKEN)
            assert delivered.wait(3),'The polling worker did not deliver a reply.'
            assert bot.stop()
            assert not bot.status()['running']
        finally:bot.stop()
    assert sent==[{'chat_id':42,'text':'Sakura integration test reply','disable_web_page_preview':True}]
    assert bot.offset==8 and bot.received==1
    model.chat.assert_not_called()
