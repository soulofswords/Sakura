import json
from unittest.mock import Mock,patch
from teacher_agent_chat import TeacherAgentChat
from agent_runtime import AgentRuntime
from agent_connections import Connections


def runtime_at(tmp_path):
    return AgentRuntime(Connections(tmp_path/'connections.json'),store_path=tmp_path/'tasks.json')


def test_teacher_creates_actual_saved_task_and_waits_for_approval(tmp_path):
    runtime=runtime_at(tmp_path);bridge=TeacherAgentChat(runtime)
    model=Mock();model._request_raw.return_value=json.dumps({'tool':'shell.run','arguments':{'command':'Write-Output hello'},'reason':'Test'})
    result=bridge.handle('Build an app in "'+str(tmp_path)+'"',{'conversation_mode':'teacher'},model,{})
    assert 'agent_task' in result
    identifier=result['agent_task']['id']
    bridge.jobs[identifier]['thread'].join(5)
    state=bridge.status(identifier)
    assert state['pending']['tool']=='shell.run'
    assert state['run']['status']=='awaiting_approval'
    assert state['pending'].get('result') is None
    assert (tmp_path/'tasks.json').exists()


def test_friend_never_creates_tasks_and_calendar_uses_existing_handler(tmp_path):
    runtime=runtime_at(tmp_path);bridge=TeacherAgentChat(runtime)
    assert bridge.handle('Make an app',{'conversation_mode':'friend'},Mock(),{}) is None
    assert bridge.handle('Add interview tomorrow at 11 am',{'conversation_mode':'teacher'},Mock(),{}) is None
    assert runtime.states()==[]


def test_workspace_question_does_not_run_anything(tmp_path):
    runtime=runtime_at(tmp_path);bridge=TeacherAgentChat(runtime);model=Mock()
    result=bridge.handle('Make a trading app',{'conversation_mode':'teacher'},model,{})
    assert 'Which folder' in result['reply'];assert runtime.states()==[];model._request_raw.assert_not_called()


def test_reject_is_bound_to_the_current_chat_task(tmp_path):
    runtime=runtime_at(tmp_path);bridge=TeacherAgentChat(runtime)
    run=runtime.new_run('Test',str(tmp_path),False);bridge.jobs[run['id']]={'running':False,'error':''}
    runtime.propose(run['id'],'shell.run',{'command':'Write-Output hello'},'Test')
    import pytest
    with pytest.raises(ValueError):bridge.decide(run['id'],'made-up-id',True,Mock())
    with patch.object(runtime,'_execute') as execute:
        action=bridge.status(run['id'])['pending']['id'];bridge.decide(run['id'],action,False,Mock());bridge.jobs[run['id']]['thread'].join(3)
        execute.assert_not_called();assert runtime.state(run['id'])['steps'][-1]['status']=='rejected'


def test_repeating_task_requires_a_reviewed_completed_workflow(tmp_path):
    runtime=runtime_at(tmp_path);bridge=TeacherAgentChat(runtime)
    run=runtime.new_run('Research market',str(tmp_path),False);bridge.jobs[run['id']]={'running':False,'error':''};bridge.latest['desktop']=run['id']
    result=bridge.handle('Repeat this task every 30 minutes',{'conversation_mode':'teacher'},Mock(),{})
    assert 'Finish and review' in result['reply'];assert not bridge.schedules
    with runtime.lock:
        runtime.runs[run['id']]['status']='completed';runtime.runs[run['id']]['steps']=[{'id':'done','tool':'web.search','arguments':{'query':'example'},'status':'completed'}]
    result=bridge.handle('Repeat this task every 30 minutes',{'conversation_mode':'teacher'},Mock(),{})
    assert result['agent_task']['schedule_minutes']==30
    scheduler=Mock();scheduler.create.return_value={'minutes':30};runtime.chat_automations=scheduler
    import pytest
    with pytest.raises(ValueError):bridge.schedule(run['id'],False)
    scheduler.create.assert_not_called()
    bridge.schedule(run['id'],True);scheduler.create.assert_called_once_with(run['id'],'Research market',30,True)
    with pytest.raises(ValueError):bridge.schedule(run['id'],True)
    assert scheduler.create.call_count==1


def test_phone_does_not_gain_pc_tools_from_teacher_mode_alone(tmp_path):
    runtime=runtime_at(tmp_path);bridge=TeacherAgentChat(runtime)
    result=bridge.handle('Build an app',{'conversation_mode':'teacher'},Mock(),{'phone':True})
    assert 'phone system access' in result['reply'];assert runtime.states()==[]


def test_teacher_chat_endpoint_creates_bridge_response_not_hallucinated_claim(tmp_path):
    import asyncio,app
    model=Mock();bridge_result={'reply':'Created a real Agent task.','audio':None,'agent_task':{'id':'test-id'}}
    with patch.object(app,'get_settings',return_value={'conversation_mode':'teacher','response_restriction_level':'off'}),patch.object(app,'llm',model),patch('teacher_agent_chat.teacher_agent_chat.handle',return_value=bridge_result) as handle,patch.object(app,'_chat_core') as ordinary:
        result=asyncio.run(app.chat({'text':'Build an app','defer_audio':True}))
        assert result['agent_task']['id']=='test-id';handle.assert_called_once();ordinary.assert_not_called()


def test_companion_approval_denies_friend_and_requires_real_pending_task():
    import asyncio,app
    with patch.object(app,'get_settings',return_value={'conversation_mode':'friend'}),patch('teacher_agent_chat.teacher_agent_chat.decide') as decide:
        result=asyncio.run(app.companion_agent_decide('test',{'action':'x','approved':True}))
        assert result.status_code==409;decide.assert_not_called()
