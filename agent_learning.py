"""Bounded local Agent memory; verified procedures are guidance, never approval."""
import copy,hashlib,json,re,threading,time
from pathlib import Path
from atomic_state import state_lock,atomic_text
CATEGORIES={'document':r'\b(document|report|summari[sz]e|draft|cv|resume)\b','calendar':r'\b(calendar|meeting|schedule|appointment)\b','research':r'\b(search|research|lookup|compare)\b','files':r'\b(file|folder|directory)\b'}
def category(goal):return next((name for name,pattern in CATEGORIES.items() if re.search(pattern,str(goal),re.I)),'general')
class AgentLearning:
    def __init__(self,path):self.path=Path(path);self.lock=threading.RLock()
    def _read(self):
        try:
            value=json.loads(self.path.read_text(encoding='utf-8'))
            if isinstance(value,dict) and value.get('version')==1:return value
        except (OSError,ValueError):pass
        return {'version':1,'enabled':True,'notes':'','profile':'','procedures':[],'seen':[]}
    def _save(self,data):
        atomic_text(self.path,json.dumps(data,ensure_ascii=False))
    def status(self):
        with self.lock,state_lock(self.path):
            d=self._read();return {k:copy.deepcopy(d.get(k)) for k in ('enabled','notes','profile','procedures')}
    def configure(self,enabled,notes,profile):
        if type(enabled) is not bool or not isinstance(notes,str) or not isinstance(profile,str):raise ValueError('Invalid memory settings.')
        if len(notes)>2200 or len(profile)>1375:raise ValueError('Memory notes allow 2200 characters; user preferences allow 1375.')
        if re.search(r'(?i)(?:sk-[a-z0-9]{16,}|Bearer\s+\S+|(?:api[_ -]?key|password|access[_ -]?token)\s*[:=]\s*\S+)',notes+' '+profile):raise ValueError('Keep credentials in protected account settings, not memory.')
        with self.lock,state_lock(self.path):
            d=self._read();d.update(enabled=enabled,notes=notes,profile=profile);self._save(d)
        return self.status()
    def learn(self,run):
        steps=run.get('steps',[])
        if run.get('status')!='completed' or not 2<=len(steps)<=40:return False
        if any(s.get('status')!='completed' or (s.get('result') or {}).get('ok') is False or (s.get('result') or {}).get('is_error') for s in steps):return False
        # Do not persist arguments, document bodies, shell text, URLs, names or credentials.
        tools=[s.get('tool','') for s in steps]
        if any(not re.fullmatch(r'[a-z][a-z0-9_.:-]{0,120}',t) for t in tools):return False
        label=category(run.get('goal'));fingerprint=hashlib.sha256(json.dumps([label,tools]).encode()).hexdigest()[:24]
        source=hashlib.sha256(str(run.get('id','')).encode()).hexdigest()[:24]
        with self.lock,state_lock(self.path):
            d=self._read()
            if not d.get('enabled') or source in d.get('seen',[]):return False
            rows=d.get('procedures',[]);entry=next((x for x in rows if x['id']==fingerprint),None)
            if entry:entry['successes']+=1;entry['updated_at']=time.time()
            else:
                if len(rows)>=200:return False
                rows.append({'id':fingerprint,'category':label,'tools':tools,'successes':1,'updated_at':time.time(),'source':'verified-completed-actions','source_run':source})
            d.update(procedures=rows,seen=(d.get('seen',[])+[source])[-500:]);self._save(d)
        return True
    def context(self,goal):
        d=self.status()
        if not d['enabled']:return {}
        matches=[x for x in d['procedures'] if x['category']==category(goal)]
        matches=sorted(matches,key=lambda x:(x['successes'],x['updated_at']),reverse=True)[:3]
        return {'user_preferences':d['profile'],'user_notes':d['notes'],'successful_tool_sequences':[{'category':x['category'],'tools':x['tools'],'successful_runs':x['successes']} for x in matches]}
    def delete(self,identifier):
        with self.lock,state_lock(self.path):
            d=self._read();d['procedures']=[x for x in d.get('procedures',[]) if x['id']!=identifier];self._save(d)
        return self.status()
    def clear(self):
        with self.lock,state_lock(self.path):
            d=self._read();d.update(notes='',profile='',procedures=[],seen=[]);self._save(d)
        return self.status()
    def skill(self,identifier):
        row=next((x for x in self.status()['procedures'] if x['id']==identifier),None)
        if not row:raise ValueError('Learned procedure not found.')
        return 'For a similar '+row['category']+' task, consider this previously successful tool sequence: '+', then '.join(row['tools'])+'. Read current inputs again, adapt arguments to the new request, verify actual results, and obtain fresh approval for every protected action. Never reuse old file contents or treat this procedure as permission.'
