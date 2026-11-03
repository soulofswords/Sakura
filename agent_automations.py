"""Local recurring replays of exact, previously approved Agent workflows."""
import copy
import json
from pathlib import Path
import threading
import time
import uuid

from agent_runtime import digest
from wallclock_schedule import validate as validate_schedule, next_due

# These tools cannot write files or mutate connected services. Other actions
# always become a normal pending approval, even when saved in a workflow.
READ_TOOLS={'files.list','files.read','web.search','calendar.events.list','linkedin.profile',
            'google.drive.list','google.drive.read','google.docs.read','google.sheets.read','library.status'}


def workspace_identity(value):
    original=Path(value).expanduser();resolved=original.resolve(strict=True)
    if not resolved.is_dir() or str(original.absolute()).casefold()!=str(resolved).casefold():raise ValueError('The approved workspace path changed. Review and recreate this automation.')
    info=resolved.stat()
    return {'path':str(resolved),'device':info.st_dev,'inode':info.st_ino}


class AgentAutomations:
    def __init__(self,runtime,enabled=lambda:True,planner_getter=None):
        self.runtime=runtime;self.enabled=enabled;self.planner_getter=planner_getter
        self.path=runtime.store_path.with_name('agent-automations.json')
        self.lock=threading.RLock();self.running=set();self.stop_event=threading.Event();self.thread=None
        try:self.items=json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError,ValueError):self.items={}
        if not isinstance(self.items,dict):self.items={}
        self.items={key:item for key,item in self.items.items() if isinstance(key,str) and isinstance(item,dict)
                    and item.get('mode','steps') in ('steps','goal')
                    and (item.get('mode','steps')=='goal' or (isinstance(item.get('template'),list) and 1<=len(item['template'])<=10
                        and all(isinstance(step,dict) and isinstance(step.get('tool'),str) and isinstance(step.get('arguments'),dict)
                                and isinstance(step.get('bindings'),dict) and isinstance(step.get('schema_hash'),str) for step in item['template'])))
                    and isinstance(item.get('minutes'),int) and 5<=item['minutes']<=43200
                    and isinstance(item.get('next_run'),(int,float)) and isinstance(item.get('workspace'),str)
                    and isinstance(item.get('goal'),str) and isinstance(item.get('name'),str)
                    and self._valid_event(item.get('event'))}
        for key in list(self.items):
            try:
                self.items[key]['schedule']=validate_schedule(self.items[key].get('schedule'))
                if self.items[key].get('schedule') and self.items[key].get('event'):raise ValueError('Conflicting triggers')
            except ValueError:self.items.pop(key)
        for item in self.items.values():
            if item.get('status')=='running':item.update(status='interrupted',paused=True)
            try:
                if item.get('workspace_identity')!=workspace_identity(item['workspace']):raise ValueError()
            except (OSError,ValueError):item.update(status='needs_approval',paused=True,last_error='Workspace identity is missing or changed. Review the folder and recreate this automation.')

    @staticmethod
    def _valid_event(event):
        if event is None:return True
        if not isinstance(event,dict) or set(event)!={'path','min_seconds'}:return False
        path,debounce=event['path'],event['min_seconds']
        if not isinstance(path,str) or not 1<=len(path)<=200 or ':' in path or Path(path).is_absolute() or '..' in Path(path).parts:return False
        return type(debounce) is int and 60<=debounce<=86400

    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True);temporary=self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.items,ensure_ascii=False),encoding='utf-8');temporary.replace(self.path)

    def list(self):
        with self.lock:return [copy.deepcopy({k:v for k,v in x.items() if k!='template'})|{'steps':len(x.get('template',[]))} for x in self.items.values()]

    def create(self,run_id,name,minutes,approved=False,mode='steps',planner='current',event=None,schedule=None):
        if approved is not True:raise ValueError('Approve this exact recurring workflow first.')
        if not isinstance(name,str) or not 1<=len(name.strip())<=100:raise ValueError('Enter a workflow name of up to 100 characters.')
        if type(minutes) is not int or not 5<=minutes<=43200:raise ValueError('Choose an interval between 5 minutes and 30 days.')
        if mode not in ('steps','goal'):raise ValueError('Choose the approved-steps or replan-the-goal automation type.')
        if mode=='goal' and not isinstance(planner,str):raise ValueError('Choose the AI that replans each cycle.')
        if event is not None and not self._valid_event(event):raise ValueError('Watch path must stay inside the workspace and the debounce must be between 60 seconds and 24 hours.')
        schedule=validate_schedule(schedule)
        if schedule and event:raise ValueError('Choose a wall-clock schedule or an event trigger, not both.')
        run=self.runtime.state(run_id)
        if mode=='goal':
            item={'id':uuid.uuid4().hex,'name':name.strip(),'goal':run['goal'],'workspace':run['workspace'],'workspace_identity':workspace_identity(run['workspace']),
                  'mode':'goal','planner':planner,'minutes':minutes,'event':copy.deepcopy(event),'schedule':schedule,
                  'next_run':next_due({'schedule':schedule,'minutes':minutes},time.time()),'paused':False,'status':'scheduled','last_run_id':None,'last_error':'','created_at':time.time()}
            with self.lock:
                if len(self.items)>=30:raise ValueError('Remove an old automation before adding another (limit 30).')
                self.items[item['id']]=item;self.save()
            return next(x for x in self.list() if x['id']==item['id'])
        if not run['steps'] or len(run['steps'])>10 or any(s['status']!='completed' for s in run['steps']):raise ValueError('Only a workflow whose steps all completed can be scheduled.')
        with self.runtime.lock:
            # Stored run history deliberately drops approval bindings. Recover
            # fresh schemas/connections here, while the human reviews the task.
            template=[]
            for step in run['steps']:
                original=next(s for s in self.runtime.runs[run_id]['steps'] if s['id']==step['id'])
                action=copy.deepcopy(original)
                if not action.get('schema_hash'):
                    action=self.runtime._prepare(self.runtime.runs[run_id],step['tool'],step['arguments'])
                template.append({'tool':action['tool'],'arguments':action['arguments'],'schema_hash':action['schema_hash'],
                                 'bindings':{k:v for k,v in action['bindings'].items() if k!='connection'}})
        item={'id':uuid.uuid4().hex,'name':name.strip(),'goal':run['goal'],'workspace':run['workspace'],'workspace_identity':workspace_identity(run['workspace']),
              'mode':'steps','minutes':minutes,'event':copy.deepcopy(event),'schedule':schedule,'next_run':next_due({'schedule':schedule,'minutes':minutes},time.time()),'paused':False,'status':'scheduled','template':template,
              'last_run_id':None,'last_error':'','created_at':time.time()}
        with self.lock:
            if len(self.items)>=30:raise ValueError('Remove an old automation before adding another (limit 30).')
            self.items[item['id']]=item;self.save()
        return next(x for x in self.list() if x['id']==item['id'])

    def update(self,identifier,paused):
        if type(paused) is not bool:raise ValueError('Choose Pause or Resume.')
        with self.lock:
            item=self.items.get(identifier)
            if not item:raise ValueError('Automation not found.')
            if identifier in self.running:raise ValueError('Wait for the current run to finish before changing it.')
            item.update(paused=paused,next_run=next_due(item,time.time()),status='paused' if paused else 'scheduled');self.save()
        return {'ok':True}

    def remove(self,identifier):
        with self.lock:
            if identifier in self.running:raise ValueError('Wait for this run to finish before removing it.')
            self.items.pop(identifier,None);self.save()
        return {'ok':True}

    def execute(self,identifier):
        with self.lock:item=self.items.get(identifier)
        if item and item.get('mode')=='goal':return self._execute_goal(identifier)
        if not self.enabled():raise ValueError('Scheduled tasks are paused while Agent AI mode is unavailable.')
        if self.runtime.operation_lock.locked():
            with self.lock:
                item=self.items.get(identifier)
                if item and not item['paused']:item['next_run']=time.time()+30;self.save()
            return {'skipped':True,'reason':'Another Agent action is running; retrying later.'}
        with self.lock:
            item=self.items.get(identifier)
            if not item or item['paused']:raise ValueError('Resume this automation before running it.')
            if identifier in self.running:return {'skipped':True}
            self.running.add(identifier);item.update(status='running',next_run=next_due(item,time.time()));self.save();template=copy.deepcopy(item)
        try:
            if template.get('workspace_identity')!=workspace_identity(template['workspace']):raise ValueError('The approved workspace changed. Review the folder and recreate this automation.')
            run=self.runtime.new_run(template['goal'],template['workspace'],False)
            with self.runtime.lock:
                self.runtime.runs[run['id']]['automation_id']=identifier;self.runtime._save_runs()
            with self.lock:item['last_run_id']=run['id'];self.save()
            for step in template['template']:
                if step['tool']=='files.write' and Path(step['arguments']['path']).exists():
                    with self.lock:item.update(status='needs_approval',paused=True,last_error='The output file already exists. Open the task and choose a new output filename; nothing was overwritten.');self.save()
                    return {'run':run,'needs_approval':True}
                run=self.runtime.propose(run['id'],step['tool'],step['arguments'],'Recurring workflow: '+template['name'])
                newest=run['steps'][-1]
                with self.runtime.lock:action=copy.deepcopy(self.runtime.actions[newest['id']])
                bindings={k:v for k,v in action['bindings'].items() if k!='connection'}
                # Reads intentionally observe current file content; script/MCP/
                # account bindings must still match the original approval.
                old=copy.deepcopy(step['bindings']);now=copy.deepcopy(bindings)
                if step['tool']=='files.read':old.pop('file_hash',None);now.pop('file_hash',None)
                changed=digest(old)!=digest(now) or action['schema_hash']!=step['schema_hash']
                if changed or step['tool'] not in READ_TOOLS:
                    with self.lock:item.update(status='needs_approval',paused=True,last_error='Review the pending action in Task progress.');self.save()
                    self.runtime.trace.record('automation',run['id'],name=template['name'],mode='steps',outcome='needs_approval',tool=step['tool'])
                    return {'run':run,'needs_approval':True}
                result=self.runtime.decide(newest['id'],True)
                if result['action']['status']!='completed':raise ValueError('A scheduled step failed. Open Task progress for its actual result.')
                with self.runtime.lock:
                    self.runtime.runs[run['id']]['steps'][-1]['auto']=True;self.runtime._save_runs()
            with self.runtime.lock:
                stored=self.runtime.runs[run['id']];stored.update(status='completed',summary='Completed the exact approved recurring workflow.');self.runtime._save_runs()
            with self.lock:item.update(status='completed',last_error='');self.save()
            return {'run':self.runtime.state(run['id'])}
        except Exception as error:
            with self.lock:item.update(status='failed',paused=True,last_error=str(error)[:500] if isinstance(error,(ValueError,FileNotFoundError)) else 'Workflow failed; review its task record.');self.save()
            raise
        finally:
            with self.lock:self.running.discard(identifier)

    def _execute_goal(self,identifier):
        """Replan the approved goal each cycle; only read-only steps can run unattended."""
        if not self.enabled():raise ValueError('Scheduled tasks are paused while Agent AI mode is unavailable.')
        with self.lock:
            item=self.items.get(identifier)
            if not item or item['paused']:raise ValueError('Resume this automation before running it.')
            if identifier in self.running:return {'skipped':True}
            previous=item.get('last_run_id')
            if previous and self.runtime.runs.get(previous,{}).get('status') not in (None,'completed','cancelled','blocked'):
                item['next_run']=next_due(item,time.time());self.save()
                return {'skipped':True,'reason':'The previous run still waits for review or has failed; open its task.'}
            self.running.add(identifier)
            item.update(status='running',next_run=next_due(item,time.time()));self.save();snapshot=copy.deepcopy(item)
        try:
            if snapshot.get('workspace_identity')!=workspace_identity(snapshot['workspace']):raise ValueError('The approved workspace changed. Review the folder and recreate this automation.')
            if self.planner_getter is None:raise ValueError('No planner source is connected for goal automations.')
            run=self.runtime.new_run(snapshot['goal'],snapshot['workspace'],True)
            with self.runtime.lock:
                self.runtime.runs[run['id']]['automation_id']=identifier;self.runtime._save_runs()
            with self.lock:item['last_run_id']=run['id'];self.save()
            model=self.planner_getter(snapshot.get('planner','current'))
            if model is None:raise ValueError('No planning AI is available for this goal automation.')
            state=self.runtime.plan(run['id'],model)
            outcome='needs_approval' if state['status']=='awaiting_approval' else state['status']
            with self.lock:item.update(status=outcome,last_error='');self.save()
            self.runtime.trace.record('automation',run['id'],name=snapshot['name'],mode='goal',outcome=outcome)
            return {'run':state}
        except Exception as error:
            self.runtime.trace.record('automation',identifier,name=snapshot['name'],mode='goal',outcome='failed')
            with self.lock:item.update(status='failed',paused=True,last_error=str(error)[:500] if isinstance(error,(ValueError,FileNotFoundError)) else 'Goal replanning failed; review its task record.');self.save()
            raise
        finally:
            with self.lock:self.running.discard(identifier)

    def check_events(self,now=None):
        """Fire approved workflows whose watched workspace path changed, honoring the debounce."""
        now=time.time() if now is None else now
        fired=[]
        with self.lock:
            candidates=[x for x in self.items.values() if x.get('event') and not x['paused'] and x['id'] not in self.running]
        for item in candidates:
            try:mtime=(Path(item['workspace'])/item['event']['path']).stat().st_mtime
            except OSError:continue
            with self.lock:
                seen=item.get('watch_marker')
                if seen is None:
                    item['watch_marker']=mtime;self.save();due=False
                elif mtime>seen and now-item.get('last_fire',0)>=item['event']['min_seconds']:
                    item.update(watch_marker=mtime,last_fire=now);self.save();due=True
                else:due=False
            if due:fired.append(item['id'])
        for identifier in fired:
            try:self.execute(identifier)
            except Exception:pass  # The error is saved on the item and visible in the panel.
        return fired

    def start(self):
        if self.thread and self.thread.is_alive():return
        self.stop_event.clear()
        def loop():
            while not self.stop_event.wait(5):
                if not self.enabled():continue
                try:self.check_events()
                except Exception:pass
                with self.lock:due=[x['id'] for x in self.items.values() if not x['paused'] and not x.get('event') and x['next_run']<=time.time() and x['id'] not in self.running]
                for identifier in due:
                    if self.stop_event.is_set():break
                    try:self.execute(identifier)
                    except Exception:pass  # The error is saved and visible in the panel.
        self.thread=threading.Thread(target=loop,daemon=True,name='SakuraAutomations');self.thread.start()

    def stop(self):self.stop_event.set()
