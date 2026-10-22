import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from llm import LLM

class GameLaugh(unittest.TestCase):
    def test_laugh_protocol_survives_language_and_context_fit(self):
        with tempfile.TemporaryDirectory() as folder:
            model=LLM(Path(folder)/'memory.json');model.reply_language='Hindi'
            for tag in ('MISS','REPEATED_MISS','DEATH'):
                with patch.object(model,'_request_raw',return_value=f'[GAME:{tag}] Next round!') as raw:
                    reply=model._screen_reaction_request('image',screen_frames=['one','two'])
                    self.assertTrue(reply.startswith(f'[GAME:{tag}]'))
                    self.assertTrue(raw.call_args.kwargs['structured'])
                    fitted=model._fit_local_messages(raw.call_args.args[0],4096,160)
                    self.assertIn(f'[GAME:{tag}]','\n'.join(m['content'] for m in fitted if m['role']=='system'))

    def test_laugh_requires_evidence_and_new_event(self):
        with tempfile.TemporaryDirectory() as folder:
            model=LLM(Path(folder)/'memory.json')
            def observe(now,tag,frames=None,initial=False):
                with patch('llm.time.monotonic',return_value=now),patch.object(model,'_screen_reaction_request',return_value=tag):
                    return model.screen_reaction('image',initial,game_watch=True,return_details=True,screen_frames=frames)
            self.assertIsNone(observe(100,'[GAME:MISS] That shot escaped.')['game_result'])
            first=observe(101,'[GAME:MISS] That shot escaped.',['one','two'])
            self.assertEqual(first['game_result'],'laugh');self.assertEqual(first['reply'],'That shot escaped.')
            self.assertEqual(observe(140,'[GAME:MISS] That shot escaped again.',['one','two'])['reply'],'[QUIET]')
            observe(141,'[GAME:NONE] [QUIET]')
            self.assertIsNone(observe(150,'[GAME:DEATH] Next round!')['game_result'],'Cooldown prevents repeated taunts')
            observe(230,'[GAME:NONE] [QUIET]')
            deep=observe(300,'[GAME:REPEATED_MISS] The wall survived.',['one','two','three'])
            self.assertEqual(deep['game_result'],'laugh_bend')
            observe(301,'[GAME:NONE] [QUIET]')
            self.assertEqual(observe(400,'[GAME:DEATH] A fresh start next round.')['game_result'],'laugh_bend')
            observe(401,'[GAME:NONE] [QUIET]')
            self.assertIsNone(observe(600,'[GAME:DEATH] Next round!',initial=True)['game_result'])
            self.assertEqual(model.history,[])

if __name__=='__main__':unittest.main()
