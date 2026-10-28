import copy
import json
import re
import threading
import time
import uuid

from agent_history import public_record


class AgentImports:
    def __init__(self,runtime):self.runtime=runtime;self.pending={};self.lock=threading.RLock()

    def preview(self,filename,text):
        if not isinstance(filename,str) or not isinstance(text,str) or len(text.encode('utf-8'))>1_000_000:raise ValueError('Choose a skill Markdown or session JSON file under 1 MB.')
        if filename.lower().endswith('.md'):
            match=re.match(r'\A---\r?\n(.*?)\r?\n---\r?\n(.*)\Z',text,re.S)
            if not match:raise ValueError('Skill Markdown must have frontmatter containing a lowercase name.')
            name=re.search(r'^name:\s*[\"\']?([a-z0-9][a-z0-9-]{0,59})[\"\']?\s*$',match[1],re.M)
            if not name:raise ValueError('Skill frontmatter needs name: lowercase-hyphenated-name.')
            payload={'skills':[{'name':name[1],'instructions':match[2].strip()}]}
        elif filename.lower().endswith('.json'):
            try:payload=json.loads(text)
            except ValueError:raise ValueError('Choose a valid JSON export.') from None
        else:raise ValueError('Only .md procedures and .json exports are accepted; archives and executable plugins are not imported.')
        if not isinstance(payload,dict) or not set(payload)<= {'version','skills','runs'} or ('skills' in payload)==('runs' in payload):
            raise ValueError('Import one export type at a time: {"skills":[...]} or {"runs":[...]}. Settings, credentials and permissions are never imported.')
        if 'skills' in payload:
            source=payload['skills'];items=[]
            if not isinstance(source,list) or not 1<=len(source)<=20:raise ValueError('Import 1 to 20 skills at a time.')
            for skill in source:
                if not isinstance(skill,dict):raise ValueError('Each skill must contain a name and instructions.')
                name=skill.get('name');instructions=skill.get('instructions')
                if not isinstance(name,str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,59}',name):raise ValueError('Invalid imported skill name.')
                if not isinstance(instructions,str) or not 10<=len(instructions.strip())<=4000:raise ValueError('Imported procedures must be 10 to 4000 characters.')
                if set(skill)-{'name','instructions','source','description'}:raise ValueError('Skills cannot import executable files, secrets or approval settings.')
                items.append({'name':name,'instructions':instructions.strip(),'source':'user-imported'})
            if len({item['name'] for item in items})!=len(items):raise ValueError('The export contains duplicate skill names.')
            prepared={'kind':'skills','items':items}
        else:
            source=payload['runs'];items=[]
            if not isinstance(source,list) or not 1<=len(source)<=50:raise ValueError('Import 1 to 50 archived tasks at a time.')
            for run in source:
                if not isinstance(run,dict) or not isinstance(run.get('goal'),str) or not 1<=len(run['goal'])<=4000:raise ValueError('Each archived task needs a bounded goal.')
                steps=run.get('steps',[])
                if not isinstance(steps,list) or len(steps)>10:raise ValueError('An archived task can contain up to 10 steps.')
                record={'id':uuid.uuid4().hex,'goal':run['goal'],'summary':str(run.get('summary',''))[:5000],
                        'workspace':str(run.get('workspace',''))[:500],'created_at':time.time(),'status':'imported','steps':[],
                        'imported':True,'source_created_at':str(run.get('created_at',''))[:100]}
                for step in steps:
                    if not isinstance(step,dict) or not isinstance(step.get('tool'),str):raise ValueError('Invalid archived step.')
                    record['steps'].append(public_record({key:step.get(key) for key in ('tool','arguments','reason','result')})|{'status':'imported'})
                items.append(record)
            prepared={'kind':'history','items':items}
        with self.lock:
            self.pending={key:value for key,value in self.pending.items() if value['expires']>time.time()}
            if len(self.pending)>=10:raise ValueError('Finish a pending import before previewing another.')
            identifier=uuid.uuid4().hex
            self.pending[identifier]={'prepared':copy.deepcopy(prepared),'expires':time.time()+600}
        return {'id':identifier,**prepared,'warning':'Imported text is untrusted guidance or historical data, not verified results. No code, credentials, approvals or live tasks are restored.'}

    def confirm(self,identifier,approved):
        if approved is not True:raise ValueError('Review and approve the exact import preview first.')
        with self.lock:
            entry=self.pending.get(identifier)
            if not entry or entry['expires']<time.time():raise ValueError('Import preview expired. Choose the file again.')
            prepared=entry['prepared']
            if prepared['kind']=='skills':
                skills=self.runtime.skills
                with skills.lock:
                    existing=skills.list()
                    if len(existing)+len(prepared['items'])>50:raise ValueError('The skills library would exceed 50 procedures.')
                    if {item['name'] for item in existing}&{item['name'] for item in prepared['items']}:raise ValueError('A skill with this name already exists. Existing procedures are never overwritten.')
                    skills._write(existing+prepared['items'])
            else:
                with self.runtime.lock:self.runtime.history.save(prepared['items'])
            self.pending.pop(identifier)
        return {'ok':True,'imported':len(prepared['items']),'kind':prepared['kind']}
