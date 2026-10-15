"""Provider-bound model discovery and small generation checks; never trial keys elsewhere."""
import re
import requests
from cloud_api import PROVIDERS,validate

def provider_error(provider,response,key=''):
    code=kind=detail=''
    try:
        error=response.json().get('error',{})
        if isinstance(error,dict):code=str(error.get('code',''));kind=str(error.get('type',error.get('status','')));detail=str(error.get('message',''))
    except (ValueError,AttributeError,TypeError):pass
    status=response.status_code;info=(code+' '+kind+' '+detail).lower()
    if status in (402,429) and any(word in info for word in ('insufficient_quota','credit','billing','spend_limit','usage_limit','limit: 0')):
        hint='API billing/quota limit reached. Check API credits and project usage limits; creating another key does not reset them.'
    elif status==429:hint='Rate or quota limit reached. Wait before retrying and check project limits.'
    elif status==401 or 'api_key_invalid' in info or 'api key not valid' in info:hint='API key rejected. Save a key issued by this provider.'
    elif status==403:hint='Access denied. Check project/API permissions, key restrictions and regional availability.'
    elif status==404:hint='Model or endpoint not found. Use Find available models and select a compatible chat model.'
    elif status>=500:hint='Service temporarily unavailable. Try again later.'
    else:hint='Request rejected. Check this model and its supported API features.'
    if key:detail=detail.replace(key,'[redacted]')
    detail=re.sub(r'(?i)(?:sk-[\w-]{4,}|AIza[\w-]{4,}|Bearer\s+\S+)','[redacted]',detail)
    detail=' '.join(detail.split())[:420]
    code=re.sub(r'[^A-Za-z0-9_.-]','',code)[:80]
    return f'{provider}: {hint} (HTTP {status}'+(f', {code}' if code else '')+').'+(f' Provider detail: {detail}' if detail else '')

def connection(provider,key,model='',endpoint=''):
    if not key:raise ValueError('Enter a key for the selected provider, or keep its saved key.')
    if provider=='gemini':
        model=(model or 'gemini-flash-latest').removeprefix('models/').strip()
        if not re.fullmatch(r'[A-Za-z0-9._-]{1,100}',model):raise ValueError('Enter the Gemini model ID, not a URL.')
        return 'https://generativelanguage.googleapis.com/v1beta',model,{'x-goog-api-key':key}
    base,model,_=validate(provider,model or PROVIDERS.get(provider,('','',False))[1] or 'catalog-placeholder',endpoint)
    headers={'x-api-key':key,'anthropic-version':'2023-06-01'} if provider=='anthropic' else {'Authorization':'Bearer '+key}
    return base,model,headers

def fetch(provider,key,method,url,headers,**kwargs):
    try:response=requests.request(method,url,headers=headers,timeout=(5,30),allow_redirects=False,**kwargs)
    except requests.RequestException:raise ValueError(f'{provider} could not be reached. Check internet access and the API endpoint.') from None
    if not 200<=response.status_code<300:raise ValueError(provider_error(provider,response,key))
    try:return response.json()
    except ValueError:raise ValueError(f'{provider} returned invalid API JSON. Check the configured endpoint.') from None

def discover(provider,key,model='',endpoint=''):
    base,_,headers=connection(provider,key,model,endpoint);models=[];page=''
    for _ in range(5):
        params={'pageSize':100,**({'pageToken':page} if page else {})} if provider=='gemini' else {'limit':100,**({'after_id':page} if page else {})} if provider=='anthropic' else {}
        data=fetch(provider,key,'GET',base+'/models',headers,params=params)
        entries=data.get('models' if provider=='gemini' else 'data',[])
        if not isinstance(entries,list):raise ValueError('This service does not provide a compatible model catalog. Enter its exact model ID manually.')
        for entry in entries:
            if not isinstance(entry,dict):continue
            identifier=str(entry.get('name' if provider=='gemini' else 'id','')).removeprefix('models/')
            if not re.fullmatch(r'[A-Za-z0-9._:/-]{1,150}',identifier):continue
            if provider=='gemini' and ('generateContent' not in entry.get('supportedGenerationMethods',[]) or not identifier.startswith('gemini') or any(x in identifier for x in ('tts','image'))):continue
            if provider=='openai' and (not re.match(r'^(gpt-|o\d)',identifier) or re.search(r'audio|realtime|transcrib|image|tts|search|instruct|codex|pro',identifier)):continue
            models.append(identifier)
        page=data.get('nextPageToken','') if provider=='gemini' else data.get('last_id','') if provider=='anthropic' and data.get('has_more') else ''
        if not page:break
    return sorted(set(models))[:1000]

def test_generation(provider,key,model,endpoint=''):
    base,model,headers=connection(provider,key,model,endpoint)
    if model=='catalog-placeholder':raise ValueError('Select a chat model before testing.')
    if provider=='gemini':route='/models/'+model+':generateContent';body={'contents':[{'role':'user','parts':[{'text':'Reply OK.'}]}],'generationConfig':{'maxOutputTokens':64}}
    elif provider=='anthropic':route='/messages';body={'model':model,'messages':[{'role':'user','content':'Reply OK.'}],'max_tokens':32}
    else:route='/chat/completions';body={'model':model,'messages':[{'role':'user','content':'Reply OK.'}],('max_completion_tokens' if provider=='openai' else 'max_tokens'):32}
    data=fetch(provider,key,'POST',base+route,headers,json=body)
    if not data.get('candidates' if provider=='gemini' else 'content' if provider=='anthropic' else 'choices'):
        raise ValueError('The provider returned no generation result. Check model compatibility.')
    return f'API test Passed: {provider} / {model}. Generation was accepted; voice and image support were not tested.'
