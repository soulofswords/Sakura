"""User-authored reusable procedures. Procedures never grant execution approval."""
import json
import re
import threading
from pathlib import Path

class AgentSkills:
    def __init__(self, path):
        self.path=Path(path); self.lock=threading.RLock()
    def list(self):
        with self.lock:
            try:
                data=json.loads(self.path.read_text(encoding='utf-8'))
                return data if isinstance(data,list) else []
            except (OSError,ValueError): return []
    def _write(self, items):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(items,ensure_ascii=False),encoding='utf-8')
        temporary.replace(self.path)
    def save(self, name, instructions):
        if not isinstance(name,str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,59}',name):
            raise ValueError('Use a skill name of up to 60 lowercase letters, numbers or hyphens.')
        if not isinstance(instructions,str) or not 10<=len(instructions.strip())<=4000:
            raise ValueError('Write a procedure of 10 to 4000 characters.')
        with self.lock:
            items=self.list()
            if any(item['name']==name for item in items):raise ValueError('That skill already exists. Delete it first or choose another name.')
            if len(items)>=50:raise ValueError('The skills library is full (50 skills).')
            item={'name':name,'instructions':instructions.strip(),'source':'user-provided'}
            self._write(items+[item]);return item
    def delete(self, name):
        with self.lock:self._write([item for item in self.list() if item['name']!=name])
        return {'ok':True}
    def get(self, name):
        item=next((item for item in self.list() if item['name']==name),None)
        if item is None:raise ValueError('Skill not found. Choose an existing skill.')
        return item
