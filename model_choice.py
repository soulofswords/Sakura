"""Opt-in routing from explicit synthetic benchmark measurements, never guesses."""
import json
import time
from pathlib import Path
from atomic_state import atomic_text,state_lock

CASES={
 'chat': [('Reply with exactly: READY','READY')],
 'reasoning':[('What is 17 * 19? Reply with only the integer.','323'),('A box has 4 red and 6 blue balls. How many balls total? Reply with only the integer.','10')],
 'coding':[('Return only a JSON object with keys "tool" and "arguments". The tool is files.list and arguments is an empty object.',None)]}


class ModelChoice:
    def __init__(self,path):self.path=Path(path)
    def state(self):
        try:data=json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError,ValueError):data={}
        if not isinstance(data,dict):data={}
        profiles=data.get('profiles',[])
        if not isinstance(profiles,list):profiles=[]
        required={'provider','category','quality','seconds','cloud','identity','measured_at'}
        import math
        profiles=[p for p in profiles if isinstance(p,dict) and required<=p.keys() and isinstance(p['provider'],str) and isinstance(p['category'],str) and isinstance(p['identity'],dict) and type(p['cloud']) is bool and all(type(p[k]) in (int,float) and math.isfinite(p[k]) and p[k]>=0 for k in ('quality','seconds','measured_at'))]
        return {'enabled':data.get('enabled') is True,'allow_cloud':data.get('allow_cloud') is True,'profiles':profiles[-50:]}
    def configure(self,enabled,allow_cloud):
        if type(enabled) is not bool or type(allow_cloud) is not bool:raise ValueError('Use routing switches.')
        with state_lock(self.path):
            data=self.state();data.update(enabled=enabled,allow_cloud=allow_cloud);atomic_text(self.path,json.dumps(data))
        return data
    def measure(self,provider,model,cloud=False):
        from agent_runtime import _planner_selection
        if provider=='auto':raise ValueError('Benchmark a specific provider.')
        profiles=[]
        for category,cases in CASES.items():
            correct=0;elapsed=0
            for prompt,expected in cases:
                start=time.monotonic();reply=model._request_raw([{'role':'user','content':prompt}]);elapsed+=time.monotonic()-start
                if expected is None:
                    try:
                        obj=json.loads(reply);passed=obj=={'tool':'files.list','arguments':{}}
                    except (TypeError,ValueError):passed=False
                else:passed=str(reply).strip()==expected
                correct+=int(passed)
            profiles.append({'provider':provider,'category':category,'quality':correct/len(cases),'seconds':elapsed/len(cases),'cloud':bool(cloud),'identity':_planner_selection(model),'measured_at':time.time(),'scope':'Small synthetic checks; not a general intelligence score'})
        with state_lock(self.path):
            data=self.state();data['profiles']=[x for x in data['profiles'] if x['provider']!=provider]+profiles;atomic_text(self.path,json.dumps(data))
        return profiles
    def select(self,category,models):
        from agent_runtime import _planner_selection
        data=self.state()
        if not data['enabled']:raise ValueError('Enable measured model routing and benchmark configured models first.')
        candidates=[p for p in data['profiles'] if p['category']==category and p['quality']>=.99 and p['provider'] in models and (data['allow_cloud'] or not p['cloud']) and time.time()-p['measured_at']<30*86400 and p['identity']==_planner_selection(models[p['provider']])]
        if not candidates:raise ValueError('No current model passed this category. Benchmark a model or select one manually.')
        winner=min(candidates,key=lambda p:p['seconds'])
        return winner['provider'],models[winner['provider']]
