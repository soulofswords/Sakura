import json
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

    def test_planning_gets_json_mode_and_room_for_a_full_action(self):
        success = Mock(status_code=200)
        success.json.return_value = {'message':{'content':'{"tool":"files.write","arguments":{"path":"a.md"}}'}}
        with tempfile.TemporaryDirectory() as folder:
            llm = LLM(Path(folder) / 'memory.json')
            llm.configure_local('qwen3:4b', fallback=False, context=4096, timeout=8)
            with patch('llm.requests.post', return_value=success) as post:
                reply = llm._request_raw([{'role':'system','content':'Plan one step.'},{'role':'user','content':'{}'}],
                                         structured=True, planning=True)
            payload = post.call_args.kwargs['json']
            self.assertEqual(payload['format'], 'json')
            self.assertGreaterEqual(payload['options']['num_predict'], 1024)
            self.assertGreaterEqual(payload['options']['num_ctx'], 8192)
            self.assertEqual(payload['options']['temperature'], 0.1)
            self.assertNotIn('Speak directly to the user in your own voice', json.dumps(payload['messages']))
            self.assertEqual(reply, '{"tool":"files.write","arguments":{"path":"a.md"}}')
            # A plan cut off by the token limit must stay cut off, not be
            # "finished" into spoken prose that the runtime cannot parse.
            success.json.return_value = {'message':{'content':'{"tool":"files"},"reason":"earl'},'done_reason':'length'}
            with patch('llm.requests.post', return_value=success):
                self.assertEqual(llm._request_raw([{'role':'user','content':'{}'}],structured=True,planning=True),
                                 '{"tool":"files"},"reason":"earl')
            # Ordinary companion replies keep the short cap that makes them begin quickly.
            success.json.return_value = {'message':{'content':'Sure.'}}
            with patch('llm.requests.post', return_value=success) as post:
                llm._request_raw([{'role':'user','content':'hello'}])
            self.assertEqual(post.call_args.kwargs['json']['options']['num_predict'], 192)
            self.assertNotIn('format', post.call_args.kwargs['json'])

    def test_gemini_planning_requests_json_without_disabling_thinking(self):
        ok = Mock(status_code=200, ok=True, headers={})
        ok.json.return_value = {'candidates':[{'content':{'parts':[{'text':'{"done":true,"summary":"ok"}'}]}}]}
        with tempfile.TemporaryDirectory() as folder:
            llm = LLM(Path(folder) / 'memory.json')
            llm.gemini_model = 'gemini-2.5-flash'; llm.gemini_api_key = 'synthetic-key'
            with patch('llm.requests.post', return_value=ok) as post:
                llm._request_gemini([{'role':'user','content':'{}'}], planning=True)
            config = post.call_args.kwargs['json']['generationConfig']
            self.assertEqual(config['responseMimeType'], 'application/json')
            self.assertNotIn('thinkingConfig', config)
            self.assertGreaterEqual(config['maxOutputTokens'], 4096)
            with patch('llm.requests.post', return_value=ok) as post:
                llm._request_gemini([{'role':'user','content':'hello'}])
            self.assertEqual(post.call_args.kwargs['json']['generationConfig']['thinkingConfig'], {'thinkingBudget': 0})

    def test_planning_keeps_the_behaviour_rules_and_sheds_catalog_detail(self):
        instruction='You must propose a real tool for the goal. '*260
        catalog=json.dumps({'tools':[{'name':'tool'+str(i),'description':'schema detail '*22} for i in range(40)]})
        messages=[{'role':'system','content':instruction},{'role':'user','content':catalog}]
        planned=LLM._fit_local_messages([dict(m) for m in messages],8192,1536,planning=True)
        self.assertEqual(planned[0]['content'],instruction)
        self.assertLess(len(planned[1]['content']),len(catalog))
        self.assertIn('[Earlier text shortened]',planned[1]['content'])
        # The same tight budget on an ordinary reply sheds the system text first, so the
        # planner exception cannot change companion behaviour.
        ordinary=LLM._fit_local_messages([dict(m) for m in messages],8192,1536)
        self.assertLess(len(ordinary[0]['content']),len(instruction)//4)

    def test_agent_task_brief_reaches_the_chat_reply_and_cannot_order_actions(self):
        with tempfile.TemporaryDirectory() as folder:
            llm = LLM(Path(folder) / 'memory.json')
            llm.provider='ollama'; llm.context_length=32768
            brief='Goal: clone the repo · status failed. - shell.run: failed — timed out after 45 seconds'
            with patch.object(llm,'_request',return_value='The clone step timed out.') as call:
                llm.chat('What happened with my task?',agent_task=brief)
            sent=call.call_args.args[0]
            system=' '.join(m['content'] for m in sent if m['role']=='system')
            self.assertIn('Task the user is viewing in Agent mode',system)
            self.assertIn('timed out after 45 seconds',system)
            self.assertIn('Never claim a step ran',system)
            self.assertEqual([m['role'] for m in sent][-1],'user')
            with patch.object(llm,'_request',return_value='Hello.') as call:
                llm.chat('Hello there.')
            self.assertNotIn('Agent mode',json.dumps(call.call_args.args[0]))

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
