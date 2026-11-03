import json
import sqlite3
import time
import threading
from contextlib import closing
from unittest.mock import patch,Mock
import pytest
from agent_audit import AuditLog
from memory_workbench import MemoryWorkbench
from memory_vectors import MemoryStore,_LexicalEmbedder
from extension_catalog import configuration

@pytest.fixture
def workshop(tmp_path):
    with patch('memory_vectors.embedder',return_value=_LexicalEmbedder()):
        store=MemoryStore(tmp_path/'memory.sqlite3');audit=AuditLog(tmp_path/'audit.sqlite3')
        yield MemoryWorkbench(tmp_path,audit,lambda:store),store,audit

def remember(store,text,classification='User-provided',confidence=1):
    store.remember({'text':text,'classification':classification,'confidence':confidence,'sources':[],'method':'test'},merge=False)

def test_entity_index_forgets_with_source_and_clear(workshop):
    work,store,_=workshop
    remember(store,'Alice meets Bob in Pune.')
    assert work.rebuild_graph()['links']>=2
    assert work.graph('Alice')[0]['memory_id']
    store.forget({'alice'})
    assert work.graph('Alice')==[]
    with closing(store._connect()) as db:assert db.execute('SELECT count(*) FROM memory_entities').fetchone()[0]==0
    remember(store,'Charlie lives in Mumbai.');work.rebuild_graph();store.clear()
    assert work.graph()==[]

def test_retirement_preserves_ledger_and_user_facts(workshop):
    work,store,_=workshop
    remember(store,'User Alice prefers Pune.')
    remember(store,'Sensor Charlie saw Mumbai.','Unknown',.1)
    with closing(store._connect()) as db,db:db.execute('UPDATE memories SET created_at=?,last_seen=?,hits=0',(time.time()-600*86400,time.time()-600*86400))
    assert len(work.maintain(False)['candidates'])==1
    assert work.maintain(True)['retired']==1
    assert store.stats()['memories']==2
    assert store.stats()['live_count']==1
    assert len(store.recent(10,live_only=True))==1
    work.rebuild_graph();assert work.graph('Charlie')==[]
    assert not any('Charlie' in r['text'] for r in store.search('Charlie Mumbai')['results'])

def test_audit_excludes_arguments_and_diary_is_classified(workshop):
    work,store,audit=workshop
    secret='super-secret-password'
    assert audit.record('run',{'tool':'files.read','arguments':{'password':secret},'status':'completed'},'C:/private')
    rows=audit.recent();assert rows[0]['status']=='completed'
    assert secret not in json.dumps(rows);assert 'C:/private' not in json.dumps(rows)
    journal=work.journal();assert journal['audit_ids']==[rows[0]['id']]
    assert 'not user evidence' in journal['classification'];assert store.stats()['memories']==0
    assert work.enabled() is False;work.configure(True);assert work.enabled()
    with pytest.raises(ValueError):work.configure('yes')
    with pytest.raises(ValueError):work.journal('../bad')

def test_catalog_is_configuration_only_and_restricts_workspace(tmp_path):
    assert configuration('playwright')['args']==['--yes','@playwright/mcp@0.0.84','--headless','--isolated']
    with pytest.raises(ValueError):configuration('filesystem')
    assert configuration('filesystem',str(tmp_path))['args'][-1]==str(tmp_path.resolve())
    with pytest.raises(ValueError):configuration('not-a-package')

def test_real_worker_waits_for_enabled_schedule_and_stops(workshop):
    work,store,_=workshop;work.interval_seconds=.02
    remember(store,'Sensor Charlie saw Mumbai.','Unknown',.1)
    with closing(store._connect()) as db,db:db.execute('UPDATE memories SET created_at=?,last_seen=?,hits=0',(time.time()-600*86400,time.time()-600*86400))
    completed=threading.Event();journal=work.journal
    def finish():
        result=journal();completed.set();return result
    with patch.object(work,'journal',side_effect=finish):
        work.start();worker=work.thread;work.start();assert work.thread is worker
        try:
            assert not completed.wait(.08)
            assert work.status()['last_attempt_at'] is None
            work.configure(True)
            assert completed.wait(2), 'Actual scheduled worker did not complete a pass'
        finally:work.stop()
    status=work.status();assert not status['running'];assert status['next_check_at'] is None
    assert status['last_completed_at'];assert status['last_run']['retired']==1
    assert store.stats()['live_count']==0;assert store.stats()['memories']==1
    assert work.graph('Charlie')==[];assert status['journals']

def test_worker_survives_failure_without_leaking_exception(workshop):
    work,_,_=workshop;work.interval_seconds=.02;work.configure(True)
    failure=threading.Event();recovered=threading.Event();maintain=work.maintain;attempts=[]
    def attempt(apply):
        attempts.append(apply)
        if len(attempts)==1:failure.set();raise ValueError('sensitive path/password')
        return maintain(apply)
    journal=work.journal
    def finish():result=journal();recovered.set();return result
    with patch.object(work,'maintain',side_effect=attempt),patch.object(work,'journal',side_effect=finish):
        work.start()
        try:
            assert failure.wait(2);assert recovered.wait(2)
        finally:work.stop()
    assert len(attempts)>=2;assert work.status()['last_error']==''
    assert 'sensitive' not in json.dumps(work.status())

def test_fixed_inputs_produce_same_maintenance_graph_and_diary(tmp_path):
    outputs=[]
    with patch('memory_vectors.embedder',return_value=_LexicalEmbedder()),patch('memory_workbench.time.time',return_value=2000000000):
        for name in ('first','second'):
            root=tmp_path/name;root.mkdir();store=MemoryStore(root/'memory.sqlite3');audit=AuditLog(root/'audit.sqlite3')
            work=MemoryWorkbench(root,audit,lambda:store)
            remember(store,'Alice prefers Pune.')
            remember(store,'Charlie visited Mumbai.','Unknown',.1)
            with closing(store._connect()) as db,db:db.execute('UPDATE memories SET created_at=?,last_seen=?,hits=0',(1900000000,1900000000))
            audit.record('run',{'tool':'files.read','status':'completed'})
            preview=work.maintain(False);applied=work.maintain(True);graph=work.rebuild_graph()
            outputs.append((preview,applied,graph,work.graph(),work.journal('2033-05-18')))
    assert outputs[0]==outputs[1]

def test_fastapi_lifespan_starts_real_worker_and_joins_on_shutdown(tmp_path,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from agent_connections import Connections
    from agent_runtime import AgentRuntime
    import agent_api
    real_workbench=MemoryWorkbench;created=[]
    def build(root,audit,getter):
        instance=real_workbench(root,audit,getter,interval_seconds=.02);created.append(instance);return instance
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'))
    store=MemoryStore(tmp_path/'memory.sqlite3');model=Mock(memory_store=store)
    monkeypatch.setattr(agent_api,'runtime',runtime)
    monkeypatch.setattr('memory_workbench.MemoryWorkbench',build)
    for target in ('agent_automations.AgentAutomations.start','agent_automations.AgentAutomations.stop',
                   'agent_library_owner.owner_library.open','agent_library_owner.owner_library.close',
                   'telegram_bot.gateway.start','telegram_bot.gateway.stop',
                   'agent_messaging.MessagingGateways.start','agent_messaging.MessagingGateways.stop'):
        monkeypatch.setattr(target,lambda *args:None)
    app=FastAPI();app.include_router(agent_api.agent_router(lambda choice:model))
    worker=created[0];worker.configure(True)
    completed=threading.Event();journal=worker.journal
    def finish():result=journal();completed.set();return result
    monkeypatch.setattr(worker,'journal',finish)
    with TestClient(app):
        assert worker.status()['running'];assert completed.wait(2)
    assert not worker.thread.is_alive()
