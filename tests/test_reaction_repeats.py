import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from llm import LLM

class ReactionRepeatTests(unittest.TestCase):
    def test_game_classification_not_overridden_by_speech_only_prompt(self):
        with tempfile.TemporaryDirectory() as folder:
            model=LLM(Path(folder)/'memory.json');model.reply_language='Hindi'
            with patch.object(model,'_request_raw',return_value='[GAME:VICTORY] जीत गए!') as raw:
                reply=model._screen_reaction_request('image')
                self.assertTrue(reply.startswith('[GAME:VICTORY]'))
                self.assertTrue(raw.call_args.kwargs['structured'])
                self.assertIn('Keep the classification prefix exactly in English',raw.call_args.args[0][1]['content'])
                fitted=model._fit_local_messages(raw.call_args.args[0],4096,160)
                rules='\n'.join(m['content'] for m in fitted if m['role']=='system')
                self.assertIn('[GAME:VICTORY]',rules,'Result protocol survives local context compaction')
    def test_game_result_detected_during_recent_conversation_without_interrupting(self):
        with tempfile.TemporaryDirectory() as folder:
            model=LLM(Path(folder)/'memory.json');model._last_direct_reply_at=100
            with patch('llm.time.monotonic',return_value=105),patch.object(model,'_screen_reaction_request',return_value='[GAME:VICTORY] You won!'):
                result=model.screen_reaction('image',game_watch=True,return_details=True)
                self.assertEqual(result,{'reply':'[QUIET]','game_result':'victory'})
            with patch('llm.time.monotonic',return_value=110),patch.object(model,'_screen_reaction_request',return_value='[GAME:VICTORY] Great win!'):
                self.assertIsNone(model.screen_reaction('image',game_watch=True,return_details=True)['game_result'])
    def test_saved_stage_name_used_for_viewers_and_screen_cohost_only(self):
        with tempfile.TemporaryDirectory() as folder:
            model=LLM(Path(folder)/'memory.json');model.set_vtuber_name('Luna Star')
            with patch.object(model,'_request',return_value='Hello!') as infer:
                self.assertIn('Luna Star',model.viewer_reply('Viewer','What is your name?'))
                infer.assert_not_called()
                model._screen_reaction_request('image',cohost=True)
                self.assertIn('"Luna Star"',infer.call_args.args[0][1]['content'])
                model._screen_reaction_request('image',cohost=False)
                self.assertNotIn('"Luna Star"',infer.call_args.args[0][1]['content'])
                infer.reset_mock()
                self.assertIn('Luna Star',model.chat('What is your name?',cohost=True))
                infer.assert_not_called()
            self.assertEqual(model.assistant_name,'Sakura')
    def test_background_repeated_paragraph_is_silent(self):
        repeated="I'm just here to help you keep it going. I've been working on the code cleanup and model switching. "*2
        with tempfile.TemporaryDirectory() as folder:
            model=LLM(Path(folder)/'memory.json')
            with patch.object(model,'_screen_reaction_request',return_value=repeated):
                self.assertEqual(model.screen_reaction('image'),'[QUIET]')
            with patch.object(model,'_request',return_value=repeated):
                self.assertEqual(model.viewer_reply('Viewer','Hello'),'Hello!')
    def test_game_result_is_structured_once_per_visible_event(self):
        with tempfile.TemporaryDirectory() as folder:
            model=LLM(Path(folder)/'memory.json')
            def observe(now,draft,initial=False):
                with patch('llm.time.monotonic',return_value=now),patch.object(model,'_screen_reaction_request',return_value=draft):
                    return model.screen_reaction('image',initial,return_details=True)
            first=observe(100,'[GAME:VICTORY] You won that round!')
            self.assertEqual(first,{'reply':'You won that round!','game_result':'victory'})
            self.assertEqual(observe(200,'[GAME:VICTORY] Great victory!')['reply'],'[QUIET]')
            self.assertEqual(observe(231,'[GAME:NONE] [QUIET]')['game_result'],None)
            self.assertEqual(observe(262,'[GAME:DEFEAT] Tough round. Next one is yours.')['game_result'],'defeat')
            self.assertIsNone(observe(300,'[GAME:VICTORY] You took the next round!')['game_result'],'Rate limit prevents rapid repeated jumps')
            self.assertIsNone(observe(400,'[GAME:VICTORY] A victory banner is visible.',True)['game_result'],'Initial screen confirmation does not animate')
            self.assertEqual(model.history,[])

    def test_unstructured_praise_cannot_trigger_game_animation(self):
        with tempfile.TemporaryDirectory() as folder:
            model=LLM(Path(folder)/'memory.json')
            with patch.object(model,'_screen_reaction_request',return_value='You won! Victory!'):
                self.assertIsNone(model.screen_reaction('image',return_details=True)['game_result'])

    def test_direct_conversation_pauses_background_for_all_clients(self):
        with tempfile.TemporaryDirectory() as folder:
            llm=LLM(Path(folder)/'memory.json')
            with patch('llm.time.monotonic',return_value=100),patch.object(llm,'_request',return_value='The installer is still running.'):
                llm.chat('Is it finished?')
            with patch('llm.time.monotonic',return_value=110),patch.object(llm,'_screen_reaction_request') as request:
                self.assertEqual(llm.screen_reaction('image'),'[QUIET]')
                request.assert_not_called()
            with patch('llm.time.monotonic',return_value=131),patch.object(llm,'_screen_reaction_request',return_value='The installer completed.'):
                self.assertEqual(llm.screen_reaction('image'),'The installer completed.')

    def test_direct_reply_during_inference_cancels_background_reply(self):
        with tempfile.TemporaryDirectory() as folder:
            llm=LLM(Path(folder)/'memory.json')
            def infer(*args):
                llm._last_direct_reply_at=100
                return 'Hello, I am Sakura.'
            with patch('llm.time.monotonic',return_value=100),patch.object(llm,'_screen_reaction_request',side_effect=infer):
                self.assertEqual(llm.screen_reaction('image'),'[QUIET]')
            self.assertEqual(llm._recent_reactions,[])
    def test_cooldown_repeat_context_and_new_event(self):
        with tempfile.TemporaryDirectory() as folder:
            llm = LLM(Path(folder) / 'memory.json')
            with patch('llm.time.monotonic', return_value=100), patch.object(llm, '_request', return_value='Master, that was an amazing shot!') as request:
                self.assertIn('amazing', llm.screen_reaction('image'))
                self.assertEqual(llm.screen_reaction('image'), '[QUIET]')
                self.assertEqual(request.call_count, 1)
            with patch('llm.time.monotonic', return_value=131), patch.object(llm, '_request', return_value='Wow, that was an amazing shot, Master!') as request:
                self.assertEqual(llm.screen_reaction('image'), '[QUIET]')
                self.assertIn('that was an amazing shot', request.call_args.args[0][1]['content'])
            with patch('llm.time.monotonic', return_value=162), patch.object(llm, '_request', return_value='The exit just opened on your left.'):
                self.assertEqual(llm.screen_reaction('image'), 'The exit just opened on your left.')
            self.assertEqual(llm.history, [])

    def test_initial_check_bypasses_cooldown(self):
        with tempfile.TemporaryDirectory() as folder:
            llm = LLM(Path(folder) / 'memory.json')
            with patch.object(llm, '_request', return_value='I can see the game menu.'):
                llm.screen_reaction('image')
                self.assertNotEqual(llm.screen_reaction('image', True), '[QUIET]')
