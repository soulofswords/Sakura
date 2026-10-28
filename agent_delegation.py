import copy
from concurrent.futures import ThreadPoolExecutor


TOOLS=[{'name':'agents.delegate','description':'Run 2 to 4 independent child tasks concurrently with separate histories and the selected AI. Requires approval. Children can auto-read workspace files; all other actions pause for individual review. No nested delegation.',
        'inputSchema':{'type':'object','properties':{'goals':{'type':'array','minItems':2,'maxItems':4,'items':{'type':'string','minLength':3,'maxLength':2000}}},'required':['goals'],'additionalProperties':False}}]
# Kept inside agent_runtime.AUTO_RUN_TOOLS: a child may never auto-approve a step that a
# parent task could not already run unattended.
READ_TOOLS={'files.list','files.read'}


def execute(runtime,parent,goals,model):
    children=[]

    def closed(identifier):
        """Re-checked before every model call, so a cancelled parent stops queued children."""
        with runtime.lock:
            return parent['status']=='cancelled' or runtime.runs.get(identifier,{}).get('status') in ('cancelled',None)

    def work(identifier):
        try:
            selected=copy.copy(model)
            for _ in range(6):
                if closed(identifier):
                    with runtime.lock:
                        if identifier in runtime.runs:runtime.cancel(identifier)
                    break
                state=runtime._plan_once(identifier,selected)
                if state['status']!='awaiting_approval':break
                step=state['steps'][-1]
                if not state.get('auto_continue') or step['tool'] not in READ_TOOLS:break
                runtime._decide(step['id'],True,auto=True)
                if closed(identifier) or runtime.state(identifier)['status']!='ready':break
        except Exception as error:
            with runtime.lock:
                child=runtime.runs.get(identifier)
                if child and child['status']!='cancelled':
                    child.update(status='failed',summary=str(error)[:500] if isinstance(error,ValueError) else 'Child planning failed. Review this task before retrying.')
                    runtime._save_runs()
        with runtime.lock:
            child=runtime.runs.get(identifier)
            if not child:return {'id':identifier,'goal':'','status':'cancelled','summary':'Task record was removed.'}
            return {key:child.get(key) for key in ('id','goal','status','summary')}

    # Every child id is pinned here, so creating them and running them must share one
    # finally: a refused new_run would otherwise leave the earlier ids pinned forever and
    # silently drain the task slots.
    try:
        with runtime.lock:
            available=30-sum(1 for r in runtime.runs.values() if r['id'] in runtime.active_runs or r['status'] in ('running','awaiting_approval'))
            if available<len(goals):raise ValueError('Finish or cancel open tasks before starting this delegation.')
            for goal in goals:
                child=runtime.new_run(goal,parent['workspace'],parent.get('auto_continue',True))
                stored=runtime.runs[child['id']];stored.update(parent_id=parent['id'],delegated=True)
                runtime.active_runs.add(child['id']);children.append(child['id'])
            runtime._save_runs()
        with ThreadPoolExecutor(max_workers=len(children),thread_name_prefix='SakuraChild') as pool:
            results=list(pool.map(work,children))
        return {'ok':True,'children':results,'note':'Each child has its own task record. Pending actions still require individual approval; a returned child is not necessarily completed.'}
    finally:
        with runtime.lock:runtime.active_runs.difference_update(children)
