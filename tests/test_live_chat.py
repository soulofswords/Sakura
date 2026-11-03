from unittest.mock import Mock,patch
import pytest
from live_chat import LiveChat


def test_both_readers_connect_and_merge_without_cross_service_id_collision():
    youtube=Mock();twitch=Mock()
    youtube.connect.return_value='abcdefghijk';twitch.connect.return_value='channel'
    youtube.poll.return_value={'connected':True,'status':'Ready','messages':[{'id':'same','text':'YT','timestamp':20}]}
    twitch.poll.return_value={'connected':True,'status':'Ready','messages':[{'id':'same','text':'TW','timestamp':10}]}
    with patch('youtube_chat.chat',youtube),patch('twitch_chat.chat',twitch):
        chat=LiveChat();result=chat.connect('https://youtube.com/watch?v=abcdefghijk','owner','token','both','https://twitch.tv/channel')
        assert set(result)=={'youtube','twitch'}
        youtube.connect.assert_called_once();twitch.connect.assert_called_once_with('https://twitch.tv/channel','owner','token')
        data=chat.poll()
        assert data['all_connected'] and [m['source'] for m in data['messages']]==['twitch','youtube']
        assert len({m['id'] for m in data['messages']})==2
        twitch.poll.return_value={'connected':False,'status':'Disconnected','messages':[]}
        assert chat.poll()['connected'] and not chat.poll()['all_connected']
        chat.stop();assert not chat.poll()['connected'] and chat.poll()['messages']==[]


def test_second_connection_failure_stops_both_readers():
    with patch('youtube_chat.chat') as youtube,patch('twitch_chat.chat') as twitch:
        twitch.connect.side_effect=ValueError('Invalid Twitch authorization')
        chat=LiveChat()
        with pytest.raises(ValueError):chat.connect('abcdefghijk',service='both',twitch_link='https://twitch.tv/channel')
        assert youtube.stop.call_count==2 and twitch.stop.call_count==2
        assert not chat.sources


def test_invalid_dual_url_never_starts_a_reader():
    with patch('youtube_chat.chat') as youtube,patch('twitch_chat.chat') as twitch:
        with pytest.raises(ValueError):LiveChat().connect('abcdefghijk',service='both',twitch_link='https://evil.example/test')
        youtube.connect.assert_not_called();twitch.connect.assert_not_called()


def test_single_service_remains_backward_compatible():
    with patch('twitch_chat.chat') as twitch:
        twitch.connect.return_value='channel'
        assert LiveChat().connect('https://twitch.tv/channel','owner','token')=='channel'


def test_both_public_connect_handlers_forward_dual_inputs():
    import asyncio
    import app
    payload={'service':'both','link':'abcdefghijk','twitch_link':'https://twitch.tv/channel','twitch_username':'owner','twitch_token':'test-token'}
    prior=getattr(app.app.state,'ai_vtuber_audio',False)
    prior_tracking=getattr(app.app.state,'tracking_only',False)
    try:
        with patch('live_chat.chat') as chat,patch('screen_audio.listener.set_computer_only'):
            chat.connect.return_value={'youtube':'abcdefghijk','twitch':'channel'}
            result=asyncio.run(app.connect_vtuber(payload))
            assert result['ok']
            chat.connect.assert_called_once_with('abcdefghijk','owner','test-token','both','https://twitch.tv/channel')
            chat.connect.reset_mock();app.app.state.tracking_only=True
            assert asyncio.run(app.connect_chat_reader(payload))['ok']
            chat.connect.assert_called_once_with('abcdefghijk','owner','test-token','both','https://twitch.tv/channel')
    finally:
        app.app.state.ai_vtuber_audio=prior;app.app.state.tracking_only=prior_tracking
