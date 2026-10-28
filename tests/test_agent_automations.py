import json
import time
from pathlib import Path
from unittest.mock import Mock,patch

import pytest
from agent_automations import AgentAutomations
from agent_connections import Connections
from agent_runtime import AgentRuntime


def setup(tmp_path,tool='files.list',arguments=None):
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'))
    run=runtime.new_run('Read my workspace',str(tmp_path))
    result=runtime.propose(run['id'],tool,arguments or {'path':'.'})
    runtime.decide(result['steps'][-1]['id'],True)
    return runtime,run,AgentAutomations(runtime)


def test_exact_read_workflow_persists_and_replays_without_model(tmp_path):
    runtime,run,scheduler=setup(tmp_path)
    with pytest.raises(ValueError):scheduler.create(run['id'],'Check',5,False)
    item=scheduler.create(run['id'],'Check',5,True)
    (tmp_path/'new.txt').write_text('new')
    result=AgentAutomations(runtime).execute(item['id'])
    assert result['run']['status']=='completed'
    assert any(x['name']=='new.txt' for x in result['run']['steps'][0]['result']['files'])
    assert result['run']['steps'][0]['arguments']['path']==str(tmp_path)
    scheduler.update(item['id'],True)
    with pytest.raises(ValueError):scheduler.execute(item['id'])


def test_file_edits_never_repeat_automatically_or_overwrite(tmp_path):
    runtime,run,scheduler=setup(tmp_path,'files.write',{'path':'draft.md','content':'Approved draft'})
    item=scheduler.create(run['id'],'Draft',60,True)
    result=scheduler.execute(item['id'])
    assert result['needs_approval']
    assert (tmp_path/'draft.md').read_text()=='Approved draft'
    assert scheduler.list()[0]['paused']


def test_exact_shell_is_queued_for_review_not_silently_run(tmp_path):
    with patch('agent_runtime.run_process',return_value={'ok':True,'output':'done'}):
        runtime,run,scheduler=setup(tmp_path,'shell.run',{'command':'Write-Output hello'})
    item=scheduler.create(run['id'],'Shell',5,True)
    with patch('agent_runtime.run_process') as execute:
        result=scheduler.execute(item['id'])
    execute.assert_not_called()
    assert result['run']['status']=='awaiting_approval'
    assert result['run']['steps'][0]['arguments']['command']=='Write-Output hello'


def test_changed_file_read_observes_current_content(tmp_path):
    file=tmp_path/'note.txt';file.write_text('old')
    runtime,run,scheduler=setup(tmp_path,'files.read',{'path':'note.txt'})
    item=scheduler.create(run['id'],'Notes',5,True);file.write_text('new')
    assert scheduler.execute(item['id'])['run']['steps'][0]['result']['text']=='new'


def test_restart_never_replays_an_interrupted_run(tmp_path):
    runtime,run,scheduler=setup(tmp_path);item=scheduler.create(run['id'],'Check',5,True)
    scheduler.items[item['id']].update(status='running',next_run=time.time()-60);scheduler.save()
    restored=AgentAutomations(runtime);assert restored.list()[0]['paused']
    with pytest.raises(ValueError):restored.execute(item['id'])


def test_disabled_ai_mode_prevents_scheduled_execution(tmp_path):
    runtime,run,scheduler=setup(tmp_path);item=scheduler.create(run['id'],'Check',5,True)
    scheduler.enabled=lambda:False
    with pytest.raises(ValueError):scheduler.execute(item['id'])
    assert len(runtime.states())==1


def test_busy_agent_defers_schedule_without_marking_it_failed(tmp_path):
    runtime,run,scheduler=setup(tmp_path);item=scheduler.create(run['id'],'Check',5,True)
    runtime.operation_lock.acquire()
    try:assert scheduler.execute(item['id'])['skipped']
    finally:runtime.operation_lock.release()
    assert not scheduler.list()[0]['paused']
    assert len(runtime.states())==1


def test_malformed_saved_schedule_does_not_break_agent_startup(tmp_path):
    runtime,run,scheduler=setup(tmp_path)
    scheduler.path.write_text(json.dumps({'broken':{'status':'running'},'bad':['not a schedule']}))
    assert AgentAutomations(runtime).list()==[]


def test_changed_workspace_identity_is_paused_on_restore_and_before_execution(tmp_path):
    runtime,run,scheduler=setup(tmp_path);item=scheduler.create(run['id'],'Check',5,True)
    scheduler.items[item['id']]['workspace_identity']['inode']=-1;scheduler.save()
    restored=AgentAutomations(runtime)
    assert restored.list()[0]['paused'] and restored.list()[0]['status']=='needs_approval'
    with pytest.raises(ValueError):scheduler.execute(item['id'])
    assert len(runtime.states())==1


def test_web_fetch_never_is_an_unattended_read():
    from agent_automations import READ_TOOLS
    assert 'web.fetch' not in READ_TOOLS


def goal_setup(tmp_path):
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'))
    run=runtime.new_run('Tidy my notes folder',str(tmp_path))
    return runtime,run,AgentAutomations(runtime)


def test_goal_automation_replans_and_never_runs_a_change_unattended(tmp_path):
    runtime,run,scheduler=goal_setup(tmp_path)
    (tmp_path/'notes.txt').write_text('a\n',encoding='utf-8')
    item=scheduler.create(run['id'],'Goal pass',5,True,mode='goal')
    assert item['mode']=='goal' and item['steps']==0
    model=Mock();model._request_raw.return_value=json.dumps(
        {'tool':'files.text.edit','arguments':{'path':'notes.txt','replacements':[{'old':'a','new':'b','count':1}]},'reason':'Rename a line'})
    scheduler.planner_getter=lambda choice:model
    result=scheduler.execute(item['id'])
    assert result['run']['status']=='awaiting_approval'
    assert (tmp_path/'notes.txt').read_text(encoding='utf-8')=='a\n'
    assert scheduler.list()[0]['status']=='needs_approval'
    assert scheduler.execute(item['id'])['skipped']


def test_goal_automation_without_planner_source_fails_honestly(tmp_path):
    runtime,run,scheduler=goal_setup(tmp_path)
    item=scheduler.create(run['id'],'Goal pass',5,True,mode='goal')
    with pytest.raises(ValueError):scheduler.execute(item['id'])
    assert scheduler.list()[0]['paused'] and 'planner' in scheduler.list()[0]['last_error'].lower()


def test_watch_event_fires_the_approved_replay_once_after_debounce(tmp_path):
    runtime,run,scheduler=setup(tmp_path)
    (tmp_path/'inbox').mkdir()
    item=scheduler.create(run['id'],'Watch',1440,True,event={'path':'inbox','min_seconds':60})
    t=time.time()
    assert scheduler.check_events(now=t)==[]
    (tmp_path/'inbox'/'a.txt').write_text('x')
    assert scheduler.check_events(now=t+1)==[item['id']]
    (tmp_path/'inbox'/'b.txt').write_text('y')
    assert scheduler.check_events(now=t+2)==[]
    assert scheduler.check_events(now=t+70)==[item['id']]
    assert scheduler.check_events(now=t+80)==[]


def test_watch_and_mode_arguments_cannot_escape_validation(tmp_path):
    runtime,run,scheduler=setup(tmp_path)
    for kwargs in ({'event':{'path':'../outside','min_seconds':60}},{'event':{'path':'inbox','min_seconds':5}},
                  {'event':{'path':'C:/Windows','min_seconds':60}},{'mode':'everything'},{'mode':'goal','approved':False}):
        approved=kwargs.pop('approved',True)
        with pytest.raises(ValueError):scheduler.create(run['id'],'Bad',5,approved,**kwargs)
    assert scheduler.list()==[]


def test_goal_and_event_items_survive_a_restart_and_bad_items_are_dropped(tmp_path):
    runtime,run,scheduler=goal_setup(tmp_path)
    scheduler.create(run['id'],'Goal',5,True,mode='goal')
    (tmp_path/'inbox').mkdir()
    restored=AgentAutomations(runtime)
    assert [x['mode'] for x in restored.list()]==['goal']
    broken=json.loads(restored.path.read_text(encoding='utf-8'))
    broken['junk']={'mode':'steps','minutes':5,'next_run':1,'workspace':str(tmp_path),'goal':'g','name':'n'}
    broken['goal-no-template']={'mode':'goal','minutes':5,'next_run':1,'workspace':str(tmp_path),'goal':'g','name':'n','event':{'path':'..','min_seconds':60}}
    restored.path.write_text(json.dumps(broken))
    reloaded=AgentAutomations(runtime)
    assert len(reloaded.list())==1 and reloaded.list()[0]['mode']=='goal'
