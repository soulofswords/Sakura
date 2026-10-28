from pathlib import Path
from native_chat_prompt import compact_chat_messages


def test_compaction_retains_conversation_evidence_and_independent_instructions():
    persona=(Path(__file__).resolve().parents[1]/'personality/sakura.txt').read_text(encoding='utf-8')
    messages=[{'role':'system','content':persona},
              {'role':'system','content':'Current PC clock: Tuesday, 27 October 2026.'},
              {'role':'system','content':'Selected speech language: Hindi. Reply in Hindi only.'},
              {'role':'system','content':'Earlier conversation notes: user prefers concise replies.'},
              {'role':'user','content':'The person we discussed is called SoulOfSwords.'},
              {'role':'assistant','content':'What would you like to know?'},
              {'role':'user','content':'I meant that guy.'}]
    result=compact_chat_messages(messages)
    assert len(result[0]['content'])<len(persona)*.35
    assert result[1:]==messages[1:]
    assert messages[0]['content']==persona
    assert 'tool result' in result[0]['content'] and 'untrusted' in result[0]['content']


def test_custom_system_instructions_are_not_rewritten():
    messages=[{'role':'system','content':'You are my tutor. Explain electronics in detail.'},
              {'role':'user','content':'Explain PWM.'}]
    assert compact_chat_messages(messages)==messages
