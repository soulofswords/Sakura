import pytest
from twitch_chat import channel_name,parse_message,TwitchChat

@pytest.mark.parametrize('link',['http://twitch.tv/test','https://evil.test/channel','https://twitch.tv/a/b','https://twitch.tv/test%0aJOIN'])
def test_channel_injection_is_rejected(link):
    with pytest.raises(ValueError):channel_name(link)

def test_read_only_message_parser_and_channel_filter():
    line='@id=123;display-name=Viewer :viewer!viewer@viewer.tmi.twitch.tv PRIVMSG #channel :Great stream!'
    message=parse_message(line,'channel')
    assert message['id']=='123' and message['text']=='Great stream!'
    assert parse_message(line,'another') is None
    assert parse_message(':server NOTICE #channel :ignored','channel') is None

def test_invalid_credentials_never_open_a_socket(monkeypatch):
    monkeypatch.setattr('agent_connections.secret_get',lambda key:{})
    with pytest.raises(ValueError,match='OAuth token'):TwitchChat().connect('https://twitch.tv/channel','bad\r\nJOIN','password')

def test_token_identity_and_scope_are_verified(monkeypatch):
    from unittest.mock import Mock
    response=Mock(status_code=200);response.json.return_value={'login':'other','scopes':['chat:read']}
    monkeypatch.setattr('agent_connections.secret_get',lambda key:{})
    monkeypatch.setattr('requests.get',lambda *a,**k:response)
    with pytest.raises(ValueError,match='match the username'):TwitchChat().connect('https://twitch.tv/channel','reader','a'*20)
