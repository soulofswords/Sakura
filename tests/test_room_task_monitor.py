import threading,time
from types import SimpleNamespace
from room_task_monitor import snapshot

def test_only_bounded_redacted_progress_is_exposed():
    runtime=SimpleNamespace(lock=threading.RLock(),runs={'a':{'status':'running','goal':'Build a report api_key=not-for-display','updated_at':time.time(),'workspace':'PRIVATE','steps':[{'status':'completed','tool':'files.read','arguments':{'password':'SECRET'}},{'status':'running','tool':'shell.run','result':'PRIVATE LOG'}]}})
    data=snapshot(runtime)
    assert data['step']=='shell.run' and data['completed_steps']==1
    assert all(value not in str(data) for value in ('not-for-display','PRIVATE','SECRET'))
    runtime.runs['a']['status']='completed';runtime.runs['a']['updated_at']=0
    assert snapshot(runtime)['state']=='idle'

def test_old_ready_tasks_do_not_look_like_running_work():
    runtime=SimpleNamespace(lock=threading.RLock(),runs={'a':{'status':'ready','updated_at':0}})
    assert snapshot(runtime)['state']=='idle'

def test_monitor_endpoint_is_local_companion_only_and_guest_blocked(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from companion_features import router
    import companion_features,agent_runtime
    guest=SimpleNamespace(value=False)
    monkeypatch.setattr(companion_features,'features',lambda:SimpleNamespace(guest=lambda:guest.value))
    monkeypatch.setattr(agent_runtime,'runtime',SimpleNamespace(lock=threading.RLock(),runs={}))
    app=FastAPI();app.include_router(router(lambda request:True,lambda:True,lambda:None))
    client=TestClient(app)
    assert client.get('/api/features/task-monitor').json()['state']=='idle'
    guest.value=True;assert client.get('/api/features/task-monitor').status_code==409
    blocked=FastAPI();blocked.include_router(router(lambda request:False,lambda:True,lambda:None))
    assert TestClient(blocked).get('/api/features/task-monitor').status_code==403
