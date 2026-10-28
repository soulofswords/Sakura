import json
from unittest.mock import Mock,patch

import pytest

from agent_connections import Connections
from agent_runtime import AgentRuntime


@pytest.fixture
def setup(tmp_path):
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'))
    run=runtime.new_run('Permission tests',str(tmp_path))
    return runtime,run


def approve_command(runtime,run,remember=True):
    action=runtime.propose(run['id'],'shell.run',{'command':'Write-Output hello'})['steps'][-1]
    with patch('agent_runtime.run_process',return_value={'ok':True}):
        return runtime.decide(action['id'],True,remember)


def test_only_explicit_success_grants_exact_session_permission(setup,tmp_path):
    runtime,run=setup
    approve_command(runtime,run,False)
    assert runtime.permissions.list()==[]
    approve_command(runtime,run)
    exact=runtime._prepare(run,'shell.run',{'command':'Write-Output hello'})
    assert runtime.permissions.allows(exact)
    changed=runtime._prepare(run,'shell.run',{'command':'Write-Output hello; Write-Output world'})
    assert not runtime.permissions.allows(changed)
    other=tmp_path/'other';other.mkdir()
    moved=runtime._prepare(run,'shell.run',{'command':'Write-Output hello','cwd':str(other)})
    assert not runtime.permissions.allows(moved)
    assert AgentRuntime(Connections(tmp_path/'connections.json')).permissions.list()==[]
    permission=runtime.permissions.list()[0]
    runtime.permissions.revoke(permission['id'])
    assert not runtime.permissions.allows(exact)


def test_planner_reuses_only_matching_permission(setup):
    runtime,run=setup
    approve_command(runtime,run)
    model=Mock();model._request_raw.side_effect=[json.dumps({'tool':'shell.run','arguments':{'command':'Write-Output hello'}}),json.dumps({'done':True,'summary':'Verified output.'})]
    with patch('agent_runtime.run_process',return_value={'ok':True}) as execute:
        result=runtime.plan(run['id'],model)
    execute.assert_called_once()
    assert result['steps'][-1]['auto'] is True
    assert result['status']=='completed'


def test_changed_binding_and_schema_block_execution(setup):
    runtime,run=setup
    action=runtime.propose(run['id'],'shell.run',{'command':'Write-Output hello'})['steps'][-1]
    runtime.actions[action['id']]['bindings']['cwd']['inode']=-1
    with patch('agent_runtime.run_process') as execute:
        result=runtime.decide(action['id'],True,True)
    execute.assert_not_called()
    assert result['action']['status']=='failed'
    assert not runtime.permissions.list()


def test_failed_or_rejected_commands_cannot_grant_permission(setup):
    runtime,run=setup
    action=runtime.propose(run['id'],'shell.run',{'command':'Write-Output hello'})['steps'][-1]
    with pytest.raises(ValueError):runtime.decide(action['id'],False,True)
    with patch('agent_runtime.run_process',return_value={'ok':False}):runtime.decide(action['id'],True,True)
    assert not runtime.permissions.list()
    other=runtime.propose(run['id'],'files.list',{'path':'.'})['steps'][-1]
    with pytest.raises(ValueError):runtime.decide(other['id'],True,True)


def test_a_full_allow_list_cannot_rewrite_a_command_that_already_ran(setup):
    """Reporting a completed command as failed would make the reviewer run it twice."""
    runtime,run=setup
    for index in range(50):runtime.permissions.items['seed'+format(index,'03d')]={'id':'seed'+format(index,'03d'),'signature':'seed'+format(index,'03d')}
    action=runtime.propose(run['id'],'shell.run',{'command':'Write-Output hello'})['steps'][-1]
    with patch('agent_runtime.run_process',return_value={'ok':True,'output':'hello'}) as execute:
        result=runtime.decide(action['id'],True,True)
    execute.assert_called_once()
    assert result['action']['status']=='completed'
    assert result['action']['result']['output']=='hello'
    assert 'limit 50' in result['action']['permission_error']
    assert 'permission_saved' not in result['action']


def test_clearing_history_revokes_commands_remembered_in_the_session(setup):
    runtime,run=setup
    approve_command(runtime,run)
    assert runtime.permissions.list()
    runtime.clear_history()
    assert not runtime.permissions.list(),'a wiped task list must not keep unattended grants'
    assert not runtime.runs and not runtime.active_runs
