import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from llm import LLM

class ContextTests(unittest.TestCase):
    def test_instruction_growth_does_not_erase_recent_topic(self):
        messages=[{'role':'system','content':'You are Sakura. '+('Personality. '*700)},
                  {'role':'system','content':'Dialogue rules. '*110},
                  {'role':'system','content':'Current identity. '*30},
                  {'role':'user','content':'The game update has downloaded and is verifying files.'},
                  {'role':'user','content':'What are we doing right now?'}]
        fitted=LLM._fit_local_messages(messages,2048,192)
        self.assertEqual(fitted[-2:],messages[-2:])
        self.assertLessEqual(sum(len(m['content'].encode())/2+32 for m in fitted),1600)
    def test_small_context_reserves_reply_and_retains_latest_user(self):
        messages=[{'role':'system','content':'You are Sakura. '+('Long personality. '*400)}]
        messages += [{'role': 'user' if i%2==0 else 'assistant', 'content':'Earlier dialogue. '*100} for i in range(20)]
        messages += [{'role':'user','content':'hello'}, {'role':'system','content':'Reply in English only. Your current name is Myra.'}]
        original=[dict(m) for m in messages]
        fitted=LLM._fit_local_messages(messages,2048,128)
        self.assertEqual(fitted[-1],{'role':'user','content':'hello'})
        self.assertEqual(fitted[0]['role'],'system')
        self.assertIn('Your current name is Myra.',fitted[0]['content'])
        self.assertLess(sum(len(m['content'].encode())/3+16 for m in fitted),1664)
        self.assertEqual(messages,original)

    def test_images_and_large_context_personality_preserved(self):
        messages=[{'role':'system','content':'Full authored personality'}, {'role':'user','content':'What is visible?', 'images':['image-data']}]
        fitted=LLM._fit_local_messages(messages,4096,160)
        self.assertEqual(fitted,messages)

    def test_arbitrary_instructions_and_large_multilingual_input_fit(self):
        messages = [{'role':'system','content':'Unusual instructions ' * 2000},
                    {'role':'user','content':'こんにちは' * 3000 + ' Latest question?'}]
        fitted = LLM._fit_local_messages(messages, 4096, 128)
        self.assertLessEqual(sum(len(m['content'].encode()) / 2 + 32 for m in fitted), 3712)
        self.assertIn('Latest question?', fitted[-1]['content'])
        self.assertEqual(len(messages[-1]['content']), 15017)

    def test_multiple_images_keep_newest_without_mutating_input(self):
        messages = [{'role':'system','content':'Answer the latest question.'},
                    {'role':'user','content':'What changed?', 'images':['old','middle','latest']}]
        fitted = LLM._fit_local_messages(messages, 4096, 160)
        self.assertEqual(fitted[-1]['images'], ['middle','latest'])
        self.assertEqual(messages[-1]['images'], ['old','middle','latest'])

    def test_reported_context_overflow_retries_once(self):
        failure = Mock(status_code=400)
        failure.json.return_value = {'error': {'code':400,
            'message':'request (5957 tokens) exceeds the available context size (4096 tokens)',
            'type':'exceed_context_size_error','n_prompt_tokens':5957,'n_ctx':4096}}
        success = Mock(status_code=200)
        success.json.return_value = {'message':{'content':'Here is the answer.'}}
        with tempfile.TemporaryDirectory() as folder:
            llm = LLM(Path(folder) / 'memory.json')
            messages = [{'role':'user','content':'earlier '*1500},
                        {'role':'assistant','content':'old reply '*1500},
                        {'role':'user','content':'Latest question?'}]
            with patch('llm.requests.post', side_effect=[failure, success]) as post:
                self.assertEqual(llm._request_raw(messages), 'Here is the answer.')
                self.assertEqual(post.call_count, 2)
                retry = post.call_args.kwargs['json']
                self.assertEqual(retry['messages'][-1]['content'], 'Latest question?')
                self.assertEqual(retry['options']['num_ctx'], 4096)
            with patch('llm.requests.post', return_value=failure) as post:
                with self.assertRaises(ValueError): llm._request_raw(messages)
                self.assertEqual(post.call_count, 2)

    def test_unrelated_400_does_not_retry(self):
        response = Mock(status_code=400)
        response.json.return_value = {'error':'model does not support images'}
        with tempfile.TemporaryDirectory() as folder:
            llm = LLM(Path(folder) / 'memory.json')
            with patch('llm.requests.post', return_value=response) as post:
                with self.assertRaises(ValueError):
                    llm._request_raw([{'role':'user','content':'hello'}])
                self.assertEqual(post.call_count, 1)

    def test_vision_overflow_downsamples_latest_frame_on_retry(self):
        import base64
        from io import BytesIO
        from PIL import Image
        data = BytesIO()
        Image.new('RGB', (1624,832), 'blue').save(data, format='JPEG')
        original = base64.b64encode(data.getvalue()).decode()
        failure = Mock(status_code=400)
        failure.json.return_value = {'error': {'type':'exceed_context_size_error', 'n_ctx':4096}}
        success = Mock(status_code=200)
        success.json.return_value = {'message':{'content':'Blue.'}}
        messages = [{'role':'user','content':'What color?', 'images':[original,original,original]}]
        with tempfile.TemporaryDirectory() as folder:
            llm = LLM(Path(folder) / 'memory.json')
            with patch('llm.requests.post', side_effect=[failure,success]) as post:
                self.assertEqual(llm._request_raw(messages), 'Blue.')
                images = post.call_args.kwargs['json']['messages'][-1]['images']
                self.assertEqual(len(images), 1)
                image = Image.open(BytesIO(base64.b64decode(images[0])))
                self.assertLessEqual(max(image.size), 384)
                self.assertEqual(messages[-1]['images'], [original]*3)

if __name__=='__main__': unittest.main()
