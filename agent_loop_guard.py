"""Pure planner loop diagnostics; manual approvals and recovery remain available."""
import hashlib
import json


def fingerprint(tool,arguments):
    return hashlib.sha256(json.dumps([tool,arguments],sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def same_call(step,tool,arguments):
    """Whether a recorded step is the same call the planner is about to propose again.

    Preparation rewrites stored arguments (a clone gains its folder, a command gains its
    frozen cwd), so comparing whole dictionaries would hide every repeat of those tools.
    The planner's own fields still have to agree exactly.
    """
    if step.get('tool')!=tool:return False
    stored=step.get('arguments')
    if not isinstance(stored,dict) or not isinstance(arguments,dict):return stored==arguments
    return all(key in stored and stored[key]==value for key,value in arguments.items())


def inspect(steps,tool,args):
    calls=[s for s in steps if s.get('status') in ('completed','failed')]
    signatures=[fingerprint(s.get('tool'),s.get('arguments')) for s in calls]
    proposed=fingerprint(tool,args);history=signatures+[proposed]
    repeats=sum(1 for step in calls if same_call(step,tool,args))
    # Failures count: rerunning a failing command can still waste resources.
    cycling=len(history)>=6 and history[-6::2]==[history[-2]]*3 and history[-5::2]==[history[-1]]*3
    polling=tool in {'browser.snapshot','calendar.events.list','integrations.status','library.status'}
    polls=sum(s.get('tool')==tool for s in calls[-20:])
    blocked=(not polling and repeats>=3) or cycling or (polling and polls>=10)
    warning=repeats>=2 or (polling and polls>=7)
    return {'blocked':blocked,'warning':warning or blocked,
            'reason':'Repeated identical tool calls, alternating calls or excessive polling detected. Use existing results, change the approach, or ask the user for missing information.' if warning or blocked else ''}
