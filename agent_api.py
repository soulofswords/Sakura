"""Local-only API for agent review. Separate from chat/model-generated actions."""
import secrets
from datetime import datetime,timedelta
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.responses import HTMLResponse
from starlette.concurrency import run_in_threadpool
from config import BASE_DIR
from agent_runtime import runtime
from agent_linkedin import linkedin
from agent_calendar import google_calendar


def agent_router(model_getter,enabled=lambda:True,provider_status=None):
    router=APIRouter();token=secrets.token_urlsafe(40)
    def web_keys():
        """Search providers use the keys the user already saved; empty means keyless."""
        try:
            model = model_getter('current')
            gemini = str(getattr(model, 'gemini_api_key', '') or ''), str(getattr(model, 'gemini_model', '') or '')
        except Exception:
            gemini = '', ''
        try:
            from credentials import get_cloud_key
            brave = get_cloud_key('brave')
        except Exception:
            brave = ''
        return (*gemini, brave)
    runtime.web_credentials = web_keys
    def local(request:Request):
        if not enabled():raise HTTPException(409,'Agent tools are available only in Companion AI modes.')
        if not request.client or request.client.host not in ('127.0.0.1','::1'):raise HTTPException(403,'Agent approvals must be made on this PC.')
        if request.url.hostname not in ('127.0.0.1','localhost','::1'):raise HTTPException(403,'Invalid agent host.')
        origin=request.headers.get('origin')
        if origin and origin!=str(request.base_url).rstrip('/'):raise HTTPException(403,'Agent requests must come from this local app.')
        if request.headers.get('sec-fetch-site')=='cross-site':raise HTTPException(403,'Cross-site agent requests are blocked.')
    def authorize(request:Request):
        local(request)
        if not secrets.compare_digest(request.headers.get('x-sakura-agent',''),token):raise HTTPException(403,'Open the local Agent panel to authorize this request.')
    async def call(function,*args,**kwargs):
        try:return await run_in_threadpool(function,*args,**kwargs)
        except Exception as error:
            from jsonschema import ValidationError
            if isinstance(error,ValidationError):message='Tool arguments do not match the registered schema: '+error.message[:300]
            elif isinstance(error,(ValueError,FileNotFoundError,PermissionError,RuntimeError)):message=str(error)[:1200]
            elif isinstance(error,ImportError):message='The MCP runtime is missing. Install requirements-agent.txt in the app Python environment.'
            else:message='The operation failed. Check the connection and retry; no automatic retry was sent.'
            raise HTTPException(400,message) from None
    guard=[Depends(authorize)]

    @router.get('/api/agent/identity',dependencies=[Depends(local)])
    def identity():
        from agent_runtime import digest
        return {'application':'sakura-agent','installation':digest(str(BASE_DIR))}

    @router.get('/agent',response_class=HTMLResponse,dependencies=[Depends(local)])
    def page():
        text=(BASE_DIR/'static/assets/agent.html').read_text(encoding='utf-8')
        # The Agent panel is embedded in Sakura Companion's same-origin iframe.
        # SAMEORIGIN keeps it out of external frames while allowing that view.
        return HTMLResponse(text.replace('__AGENT_TOKEN__',token),headers={'Cache-Control':'no-store','X-Frame-Options':'SAMEORIGIN','Referrer-Policy':'no-referrer'})

    @router.get('/api/agent/state',dependencies=guard)
    async def state():
        return {'connections':runtime.connections.public(),'tools':runtime.catalog(),
                'providers':await call(provider_status) if provider_status else [],
                'skills':await call(runtime.skills.list),
                'runs':await call(runtime.states),
                'linkedin':await call(linkedin.status),'calendar':await call(google_calendar.status)}

    @router.post('/api/agent/connections',dependencies=guard)
    async def connection(payload:dict):return await call(runtime.connections.save,payload)

    @router.delete('/api/agent/connections/{identifier}',dependencies=guard)
    async def disconnect(identifier:str):
        await call(runtime.connections.remove,identifier);return {'ok':True}

    @router.post('/api/agent/connections/{identifier}/discover',dependencies=guard)
    async def discover(identifier:str):return await call(runtime.discover_proposal,identifier)

    @router.post('/api/agent/tasks',dependencies=guard)
    async def task(payload:dict):return await call(runtime.new_run,payload.get('goal'),payload.get('workspace'),payload.get('auto_continue',True))

    @router.delete('/api/agent/tasks',dependencies=guard)
    async def clear_tasks():return await call(runtime.clear_history)

    @router.get('/api/agent/tasks/{identifier}',dependencies=guard)
    async def task_state(identifier:str):return await call(runtime.state,identifier)

    @router.post('/api/agent/tasks/{identifier}/plan',dependencies=guard)
    async def plan(identifier:str,payload:dict):
        choice=payload.get('provider','current')
        if choice not in ('current','ollama','gemini') and not (isinstance(choice,str) and choice.startswith('ollama:')):
            raise HTTPException(400,'Choose an installed local model or Google Gemini.')
        try:model=await call(model_getter,choice)
        except ValueError as error:raise HTTPException(400,str(error)) from None
        return await call(runtime.plan,identifier,model,payload.get('skill',''))

    @router.post('/api/agent/skills',dependencies=guard)
    async def save_skill(payload:dict):
        return await call(runtime.skills.save,payload.get('name'),payload.get('instructions'))

    @router.delete('/api/agent/skills/{name}',dependencies=guard)
    async def delete_skill(name:str):return await call(runtime.skills.delete,name)

    @router.post('/api/agent/tasks/{identifier}/propose',dependencies=guard)
    async def propose(identifier:str,payload:dict):return await call(runtime.propose,identifier,payload.get('tool'),payload.get('arguments'),payload.get('reason','Manually proposed by the user.'))

    @router.post('/api/agent/actions/{identifier}/decision',dependencies=guard)
    async def decision(identifier:str,payload:dict):
        if type(payload.get('approve')) is not bool:raise HTTPException(400,'Choose Approve or Reject.')
        return await call(runtime.decide,identifier,payload['approve'])

    @router.post('/api/agent/tasks/{identifier}/cancel',dependencies=guard)
    async def cancel(identifier:str):return await call(runtime.cancel,identifier)

    @router.post('/api/agent/linkedin/configure',dependencies=guard)
    async def linkedin_config(payload:dict,request:Request):
        callback=str(request.base_url).rstrip('/')+'/api/agent/linkedin/callback'
        await call(linkedin.configure,payload.get('client_id',''),payload.get('client_secret',''),callback)
        return {'ok':True,'redirect_uri':callback}

    @router.post('/api/agent/linkedin/connect',dependencies=guard)
    async def linkedin_connect():return {'url':await call(linkedin.authorize)}

    @router.post('/api/agent/linkedin/disconnect',dependencies=guard)
    async def linkedin_disconnect():
        await call(linkedin.disconnect);return {'ok':True}

    @router.get('/api/agent/linkedin/callback',response_class=HTMLResponse)
    async def callback(request:Request,state:str='',code:str='',error:str=''):
        # OAuth navigation is cross-site by design; its one-shot state replaces
        # the agent panel token on this single callback route only.
        if not request.client or request.client.host not in ('127.0.0.1','::1') or request.url.hostname!='127.0.0.1':raise HTTPException(403,'Local callback required.')
        if error or not code:raise HTTPException(400,'LinkedIn sign-in was cancelled or permissions were not granted.')
        await call(linkedin.callback,state,code)
        return HTMLResponse('<meta charset="utf-8"><h2>LinkedIn connected</h2><p>Reading your profile or publishing still needs action approval.</p><a href="/agent">Return to the Agent workspace</a>',headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer'})

    @router.post('/api/agent/calendar/configure',dependencies=guard)
    async def calendar_config(payload:dict):
        return await call(google_calendar.configure,payload.get('client_id',''),payload.get('client_secret',''))

    @router.post('/api/agent/calendar/connect',dependencies=guard)
    async def calendar_connect(payload:dict=None):
        import webbrowser
        if payload and payload.get('workspace') is True:
            url=await call(google_calendar.authorize,True)
        else:url=await call(google_calendar.authorize)
        opened=await call(webbrowser.open,url,1,True)
        if not opened:raise HTTPException(500,'Could not open your default browser. Check the desktop browser association and try Connect again.')
        return {'opened':True}

    @router.get('/api/agent/calendar/status',dependencies=guard)
    async def calendar_status():return await call(google_calendar.status)

    @router.post('/api/agent/calendar/disconnect',dependencies=guard)
    async def calendar_disconnect():return await call(google_calendar.disconnect)

    @router.get('/api/agent/calendar/agenda',dependencies=guard)
    async def calendar_agenda():
        if not (await call(google_calendar.status)).get('connected'):
            raise HTTPException(400,'Connect Google Calendar first.')
        start=datetime.now().astimezone()
        end=start+timedelta(days=7)
        return await call(google_calendar.list_events,time_min=start.isoformat(timespec='seconds'),
                          time_max=end.isoformat(timespec='seconds'),max_results=50)

    @router.post('/api/agent/calendar/propose',dependencies=guard)
    async def calendar_propose(payload:dict):
        summary=str(payload.get('summary','')).strip()
        if not summary:raise HTTPException(400,'Enter an event title.')
        arguments={key:payload[key] for key in ('summary','start','end','location','description') if key in payload}
        run=await call(runtime.new_run,'Create Google Calendar event: '+summary,str(BASE_DIR))
        return await call(runtime.propose,run['id'],'calendar.events.create',arguments,
                          'You requested this calendar event. Review the exact details before it is added.')
    return router
