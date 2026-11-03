"""Read-only task status for the room's virtual monitor; no arguments or logs."""
import time
from agent_history import redact_text

ACTIVE={'planning','running','awaiting_approval','pausing','cancelling'}

def snapshot(runtime):
    with runtime.lock:
        runs=list(runtime.runs.values())
        active=[run for run in runs if run.get('status') in ACTIVE]
        latest=max(active or runs,key=lambda run:run.get('updated_at',0),default=None)
        if not latest or not active and time.time()-latest.get('updated_at',0)>120:
            return {'state':'idle','title':'No active task','step':'Ready when you are','completed_steps':0}
        steps=latest.get('steps') or []
        step=steps[-1] if steps else {}
        clean=lambda value,limit:redact_text(str(value or ''))[:limit]
        return {'state':clean(latest.get('status'),40),'title':clean(latest.get('goal'),140),
                'step':clean(step.get('tool') or 'Planning next action',80),
                'step_state':clean(step.get('status'),40),
                'completed_steps':sum(item.get('status')=='completed' for item in steps)}
