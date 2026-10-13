import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import app
from llm import LLM

class ScreenTests(unittest.TestCase):
    def test_vision_disables_thinking(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            llm = LLM(Path(folder) / 'memory.json')
            response = Mock()
            response.json.return_value = {'message': {'content': 'A blue cat.'}}
            with patch('llm.requests.post', return_value=response) as post:
                llm.screen_reaction('/9j/', True)
                self.assertFalse(post.call_args.kwargs['json']['think'])
                self.assertEqual(post.call_args.kwargs['json']['keep_alive'], '15m')

    def test_screen_failure_returns_readable_json(self):
        with patch.object(app, 'get_vision_status', return_value={'ready':True}), patch.object(app,'llm') as llm:
            llm.gemini_api_key = ''
            llm.screen_reaction.side_effect = ValueError('Ollama returned an empty response')
            response = TestClient(app.app).post('/api/chat', json={'text':'screen','screen_image':'/9j/',
                'screen_reaction':True,'screen_check':True,'defer_audio':True})
            self.assertEqual(response.status_code, 502)
            self.assertIn('empty response', response.json()['error'])

    def test_companion_reaction_does_not_change_memory(self):
        with tempfile.TemporaryDirectory() as folder:
            llm = LLM(Path(folder) / 'memory.json')
            with patch.object(llm, '_request', return_value='[QUIET]') as request:
                self.assertEqual(llm.screen_reaction('/9j/'), '[QUIET]')
                self.assertEqual(request.call_args.kwargs['model'], llm.vision_model)
                self.assertEqual(request.call_args.args[0][-1]['images'], ['/9j/'])
                self.assertEqual(llm.history, [])

    def test_screen_is_ephemeral_and_uses_vision_model(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'memory.json'
            llm=LLM(path)
            with patch.object(llm, '_request', return_value='A settings window.') as request:
                llm.chat('What is on my screen?', '/9j/')
                self.assertEqual(request.call_args.kwargs['model'], llm.vision_model)
                self.assertEqual(request.call_args.args[0][-1]['images'], ['/9j/'])
            self.assertNotIn('images', path.read_text())
            self.assertNotIn('/9j/', path.read_text())
            with patch.object(llm, '_request', return_value='Please turn on screen viewing.') as request:
                llm.chat('Can you see my screen now?')
                self.assertNotIn('images', request.call_args.args[0][-1])
                self.assertTrue(any('No current screen snapshot' in item['content']
                    for item in request.call_args.args[0]))

    def test_invalid_snapshot_does_not_reach_model(self):
        client=TestClient(app.app)
        for value in ['bad base64!', 'aGVsbG8=', 123, 'a' * 4_000_001]:
            with patch.object(app, 'llm') as llm:
                response=client.post('/api/chat',json={'text':'look','screen_image':value})
                self.assertEqual(response.status_code,400)
                llm.chat.assert_not_called()

    def test_vision_not_ready(self):
        with patch.object(app,'get_vision_status',return_value={'ready':False,'message':'Download vision model'}):
            response=TestClient(app.app).post('/api/chat',json={'text':'look','screen_image':'/9j/'})
            self.assertEqual(response.status_code,503)

    def test_screen_route_and_normal_chat(self):
        client=TestClient(app.app)
        with patch.object(app,'get_vision_status',return_value={'ready':True}), patch.object(app,'llm') as llm, patch.object(app,'tts') as tts:
            llm.chat.return_value='A settings window.'
            async def audio(_): return None
            tts.speak_to_file_async=audio
            response=client.post('/api/chat',json={'text':'look','screen_image':'/9j/'})
            self.assertEqual(response.status_code,200)
            llm.chat.assert_called_with('look','/9j/')
            client.post('/api/chat',json={'text':'hello'})
            llm.chat.assert_called_with('hello',None)

if __name__=='__main__': unittest.main()
