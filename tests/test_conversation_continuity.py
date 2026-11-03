from unittest.mock import patch
from llm import LLM
from conversation_modes import instruction

def test_short_followup_carries_recent_user_topic_for_both_providers(tmp_path):
    for provider in ('ollama','gemini'):
        model=LLM(tmp_path/(provider+'.json'));model.provider=provider;model.response_restriction_level='off'
        with patch('response_evidence.retrieve',return_value=None),patch.object(model,'_request',side_effect=['We can talk about that interview.','It helps you prepare clear examples.']) as call,patch.object(model,'_schedule_memory_refresh'):
            model.chat('I want to prepare for my electrical engineering interview.')
            model.chat('Why?')
        messages=call.call_args.args[0]
        assert any(row['role']=='assistant' and 'interview' in row['content'] for row in messages)
        assert 'electrical engineering interview' in messages[-1]['content']
        assert model.history[-1]['content']=='It helps you prepare clear examples.'

def test_style_preserves_continuity_without_forcing_questions():
    for mode in ('friend','teacher'):
        text=instruction(mode)
        assert 'Answer before asking' in text and 'do not reset' in text
