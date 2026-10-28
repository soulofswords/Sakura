import json
import time
from pathlib import Path
from unittest.mock import patch

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
