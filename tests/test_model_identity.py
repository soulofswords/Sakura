from types import SimpleNamespace
from model_identity import identity_reply

def test_runtime_identity_uses_actual_provider_not_a_generated_name():
    model=SimpleNamespace(provider='ollama',model='qwen3-vl:4b-instruct',vision_model='qwen3-vl:4b-instruct',last_backend='ollama',cloud_api_key='DO-NOT-DISPLAY')
    result=identity_reply('What model are you using by the way?',model,{})
    assert 'qwen3-vl:4b-instruct' in result['reply'] and 'GPT' not in result['reply']
    assert 'DO-NOT-DISPLAY' not in str(result)
    model.provider='gemini';model.gemini_model='configured-gemini';model.last_backend='gemini'
    assert 'configured-gemini' in identity_reply('Which LLM are you using?',model,{})['reply']
    assert identity_reply('What colour is this avatar?',model,{}) is None
    assert identity_reply('Which LLM should I download?',model,{}) is None

def test_native_and_vision_configuration_are_distinguished():
    model=SimpleNamespace(provider='ollama',model='sakura-native:Qwen-large.gguf',vision_model='qwen3-vl:4b',last_backend='gemini')
    reply=identity_reply('which model are you running?',model,{})['reply']
    assert 'Qwen-large.gguf' in reply and 'qwen3-vl:4b' in reply and 'last recorded' in reply and 'gemini' in reply

def test_unknown_configuration_is_not_invented():
    assert 'cannot confirm' in identity_reply('what model are you using?',None,{})['reply']

def test_chat_core_answers_identity_without_calling_the_llm(monkeypatch):
    import asyncio
    import app
    from unittest.mock import Mock
    model=SimpleNamespace(provider='ollama',model='real-qwen-model',vision_model='vision-qwen',chat=Mock())
    monkeypatch.setattr(app,'llm',model)
    monkeypatch.setattr(app,'get_settings',lambda:{'llm_provider':'ollama'})
    result=asyncio.run(app._chat_core({'text':'What model are you using by the way?','defer_audio':True}))
    assert result['response_kind']=='model_identity' and 'real-qwen-model' in result['reply']
    model.chat.assert_not_called()
