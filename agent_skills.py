"""User-authored reusable procedures. Procedures never grant execution approval."""
import json
import re
import threading
from pathlib import Path
from atomic_state import state_lock,atomic_text

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
        atomic_text(self.path,json.dumps(items,ensure_ascii=False))
    def save(self, name, instructions):
        if not isinstance(name,str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,59}',name):
            raise ValueError('Use a skill name of up to 60 lowercase letters, numbers or hyphens.')
        if not isinstance(instructions,str) or not 10<=len(instructions.strip())<=4000:
            raise ValueError('Write a procedure of 10 to 4000 characters.')
        with self.lock,state_lock(self.path):
            items=self.list()
            if any(item['name']==name for item in items):raise ValueError('That skill already exists. Delete it first or choose another name.')
            if len(items)>=50:raise ValueError('The skills library is full (50 skills).')
            item={'name':name,'instructions':instructions.strip(),'source':'user-provided'}
            self._write(items+[item]);return item
    def delete(self, name):
        with self.lock,state_lock(self.path):self._write([item for item in self.list() if item['name']!=name])
        return {'ok':True}
    def get(self, name):
        item=next((item for item in self.list() if item['name']==name),None)
        if item is None:raise ValueError('Skill not found. Choose an existing skill.')
        return item

    def import_markdown(self,text,source='uploaded SKILL.md'):
        from skill_markdown import parse_skill
        item=parse_skill(text,source)
        with self.lock,state_lock(self.path):
            items=self.list()
            if len(items)>=50 or any(x['name']==item['name'] for x in items):raise ValueError('Skill already exists or the library is full.')
            candidates=items+[item];self._resolve(item['name'],candidates,None)
            self._write(candidates)
        return item

    def _resolve(self,name,items,tools,visiting=None):
        visiting=set() if visiting is None else visiting
        if name in visiting:raise ValueError('Skill dependency cycle detected.')
        visiting.add(name)
        item=next((x for x in items if x['name']==name),None)
        if item is None:raise ValueError('Missing required skill: '+str(name))
        if tools is not None:
            missing=set(item.get('required_tools',[]))-set(tools)
            if missing:raise ValueError('Skill requires unavailable tools: '+', '.join(sorted(missing)))
        dependencies=[self._resolve(dep,items,tools,set(visiting)) for dep in item.get('dependencies',[])]
        return {**item,'dependency_guidance':dependencies}

    def resolve(self,name,tools):return self._resolve(name,self.list(),tools)
