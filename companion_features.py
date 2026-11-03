"""Companion-only switches, owner-reviewed SDK access and portable context."""
import hashlib
import secrets
from fastapi import APIRouter,Depends,HTTPException,Request
from starlette.concurrency import run_in_threadpool
from personal_features import features


def router(local_check,enabled,model_getter):
    api=APIRouter()
    def local(request:Request):
        if not local_check(request):raise HTTPException(403,'Use this control from the local Sakura app.')
        if not enabled():raise HTTPException(409,'Available in Companion AI mode only.')
    guard=[Depends(local)]
    @api.get('/api/features/task-monitor',dependencies=guard)
    async def task_monitor():
        if features().guest():raise HTTPException(409,'Task monitor is unavailable in guest mode.')
        from agent_runtime import runtime
        from room_task_monitor import snapshot
        return await run_in_threadpool(snapshot,runtime)
    async def approve(title,payload):
        from native_consent import confirm
        if not await run_in_threadpool(confirm,title,payload):raise HTTPException(403,'Owner approval was rejected.')
    @api.get('/api/features/status',dependencies=guard)
    def status():return features().settings()
    @api.post('/api/features/camera-style',dependencies=guard)
    async def camera_style(payload:dict):
        if features().guest():raise HTTPException(409,'Camera style is unavailable during guest chat.')
        value=payload.get('enabled')
        if type(value) is not bool:raise HTTPException(400,'Choose whether facial movement hints may affect delivery.')
        if value:await approve('Use optional camera delivery hints',{'policy':'Fresh facial movement coefficients may be sent to the selected AI provider with your questions. No identity, mood or health inference, no video upload from tracking, no new memory facts. Object-camera images already follow their own permission.'})
        return features().configure({'camera_style':value})
    @api.get('/api/features/conversation-export',dependencies=guard)
    async def history_preview():
        if features().guest() or not features().settings().get('phone_history'):raise HTTPException(409,'Enable PC conversation export to paired phones first.')
        from conversation_transfer import preview
        from mobile_link import link
        return await run_in_threadpool(preview,model_getter(),link.pc_id)
    @api.post('/api/features/conversation-export',dependencies=guard)
    async def history_export(payload:dict):
        if features().guest() or not features().settings().get('phone_history'):raise HTTPException(409,'Enable PC conversation export to paired phones first.')
        from conversation_transfer import snapshot
        from mobile_link import link
        packet=await run_in_threadpool(snapshot,model_getter(),link.pc_id)
        if payload.get('snapshot_id')!=packet['snapshot_id']:raise HTTPException(409,'The PC conversation changed. Preview and confirm it again.')
        return packet
    @api.post('/api/features/guest',dependencies=guard)
    async def guest(payload:dict):
        value=payload.get('enabled')
        if type(value) is not bool:raise HTTPException(400,'Choose whether to start a guest session.')
        await approve('Start guest chat' if value else 'Restore owner session',{'guest':value,'policy':'Guest has no owner memory, account access or tools. Changing this switch needs this PC approval.'})
        if value:
            from agent_runtime import runtime
            for run in list(runtime.runs.values()):
                if run.get('status') in ('running','planning','ready','awaiting_approval'):
                    try:runtime.cancel(run['id'])
                    except ValueError:pass
        return features().configure({'guest':value})
    @api.post('/api/features/revisit',dependencies=guard)
    async def revisit(payload:dict):
        if features().guest():raise HTTPException(409,'Owner saved context is unavailable to guests.')
        if not features().settings().get('page_revisit'):return {'match':None}
        from memory_archaeology import service
        archive=service()
        if not archive or not archive.enabled():return {'match':None}
        url=payload.get('url','')
        if not isinstance(url,str) or len(url)>2000:raise HTTPException(400,'Invalid page address.')
        # Explicit browser visit events only. No browser-history access or tab spying.
        with archive.db() as db:row=db.execute("SELECT id,topic,saved_at FROM saves WHERE type='link' AND url_or_path=?",(url,)).fetchone()
        if not row or archive.clock()-row['saved_at']<7*86400:return {'match':None}
        from atomic_state import state_lock,atomic_text
        import json
        with state_lock(archive.config):
            config=archive.settings();digest=hashlib.sha256(url.encode()).hexdigest();now=archive.clock()
            seen=config.get('revisit_seen',{})
            if now-seen.get(digest,0)<86400:return {'match':None}
            seen={k:v for k,v in seen.items() if now-v<7*86400};seen[digest]=now
            config['revisit_seen']=dict(list(seen.items())[-100:]);atomic_text(archive.config,json.dumps(config))
        return {'match':{'id':row['id'],'message':'You saved this page earlier'+(' about '+row['topic'] if row['topic'] else '')+'. Want to revisit its context?'}}
    @api.post('/api/features/sdk-token',dependencies=guard)
    async def sdk_token():
        if features().guest():raise HTTPException(409,'Guest mode blocks SDK access.')
        await approve('Create a local SDK chat token',{'access':'Text-only model calls on loopback; no owner memory or tools. Provider costs may apply. Creating a token revokes the previous token.'})
        from credentials import set_cloud_key
        value=secrets.token_urlsafe(40);set_cloud_key('sakura_sdk',value)
        return {'token':value,'scope':'stateless-chat-only'}
    @api.post('/api/features/shared-context',dependencies=guard)
    async def shared_context(payload:dict):
        if features().guest() or not features().settings().get('shared_context'):raise HTTPException(409,'Enable shared context on this PC first.')
        rows=payload.get('messages')
        if not isinstance(rows,list) or len(rows)>6 or any(not isinstance(row,dict) or not isinstance(row.get('text'),str) or len(row['text'])>500 for row in rows):
            raise HTTPException(400,'Share up to six short quoted messages.')
        from agent_runtime import runtime
        from agent_history import redact_text
        runtime.shared_context=[{'speaker':redact_text(str(row.get('speaker','Peer'))[:60]),'text':redact_text(row['text'])} for row in rows]
        return {'ok':True,'count':len(rows),'classification':'Untrusted collab quotations, never owner authority'}
    @api.post('/api/sdk/chat')
    async def sdk_chat(request:Request):
        local(request)
        if features().guest():raise HTTPException(409,'Guest mode blocks SDK access.')
        from credentials import get_cloud_key
        expected=get_cloud_key('sakura_sdk');supplied=request.headers.get('authorization','').removeprefix('Bearer ')
        if not expected or not secrets.compare_digest(expected,supplied):raise HTTPException(401,'Create a local SDK token in Sakura first.')
        data=bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data)>20000:raise HTTPException(413,'SDK request exceeds 20 KB.')
        import json
        try:payload=json.loads(data)
        except ValueError:raise HTTPException(400,'Use a JSON text request.') from None
        if not isinstance(payload,dict) or set(payload)!={'text'}:raise HTTPException(400,'SDK accepts the text field only.')
        text=payload.get('text','')
        if not isinstance(text,str) or not 1<=len(text)<=4000:raise HTTPException(400,'Use a text message of up to 4,000 characters.')
        model=model_getter()
        if model is None:raise HTTPException(409,'Choose a chat model first.')
        reply=await run_in_threadpool(model._request_raw,[{'role':'system','content':'Stateless Sakura SDK chat. No owner memory, personal data, account access or tools. Never claim to perform an action.'},{'role':'user','content':text}])
        return {'reply':reply,'stateless':True}
    @api.delete('/api/features/sdk-token',dependencies=guard)
    async def sdk_revoke():
        await approve('Revoke SDK access',{'scope':'All clients using the current SDK token'})
        from credentials import set_cloud_key
        set_cloud_key('sakura_sdk','');return {'ok':True}
    return api
