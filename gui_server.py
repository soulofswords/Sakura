"""Find Sakura's backend without mistaking another local app for it."""
import json
import os
import socket
import threading
import webbrowser
from urllib.request import build_opener, ProxyHandler

HOST = "127.0.0.1"
port = 8766

def archaeology_router(model_getter,local_check,enabled):
    """Panels are served by app.py; gui_server supplies routes, not a second server."""
    from fastapi import APIRouter,Request,HTTPException,Depends
    from starlette.concurrency import run_in_threadpool
    from pathlib import Path
    from memory_archaeology import MemoryArchaeology,install,QUESTION
    from agent_history import redact_text
    import hashlib,secrets
    root=Path(__file__).parent/'desktop-profile';session=secrets.token_hex(8)
    def sources():
        model=model_getter();rows=[]
        if model is None:return rows
        store=getattr(model,'memory_store',None)
        if getattr(model,'long_term_memory',False) and store is not None:
            for r in store.recent(100,live_only=True):
                rows.append({'link_type':'learned_fact','ref_id':'ledger:'+hashlib.sha256(r['text'].encode()).hexdigest(),'ref_text':r['text'][:800],'classification':r['classification']})
            from contextlib import closing
            with store.lock,closing(store._connect()) as db:
                if db.execute("SELECT 1 FROM sqlite_master WHERE name='memory_entities'").fetchone():
                    retired=' AND m.id NOT IN (SELECT memory_id FROM retired_memories)' if db.execute("SELECT 1 FROM sqlite_master WHERE name='retired_memories'").fetchone() else ''
                    for r in db.execute('SELECT e.memory_id,e.entity,e.classification FROM memory_entities e JOIN memories m ON e.memory_id=m.id WHERE m.superseded_by IS NULL'+retired+' LIMIT 100'):
                        rows.append({'link_type':'workbench_entity','ref_id':str(r[0])+':'+r[1],'ref_text':r[1],'classification':r[2]})
        for index,r in enumerate(list(getattr(model,'history',[]))[-100:]):
            if r.get('role')=='user' and isinstance(r.get('content'),str):
                text=r['content'][:800];rows.append({'link_type':'chat_turn','ref_id':session+':'+str(index)+':'+hashlib.sha256(text.encode()).hexdigest(),'ref_text':text,'classification':'User message in current session; not independently verified'})
        history=getattr(model,'task_history',None)
        if history:
            for r in history.recent(20):
                description=r['goal'][:800]
                # Learned procedures retain only a hashed source-run ID and tool pattern.
                from agent_learning import AgentLearning
                for procedure in AgentLearning(root/'agent-learning.json').status().get('procedures',[]):
                    if procedure.get('source_run')==hashlib.sha256(r['id'].encode()).hexdigest()[:24]:description+=' [Learned '+str(procedure.get('category','general'))+' tool pattern; not an approval]'
                rows.append({'link_type':'agent_run','ref_id':r['id'],'ref_text':description,'classification':'Archived task: '+r['status']})
        from learned_answers import learned_answers
        for key in list(learned_answers._read())[-100:]:
            evidence=learned_answers.recall(key)
            if evidence:rows.append({'link_type':'learned_fact','ref_id':'answer:'+hashlib.sha256(key.encode()).hexdigest(),'ref_text':evidence.text[:800],'classification':evidence.classification})
        return [dict(r,ref_text=redact_text(r['ref_text'])) for r in rows]
    def tagger(messages):
        model=model_getter()
        if model is None:raise ValueError('Choose an AI model first.')
        return model._request_raw(messages,structured=True)
    archaeology=MemoryArchaeology(root,sources=sources,tagger=tagger,allowed=enabled);install(archaeology)
    router=APIRouter(prefix='/api/memory-archaeology')
    def guard(request:Request):
        if not local_check(request):raise HTTPException(403,'Use Memory Archaeology from this local app.')
        if not enabled():raise HTTPException(409,'Memory Archaeology is available in Companion AI mode only.')
    guards=[Depends(guard)]
    async def call(fn,*args,**kwargs):
        try:return await run_in_threadpool(fn,*args,**kwargs)
        except (ValueError,FileNotFoundError) as error:raise HTTPException(400,str(error)[:400]) from None
        except Exception:raise HTTPException(503,'Saved context is unavailable. Check the selected AI and local storage, or enter tags yourself.') from None
    @router.get('/status',dependencies=guards)
    async def status():return {'enabled':archaeology.enabled(),'unconnected':await call(archaeology.unconnected),'question':QUESTION,'calendar_context_enabled':archaeology.settings().get('calendar_context_enabled',False)}
    @router.post('/configure',dependencies=guards)
    async def configure(payload:dict):return await call(archaeology.configure,payload.get('enabled'),payload.get('calendar_context_enabled'))
    @router.get('/calendar-context',dependencies=guards)
    async def calendar_context():
        from assistant_reminders import calendar_context_nudge
        return {'nudge':await call(calendar_context_nudge)}
    @router.post('/save-with-context',dependencies=guards)
    async def save(payload:dict):
        answer=payload.get('answer','');tags=[payload.get(k,'') for k in ('topic','goal','emotion')]
        row=await call(archaeology.record_save,payload.get('type'),payload.get('url_or_path'),*tags,source='web-clipper' if payload.get('type')=='link' else 'manual',answer=answer,tag_origin='user' if answer or any(tags) else 'pending')
        suggested=[{'name':key,'value':value,'classification':'User-provided' if value else 'Not provided'} for key,value in zip(('topic','goal','emotion'),tags)]
        result={'save':row,'question':QUESTION,'suggested_tags':suggested}
        if payload.get('suggest') is True and not answer:
            try:result['suggested_tags']=await call(archaeology.suggestions,payload.get('content',''))
            except HTTPException:result['suggestion_error']='AI suggestions unavailable. Your save is kept; enter tags yourself.'
        return result
    @router.post('/{identifier}/context',dependencies=guards)
    async def context(identifier:str,payload:dict):return await call(archaeology.update,identifier,*(payload.get(k,'') for k in ('topic','goal','emotion')),answer=payload.get('answer',''),origin='suggested' if payload.get('suggested') is True else 'user')
    @router.get('/recall',dependencies=guards)
    async def recall(query:str='',limit:int=5):return await call(archaeology.recall,query,limit)
    @router.get('/pending',dependencies=guards)
    async def pending():return {'saves':await call(archaeology.pending)}
    @router.delete('/{identifier}',dependencies=guards)
    async def delete(identifier:str):return await call(archaeology.delete,identifier)
    return router

def url():
    suffix = "?upload=1" if os.environ.get("SAKURA_UPLOAD_UI") == "1" else ""
    return f"http://{HOST}:{port}{suffix}"

def select_port():
    global port
    opener = build_opener(ProxyHandler({}))
    from product import EDITION
    from vtuber_instances import instance_index
    separate=(EDITION=='vtuber' or os.environ.get('SAKURA_VTUBER_INSTANCE')=='1') and 'SAKURA_INSTANCE_INDEX' in os.environ
    first=(8780 if EDITION=='vtuber' else 8830)+(instance_index()-1)*10 if separate else 8766
    for candidate in range(first,first+8 if separate else 8777):
        address = f"http://{HOST}:{candidate}"
        try:
            if separate:raise ValueError("Separate instance requires its own backend")
            with opener.open(address + "/api/identity", timeout=0.5) as response:
                from product import EDITION, INSTALLATION_ID
                identity=json.load(response)
                if identity.get("application") == "sakura-anime-assistant" and identity.get('edition')==EDITION and identity.get('installation')==INSTALLATION_ID:
                    port = candidate
                    return True
        except Exception:
            pass
        with socket.socket() as sock:
            try:
                sock.bind((HOST, candidate))
            except OSError:
                continue
        port = candidate
        return False
    raise RuntimeError(f"No available Sakura port between {first} and {first+7 if separate else 8776}")

def launch():
    import uvicorn
    if select_port():
        print(f"Opening existing Sakura backend at {url()}")
        webbrowser.open(url())
        return
    print(f"Starting Sakura at {url()}")
    # Uvicorn owns the foreground process.  Open the upload/library page only
    # after it has had a moment to begin accepting localhost connections.
    threading.Timer(0.9, lambda: webbrowser.open(url())).start()
    uvicorn.run("app:app", host=HOST, port=port, log_level="warning")
