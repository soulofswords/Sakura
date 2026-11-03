"""UI-backed, local/token-gated extensions; no new network listener."""
from fastapi import Depends,HTTPException,Request
from knowledge_folders import FolderKnowledge,manifest
from model_choice import ModelChoice
from personal_features import features


def install(router,guard,call,consent,runtime,model_getter,local_ai,provider_status):
    folders=FolderKnowledge(runtime.store_path.parent/'knowledge-folders.json',runtime.knowledge)
    routing=ModelChoice(runtime.store_path.parent/'model-routing.json')
    from speaker_profiles import SpeakerProfiles
    speakers=SpeakerProfiles(runtime.store_path.parent/'voiceprint')
    async def models():
        rows=await call(provider_status) if provider_status else []
        output={}
        for item in rows[:10]:
            if item.get('ready') and item.get('id')!='auto':
                try:output[item['id']]=await call(model_getter,item['id'])
                except ValueError:continue
        if (await call(local_ai.status)).get('loaded'):output['sakura-native']=local_ai
        return output
    async def choose(choice,category='coding'):
        if choice=='auto':return routing.select(category,await models())[1]
        return local_ai if choice=='sakura-native' else await call(model_getter,choice)
    def choose_sync(choice='current'):
        if choice!='auto':return local_ai if choice=='sakura-native' else model_getter(choice)
        available={}
        for row in (provider_status() if provider_status else [])[:10]:
            if row.get('ready') and row.get('id')!='auto':
                try:available[row['id']]=model_getter(row['id'])
                except ValueError:continue
        if local_ai.status().get('loaded'):available['sakura-native']=local_ai
        return routing.select('coding',available)[1]

    @router.get('/api/agent/speakers',dependencies=guard)
    async def speaker_status():return await call(speakers.status)
    @router.post('/api/agent/speakers/install',dependencies=guard)
    async def speaker_install():
        await consent('Download optional CPU speaker recognition',{'source':'SpeechBrain ECAPA VoxCeleb, pinned revision','dependencies':'Separate Python environment with CPU PyTorch, torchaudio and SpeechBrain. Large download. Existing Sakura environment unchanged.','policy':'Voice similarity is never authorization. Raw recordings are deleted.'})
        return await call(speakers.install)
    async def speaker_audio(request):
        data=bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data)>5_000_000:raise HTTPException(413,'Use a WAV under 5 MB.')
        return bytes(data)
    @router.post('/api/agent/speakers/compare',dependencies=guard)
    async def speaker_compare(request:Request):
        audio=await speaker_audio(request)
        return await call(speakers.identify,audio)
    @router.post('/api/agent/speakers/enroll',dependencies=guard)
    async def speaker_enroll(request:Request,name:str):
        audio=await speaker_audio(request)
        await consent('Enroll this speaker profile',{'label':name,'policy':'Encrypted local embedding only. Not a login credential. Recording deleted after encoding.'})
        return await call(speakers.enroll,name,audio)
    @router.delete('/api/agent/speakers/{name}',dependencies=guard)
    async def speaker_forget(name:str):
        await consent('Delete speaker embedding',{'label':name});return await call(speakers.forget,name)
    @router.post('/api/agent/speakers/rename',dependencies=guard)
    async def speaker_rename(payload:dict):
        await consent('Rename speaker profile',{'label':payload.get('name'),'new_label':payload.get('new_name')})
        return await call(speakers.rename,payload.get('name'),payload.get('new_name'))

    @router.get('/api/agent/knowledge/folders',dependencies=guard)
    async def folder_status():return {'folders':await call(folders.folders)}
    @router.post('/api/agent/knowledge/folders',dependencies=guard)
    async def index_folder(payload:dict):
        reviewed=await call(manifest,payload.get('folder',''))
        semantic=payload.get('semantic',False)
        if type(semantic) is not bool:raise HTTPException(400,'Choose whether to use installed local embeddings.')
        await consent('Index this document folder',{'manifest':reviewed,'semantic':semantic,'warning':'Local historical text index. Skips secrets, hidden files and links. Original files are unchanged.'})
        return await call(folders.index,reviewed,semantic)
    @router.post('/api/agent/knowledge/search-folders',dependencies=guard)
    async def search_folders(payload:dict):return await call(folders.search,payload.get('query',''))
    @router.post('/api/agent/knowledge/remove-folder',dependencies=guard)
    async def remove_folder(payload:dict):
        await consent('Forget an indexed folder',{'folder':payload.get('folder'),'original_files':'preserved'})
        return await call(folders.remove,payload.get('folder',''))
    @router.get('/api/agent/model-routing',dependencies=guard)
    async def routing_status():return routing.state()
    @router.post('/api/agent/model-routing',dependencies=guard)
    async def routing_config(payload:dict):
        await consent('Configure automatic model choice',payload)
        return routing.configure(payload.get('enabled'),payload.get('allow_cloud'))
    @router.post('/api/agent/model-routing/benchmark',dependencies=guard)
    async def benchmark(payload:dict):
        available=await models();provider=payload.get('provider')
        if provider not in available:raise HTTPException(400,'Select a ready configured model.')
        from agent_runtime import _planner_selection
        model=available[provider];identity=_planner_selection(model)
        cloud=identity.get('provider') not in ('','ollama')
        await consent('Benchmark this model',{'provider':provider,'model':identity,'calls':4,'cloud_cost_possible':cloud,'prompts':'Synthetic chat, arithmetic and JSON checks only; no personal files.'})
        return {'profiles':await call(routing.measure,provider,model,cloud)}
    @router.get('/api/agent/features',dependencies=guard)
    async def feature_state():return features().settings()
    @router.post('/api/agent/features',dependencies=guard)
    async def feature_config(payload:dict):
        if 'guest' in payload:raise HTTPException(400,'Use the dedicated guest-session switch.')
        await consent('Enable optional personal features',{'switches':payload,'phone_memory':'Allows paired phones to copy up to 100 saved references. No account tokens or original files.','phone_history':'Allows paired phones to preview and import retained raw PC conversation messages into a separate phone copy. This can contain private dialogue. No account tokens, files or trusted facts. Off by default.','camera_style':'Only explicit user-selected style hints, never inferred feelings.','shared_context':'Only manually entered collab messages; no private history.'})
        return features().configure(payload)
    @router.get('/api/agent/expenses',dependencies=guard)
    async def expenses(month:str=''):return await call(features().expenses,month)
    @router.post('/api/agent/expenses',dependencies=guard)
    async def add_expense(payload:dict):
        await consent('Record this expense locally',payload)
        return await call(features().add_expense,**payload)
    @router.delete('/api/agent/expenses/{identifier}',dependencies=guard)
    async def delete_expense(identifier:str):
        await consent('Delete local expense',{'id':identifier})
        return await call(features().delete_expense,identifier)
    return choose,choose_sync
