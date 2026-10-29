"""Inference accounting without prompts, keys, response bodies or invented prices."""
import contextvars
import copy
import math
import threading
import time
from contextlib import contextmanager

_capture=contextvars.ContextVar('sakura_usage',default=None)


def estimate_tokens(messages):
    """Cache-independent estimate, not a tokenizer or a billable token count."""
    return sum(math.ceil(len(str(m.get('content','')).encode('utf-8'))/4)+8
               +1536*len(m.get('images',[])) for m in messages)


def _number(value):
    return value if type(value) is int and 0<=value<=1_000_000_000 else None


def record_usage(provider,model,messages,data):
    sink=_capture.get()
    if sink is None:return
    data=data if isinstance(data,dict) else {}
    usage=data.get('usageMetadata') if provider=='gemini' else data.get('usage',{})
    usage=usage if isinstance(usage,dict) else {}
    if provider=='gemini':
        incoming=usage.get('promptTokenCount');outgoing=usage.get('candidatesTokenCount')
        reasoning=usage.get('thoughtsTokenCount');cached=usage.get('cachedContentTokenCount')
        if _number(outgoing) is not None and _number(reasoning) is not None:outgoing+=reasoning
    elif provider=='ollama':
        incoming=data.get('prompt_eval_count');outgoing=data.get('eval_count');reasoning=cached=None
    else:
        incoming=usage.get('prompt_tokens',usage.get('input_tokens'))
        outgoing=usage.get('completion_tokens',usage.get('output_tokens'))
        details=usage.get('completion_tokens_details') or {}
        reasoning=details.get('reasoning_tokens') if isinstance(details,dict) else None
        details=usage.get('prompt_tokens_details') or {}
        cached=details.get('cached_tokens',usage.get('cache_read_input_tokens')) if isinstance(details,dict) else None
    sink.append({'provider':str(provider)[:40],'model':str(model)[:150],
                 'input_tokens':_number(incoming),'output_tokens':_number(outgoing),
                 'reasoning_tokens':_number(reasoning),'cached_tokens':_number(cached),
                 'prompt_estimated_tokens':estimate_tokens(messages)})


class DeviceEnergy:
    """Optional NVML device energy during a window, never task-attributed energy."""
    def __init__(self):self.samples=[];self.stop=threading.Event();self.thread=None;self.api=None;self.handles=[]
    def __enter__(self):
        try:
            import pynvml
            pynvml.nvmlInit()
            self.api=pynvml
            handles=[pynvml.nvmlDeviceGetHandleByIndex(i) for i in range(pynvml.nvmlDeviceGetCount())];self.handles=handles
            if not handles:return self
            def sample():
                while not self.stop.is_set():
                    try:self.samples.append((time.monotonic(),sum(pynvml.nvmlDeviceGetPowerUsage(h)/1000 for h in handles)))
                    except Exception:break
                    self.stop.wait(.5)
            self.thread=threading.Thread(target=sample,daemon=True);self.thread.start()
        except Exception:pass
        return self
    def __exit__(self,*_):
        self.stop.set()
        if self.thread:self.thread.join(timeout=1)
        if self.api:
            try:
                if self.handles:self.samples.append((time.monotonic(),sum(self.api.nvmlDeviceGetPowerUsage(h)/1000 for h in self.handles)))
                self.api.nvmlShutdown()
            except Exception:pass
    def result(self):
        if len(self.samples)<2:return {'gpu_device_joules':None,'energy_basis':'unavailable'}
        joules=sum((b[0]-a[0])*(b[1]+a[1])/2 for a,b in zip(self.samples,self.samples[1:]))
        return {'gpu_device_joules':round(joules,3),'energy_basis':'NVIDIA device power during window; includes other GPU workloads; excludes CPU and cloud energy'}


@contextmanager
def capture_usage():
    records=[];token=_capture.set(records)
    try:yield records
    finally:_capture.reset(token)


def active_usage():return list(_capture.get() or [])


def summarize(records,prices=None):
    prices=prices or {};known_cost=0.;priced=0
    for record in records:
        rate=prices.get(record['provider']+'/'+record['model'])
        if isinstance(rate,dict) and all(record.get(k) is not None for k in ('input_tokens','output_tokens')):
            try:
                values=[float(rate[k]) for k in ('input','output')]
                if all(math.isfinite(v) and 0<=v<=10000 for v in values):
                    known_cost+=(record['input_tokens']*values[0]+record['output_tokens']*values[1])/1_000_000;priced+=1
            except (KeyError,ValueError,TypeError):pass
    result={'calls':len(records),'input_tokens':sum(r.get('input_tokens') or 0 for r in records),
            'output_tokens':sum(r.get('output_tokens') or 0 for r in records),
            'prompt_estimated_tokens':sum(r.get('prompt_estimated_tokens') or 0 for r in records),
            'usage_reported_calls':sum(r.get('input_tokens') is not None and r.get('output_tokens') is not None for r in records),
            'budget_tokens':sum(max(r.get('input_tokens') or 0,r.get('prompt_estimated_tokens') or 0)+(r.get('output_tokens') or 0) for r in records),
            'cost_usd_estimate':round(known_cost,8) if records and priced==len(records) else None,
            'cost_basis':'user-configured USD per million tokens; excludes cache discounts, provider tiers and taxes',
            'priced_calls':priced}
    return result


def merge(previous,current):
    result=copy.deepcopy(previous or {})
    for key in ('calls','input_tokens','output_tokens','prompt_estimated_tokens','usage_reported_calls','priced_calls','budget_tokens','seconds'):
        result[key]=round(result.get(key,0)+current.get(key,0),4)
    for key in ('gpu_device_joules','cost_usd_estimate'):
        a=result.get(key);b=current.get(key)
        result[key]=None if (previous and a is None) or b is None else round((a or 0)+b,8)
    result['energy_basis']=current.get('energy_basis','unavailable')
    result['cost_basis']=current.get('cost_basis','unavailable')
    return result
