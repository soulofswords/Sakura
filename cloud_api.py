"""Explicit cloud routing; key detection never sends secrets to trial endpoints."""
import re
from urllib.parse import urlsplit
import requests

PROVIDERS={
    'openai':('https://api.openai.com/v1','gpt-4.1-mini',True),
    'anthropic':('https://api.anthropic.com/v1','claude-haiku-4-5',True),
    'openrouter':('https://openrouter.ai/api/v1','',False),
    'groq':('https://api.groq.com/openai/v1','',False),
    'xai':('https://api.x.ai/v1','',False),
    'deepseek':('https://api.deepseek.com','deepseek-flash',False),
    'compatible':('','',False),
}

def detect_provider(key):
    for prefix,provider in [('AIza','gemini'),('sk-ant-','anthropic'),('sk-or-','openrouter'),('sk-proj-','openai'),('sk-svcacct-','openai'),('gsk_','groq'),('xai-','xai')]:
        if key.startswith(prefix):return provider
    raise ValueError('This key format is ambiguous. Choose its provider manually; Sakura will not try your key on multiple services.')

def validate(provider,model='',endpoint='',vision=None):
    if provider not in PROVIDERS:raise ValueError('Choose a supported cloud provider.')
    if not isinstance(model,str) or not isinstance(endpoint,str) or len(endpoint)>500:raise ValueError('Enter a valid model ID and API base URL.')
    base,default,default_vision=PROVIDERS[provider]
    if provider=='compatible':
        parsed=urlsplit(endpoint)
        # A proxy on this PC (FreeLLMAPI, LM Studio, Ollama's shim) speaks plain http on loopback;
        # requiring https there would rule out the one endpoint that never leaves the machine.
        local=parsed.hostname in ('127.0.0.1','::1','localhost')
        if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or (
                parsed.scheme!='https' and not (local and parsed.scheme=='http')):
            raise ValueError('Enter an HTTPS API base URL, or http://127.0.0.1:PORT/v1 for a proxy on this PC, without a password, query or fragment.')
        base=endpoint.rstrip('/')
    model=model.strip() or default
    if not re.fullmatch(r'[A-Za-z0-9._:/-]{1,150}',model):raise ValueError('Enter the exact model ID from your provider.')
    if vision is not None and type(vision) is not bool:raise ValueError('Choose whether this model supports images.')
    return base,model,default_vision if vision is None else vision

def request(provider,model,key,messages,endpoint='',vision=False,summarizing=False,planning=False):
    if not key:raise ValueError(f'No API key saved for {provider}. Add it in Settings > AI.')
    base,model,_=validate(provider,model,endpoint,vision)
    if any(m.get('images') for m in messages) and not vision:
        raise ValueError('This cloud model is configured for text only. Select an image-capable model and enable image support in Settings > AI.')
    systems='\n\n'.join(m['content'] for m in messages if m['role']=='system')
    converted=[]
    for message in messages:
        if message['role']=='system':continue
        if provider=='anthropic':
            parts=[{'type':'text','text':message['content']}]
            parts += [{'type':'image','source':{'type':'base64','media_type':'image/jpeg','data':image}} for image in message.get('images',[])]
        else:
            parts=[{'type':'text','text':message['content']}]
            parts += [{'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+image}} for image in message.get('images',[])]
        converted.append({'role':message['role'],'content':parts if provider=='anthropic' or message.get('images') else message['content']})
    limit=4096 if planning else (2048 if summarizing else 1024)
    if provider=='anthropic':
        route='/messages';headers={'x-api-key':key,'anthropic-version':'2023-06-01'}
        body={'model':model,'system':systems,'messages':converted,'max_tokens':limit}
    else:
        route='/chat/completions';headers={'Authorization':'Bearer '+key}
        body={'model':model,'messages':[{'role':'system','content':systems},*converted],'stream':False}
        if planning and provider in ('openai','groq'):body['response_format']={'type':'json_object'}
        if provider=='openai':body['max_completion_tokens']=limit
        else:body['max_tokens']=limit
    try:
        response=requests.post(base+route,headers=headers,json=body,timeout=(5,45),allow_redirects=False)
    except requests.RequestException:
        raise ValueError(f'{provider} could not be reached. Check your connection and endpoint.') from None
    if not response.ok:
        from cloud_diagnostics import provider_error
        raise ValueError(provider_error(provider,response,key))
    try:
        data=response.json()
        from agent_usage import record_usage
        record_usage(provider,model,messages,data)
        if provider=='anthropic':reply=''.join(part.get('text','') for part in data.get('content',[]) if part.get('type')=='text')
        else:reply=data['choices'][0]['message']['content']
        if not isinstance(reply,str) or not reply.strip():raise ValueError()
        return reply.strip()
    except (ValueError,KeyError,IndexError,TypeError):
        raise ValueError(f'{provider} returned no usable text. Check that this endpoint supports chat completions.') from None
