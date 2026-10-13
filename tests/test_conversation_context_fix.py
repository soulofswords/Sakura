import base64
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from llm import LLM
from vision_context import combine_screen_avatar

class ConversationContextFix(unittest.TestCase):
    def test_small_context_keeps_recent_followup(self):
        history=[{'role':'system','content':'You are Sakura. '+('Long personality. '*500)},
            {'role':'user','content':'Can you dance?'},{'role':'assistant','content':'I can play a short dance.'},
            {'role':'user','content':'Just do what you have. I want to see that.'}]
        fitted=LLM._fit_local_messages(history,2048,128)
        self.assertEqual(fitted[1:],history[1:])
    def test_action_history_is_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'memory.json';llm=LLM(path);llm.remember_exchange('make u dance','Here comes a little dance.')
            self.assertEqual(LLM(path).history[0]['content'],'make u dance')
    def test_two_views_are_one_bounded_image(self):
        def encode(color):
            data=BytesIO();Image.new('RGB',(1920,1080),color).save(data,format='JPEG');return base64.b64encode(data.getvalue()).decode()
        result=combine_screen_avatar(encode('red'),encode('blue'))
        image=Image.open(BytesIO(base64.b64decode(result)));self.assertLessEqual(image.width,1624);self.assertLessEqual(image.height,832)
        self.assertGreater(image.getpixel((100,100))[0],240);self.assertGreater(image.getpixel((1000,100))[2],240)
    def test_latest_question_and_avatar_reach_chat(self):
        with tempfile.TemporaryDirectory() as directory:
            llm=LLM(Path(directory)/'memory.json');llm.history=[{'role':'user','content':'What is on screen?'},{'role':'assistant','content':'A download at 36%.'}]
            with patch('vision_context.combine_screen_avatar',return_value='combined'),patch.object(llm,'_request',return_value='Your avatar has pink hair.') as request:
                llm.chat('You do not see a pink hair girl here?', 'screen', 'avatar')
            sent=request.call_args.args[0];self.assertEqual(sent[-1]['images'],['combined']);self.assertIn('pink hair',sent[-1]['content']);self.assertTrue(any('latest user question first' in m['content'] for m in sent))
