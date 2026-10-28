import json
import threading
from unittest.mock import patch

import pytest

from agent_connections import Connections
from agent_runtime import AgentRuntime,planner_identity


class ParallelModel:
    provider='ollama';model='qwen3:8b'
    def __init__(self,barrier,write=False):self.barrier=barrier;self.write=write
    def _request_raw(self,messages,**kwargs):
        self.barrier.wait(timeout=5)
        context=json.loads(messages[1]['content'])
        assert context['steps_done']==[]
        if self.write:return json.dumps({'tool':'files.write','arguments':{'path':context['goal']+'.md','content':'A draft'}})
        return json.dumps({'done':True,'summary':'Read task '+context['goal']})


def prepare(tmp_path,write=False):
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'))
    run=runtime.new_run('Parent research',str(tmp_path))
    runtime.planners[run['id']]=ParallelModel(threading.Barrier(2),write)
    action=runtime.propose(run['id'],'agents.delegate',{'goals':['first topic','second topic']})['steps'][-1]
    return runtime,run,action


def test_workers_really_overlap_with_isolated_histories(tmp_path):
    runtime,run,action=prepare(tmp_path)
    result=runtime.decide(action['id'],True)
    children=result['action']['result']['children']
    assert len(children)==2
    assert all(child['status']=='completed' for child in children)
    assert len({child['id'] for child in children})==2
    assert not runtime.active_runs
    for child in children:
        state=runtime.state(child['id'])
        assert state['parent_id']==run['id']
        assert state['goal'] in child['summary']
        assert not state['steps']


def test_child_writes_wait_for_separate_approval_and_no_recursion(tmp_path):
    runtime,run,action=prepare(tmp_path,True)
    with patch.object(runtime,'_write_docx',create=True) as write:
        result=runtime.decide(action['id'],True)
    write.assert_not_called()
    for child in result['action']['result']['children']:
        state=runtime.state(child['id'])
        assert state['status']=='awaiting_approval'
        assert not (tmp_path/(child['goal']+'.md')).exists()
        runtime.decide(state['steps'][-1]['id'],False)
        with pytest.raises(ValueError,match='Nested'):runtime.propose(child['id'],'agents.delegate',{'goals':['one goal','another goal']})


def test_rejection_never_starts_children_and_provider_change_blocks(tmp_path):
    runtime,run,action=prepare(tmp_path)
    runtime.decide(action['id'],False)
    assert len(runtime.runs)==1
    action=runtime.propose(run['id'],'agents.delegate',{'goals':['first topic','second topic']})['steps'][-1]
    runtime.planners[run['id']]=object()
    result=runtime.decide(action['id'],True)
    assert result['action']['status']=='failed'
    assert len(runtime.runs)==1


class BlockingModel:
    """Holds both planner requests open so the test can cancel mid-execution."""
    def __init__(self,workers=2):
        self.workers=workers;self.mutex=threading.Lock();self.calls=[]
        self.entered=threading.Event();self.release=threading.Event()
    def _request_raw(self,messages,**kwargs):
        with self.mutex:
            self.calls.append(json.loads(messages[1]['content'])['goal'])
            if len(self.calls)>=self.workers:self.entered.set()
        self.release.wait(timeout=5)
        return json.dumps({'done':True,'summary':'finished'})


def test_cancelling_a_running_parent_cannot_evict_or_fail_its_children(tmp_path):
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'))
    run=runtime.new_run('Parent research',str(tmp_path))
    model=BlockingModel();runtime.planners[run['id']]=model
    action=runtime.propose(run['id'],'agents.delegate',{'goals':['alpha','beta']})['steps'][-1]
    failures={}
    finished=threading.Event()
    def runner():
        try:runtime.decide(action['id'],True)
        except Exception as error:failures['error']=error
        finally:finished.set()
    threading.Thread(target=runner,daemon=True).start()
    assert model.entered.wait(timeout=5),'delegation never reached the planner'
    runtime.cancel(run['id'])
    for index in range(27):runtime.new_run('Filler task '+str(index),str(tmp_path))
    runtime.new_run('Filler task that forces a sweep',str(tmp_path))
    model.release.set()
    assert finished.wait(timeout=10),'approval finalization hung'
    assert not failures,failures
    # The cancelled parent is the only evictable-looking record, so the sweep must have
    # recycled a filler instead of dropping the task the reviewer is still watching.
    assert run['id'] in runtime.runs
    assert len(model.calls)==2,'a cancelled child called the planner again'
    children=runtime.state(run['id'])['steps'][-1]['result']['children']
    assert [runtime.state(child['id'])['status'] for child in children]==['cancelled','cancelled']
    assert not runtime.active_runs


class CloudModel:
    provider='gemini';model='gemini-2.5-flash';base_url='https://generativelanguage.googleapis.com'


def test_identity_tracks_the_actual_provider_and_native_configuration():
    from types import SimpleNamespace
    for attributes,field,new_value in [
        ({'provider':'gemini','gemini_model':'flash'},'gemini_model','pro'),
        ({'provider':'openai','cloud_model':'a','cloud_endpoint':'https://one.test'},'cloud_endpoint','https://two.test'),
        ({'loaded':'first.gguf','loaded_engine':'llama.cpp','root':'models','port':8080},'loaded','second.gguf'),
    ]:
        model=SimpleNamespace(**attributes)
        before=planner_identity(model)
        setattr(model,field,new_value)
        assert before!=planner_identity(model)


def test_a_refused_plan_cannot_replace_the_ai_behind_a_pending_delegation(tmp_path):
    runtime,run,action=prepare(tmp_path)
    reviewed=runtime.planners[run['id']]
    with pytest.raises(ValueError,match='pending step'):runtime.plan(run['id'],ParallelModel(threading.Barrier(1)))
    assert runtime.planners[run['id']] is reviewed,'plan() discarded the planner the reviewer was looking at'


def test_delegate_binds_the_ai_by_content_so_a_reused_address_cannot_pass(tmp_path):
    """Approval must follow what the model is, because CPython reuses freed object addresses."""
    runtime,run,action=prepare(tmp_path)
    assert action['preview']['ai']=='ollama qwen3:8b','the card must name the AI that runs the children'
    bound=runtime.actions[action['id']]['bindings']['planner']
    assert bound==planner_identity(ParallelModel(threading.Barrier(1)))
    assert bound!=id(runtime.planners[run['id']])
    assert bound!=planner_identity(CloudModel())
    runtime.planners[run['id']]=CloudModel()
    result=runtime.decide(action['id'],True)
    assert 'Planning AI changed' in result['action']['result']['error']
    assert not [record for record in runtime.runs.values() if record.get('parent_id')],'child was created by a refused delegation'


def test_failed_child_creation_releases_every_pin(tmp_path):
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'))
    run=runtime.new_run('Parent research',str(tmp_path))
    runtime.planners[run['id']]=ParallelModel(threading.Barrier(1))
    action=runtime.propose(run['id'],'agents.delegate',{'goals':['alpha','beta']})['steps'][-1]
    original=runtime.new_run;seen=[]
    def flaky(goal,*rest,**kwargs):
        seen.append(goal)
        if len(seen)>1:raise ValueError('Workspace vanished.')
        return original(goal,*rest,**kwargs)
    with patch.object(runtime,'new_run',flaky):
        result=runtime.decide(action['id'],True)
    assert result['action']['status']=='failed'
    assert not runtime.active_runs,'a half-created delegation left its first child pinned forever'
    for index in range(29):runtime.new_run('Filler task '+str(index),str(tmp_path))
