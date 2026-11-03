"""Model identity comes from runtime configuration, never model-generated claims."""
import re

QUESTION=re.compile(r"\b(?:what|which)\s+(?:(?:ai|llm|language|local|cloud)\s+)?(?:model|llm)\s+(?:are\s+(?:you|u)\s+(?:using|running)|do\s+(?:you|u)\s+use|powers\s+you|is\s+active)|\b(?:what(?:'s| is)|tell me)\s+your\s+(?:llm|language model)(?:\s+name)?\b",re.I)

def identity_reply(text,model,settings):
    if not QUESTION.search(str(text)):return None
    def field(name,fallback=''):
        value=getattr(model,name,None)
        return value[:160] if isinstance(value,str) and value else str(fallback or '')[:160]
    provider=field('provider',settings.get('llm_provider',''))
    if provider=='gemini':name=field('gemini_model',settings.get('gemini_model'))
    elif provider=='ollama':name=field('model',settings.get('ollama_model'))
    else:name=field('cloud_model',settings.get('cloud_model'))
    if not name:return {'reply':'I cannot confirm the configured LLM name. Check Settings → AI & LLM.','response_kind':'model_identity','audio':None}
    backend='Sakura Local AI' if name.startswith('sakura-native:') else (provider or 'the selected backend')
    reply='Text chat is configured to use '+name.removeprefix('sakura-native:')+' through '+backend+'.'
    vision=field('vision_model') if provider=='ollama' else ''
    if vision and vision!=name:reply+=' Screen and camera requests use '+vision+'.'
    last=field('last_backend')
    if last and last not in (provider,'sakura-native'):reply+=' The last recorded request backend was '+last+' (for example, a fallback).'
    return {'reply':reply,'response_kind':'model_identity','audio':None,'model_identity':{'provider':provider,'model':name,'vision_model':vision}}
