"""Voice-reachable NVIDIA Broadcast effects over an explicitly configured MCP connection.

Only the set_effects tool is callable, only for the effects listed in EFFECTS, and only with
parameters inside the bounds Broadcast itself publishes. An effect change is applied straight
away because naming the effect out loud is the consent; the MCP connection has to have been
added by the user already, and computer access has to be enabled.
"""
import re

# Excluded on purpose: background_replace needs an absolute image path, video_super_resolution
# needs output dimensions, video_frame_generation is not in the settable effect list.
EFFECTS={
    'background_blur':{'label':'Background blur','pct':'strength'},
    'background_remove':{'label':'Background removal','pct':None},
    'vignette':{'label':'Vignette','pct':'strength'},
    'eye_contact':{'label':'Eye contact','pct':None},
    'auto_frame':{'label':'Auto frame','pct':'zoom'},
    'video_noise_removal':{'label':'Video noise removal','pct':None},
    'virtual_key_light':{'label':'Virtual key light','pct':None},
    'studio_voice':{'label':'Studio voice','pct':None,'profile':'micProfile'},
    'noise_removal':{'label':'Microphone noise removal','pct':'strength'},
    'room_echo_removal':{'label':'Room echo removal','pct':'strength'},
    'speaker_noise_removal':{'label':'Speaker noise removal','pct':'strength'},
    'speaker_echo_removal':{'label':'Speaker echo removal','pct':'strength'},
    'background_replace':{'label':'Background replacement','pct':None,'needs_asset':True},
}

# Regex fragments, matched after the lead verb and before the trailing particle.
_ALIASES=[
    (r'remove (?:my |the |your )?background(?! noise)|background remover(?:val)?|background removal|cut out (?:my |the )?background','background_remove'),
    (r'replace (?:my |the |your )?background|background replace(?:ment)?|swap (?:my |the )?background','background_replace'),
    (r'background bl(?:ur|urring)|blurred background|blur(?:ring|red)?','background_blur'),
    (r'(?:remove|kill|reduce) (?:the )?(?:video|camera) noise|(?:video|camera) noise (?:removal|reduction|remover)?','video_noise_removal'),
    (r'(?:virtual )?key light(?:ing)?','virtual_key_light'),
    (r'auto ?fram(?:e|ing)|autoframe|frame me automatically','auto_frame'),
    (r'(?:keep |steady )?eye contact','eye_contact'),
    (r'vignette','vignette'),
    (r'studio (?:voice|sound)','studio_voice'),
    (r'(?:remove|kill|reduce|cut) (?:my |the |your |background )?noise|(?:mic|microphone )?noise (?:removal|reduction|cancellation|canceller)|background noise','noise_removal'),
    (r'(?:remove|kill|reduce) (?:the )?noise (?:from|on) (?:my |the )?speakers|speaker noise(?: removal)?|noise (?:from|on) (?:my |the )?speakers','speaker_noise_removal'),
    (r'(?:remove|kill|reduce) (?:the )?echo (?:from|on) (?:my |the )?speakers|speaker echo(?: removal)?','speaker_echo_removal'),
    (r'(?:remove|kill|reduce) (?:my |the |room )?echo|room echo(?: removal)?|echo (?:removal|reduction)|mic echo','room_echo_removal'),
]

# A speaker phrase under a microphone effect (or the reverse) re-resolves to that section.
_SECTION_SWAP={'noise_removal':'speaker_noise_removal','room_echo_removal':'speaker_echo_removal',
               'speaker_noise_removal':'noise_removal','speaker_echo_removal':'room_echo_removal'}
_SPEAKER=re.compile(r'\b(?:speakers?|headphones?)\b')
_POLITE=r'please|kindly|just|also|then|now|go ahead and|can you|could you|would you|will you|try to|i want (?:you to|to)'
_VERB=r'turn(?: the| my)?|switch(?: the| my)?|set|put|make|enable|disable|stop|deactivate|start|activate|apply|use'
_OFF_VERBS=('disable','stop','deactivate')
_PREFIX=(r'^(?:(?:'+_POLITE+r')\s+)*(?:(?P<verb>'+_VERB+r')\s+)?(?:(?P<lead>on|off)\s+)?'
         r'(?:(?:my|the|your|nvidia|system|broadcast)\s+)?')
_OBJECT=r'(?: (?:my|the|your) (?:camera |face )?(?:background|voice|mic|microphone|speakers|audio))?'
_SUFFIX=r'(?: (?:please|now|for me|when you can|thanks|thank you))*[ .!?]*$'
_TAIL=r'(?P<tail> on| off)?'+_OBJECT+r'(?P<zone>(?: (?:from|for|in|of) (?:my|the|your)? ?' \
      r'(?:mic|microphone|headset|speakers|speaker|headphones|camera|voice|audio))?)' \
      r'(?P<profile> (?:bright|full|warm|default))?'+_SUFFIX


def _percent(text):
    match=re.search(r'\b(?:(?:to|at|by)\s+)?(\d{1,3})\s*(?:%|percent)(?![a-z0-9])',text)
    if not match:match=re.search(r'\b(?:to|at)\s*(\d{1,3})\b(?!\s*(?:am|pm|oclock))[ ,]*$',text)
    if not match:return None,text
    value=int(match.group(1))
    if not 0<=value<=100:raise ValueError('Choose an effect strength from 0 to 100 percent.')
    return value/100,(text[:match.start()]+' '+text[match.end():]).strip()


def classify(text):
    """Return {'changes':[{effect,enabled,params}]} for an effect request, otherwise None."""
    t=re.sub(r'\s+',' ',str(text).lower().replace('’',"'")).strip(' .!?,')
    if not t:return None
    if re.match(r'(?:how|why|what|when|whether|is|are|was|do|does|did|tell|explain)\b',t) \
            and not re.search(r'\b(?:turn|switch|set|put|enable|disable|start|stop|activate|apply)\b',t):return None
    amount,t=_percent(t)
    t=re.sub(r'\s+',' ',t).strip(' .,!?')
    for names,effect in _ALIASES:
        match=re.fullmatch(_PREFIX+'(?:'+names+')'+_TAIL,t,re.I)
        if not match:continue
        spec=EFFECTS[effect]
        verb=(match.group('verb') or '').split()[0] if match.group('verb') else ''
        off=match.group('lead')=='off' or (match.group('tail') or '')==' off' or verb in _OFF_VERBS
        enabled=not off
        zone=match.group('zone') or ''
        if _SPEAKER.search(zone) and effect in _SECTION_SWAP:effect,spec=_SECTION_SWAP[effect],EFFECTS[_SECTION_SWAP[effect]]
        params={}
        if amount is not None:
            if not spec['pct']:raise ValueError(spec['label']+' has no strength setting in NVIDIA Broadcast.')
            params[spec['pct']]=round(amount,3)
            enabled=True
        if spec.get('profile') and enabled and match.group('profile'):
            params[spec['profile']]=match.group('profile').strip()
        if spec.get('needs_asset') and enabled:return {'changes':[],'needs_asset':effect}
        return {'changes':[{'effect':effect,'enabled':enabled,'params':params}]}
    return None


def _describe(change):
    spec=EFFECTS[change['effect']]
    params=change.get('params') or {}
    if not change['enabled']:return spec['label']+' is off.'
    for key in ('strength','zoom'):
        if key in params:return spec['label']+' is on at '+str(round(100*params[key]))+' percent.'
    if 'micProfile' in params:return spec['label']+' is on with the '+params['micProfile']+' profile.'
    return spec['label']+' is on.'


def _connection():
    from agent_connections import Connections
    for config in Connections().all().values():
        if config.get('transport')!='http':continue
        url=str(config.get('url',''))
        from urllib.parse import urlsplit
        try:parsed=urlsplit(url);trusted=parsed.scheme=='http' and parsed.hostname in ('127.0.0.1','localhost','::1') and parsed.port==18100 and parsed.path.rstrip('/')=='/gateway' and not parsed.username and not parsed.password
        except ValueError:trusted=False
        if trusted:
            return config
    return None


def apply(changes):
    from agent_connections import mcp_request
    from agent_runtime import digest
    config=_connection()
    if config is None:
        return {'ok':False,'reply':'I could not find an NVIDIA Broadcast connection. Add it under Agent mode > MCP connections, keep NVIDIA Broadcast open, then ask me again.'}
    try:
        tools=mcp_request(config,'discover')
    except Exception as error:
        return {'ok':False,'reply':'NVIDIA Broadcast is not reachable right now. Open the app and try again. ('+str(error)[:100]+')'}
    selected=next((item for item in tools if item['name']=='set_effects'),None)
    if selected is None:return {'ok':False,'reply':'That MCP connection does not offer NVIDIA Broadcast effects.'}
    effects=[]
    for change in changes:
        spec=EFFECTS.get(change['effect'])
        if not spec:return {'ok':False,'reply':'That is not one of the effects I am allowed to change.'}
        allowed=[]
        if spec['pct']:allowed.append(spec['pct'])
        if spec.get('profile'):allowed.append(spec['profile'])
        params=change.get('params') or {}
        if any(key not in allowed for key in params):return {'ok':False,'reply':'NVIDIA Broadcast does not take that setting for '+spec['label']+'.'}
        for key in ('strength','zoom'):
            if key in params:
                value=params[key]
                if not isinstance(value,(int,float)) or not 0<=float(value)<=1:
                    return {'ok':False,'reply':'Effect strength must be between 0 and 100 percent.'}
        argument={'effectId':change['effect'],'enabled':bool(change['enabled'])}
        if params:argument['params']=dict(params)
        effects.append(argument)
    if not effects:return {'ok':False,'reply':'Tell me which NVIDIA Broadcast effect to change.'}
    try:
        result=mcp_request(config,'call',tool='set_effects',arguments={'effects':effects},schema_hash=digest(selected['inputSchema']))
    except Exception as error:
        return {'ok':False,'reply':'NVIDIA Broadcast did not apply that change. ('+str(error)[:100]+')'}
    if result.get('is_error'):
        detail=' '.join(str(item.get('text','')) for item in result.get('content',[]) if item.get('type')=='text')[:120]
        return {'ok':False,'reply':'NVIDIA Broadcast refused that change.'+((' '+detail) if detail else '')}
    return {'ok':True,'reply':' '.join(_describe(change) for change in changes),'data':{'connection':config['id'],'effects':effects}}


ASSET_HELP='I can turn background replacement off by voice, but picking a new image needs its file path. Ask me to blur or remove the background instead, or set the image in NVIDIA Broadcast.'


def handle_request(request):
    """Apply what classify() decided; this is the only path that reaches the network."""
    if request.get('needs_asset'):return {'ok':False,'reply':ASSET_HELP}
    return apply(request['changes'])
