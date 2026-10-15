"""Kokoro preset catalog and migration of previously saved online selections."""
DEFAULT_VOICE_ID='kokoro_af_heart'
VOICE_PRESETS=[]
_female=['af_heart','af_bella','af_nicole','af_aoede','af_kore','af_sarah','af_nova','bf_emma','bf_isabella','bf_alice']
_male=['am_michael','am_fenrir','am_puck','am_echo','am_onyx','am_eric','bm_george','bm_fable','bm_lewis','bm_daniel']
for gender,voices in [('Female',_female),('Male',_male)]:
    for voice in voices:
        name=voice.split('_',1)[1].title()
        if voice=='af_heart':name='Sakura · Heart'
        british=voice.startswith('b')
        VOICE_PRESETS.append({'id':'kokoro_'+voice,'name':name,'voice':voice,'backend':'kokoro','gender':gender,
            'language':'English','kokoro_language':'en-gb' if british else 'en-us','rate':'+0%','pitch':'+0Hz',
            'desc':f"Local Kokoro · {gender} · {'British' if british else 'American'} English"})
VOICE_PRESETS += [
    {'id':'kokoro_hf_alpha_hindi','name':'Alpha · Hindi','voice':'hf_alpha','backend':'kokoro','gender':'Female','language':'Hindi','kokoro_language':'hi','rate':'+0%','pitch':'+0Hz','desc':'Local Kokoro · Hindi'},
    {'id':'kokoro_hf_beta_hinglish','name':'Beta · Hinglish','voice':'hf_beta','backend':'kokoro','gender':'Female','language':'Hinglish','kokoro_language':'hi','rate':'+0%','pitch':'+0Hz','desc':'Local Kokoro · Hindi and English mixed conversation'},
    {'id':'rvc_custom','name':'Custom RVC','voice':'rvc','gender':'Custom','language':'English','rate':'+0%','pitch':'+0Hz','desc':'Imported RVC voice; local Kokoro base speech'},
]
_old_female=['sakura_ava','emma_energetic','jenny_companion','michelle_soft','sonia_maid','aria_confident','libby_english','natasha_english','clara_english','ana_english']
_old_male=['guy_english','andrew_english','brian_english','christopher_english','eric_english','roger_english','steffan_english','ryan_english','thomas_english','liam_english']
VOICE_ALIASES={old:'kokoro_'+new for old,new in zip(_old_female+_old_male,_female+_male)}
VOICE_ALIASES.update({'swara_hindi':'kokoro_hf_alpha_hindi','neerja_hinglish':'kokoro_hf_beta_hinglish','nanami_japanese':'kokoro_bf_alice'})
# Direct Edge voice IDs were also supported by older releases.
_old_names=['en-US-AvaNeural','en-US-EmmaNeural','en-US-JennyNeural','en-US-MichelleNeural','en-GB-SoniaNeural','en-US-AriaNeural','en-GB-LibbyNeural','en-AU-NatashaNeural','en-CA-ClaraNeural','en-US-AnaNeural',
    'en-US-GuyNeural','en-US-AndrewNeural','en-US-BrianNeural','en-US-ChristopherNeural','en-US-EricNeural','en-US-RogerNeural','en-US-SteffanNeural','en-GB-RyanNeural','en-GB-ThomasNeural','en-CA-LiamNeural']
VOICE_ALIASES.update({old:'kokoro_'+new for old,new in zip(_old_names,_female+_male)})
VOICE_ALIASES.update({'hi-IN-SwaraNeural':'kokoro_hf_alpha_hindi','en-IN-NeerjaExpressiveNeural':'kokoro_hf_beta_hinglish'})


def canonical_voice_id(value):
    if not isinstance(value,str):return DEFAULT_VOICE_ID
    selected=VOICE_ALIASES.get(value,value)
    if selected.startswith(('rvc_','system_')) or any(p['id']==selected for p in VOICE_PRESETS):return selected
    return DEFAULT_VOICE_ID


def voice_language(preset_id):
    if str(preset_id).startswith('system_hi_'):return 'Hindi'
    preset_id=canonical_voice_id(preset_id)
    return next((p['language'] for p in VOICE_PRESETS if p['id']==preset_id),'English')
