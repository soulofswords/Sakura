"""Teacher chat bridge to real Agent tasks; plans stop at existing approvals."""
import re
import copy
import threading
import time
from pathlib import Path
from agent_runtime import runtime,digest
from native_consent import confirm as native_confirm


class TeacherAgentChat:
    def __init__(self,agent=runtime):
        self.agent=agent;self.lock=threading.RLock();self.jobs={};self.latest={};self.pending={};self.schedules={}

    def _worker(self,identifier,model,decision=None):
        try:
            if decision:
                action,approved,expected=decision
                result=self.agent.decide(action,approved,expected_digest=expected)
                if not approved:return
                if result.get('run',{}).get('status') in ('failed','cancelled','completed'):return
            self.agent.plan(identifier,model)
        except Exception as error:
            with self.lock:self.jobs[identifier]['error']=str(error)[:350] if isinstance(error,ValueError) else 'Task planning failed. Open Agent mode for details; nothing is marked complete.'
        finally:
            with self.lock:self.jobs[identifier]['running']=False

    def launch(self,identifier,model,decision=None):
        with self.lock:
            if identifier in self.jobs and self.jobs[identifier]['running']:raise ValueError('This task is still planning or running.')
            self.jobs[identifier]={'running':True,'error':''}
            thread=threading.Thread(target=self._worker,args=(identifier,model,decision),daemon=True,name='SakuraTeacherTask')
            self.jobs[identifier]['thread']=thread;thread.start()
        return self.status(identifier)

    def status(self,identifier):
        with self.lock:
            if identifier not in self.jobs:raise ValueError('This is not a Companion chat task.')
            job=self.jobs[identifier]
            running=job['running'];error=job['error']
        run=self.agent.state(identifier)
        pending=next((s for s in reversed(run['steps']) if s.get('status')=='pending'),None)
        return {'id':identifier,'run':run,'planning':running,'error':error,'pending':pending}

    def decide(self,identifier,action,approved,model):
        if type(approved) is not bool:raise ValueError('Choose Approve or Reject.')
        state=self.status(identifier)
        if not state['pending'] or state['pending']['id']!=action:raise ValueError('This action changed or is no longer pending. Refresh the task.')
        expected=None
        if approved:
            with self.agent.lock:pending=copy.deepcopy(self.agent.actions.get(action))
            if not pending:raise ValueError('This action is no longer pending.')
            expected=digest(pending)
            if not native_confirm('Run Companion Agent action',pending):raise ValueError('Native approval rejected. Nothing was executed.')
        return self.launch(identifier,model,(action,approved,expected))

    def schedule(self,identifier,approved):
        if approved is not True:raise ValueError('Approve the exact recurring workflow first.')
        self.status(identifier)
        with self.lock:proposal=self.schedules.get(identifier)
        if not proposal:raise ValueError('Ask to repeat this completed task at an interval first.')
        run=self.agent.state(identifier)
        if digest(run['steps'])!=proposal['steps_hash']:raise ValueError('The task changed. Ask for a fresh schedule proposal.')
        if not native_confirm('Schedule Companion workflow',{'goal':run['goal'],'minutes':proposal['minutes'],'steps':run['steps']}):raise ValueError('Native approval rejected. No workflow was scheduled.')
        scheduler=getattr(self.agent,'chat_automations',None)
        if scheduler is None:raise ValueError('The Agent scheduler is not available.')
        with self.lock:
            if self.schedules.get(identifier) is not proposal:raise ValueError('This schedule approval was already used or changed.')
            self.schedules.pop(identifier)
        try:return scheduler.create(identifier,run['goal'][:100],proposal['minutes'],True)
        except Exception:
            with self.lock:self.schedules.setdefault(identifier,proposal)
            raise

    def handle(self,text,cfg,model,payload):
        if cfg.get('conversation_mode')!='teacher' or model is None or getattr(model,'tracking_only',False) is True:return None
        if any(payload.get(k) for k in ('screen_reaction','screen_observation','camera_reaction','ai_vtuber','attachments')):return None
        channel='phone' if payload.get('phone') else 'desktop'
        with self.lock:latest=self.latest.get(channel);pending=self.pending.get(channel)
        if re.fullmatch(r'(?:show |check |what is |what is the |what\'s the )?(?:task status|agent task status)[?.! ]*',text,re.I) and latest:
            state=self.status(latest);return {'reply':'Your task is '+state['run']['status']+'.','agent_task':{'id':latest},'audio':None}
        interval=re.search(r'\bevery\s+(?:(\d+)\s+)?(minutes?|hours?|days?)\b',text,re.I)
        repeat=bool(re.search(r'\b(?:repeat|schedule|run|automate)\b.{0,35}\b(?:this|that|the) (?:task|workflow)\b',text,re.I))
        if repeat and interval and latest:
            if payload.get('phone') and not (cfg.get('computer_control_enabled') and cfg.get('phone_system_access_enabled')):
                return {'reply':'Enable computer access and phone system access on the PC before scheduling a PC workflow from the phone.','audio':None}
            minutes=int(interval.group(1) or 1)*({'minute':1,'hour':60,'day':1440}[interval.group(2).lower().rstrip('s')])
            if not 5<=minutes<=43200:return {'reply':'Choose an interval from 5 minutes to 30 days.','audio':None}
            run=self.agent.state(latest)
            if run['status']!='completed' or not run['steps'] or any(s['status']!='completed' for s in run['steps']):
                return {'reply':'Finish and review this task first. Only its successfully completed steps can become a recurring workflow.','agent_task':{'id':latest},'audio':None}
            with self.lock:self.schedules[latest]={'minutes':minutes,'steps_hash':digest(run['steps'])}
            return {'reply':f'Review repeating this completed workflow every {minutes} minutes. It is not scheduled yet. Sakura must be running; file edits and service changes will still require approval.','agent_task':{'id':latest,'schedule_minutes':minutes},'audio':None}
        from conversation_modes import work_request
        # Calendar conversation already has a separate confirmation-based backend.
        if re.search(r'\b(?:calendar|birthday|meeting|appointment|interview|remind(?:er)?)\b',text,re.I) and not re.search(r'\b(?:app|application|script|website|bot|agent)\b',text,re.I):return None
        path=re.search(r'(?i)([A-Z]:[\\/][^"\n]*?)(?:"|$)',text)
        goal=text
        if pending and time.monotonic()-pending['created']<900 and path:
            goal=pending['goal']
        elif not work_request(text) or re.search(r'\b(?:dance|sing|voice|tracking|transparency|model|camera)\b',text,re.I):return None
        if payload.get('phone') and not (cfg.get('computer_control_enabled') and cfg.get('phone_system_access_enabled')):
            return {'reply':'Enable computer access and phone system access on the PC before creating a PC Agent task from the phone. Nothing has run.','audio':None}
        providers=re.findall(r'\b(playwright|firecrawl|nuclei)\b',goal,re.I)
        setup_requested=bool(providers and re.search(r'\b(?:install|add|set up|setup|enable|integrate)\b',goal,re.I))
        from config import BASE_DIR
        workspace=path.group(1).strip().rstrip(' .') if path else (str(BASE_DIR) if setup_requested else None)
        if not workspace:
            with self.lock:self.pending[channel]={'goal':goal,'created':time.monotonic()}
            return {'reply':'I can create an Agent task for that. Which folder should I use as its workspace? Send the full folder path, for example C:\\Users\\you\\Documents\\MyProject. I have not run the task yet.','audio':None}
        try:
            run=self.agent.new_run(goal,workspace,True)
            with self.lock:
                self.latest[channel]=run['id'];self.pending.pop(channel,None)
            if setup_requested and len(set(name.lower() for name in providers))==1:
                provider=providers[0].lower()
                self.agent.propose(run['id'],'integrations.setup',{'provider':provider},'Prepare the tool you asked to add; secrets must be entered in Connections, never chat.')
                with self.lock:self.jobs[run['id']]={'running':False,'error':''}
                return {'reply':'I prepared '+provider+' setup as an Agent task. Review and approve the step below. I will report it ready only after checking the result.','agent_task':{'id':run['id']},'audio':None}
            self.launch(run['id'],model)
            return {'reply':'Created an Agent task and started planning. Progress and any required approvals appear below; changes have not been approved automatically.','agent_task':{'id':run['id']},'audio':None}
        except (ValueError,OSError) as error:return {'reply':'I could not create that task: '+str(error)[:300],'audio':None}


teacher_agent_chat=TeacherAgentChat()
