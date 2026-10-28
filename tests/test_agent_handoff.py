from unittest.mock import Mock,patch

import agent_handoff


def test_only_an_explicit_prefix_creates_a_task():
    assert agent_handoff.goal_for('agent: list the files in my workspace')=='list the files in my workspace'
    assert agent_handoff.goal_for('Computer - write a python script')=='write a python script'
    for text in ('hello','agent','agent:','agent: x','can you be my agent','pc specs','computer access'):
        assert agent_handoff.goal_for(text)=='',text


def test_handoff_creates_a_ready_task_without_running_any_tool(tmp_path):
    run={'id':'abc','status':'ready','steps':[]}
    runtime=Mock();runtime.new_run.return_value=run
    with patch('agent_runtime.runtime',runtime):
        result=agent_handoff.start('agent: inspect this folder',str(tmp_path))
    runtime.new_run.assert_called_once_with('inspect this folder',str(tmp_path))
    assert result['agent_run']=='abc'
    assert 'nothing has run yet' in result['reply']
    runtime.propose.assert_not_called()
    runtime.decide.assert_not_called()


def test_ordinary_chat_returns_none(tmp_path):
    assert agent_handoff.start('what are my pc specs',str(tmp_path)) is None
