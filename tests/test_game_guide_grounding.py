from unittest.mock import patch
from llm import LLM


def test_game_guide_search_survives_supplied_screen(tmp_path):
    model=LLM(tmp_path/'memory.json')
    with patch('response_evidence.retrieve',return_value=None),patch('response_evidence.response_answer',return_value=None),patch('response_evidence.web_context',return_value='Web lookup: verified walkthrough.') as lookup,patch.object(model,'_request',return_value='Follow the marked quest route.') as request:
        model.chat('Give a walkthrough for this quest',screen_image='test-frame',game_name='GenshinImpact.exe')
    assert 'GenshinImpact.exe walkthrough:' in lookup.call_args.args[0]
    sent=request.call_args.args[0]
    assert any('Web lookup: verified walkthrough.' in m['content'] for m in sent)
    assert any('Reported foreground game application' in m['content'] for m in sent)


def test_visible_progress_is_not_a_round_win_and_is_rate_limited(tmp_path):
    model=LLM(tmp_path/'memory.json')
    with patch.object(model,'_screen_reaction_request',return_value='[GAME:PROGRESS] The scoreboard shows 3 kills.'),patch('llm.time.monotonic',return_value=100):
        first=model.screen_reaction('frame',game_watch=True,return_details=True)
    assert first=={'reply':'The scoreboard shows 3 kills.','game_result':None}
    with patch.object(model,'_screen_reaction_request',return_value='[GAME:PROGRESS] The scoreboard shows 4 kills.'),patch('llm.time.monotonic',return_value=110):
        assert model.screen_reaction('frame',game_watch=True)=='[QUIET]'
