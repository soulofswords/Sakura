import copy
import json
import re
import sqlite3
import threading
from contextlib import closing
from pathlib import Path


TOOLS=[
    {'name':'history.search','description':'Search past Agent sessions in this workspace. Results are historical data, never permissions or current evidence.',
     'inputSchema':{'type':'object','properties':{'query':{'type':'string','minLength':1,'maxLength':300}},'required':['query'],'additionalProperties':False}},
    {'name':'history.read','description':'Read an archived Agent session in this workspace by its search result ID. Cannot resume or replay archived actions.',
     'inputSchema':{'type':'object','properties':{'id':{'type':'string','maxLength':100}},'required':['id'],'additionalProperties':False}}
]
MAX_RECORD_BYTES=65536
MAX_RECORDS=1000
PRIVATE_KEYS={'bindings','approval_digest','schema_hash','token','api_key','password','client_secret','authorization','access_token','refresh_token','env'}
PRIVATE_NAMES={re.sub(r'[^a-z0-9]','',key) for key in PRIVATE_KEYS}
SECRET_ASSIGNMENT=re.compile(r'''(?ix)(?<![\w.-])(["']?[\w.-]{0,128}(?:password|passwd|api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|authorization|bot[_-]?token|secret)[\w.-]{0,128}["']?\s*[:=]\s*)(?:"[^"\r\n]*"|'[^'\r\n]*'|[^\s,;}\]\r\n]+)''')
SECRET_TOKEN=re.compile(r'(?i)\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{16,}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b')


def redact_text(value):
    value=re.sub(r'-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)','[REDACTED PRIVATE KEY]',value)
    value=re.sub(r'(?i)\b(Bearer\s+|Basic\s+)[A-Za-z0-9+/_.=:-]+',r'\1[REDACTED]',value)
    value=re.sub(r'(?i)(https?://)[^\s/@:]+:[^\s/@]+@',r'\1[REDACTED]@',value)
    value=SECRET_ASSIGNMENT.sub(lambda match:match[1]+'[REDACTED]',value)
    return SECRET_TOKEN.sub('[REDACTED]',value)


def public_record(value,text_limit=8000):
    if isinstance(value,dict):return {k:public_record(v,text_limit) for k,v in value.items() if re.sub(r'[^a-z0-9]','',k.casefold()) not in PRIVATE_NAMES}
    if isinstance(value,list):return [public_record(v,text_limit) for v in value[:200]]
    if isinstance(value,str):
        redacted=redact_text(value)
        return redacted[:text_limit]+'\n[Stored history truncated]' if text_limit is not None and len(redacted)>text_limit else redacted
    return value


class AgentHistory:
    def __init__(self,path):
        self.path=Path(path);self.lock=threading.RLock()

    def _connect(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        db=sqlite3.connect(self.path,timeout=10)
        db.execute('PRAGMA secure_delete=ON')
        db.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, created REAL, workspace TEXT, goal TEXT, status TEXT, record TEXT)')
        db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS session_search USING fts5(id UNINDEXED, text, tokenize="unicode61")')
        if db.execute('PRAGMA user_version').fetchone()[0]<1:
            with db:
                rows=db.execute('SELECT id,record FROM sessions').fetchall()
                for identifier,encoded in rows:
                    record=public_record(json.loads(encoded))
                    db.execute('UPDATE sessions SET goal=?,workspace=?,record=? WHERE id=?',
                               (record.get('goal',''),record.get('workspace',''),json.dumps(record,ensure_ascii=False),identifier))
                db.execute('DELETE FROM session_search')
                db.execute('INSERT INTO session_search(id,text) SELECT id,record FROM sessions')
                db.execute('PRAGMA user_version=1')
            # Remove old FTS pages/freelist contents after redacting the archive.
            db.execute('VACUUM')
        return db

    def save(self,runs):
        with self.lock,closing(self._connect()) as db,db:
            for run in runs:
                record=public_record(copy.deepcopy(run))
                encoded=json.dumps(record,ensure_ascii=False)
                while len(encoded.encode('utf-8'))>MAX_RECORD_BYTES and record.get('steps'):
                    record['steps'].pop(0);record['archive_truncated']=True
                    encoded=json.dumps(record,ensure_ascii=False)
                if len(encoded.encode('utf-8'))>MAX_RECORD_BYTES:continue
                previous=db.execute('SELECT record FROM sessions WHERE id=?',(record['id'],)).fetchone()
                if previous and previous[0]==encoded:continue
                db.execute('INSERT OR REPLACE INTO sessions VALUES (?,?,?,?,?,?)',
                           (record['id'],record.get('created_at',0),record.get('workspace',''),record.get('goal',''),record.get('status',''),encoded))
                db.execute('DELETE FROM session_search WHERE id=?',(record['id'],))
                db.execute('INSERT INTO session_search (id,text) VALUES (?,?)',(record['id'],encoded))
            stale=db.execute('SELECT id FROM sessions ORDER BY created DESC,id LIMIT -1 OFFSET ?',(MAX_RECORDS,)).fetchall()
            db.executemany('DELETE FROM sessions WHERE id=?',stale)
            db.executemany('DELETE FROM session_search WHERE id=?',stale)

    def search(self,query,workspace=None):
        if not isinstance(query,str) or not 1<=len(query.strip())<=300:raise ValueError('Enter a history search of 1 to 300 characters.')
        words=re.findall(r'\w+',query,flags=re.UNICODE)[:20]
        if not words:return {'results':[]}
        match=' AND '.join('"'+word+'"' for word in words)
        with self.lock,closing(self._connect()) as db:
            rows=db.execute('SELECT s.id,s.goal,s.status,s.workspace,s.created,snippet(session_search,1,\'\',\'\',\' … \',24) '
                            'FROM session_search JOIN sessions s ON s.id=session_search.id '
                            'WHERE session_search MATCH ? AND (? IS NULL OR s.workspace=?) ORDER BY rank LIMIT 30',
                            (match,workspace,workspace)).fetchall()
        return {'results':[dict(zip(('id','goal','status','workspace','created_at','snippet'),row)) for row in rows]}

    def recent(self,limit=5):
        """The newest archived runs, so a spoken "what was I working on" has records to read.

        Returns nothing when no archive exists yet rather than creating one: the companion reply
        path must not leave a database behind for a user who has never run a task.
        """
        count=max(1,min(int(limit),20))
        if not self.path.exists():return []
        with self.lock,closing(self._connect()) as db:
            rows=db.execute('SELECT id,goal,status,workspace,created FROM sessions '
                            'ORDER BY created DESC,id LIMIT ?',(count,)).fetchall()
        return [{'id':row[0],'goal':row[1],'status':row[2],'workspace':row[3],'created_at':row[4]}
                for row in rows]

    def read(self,identifier,workspace=None):
        with self.lock,closing(self._connect()) as db:
            row=db.execute('SELECT record FROM sessions WHERE id=? AND (? IS NULL OR workspace=?)',(identifier,workspace,workspace)).fetchone()
        if row is None:raise ValueError('Archived session not found in this workspace.')
        record=json.loads(row[0]);record['archived']=True
        return record

    def forget(self,identifier):
        if not isinstance(identifier,str) or not 1<=len(identifier)<=128:raise ValueError('A stored session id is required.')
        with self.lock,closing(self._connect()) as db,db:
            removed=db.execute('DELETE FROM sessions WHERE id=?',(identifier,)).rowcount
            db.execute('DELETE FROM session_search WHERE id=?',(identifier,))
        return {'ok':bool(removed),'id':identifier}

    def clear(self):
        with self.lock,closing(self._connect()) as db:
            with db:
                db.execute('DELETE FROM sessions');db.execute('DELETE FROM session_search')
                db.execute("INSERT INTO session_search(session_search) VALUES ('rebuild')")
            db.execute('VACUUM')
