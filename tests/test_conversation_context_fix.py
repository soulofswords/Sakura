from tests.generation_quality_isolation import GenerationQualityIsolation
import base64
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from llm import LLM
from vision_context import combine_screen_avatar

class ConversationContextFix(GenerationQualityIsolation,unittest.TestCase):
    def test_unsolicited_hindi_flattery_retried_and_failed_drafts_not_saved(self):
        bad='मुझे आपके बारे में बहुत अच्छा लगता है, आप एक बहुत अच्छा और आकर्षक व्यक्ति हैं। आपके चेहरे पर एक बहुत अच्छा विश्वास आता है।'
        with tempfile.TemporaryDirectory() as directory:
            model=LLM(Path(directory)/'memory.json');model.reply_language='Hindi'
            with patch.object(model,'_request',side_effect=[bad,'किस ऐप का अपडेट चल रहा है?']) as infer:
                self.assertEqual(model.chat('मुझे अपडेट की स्थिति नहीं पता।'),'किस ऐप का अपडेट चल रहा है?')
                self.assertEqual(infer.call_count,2)
            size=len(model.history)
            with patch.object(model,'_request',return_value=bad):
                self.assertEqual(model.chat('क्या हुआ?'),'')
            self.assertEqual(len(model.history),size)
        self.assertFalse(LLM._irrelevant_appearance_praise('Open Settings, then you look for Audio.','Where is audio?'))

    def test_confirmed_length_limit_discards_unfinished_tail(self):
        self.assertEqual(LLM._finish_limited_reply('अपडेट चल रहा है। अभी थोड़ा इंतज़ार करो। आपके चेहरे पर एक'),'अपडेट चल रहा है। अभी थोड़ा इंतज़ार करो।')
        self.assertEqual(LLM._finish_limited_reply('One complete thought. An unfinished'),'One complete thought.')
        self.assertEqual(LLM._finish_limited_reply('An unfinished thought'),'')
    def test_avatar_self_reference_overrides_female_default(self):
        with tempfile.TemporaryDirectory() as directory:
            model=LLM(Path(directory)/'memory.json');model.avatar_presentation='masculine'
            with patch.object(model,'_request',return_value='मैं तैयार हूँ।') as request:
                model.chat('Are you ready?')
                prompt='\n'.join(m['content'] for m in request.call_args.args[0] if m['role']=='system')
                self.assertIn('masculine self-presentation',prompt)
                self.assertIn('Hindi grammatical gender',prompt)
                self.assertIn('overrides the anime-girl/female default',prompt)
            model.avatar_presentation='auto'
            with patch.object(model,'_request',return_value='Ready.') as request,patch('vision_context.combine_screen_avatar',return_value='combined'):
                model.chat('Ready?','screen','avatar')
                prompt='\n'.join(m['content'] for m in request.call_args.args[0] if m['role']=='system')
                self.assertIn('fictional avatar',prompt);self.assertIn('real user',prompt)
    def test_repetition_loop_retries_once_and_preserves_latest_topic(self):
        bad = "Oh, I see. " + "I'm just here to be a little bit more helpful than that. " * 7 + "I'm just"
        question = "I don't know if it is updating so I can't be with you."
        with tempfile.TemporaryDirectory() as directory:
            model = LLM(Path(directory)/'memory.json')
            model.history = [{'role':'user','content':'Is it updating?'},
                             {'role':'assistant','content':bad}]
            with patch.object(model,'_request',side_effect=[bad,'Do you mean the app is updating?']) as request:
                self.assertEqual(model.chat(question),'Do you mean the app is updating?')
            self.assertEqual(request.call_count,2)
            sent = request.call_args.args[0]
            self.assertTrue(any(m['role']=='user' and m['content']==question for m in sent))
            self.assertFalse(any(m['role']=='assistant' and m['content']==bad for m in sent))
            self.assertEqual(model.history[-1]['content'],'Do you mean the app is updating?')
            with patch.object(model,'_request',return_value=bad) as request:
                reply = model.chat('What?')
                self.assertEqual(request.call_count,2)
                self.assertFalse(LLM._repetition_loop(reply))

    def test_loop_detection_preserves_normal_answers(self):
        for text in ['Yes. Yes. Yes.', 'Use "hello world" as an example. Use "hello world" again.',
                     'The update may still be running. You can check its progress.']:
            self.assertFalse(LLM._repetition_loop(text))
        self.assertTrue(LLM._repetition_loop('I am here. I am here! I am here.'))

    def test_repeated_project_passage_is_rejected_on_second_copy(self):
        passage="I'm just here to help you keep it going. I've been working on the code cleanup and the model switching, and I'm glad you're not just focusing on the task. "
        self.assertTrue(LLM._repetition_loop('Master, this is a great project. '+passage*2))
        self.assertFalse(LLM._repetition_loop(passage))

    def test_canned_second_reply_is_regenerated_from_current_topic(self):
        canned="Huh, I'm Sakura, not perfect, but I'm here to be your quiet friend. What's on your mind? W?"
        with tempfile.TemporaryDirectory() as directory:
            llm=LLM(Path(directory)/'memory.json')
            llm.history=[{'role':'user','content':'Is the game update finished?'},
                         {'role':'assistant','content':canned}]
            with patch.object(llm,'_request',side_effect=[canned,'The download is finished; the installer is still running.']) as request:
                reply=llm.chat('Can you see the screen now?', 'image')
            self.assertEqual(request.call_count,2)
            self.assertEqual(reply,'The download is finished; the installer is still running.')
            self.assertFalse(any(m.get('role')=='assistant' and m['content']==canned for m in request.call_args.args[0]))
            self.assertEqual(llm.history[1]['content'],canned,'Archive is preserved')
            self.assertEqual(llm.history[-1]['content'],reply)

    def test_screen_reactions_never_restart_self_introduction(self):
        with tempfile.TemporaryDirectory() as directory:
            llm=LLM(Path(directory)/'memory.json')
            with patch.object(llm,'_screen_reaction_request',return_value="Huh, I'm Sakura, your quiet friend."):
                self.assertEqual(llm.screen_reaction('image'), '[QUIET]')
            self.assertEqual(llm._recent_reactions,[])

    def test_incomplete_trailing_letter_is_not_spoken_or_reused(self):
        self.assertEqual(LLM._spoken_reply("What's on your mind? W"), "What's on your mind?")
        self.assertEqual(LLM._spoken_reply("What's on your mind? W?"), "What's on your mind?")
        for text in ['The symbol is W', 'The letter is "W".', 'Vitamin B', 'I choose option A', 'Can I?', 'W']:
            self.assertEqual(LLM._spoken_reply(text), text)
        with tempfile.TemporaryDirectory() as directory:
            llm=LLM(Path(directory)/'memory.json')
            llm.history=[{'role':'user','content':'Hello'},
                         {'role':'assistant','content':"What's on your mind? W"}]
            with patch.object(llm,'_request',return_value='Hello again.') as request:
                llm.chat('Continue')
            sent=request.call_args.args[0]
            self.assertTrue(any(m.get('role')=='assistant' and m['content']=="What's on your mind?" for m in sent))
            self.assertTrue(llm.history[1]['content'].endswith(' W'))

    def test_repetitive_canned_followup_is_removed_after_actual_answer(self):
        self.assertEqual(LLM._spoken_reply("I'm awake. What's on your mind today?"), "I'm awake.")
        self.assertEqual(LLM._spoken_reply('I’m Sakura. What’s on your mind, Master?'), 'I’m Sakura.')
        self.assertEqual(LLM._spoken_reply('I’m here, Master—what’s on your mind? 🌸'), 'I’m here, Master')
        self.assertEqual(LLM._spoken_reply("What's on your mind?"), "What's on your mind?")
    def test_narrated_greeting_becomes_spoken_dialogue(self):
        reply='Sakura’s avatar smiles softly, her screen softly glowing. “Hello, Master. How’s your day? I’m here—quiet, ready, and listening.” '
        self.assertEqual(LLM._spoken_reply(reply),'Hello, Master. How’s your day? I’m here—quiet, ready, and listening.')
        ordinary='Use "Hello" as your test input.'
        self.assertEqual(LLM._spoken_reply(ordinary),ordinary)
        self.assertEqual(LLM._spoken_reply('Hello! How are you?'),'Hello! How are you?')
        latest='Sakura’s avatar tilts slightly, her screen humming with gentle warmth. “Hello again, Master. You’re welcome to linger, or to dive into something new. What’s on your mind?”'
        self.assertEqual(LLM._spoken_reply(latest), 'Hello again, Master. You’re welcome to linger, or to dive into something new. What’s on your mind?')
    def test_old_narrated_history_is_cleaned_without_deleting_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            llm=LLM(Path(directory)/'memory.json')
            narrated='Sakura tilts her head. “Hello again!”'
            llm.history=[{'role':'user','content':'Hello'},{'role':'assistant','content':narrated}]
            with patch.object(llm,'_request',return_value='How are you?') as request:
                llm.chat('What is next?')
            sent=request.call_args.args[0]
            self.assertTrue(any(m.get('role')=='assistant' and m['content']=='Hello again!' for m in sent))
            self.assertEqual(llm.history[1]['content'],narrated)
    def test_small_context_keeps_recent_followup(self):
        history=[{'role':'system','content':'You are Sakura. '+('Long personality. '*500)},
            {'role':'user','content':'Can you dance?'},{'role':'assistant','content':'I can play a short dance.'},
            {'role':'user','content':'Just do what you have. I want to see that.'}]
        fitted=LLM._fit_local_messages(history,2048,128)
        self.assertEqual(fitted[1:],history[1:])
    def test_unverified_action_dialogue_is_not_persisted_as_a_fact(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'memory.json';llm=LLM(path);llm.remember_exchange('make u dance','Here comes a little dance.')
            restored=LLM(path)
            self.assertEqual(restored.trusted_memory,[])
            self.assertEqual([item['role'] for item in restored.history],['user','assistant'])
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
