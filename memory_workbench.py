"""Deterministic maintenance, source-linked entity index and separate activity journal."""
import json
import re
import sqlite3
import threading
import time
from pathlib import Path
from datetime import datetime,timezone
from contextlib import contextmanager,closing
from atomic_state import atomic_text,state_lock

class MemoryWorkbench:
    def __init__(self,root,audit,store_getter,*,interval_seconds=3600):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.path=self.root/'memory-workbench.sqlite3'
        self.config=self.root/'memory-maintenance.json';self.audit=audit;self.store_getter=store_getter
        self.stop_event=threading.Event();self.thread=None;self.last_error='';self.lock=threading.RLock()
        if not isinstance(interval_seconds,(int,float)) or not 0<interval_seconds<=86400:raise ValueError('Invalid maintenance interval.')
        self.interval_seconds=interval_seconds;self.last_attempt_at=None;self.last_completed_at=None;self.last_run=None;self.next_check_at=None
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS journal(day TEXT PRIMARY KEY,classification TEXT,text TEXT,sources TEXT)')
            db.execute('DROP TABLE IF EXISTS entities')  # Entity hints belong to the source ledger, so forgetting can remove them atomically.
    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=5)
        try:
            with db:yield db
        finally:db.close()
    def enabled(self):
        try:return json.loads(self.config.read_text(encoding='utf-8')).get('enabled') is True
        except (OSError,ValueError,AttributeError):return False
    def configure(self,enabled):
        if type(enabled) is not bool:raise ValueError('Choose whether hourly maintenance is enabled.')
        with state_lock(self.config):atomic_text(self.config,json.dumps({'enabled':enabled}))
        return {'enabled':enabled}
    def _store(self):
        store=self.store_getter()
        if store is None:raise ValueError('Enable Companion long-term memory before using memory maintenance or the entity index.')
        return store
    def maintain(self,apply=False):
        store=self._store();now=time.time()
        with self.lock,store.lock,closing(store._connect()) as db,db:
            db.execute('CREATE TABLE IF NOT EXISTS retired_memories(memory_id INTEGER PRIMARY KEY,retired_at REAL,reason TEXT)')
            retired={r[0] for r in db.execute('SELECT memory_id FROM retired_memories')}
            rows=store._rows(db);candidates=[]
            for row in rows:
                classification=str(row['classification']).lower()
                # Explicit user facts and verified evidence are never retired by this policy.
                if row['id'] in retired or row.get('superseded_by') or 'user' in classification or 'verified' in classification:continue
                if now-(row['last_seen'] or row['created_at'])<180*86400 or (row['hits'] or 0)>0:continue
                if (row['confidence'] or 0)<.5 and store._strength(row,now)<.15:candidates.append(row['id'])
            if apply:
                db.executemany('INSERT OR IGNORE INTO retired_memories VALUES(?,?,?)',[(i,now,'Weak, unused, non-user record older than 180 days') for i in candidates]);db.commit()
            return {'ok':True,'mode':'applied' if apply else 'preview','candidates':candidates,'retired':len(candidates) if apply else 0,'records':len(rows),'policy':'No LLM rewriting. User-provided and verified records are retained. Raw ledger rows are never deleted.'}
    def rebuild_graph(self):
        store=self._store()
        with self.lock,store.lock,closing(store._connect()) as source,source:
            source.execute('CREATE TABLE IF NOT EXISTS memory_entities(memory_id INTEGER,entity TEXT,classification TEXT,PRIMARY KEY(memory_id,entity))')
            retired=set()
            if source.execute("SELECT 1 FROM sqlite_master WHERE name='retired_memories'").fetchone():retired={r[0] for r in source.execute('SELECT memory_id FROM retired_memories')}
            rows=store._rows(source);links=[]
            for row in rows:
                if row.get('superseded_by') or row['id'] in retired:continue
                names=set(re.findall(r'\b[A-Z][A-Za-z0-9_-]{2,35}(?: [A-Z][A-Za-z0-9_-]{2,35})?\b',row['text']))
                for name in sorted(names-{'The','This','That','Your','User','Provided','Verified','Unknown','Sakura'})[:12]:links.append((row['id'],name,str(row['classification'])[:60]))
            source.execute('DELETE FROM memory_entities');source.executemany('INSERT OR IGNORE INTO memory_entities VALUES(?,?,?)',links)
            return {'ok':True,'links':len(links),'relation':'mentioned_in','note':'Deterministic name hints, not inferred relationships or new facts. Every link points to its source memory ID.'}
    def graph(self,query=''):
        if not isinstance(query,str) or len(query)>100:raise ValueError('Use a short entity search.')
        store=self._store()
        with store.lock,closing(store._connect()) as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='memory_entities'").fetchone():return []
            retired=' AND m.id NOT IN (SELECT memory_id FROM retired_memories)' if db.execute("SELECT 1 FROM sqlite_master WHERE name='retired_memories'").fetchone() else ''
            return [{'memory_id':r[0],'entity':r[1],'classification':r[2],'relation':'mentioned_in'} for r in db.execute('SELECT e.memory_id,e.entity,e.classification FROM memory_entities e JOIN memories m ON m.id=e.memory_id WHERE m.superseded_by IS NULL'+retired+' AND instr(lower(e.entity),lower(?))>0 ORDER BY e.entity LIMIT 200',(query,))]
    def journal(self,day=None):
        day=day or datetime.now(timezone.utc).strftime('%Y-%m-%d')
        try:datetime.strptime(day,'%Y-%m-%d')
        except (TypeError,ValueError):raise ValueError('Use a YYYY-MM-DD UTC date.') from None
        rows=[r for r in self.audit.day(day) if r['status']!='started']
        counts={name:sum(r['status']==name for r in rows) for name in ('completed','failed','cancelled')}
        text=f"On {day} (UTC), I recorded {counts['completed']} completed tool calls, {counts['failed']} failed calls and {counts['cancelled']} cancelled calls. This is an activity summary, not a statement from the user or an account of feelings."
        classification='Assistant reflection - derived activity, not user evidence'
        sources=[r['id'] for r in rows]
        with self.db() as db:db.execute('INSERT OR REPLACE INTO journal VALUES(?,?,?,?)',(day,classification,text,json.dumps(sources)))
        return {'day':day,'classification':classification,'text':text,'audit_ids':sources}
    def status(self):
        with self.db() as db:
            journals=[{'day':r[0],'classification':r[1],'text':r[2],'audit_ids':json.loads(r[3])} for r in db.execute('SELECT * FROM journal ORDER BY day DESC LIMIT 14')]
        return {'enabled':self.enabled(),'journals':journals,'last_error':self.last_error,
                'running':bool(self.thread and self.thread.is_alive()),'interval_seconds':self.interval_seconds,
                'next_check_at':self.next_check_at,'last_attempt_at':self.last_attempt_at,
                'last_completed_at':self.last_completed_at,'last_run':self.last_run}
    def _scheduled_pass(self):
        if not self.enabled() or self.stop_event.is_set():return
        self.last_attempt_at=time.time()
        try:
            result=self.maintain(True)
            if self.stop_event.is_set():return
            graph=self.rebuild_graph()
            if self.stop_event.is_set():return
            journal=self.journal()
            self.last_run={'retired':result['retired'],'records':result['records'],'entity_links':graph['links'],'journal_day':journal['day']}
            self.last_completed_at=time.time();self.last_error=''
        except Exception:self.last_error='Maintenance could not run. Check whether long-term memory is enabled and its files are writable.'
    def start(self):
        if self.thread and self.thread.is_alive():return
        self.stop_event.clear()
        def loop():
            try:
                while True:
                    self.next_check_at=time.time()+self.interval_seconds
                    if self.stop_event.wait(self.interval_seconds):break
                    self._scheduled_pass()
            finally:self.next_check_at=None
        self.thread=threading.Thread(target=loop,daemon=True,name='SakuraMemoryMaintenance');self.thread.start()
    def stop(self):
        self.stop_event.set()
        if self.thread and self.thread is not threading.current_thread():self.thread.join(timeout=5)
