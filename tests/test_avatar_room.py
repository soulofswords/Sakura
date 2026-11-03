from avatar_room import instruction, extract, ACTIONS


def test_protocol_only_advertises_real_known_actions():
    assert instruction(None)==''
    assert instruction('desk')==''
    assert instruction(['delete_everything'])==''
    result=instruction(['desk','mirror','steal secrets'])
    assert 'desk' in result and 'mirror' in result and 'steal secrets' not in result
    assert 'virtual' in result and 'hello' in result


def test_strips_tokens_and_rejects_unknown_or_multiple_actions():
    for action in ACTIONS:assert extract('Hello. [[avatar:'+action+']]')==('Hello.',action)
    assert extract('Hello [[avatar:delete files]]')==('Hello',None)
    assert extract('Hello [[avatar:desk]][[avatar:bed]]')==('Hello',None)
    assert extract('Hello')==('Hello',None)


def test_direct_room_requests_are_not_computer_commands():
    from avatar_room import requested_action
    assert requested_action('Sakura, please go to the desk!')=='desk'
    assert requested_action('Could you lie on the bed?')=='bed'
    assert requested_action('u can sleep now')=='bed'
    assert requested_action('You can sleep now.')=='bed'
    assert requested_action('सो जाओ')=='bed'
    for value in ['delete the bed file','he said go to bed','open the desk application','what does nod mean?','I cannot sleep','remind me to sleep at ten']:
        assert requested_action(value) is None


def test_model_control_token_never_reaches_speech_or_history():
    from llm import LLM
    from unittest.mock import patch
    model=object.__new__(LLM);model.reply_language='English'
    with patch.object(model,'_request_raw',return_value='Let me stretch. [[avatar:stretch]]'):
        result=model._request([{'role':'system','content':instruction(['stretch'])},{'role':'user','content':'Hello'}])
    assert '[[avatar:' not in result and model.last_avatar_plan=='stretch'
    with patch.object(model,'_request_raw',return_value='Hi [[avatar:bed]]'):
        model._request([{'role':'user','content':'Hello'}])
    assert model.last_avatar_plan is None


import unittest
from tests.generation_quality_isolation import GenerationQualityIsolation


class RoomChatIntegration(GenerationQualityIsolation,unittest.IsolatedAsyncioTestCase):
    async def test_actual_chat_route_propagates_only_advertised_action(self):
        from unittest.mock import Mock,patch
        import app as server
        model=Mock();model.chat.return_value='I can head to the virtual desk.';model.last_avatar_plan='desk'
        with patch.object(server,'llm',model),patch.object(server,'get_settings',return_value={'conversation_mode':'friend'}),patch.object(server.app.state,'tracking_only',False,create=True),patch('personal_features.features') as features:
            features.return_value.guest.return_value=False;features.return_value.settings.return_value={}
            result=await server._chat_core({'text':'Visit the desk with me','avatar_room':['desk'],'defer_audio':True})
            assert result['avatar_motion']=='room:desk'
            assert model.chat.call_args.kwargs['avatar_scene']==['desk']
            model.last_avatar_plan='bed'
            result=await server._chat_core({'text':'Let us talk about the room','avatar_room':['desk'],'defer_audio':True})
            assert result['avatar_motion'] is None
            with patch.object(server,'get_settings',return_value={'conversation_mode':'teacher'}):
                result=await server._chat_core({'text':'You can sleep now','avatar_room':['bed'],'defer_audio':True})
                assert result['avatar_motion']=='room:bed'
                assert 'no need to rest' not in result['reply']
                result=await server._chat_core({'text':'wake up sakura','avatar_room':['home'],'defer_audio':True})
                assert result['avatar_motion']=='room:home'
            model.last_avatar_plan='desk'
            result=await server._chat_core({'text':'hello','avatar_room':['desk'],'avatar_can_greet':True,'defer_audio':True})
            assert result['avatar_motion']=='greeting_wave'
            model.last_avatar_plan=None
            result=await server._chat_core({'text':'u can sleep now','avatar_room':['bed'],'defer_audio':True})
            assert result['avatar_motion']=='room:bed'
            result=await server._chat_core({'text':'u can sleep now','avatar_room':[],'defer_audio':True})
            assert result['avatar_motion'] is None
