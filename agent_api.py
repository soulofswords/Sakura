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


def agent_router(model_getter,enabled=lambda:True,provider_status=None,voice_transcriber=None):
    router=APIRouter();token=secrets.token_urlsafe(40)
    from agent_imports import AgentImports
    imports=AgentImports(runtime)
    from agent_automations import AgentAutomations
    from agent_local_ai import local_ai
    from agent_library_owner import owner_library
    owner_library.enabled=enabled
    automations=AgentAutomations(runtime,enabled,model_getter)
    runtime.chat_automations=automations
    from telegram_bot import gateway as telegram
    def telegram_reply(text):
        if not enabled():raise RuntimeError('AI replies are paused.')
        model=model_getter('current')
        if model is None:return 'No AI model is configured on the PC yet.'
        # chat() retrieves desktop memory and dispatches local commands.
        return model._request_raw([
            {'role':'system','content':'You are Sakura replying to one Telegram message. Answer using only this message; you have no desktop history, files, screen or tools. Never claim to execute actions.'},
            {'role':'user','content':text}])
    telegram.handler=telegram_reply;telegram.transcriber=voice_transcriber
    from agent_messaging import MessagingGateways
    gateways=MessagingGateways(runtime.store_path.parent,telegram_reply)
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def automation_lifespan(app):
        automations.start();owner_library.open()
        for starter in (telegram.start,gateways.start):
            try:
                if enabled():starter()
            except Exception:
                with telegram.lock:telegram.last_error='Telegram could not start. Review its settings on this PC.'
        try:yield
        finally:
            # One attempt each, in order: a hung automation thread must not leave the messaging
            # pollers running or a browser worker holding a live page after the window closes.
            for stopper in (automations.stop,owner_library.close,telegram.stop,gateways.stop,runtime.browser.close):
                try:stopper()
                except Exception:pass
    router.lifespan_context=automation_lifespan
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
        from agent_starter_skills import describe
        providers=await call(provider_status) if provider_status else []
        native=await call(local_ai.status)
        providers=[{'id':'sakura-native','label':'Sakura Local AI · '+(native['loaded'] or 'load a model'),'ready':bool(native['loaded'])},*providers]
        return {'connections':runtime.connections.public(),'tools':runtime.catalog(),
                'providers':providers,'automations':automations.list(),'library_sync':owner_library.status(),
                'skills':describe(await call(runtime.skills.list)),'learning':await call(runtime.learning.status),
                'runs':await call(runtime.states),'command_permissions':runtime.permissions.list(),
                'linkedin':await call(linkedin.status),'calendar':await call(google_calendar.status)}

    @router.get('/api/agent/metrics',dependencies=guard)
    async def agent_metrics(window:int=900):
        return await call(runtime.metrics,window)

    @router.get('/api/agent/telegram',dependencies=guard)
    async def telegram_state():return await call(telegram.status)

    @router.post('/api/agent/telegram',dependencies=guard)
    async def telegram_configure(payload:dict):
        if set(payload)-{'enabled','chat_ids','token','clear_token','voice_enabled'}:raise HTTPException(400,'Unexpected Telegram fields.')
        if type(payload.get('enabled')) is not bool:raise HTTPException(400,'Choose whether the Telegram gateway is enabled.')
        if 'clear_token' in payload and type(payload['clear_token']) is not bool:raise HTTPException(400,'Choose whether to remove the saved token.')
        return await call(telegram.configure,payload['enabled'],payload.get('chat_ids',[]),
                          payload.get('token'),payload.get('clear_token',False),payload.get('voice_enabled',False))

    @router.get('/api/agent/gateways',dependencies=guard)
    async def gateway_states():return await call(gateways.status)

    @router.post('/api/agent/gateways/{provider}',dependencies=guard)
    async def gateway_configure(provider:str,payload:dict):
        gateway=await call(gateways.get,provider)
        return await call(gateway.configure,payload)

    @router.get('/api/messaging/whatsapp/webhook')
    async def whatsapp_challenge(request:Request):
        from fastapi.responses import PlainTextResponse
        query=request.query_params
        try:challenge=await run_in_threadpool(gateways.get('whatsapp').verify_challenge,query.get('hub.mode',''),query.get('hub.verify_token',''),query.get('hub.challenge',''))
        except ValueError:raise HTTPException(403,'Webhook verification refused.') from None
        return PlainTextResponse(challenge)

    @router.post('/api/messaging/whatsapp/webhook')
    async def whatsapp_webhook(request:Request):
        body=bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body)>256000:raise HTTPException(413,'Webhook payload is too large.')
        try:return await run_in_threadpool(gateways.get('whatsapp').accept_webhook,bytes(body),request.headers.get('x-hub-signature-256',''))
        except Exception:raise HTTPException(403,'Webhook delivery refused.') from None

    @router.post('/api/agent/imports/preview',dependencies=guard)
    async def import_preview(payload:dict):return await call(imports.preview,payload.get('filename'),payload.get('text'))

    @router.post('/api/agent/imports/{identifier}/confirm',dependencies=guard)
    async def import_confirm(identifier:str,payload:dict):
        if set(payload)-{'approved'}:raise HTTPException(400,'Import confirmation accepts approval only, not changes to the preview.')
        return await call(imports.confirm,identifier,payload.get('approved'))

    @router.post('/api/agent/voice/transcribe',dependencies=guard)
    async def voice_memo(request:Request):
        from agent_voice import MAX_BYTES,transcribe
        data=bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data)>MAX_BYTES:raise HTTPException(413,'Voice memo must be under 4 MB.')
        return {'text':await call(transcribe,bytes(data),voice_transcriber)}

    @router.post('/api/agent/connections',dependencies=guard)
    async def connection(payload:dict):return await call(runtime.connections.save,payload)

    def service_connection(service):
        from agent_service_mcp import SERVICES
        if service not in SERVICES:raise ValueError('Choose a supported service.')
        existing=next((entry for entry in runtime.connections.public() if entry.get('transport')=='builtin' and entry.get('service')==service),None)
        return existing or runtime.connections.save({'name':SERVICES[service], 'transport':'builtin', 'service':service})

    @router.post('/api/agent/services/{service}',dependencies=guard)
    async def add_service(service:str):return await call(service_connection,service)

    @router.post('/api/agent/services/{service}/connect',dependencies=guard)
    async def connect_service(service:str):
        import webbrowser
        await call(service_connection,service)
        if service=='linkedin':url=await call(linkedin.authorize)
        else:url=await call(google_calendar.authorize,service=='google-drive')
        if not await call(webbrowser.open,url,1,True):raise HTTPException(500,'Could not open your default browser. Check its desktop association and try Connect again.')
        return {'opened':True}

    @router.post('/api/agent/services/{service}/disconnect',dependencies=guard)
    async def disconnect_service(service:str):
        from agent_service_mcp import SERVICES
        if service not in SERVICES:raise HTTPException(400,'Choose a supported service.')
        await call(linkedin.disconnect if service=='linkedin' else google_calendar.disconnect)
        # A revoked account must not leave discoverable tools in the active planner.
        for item in runtime.connections.public():
            if item.get('transport')=='builtin' and (item.get('service')==service or (service.startswith('google-') and item.get('service','').startswith('google-'))):
                runtime.connections.tools.pop(item['id'],None)
        return {'ok':True}

    @router.delete('/api/agent/connections/{identifier}',dependencies=guard)
    async def disconnect(identifier:str):
        await call(runtime.connections.remove,identifier);return {'ok':True}

    @router.post('/api/agent/connections/{identifier}/discover',dependencies=guard)
    async def discover(identifier:str):return await call(runtime.discover_proposal,identifier)

    @router.post('/api/agent/tasks',dependencies=guard)
    async def task(payload:dict):
        current=await call(model_getter)
        if getattr(current,'conversation_mode',None)=='friend':
            from conversation_modes import teacher_prompt
            raise HTTPException(409,teacher_prompt())
        return await call(runtime.new_run,payload.get('goal'),payload.get('workspace'),payload.get('auto_continue',True))

    @router.delete('/api/agent/tasks',dependencies=guard)
    async def clear_tasks():return await call(runtime.clear_history)

    @router.get('/api/agent/tasks/{identifier}',dependencies=guard)
    async def task_state(identifier:str):return await call(runtime.state,identifier)

    @router.get('/api/agent/history/search',dependencies=guard)
    async def history_search(q:str):return await call(runtime.history.search,q)

    @router.get('/api/agent/history/{identifier}',dependencies=guard)
    async def history_read(identifier:str):return await call(runtime.history.read,identifier)

    @router.delete('/api/agent/history/{identifier}',dependencies=guard)
    async def history_forget(identifier:str):return await call(runtime.history.forget,identifier)

    @router.post('/api/agent/tasks/{identifier}/plan',dependencies=guard)
    async def plan(identifier:str,payload:dict):
        choice=payload.get('provider','current')
        if choice not in ('current','ollama','gemini','sakura-native') and not (isinstance(choice,str) and choice.startswith('ollama:')):
            raise HTTPException(400,'Choose an installed local model or Google Gemini.')
        try:model=local_ai if choice=='sakura-native' else await call(model_getter,choice)
        except ValueError as error:raise HTTPException(400,str(error)) from None
        return await call(runtime.plan,identifier,model,payload.get('skill',''))

    @router.post('/api/agent/tasks/{identifier}/delegate',dependencies=guard)
    async def delegate(identifier:str,payload:dict):
        choice=payload.get('provider','current')
        if choice not in ('current','ollama','gemini','sakura-native') and not (isinstance(choice,str) and choice.startswith('ollama:')):
            raise HTTPException(400,'Choose an installed local model or Google Gemini.')
        model=local_ai if choice=='sakura-native' else await call(model_getter,choice)
        return await call(runtime.delegate_proposal,identifier,model,payload.get('goals'))

    @router.post('/api/agent/automations',dependencies=guard)
    async def automation_create(payload:dict):
        if set(payload)-{'run_id','name','minutes','approved','mode','planner','event'}:raise HTTPException(400,'Unexpected automation fields.')
        event=payload.get('event')
        if event is not None and (not isinstance(event,dict) or set(event)-{'path','min_seconds'}):raise HTTPException(400,'Event trigger accepts only path and min_seconds.')
        return await call(automations.create,payload.get('run_id'),payload.get('name'),payload.get('minutes'),payload.get('approved',False),
                          payload.get('mode','steps'),payload.get('planner','current'),event)

    @router.get('/api/agent/library-sync',dependencies=guard)
    async def library_sync_state():return await call(owner_library.status)

    @router.post('/api/agent/library-sync/run',dependencies=guard)
    async def library_sync_run(payload:dict):
        if set(payload)-{'approved'}:raise HTTPException(400,'This workflow accepts approval only, never paths or commands.')
        return await call(owner_library.start,payload.get('approved',False))

    @router.post('/api/agent/library-sync/schedule',dependencies=guard)
    async def library_sync_schedule(payload:dict):
        if set(payload)-{'enabled','minutes','approved'}:raise HTTPException(400,'Unexpected schedule fields.')
        return await call(owner_library.schedule,payload.get('enabled'),payload.get('minutes'),payload.get('approved',False))

    @router.post('/api/agent/automations/{identifier}',dependencies=guard)
    async def automation_update(identifier:str,payload:dict):return await call(automations.update,identifier,payload.get('paused'))

    @router.delete('/api/agent/automations/{identifier}',dependencies=guard)
    async def automation_delete(identifier:str):return await call(automations.remove,identifier)

    @router.post('/api/agent/automations/{identifier}/run',dependencies=guard)
    async def automation_run(identifier:str):return await call(automations.execute,identifier)

    @router.get('/api/agent/local-ai',dependencies=guard)
    async def local_ai_state():return local_ai.status()

    @router.get('/api/agent/local-ai/search',dependencies=guard)
    async def local_ai_search(q:str):return await call(local_ai.search,q)

    @router.get('/api/agent/local-ai/files',dependencies=guard)
    async def local_ai_files(repo:str):return await call(local_ai.files,repo)

    @router.post('/api/agent/local-ai/runtime',dependencies=guard)
    async def local_ai_runtime(payload:dict):return await call(local_ai.install_runtime,payload.get('backend','vulkan'),payload.get('engine','llama.cpp'))

    @router.post('/api/agent/local-ai/download',dependencies=guard)
    async def local_ai_download(payload:dict):return await call(local_ai.download,payload.get('repo'),payload.get('file'))

    @router.post('/api/agent/local-ai/import',dependencies=guard)
    async def local_ai_import(payload:dict):return await call(local_ai.import_file,payload.get('path'),payload.get('name',''),payload.get('projector',False))

    @router.post('/api/agent/local-ai/colibri/import',dependencies=guard)
    async def local_ai_colibri_import(payload:dict):return await call(local_ai.import_colibri,payload.get('path'),payload.get('name',''))

    @router.post('/api/agent/local-ai/inspect',dependencies=guard)
    async def local_ai_inspect(payload:dict):return await call(local_ai.inspect_folder,payload.get('path'))

    @router.post('/api/agent/local-ai/import-detected',dependencies=guard)
    async def local_ai_import_detected(payload:dict):return await call(local_ai.import_detected,payload.get('path'))

    @router.post('/api/agent/local-ai/load',dependencies=guard)
    async def local_ai_load(payload:dict):return await call(local_ai.load,payload.get('id'),payload.get('projector',''),payload.get('context',4096),payload.get('gpu_layers',0),payload.get('backend','auto'))

    @router.post('/api/agent/local-ai/unload',dependencies=guard)
    async def local_ai_unload():
        await call(local_ai.unload);return local_ai.status()

    @router.delete('/api/agent/local-ai/models/{identifier}',dependencies=guard)
    async def local_ai_remove(identifier:str,delete:bool=False):return await call(local_ai.remove,identifier,delete)

    @router.post('/api/agent/local-ai/chat',dependencies=guard)
    async def local_ai_chat(payload:dict):return {'text':await call(local_ai._request_raw,payload.get('messages'))}

    @router.post('/api/agent/memory',dependencies=guard)
    async def configure_memory(payload:dict):
        if set(payload)-{'enabled','notes','profile'}:raise HTTPException(400,'Invalid memory settings.')
        return await call(runtime.learning.configure,payload.get('enabled'),payload.get('notes',''),payload.get('profile',''))

    @router.delete('/api/agent/memory',dependencies=guard)
    async def clear_memory():return await call(runtime.learning.clear)

    @router.delete('/api/agent/memory/{identifier}',dependencies=guard)
    async def delete_memory(identifier:str):return await call(runtime.learning.delete,identifier)

    @router.post('/api/agent/memory/{identifier}/skill',dependencies=guard)
    async def memory_to_skill(identifier:str,payload:dict):
        if set(payload)-{'name'}:raise HTTPException(400,'Invalid skill request.')
        return await call(runtime.skills.save,payload.get('name'),runtime.learning.skill(identifier))

    @router.post('/api/agent/skills',dependencies=guard)
    async def save_skill(payload:dict):
        return await call(runtime.skills.save,payload.get('name'),payload.get('instructions'))

    @router.post('/api/agent/skills/learn',dependencies=guard)
    async def learn_skill(payload:dict):
        if set(payload)-{'run_id','name'}:raise HTTPException(400,'Invalid learn request.')
        from agent_starter_skills import learn_completed
        return await call(learn_completed,runtime.skills,runtime.state(payload.get('run_id')),payload.get('name'))

    @router.delete('/api/agent/skills/{name}',dependencies=guard)
    async def delete_skill(name:str):return await call(runtime.skills.delete,name)

    @router.post('/api/agent/tasks/{identifier}/propose',dependencies=guard)
    async def propose(identifier:str,payload:dict):return await call(runtime.propose,identifier,payload.get('tool'),payload.get('arguments'),payload.get('reason','Manually proposed by the user.'))

    @router.post('/api/agent/actions/{identifier}/decision',dependencies=guard)
    async def decision(identifier:str,payload:dict):
        if type(payload.get('approve')) is not bool:raise HTTPException(400,'Choose Approve or Reject.')
        if type(payload.get('remember',False)) is not bool:raise HTTPException(400,'Choose whether to allow this exact command for this session.')
        return await call(runtime.decide,identifier,payload['approve'],payload.get('remember',False))

    @router.delete('/api/agent/permissions/{identifier}',dependencies=guard)
    async def revoke_permission(identifier:str):return await call(runtime.permissions.revoke,identifier)

    @router.post('/api/agent/tasks/{identifier}/cancel',dependencies=guard)
    async def cancel(identifier:str):return await call(runtime.cancel,identifier)

    @router.post('/api/agent/tasks/{identifier}/pause',dependencies=guard)
    async def pause(identifier:str):return await call(runtime.pause,identifier)

    @router.post('/api/agent/tasks/{identifier}/resume',dependencies=guard)
    async def resume(identifier:str,payload:dict):
        choice=payload.get('provider','current')
        if choice not in ('current','ollama','gemini','sakura-native') and not (isinstance(choice,str) and choice.startswith('ollama:')):
            raise HTTPException(400,'Choose an installed local model or Google Gemini.')
        extra=payload.get('additional_steps',0)
        if type(extra) is not int or not 0<=extra<=500:raise HTTPException(400,'additional_steps must be a whole number from 0 to 500.')
        try:model=local_ai if choice=='sakura-native' else await call(model_getter,choice)
        except ValueError as error:raise HTTPException(400,str(error)) from None
        return await call(runtime.resume,identifier,model,payload.get('skill',''),extra)

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
