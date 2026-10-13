import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from youtube_chat import video_id, YouTubeChat
from llm import LLM

class VTuberTests(unittest.TestCase):
    def test_supported_links_and_reject_other_hosts(self):
        for link in ['https://youtu.be/abcdefghijk', 'https://www.youtube.com/live/abcdefghijk',
                     'https://www.youtube.com/live_chat?v=abcdefghijk', 'abcdefghijk']:
            self.assertEqual(video_id(link), 'abcdefghijk')
        with self.assertRaises(ValueError):
            video_id('https://example.com/watch?v=abcdefghijk')

    def test_bounded_queue_and_disconnect(self):
        inbox = YouTubeChat()
        for index in range(100):
            inbox.messages.append({'id': str(index)})
        self.assertEqual(len(inbox.poll()['messages']), 30)
        self.assertEqual(inbox.poll()['messages'], [])
        inbox.stop()
        self.assertFalse(inbox.connected)

    def test_viewer_reply_isolated_from_private_memory(self):
        with tempfile.TemporaryDirectory() as folder:
            llm = LLM(Path(folder) / 'memory.json')
            llm.history = [{'role': 'user', 'content': 'private secret'}]
            with patch.object(llm, '_request', return_value='Hi viewer!') as request:
                self.assertEqual(llm.viewer_reply('viewer', 'hello'), 'Hi viewer!')
                messages = request.call_args.args[0]
                self.assertNotIn('private secret', str(messages))
                self.assertIn('untrusted', messages[0]['content'])
                self.assertEqual(len(llm.history), 1)
                self.assertIn('Never address anyone as Master', messages[0]['content'])

    def test_cohost_screen_prompt_uses_audience_address(self):
        with tempfile.TemporaryDirectory() as folder:
            llm=LLM(Path(folder)/'memory.json')
            with patch.object(llm,'_request',return_value='Nice play!') as request:
                llm.screen_reaction('image',cohost=True)
                self.assertIn('Never say Master or Beta',request.call_args.args[0][0]['content'])
