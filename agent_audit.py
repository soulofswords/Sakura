"""Bounded per-call metadata audit; never persist raw arguments or tool output."""
import hashlib
import json
from pathlib import Path
import sqlite3
import time
from contextlib import contextmanager

class AuditLog:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self._connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS calls(id INTEGER PRIMARY KEY, time REAL, run_id TEXT, step_id TEXT, tool TEXT, workspace_digest TEXT, arguments_digest TEXT, status TEXT, seconds REAL)')
            db.execute('CREATE INDEX IF NOT EXISTS calls_time ON calls(time)')
    @contextmanager
    def _connect(self):
        db=sqlite3.connect(self.path,timeout=5)
        try:
            with db:yield db
        finally:db.close()
    def record(self,run_id,action,workspace='',status=None):
        try:
            args=json.dumps(action.get('arguments',{}),sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
            digest=lambda value:hashlib.sha256(value).hexdigest()
            with self._connect() as db:
                db.execute('INSERT INTO calls(time,run_id,step_id,tool,workspace_digest,arguments_digest,status,seconds) VALUES(?,?,?,?,?,?,?,?)',
                           (time.time(),str(run_id)[:64],str(action.get('id',''))[:64],str(action.get('tool',''))[:120],digest(str(workspace).encode()),digest(args),str(status or action.get('status','unknown'))[:30],max(0,float(action.get('seconds',0)))))
                db.execute('DELETE FROM calls WHERE id NOT IN (SELECT id FROM calls ORDER BY id DESC LIMIT 10000)')
            return True
        except Exception:return False  # Logging must never turn an executed action into a retryable failure.
    def recent(self,limit=100):
        with self._connect() as db:
            db.row_factory=sqlite3.Row
            return [dict(row) for row in db.execute('SELECT * FROM calls ORDER BY id DESC LIMIT ?', (max(1,min(int(limit),500)),))]
    def day(self,day):
        from datetime import datetime,timezone
        start=datetime.strptime(day,'%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp()
        with self._connect() as db:
            db.row_factory=sqlite3.Row
            return [dict(row) for row in db.execute('SELECT * FROM calls WHERE time>=? AND time<? ORDER BY id',(start,start+86400))]
