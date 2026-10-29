from pathlib import Path
from unittest.mock import Mock,patch
import pytest
from llm import LLM

@pytest.mark.parametrize('provider',['gemini','ollama'])
@pytest.mark.parametrize('mode',['friend','teacher'])
def test_selected_mode_reaches_both_providers(tmp_path,provider,mode):
    model=LLM(tmp_path/'memory.json');model.provider=provider;model.conversation_mode=mode;model.context_length=32768
    if provider=='gemini':
        with patch.object(model,'_request_gemini',return_value='Hello.') as call:
            model._request_raw([{'role':'user','content':'Teach me fractions.'}]);messages=call.call_args.args[0]
    else:
        reply=Mock(status_code=200);reply.json.return_value={'message':{'content':'Hello.'}}
        with patch('llm.requests.post',return_value=reply) as call:
            model._request_raw([{'role':'user','content':'Teach me fractions.'}]);messages=call.call_args.kwargs['json']['messages']
    text=' '.join(m['content'] for m in messages if m['role']=='system');assert 'Selected conversation mode: '+mode.title() in text


def test_teacher_mode_does_not_change_machine_readable_plans(tmp_path):
    model=LLM(tmp_path/'memory.json');model.provider='gemini';model.conversation_mode='teacher'
    with patch.object(model,'_request_gemini',return_value='{}') as call:
        model._request_raw([{'role':'user','content':'Plan a task.'}],planning=True)
    assert not any('Selected conversation mode:' in m['content'] for m in call.call_args.args[0])


def test_settings_validates_saves_and_applies_conversation_mode():
    import asyncio,app
    from starlette.requests import Request
    origin='http://127.0.0.1:'+str(app.gui_server.port)
    request=Request({'type':'http','method':'POST','scheme':'http','path':'/api/settings','query_string':b'','headers':[(b'host',origin.split('://')[1].encode()),(b'origin',origin.encode())],'client':('127.0.0.1',1234),'server':('127.0.0.1',app.gui_server.port)})
    model=Mock()
    with patch.object(app,'llm',model),patch.object(app,'save_settings',return_value={'conversation_mode':'teacher'}) as save:
        invalid=asyncio.run(app.update_app_settings(request,{'conversation_mode':'invalid'}));assert invalid.status_code==400;save.assert_not_called()
        result=asyncio.run(app.update_app_settings(request,{'conversation_mode':'teacher'}))
        assert not hasattr(result,'status_code') or result.status_code==200
        save.assert_called_once_with({'conversation_mode':'teacher'});assert model.conversation_mode=='teacher'


@pytest.mark.parametrize('with_image',[False,True])
def test_third_party_followup_keeps_topic_in_small_context(tmp_path,with_image):
    model=LLM(tmp_path/'memory.json');model.context_length=2048
    model.history=[{'role':'user','content':'Do you know who moonriverstream is?'},
                   {'role':'assistant','content':'I am not sure which creator you mean.'},
                   {'role':'user','content':'I will give you his photo.'},
                   {'role':'assistant','content':'Please attach it.'}]
    attachments=[{'kind':'image','name':'photo.jpg','image':'test-image'}] if with_image else None
    with patch.object(model,'_request',return_value='You mean moonriverstream, the creator we were discussing.') as call:
        model.chat('I meant that is moonriverstream',attachments=attachments)
    sent=call.call_args.args[0]
    assert 'Do you know who moonriverstream is?' in sent[-1]['content']
    assert 'Latest user message: I meant that is moonriverstream' in sent[-1]['content']
    fitted=model._fit_local_messages(sent,4096 if with_image else 2048,160 if with_image else 128)
    assert 'moonriverstream' in fitted[-1]['content']
    assert 'Latest user message:' in fitted[-1]['content']
    assert model.history[-2]['content']=='I meant that is moonriverstream'
    assert 'test-image' not in str(model.history)


def test_unfamiliar_creator_rules_do_not_invent_biography(tmp_path):
    model=LLM(tmp_path/'memory.json')
    with patch.object(model,'_request',return_value='I am not sure which creator you mean. Can you share a channel link?') as call:
        model.chat('Do you know moonriverstream?')
    rules=' '.join(m['content'] for m in call.call_args.args[0] if m['role']=='system')
    assert 'do not fabricate a biography' in rules
    assert 'failed upload is not visual evidence' in rules


@pytest.mark.parametrize('text',[
    'Make a trading app for me','Can you build a website?','Please write a Python script',
    'I want you to create a market research agent','Edit my CV','Add a meeting to my calendar',
    'Help me create a spreadsheet','Schedule a report for tomorrow'])
def test_friend_requests_substantial_work_in_teacher(text):
    from conversation_modes import work_request
    assert work_request(text)

@pytest.mark.parametrize('text',[
    'Hello','I had a hard day','Can you make me laugh?','I use a trading app',
    'What is a trading app?','Do not delete my files','What is on my calendar?',
    'Can you tell me what you see?'])
def test_friend_retains_conversation_and_readonly_questions(text):
    from conversation_modes import work_request
    assert not work_request(text)


def test_friend_task_gate_runs_before_search_tools_or_generation():
    import asyncio,app
    model=Mock()
    with patch.object(app,'get_settings',return_value={'conversation_mode':'friend','response_restriction_level':'off'}),patch.object(app,'llm',model),patch.object(app,'_chat_core') as generate,patch('search_confirmation.search_consent.respond') as search:
        result=asyncio.run(app.chat({'text':'Make a trading app','defer_audio':True}))
        assert result['mode_required']=='teacher' and 'speaker icon on the left' in result['reply']
        generate.assert_not_called();search.assert_not_called()


def test_voice_mode_switch_saves_and_does_not_execute_queued_task():
    import asyncio,app
    model=Mock()
    with patch.object(app,'get_settings',return_value={'conversation_mode':'friend'}),patch.object(app,'save_settings') as save,patch.object(app,'llm',model),patch.object(app,'_chat_core') as generate:
        result=asyncio.run(app.chat({'text':'switch to Teacher mode','defer_audio':True}))
        assert result['conversation_mode']=='teacher' and model.conversation_mode=='teacher'
        save.assert_called_once_with({'conversation_mode':'teacher'});generate.assert_not_called()


def test_teacher_request_continues_to_existing_tools():
    import asyncio,app
    with patch.object(app,'get_settings',return_value={'conversation_mode':'teacher','response_restriction_level':'off'}),patch.object(app,'llm',None),patch.object(app,'_chat_core',return_value={'reply':'Choose the workspace in Agent mode.'}) as generate,patch('search_confirmation.search_consent.respond',return_value=None),patch('learned_answers.learned_answers.recall',return_value=None):
        result=asyncio.run(app.chat({'text':'Make a trading app','defer_audio':True}))
        assert result['reply']=='Choose the workspace in Agent mode.';generate.assert_awaited_once()


def test_teacher_appearance_repair_uses_real_ui_action_and_saved_mode():
    import asyncio,app
    model=Mock(conversation_mode='friend')
    with patch.object(app,'get_settings',return_value={'conversation_mode':'teacher'}),patch.object(app,'llm',model),patch.object(app,'_chat_core') as generate:
        result=asyncio.run(app.chat({'text':'Can you fix the model, actually the hair is pink?'}))
        assert model.conversation_mode=='teacher'
        assert result['avatar_ui_action']=='check_textures'
        assert 'Teacher mode' not in result['reply']
        generate.assert_not_called()
        state=asyncio.run(app.chat({'text':'you are in teacher mode'}))
        assert state['reply']=='Teacher mode is currently on.'


def test_friend_is_default_and_emotional_style_stays_grounded():
    from conversation_modes import instruction
    assert 'Selected conversation mode: Friend' in instruction(None)
    assert 'empathy, curiosity, delight' in instruction('friend')
    assert 'Never guilt the user' in instruction('friend')
    assert 'successful tool results' in instruction('teacher')


def test_agent_new_task_is_blocked_in_friend_with_ui_guidance(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from agent_api import agent_router
    import re
    application=FastAPI();application.include_router(agent_router(lambda:Mock(conversation_mode='friend')))
    client=TestClient(application,base_url='http://127.0.0.1:8790',client=('127.0.0.1',35000))
    token=re.search(r"const token='([^']+)'",client.get('/agent').text)[1]
    response=client.post('/api/agent/tasks',headers={'X-Sakura-Agent':token},json={'goal':'Build an app','workspace':str(tmp_path)})
    assert response.status_code==409
    assert 'Voice & speech' in response.json()['detail']
