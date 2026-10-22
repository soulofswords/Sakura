import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch,AsyncMock
import numpy as np
import soundfile as sf
import app
from dance_commands import dance_action,dance_style_followup
from user_address import greeting,address_text
from singing import requested,make_vocalise
from llm import LLM


class PerformanceTests(unittest.IsolatedAsyncioTestCase):
    async def test_ai_vtuber_performances_keep_private_memory_isolated(self):
        model=Mock()
        with patch.object(app,'llm',model),patch.object(app,'get_settings',return_value={'user_address':'maam'}):
            result=await app.reply_vtuber({'author':'viewer','text':'can you dance disco?','avatar_can_dance':True})
            self.assertEqual(result['avatar_motion'],'disco')
            self.assertNotIn('Ma’am',result['reply'])
            model.remember_exchange.assert_not_called();model.viewer_reply.assert_not_called()
            result=await app.reply_vtuber({'author':'viewer','text':'please do a floss dance','avatar_can_dance':True})
            self.assertIsNone(result['avatar_motion'])
            with patch.object(app,'short_singing_reply',new_callable=AsyncMock,return_value={'reply':'An original tune.','performance_audio':'/audio/test.wav'}) as sing:
                result=await app.reply_vtuber({'author':'viewer','text':'can you sing Lalabie?'})
                self.assertEqual(result['performance_audio'],'/audio/test.wav');sing.assert_awaited_once()
                model.remember_exchange.assert_not_called()
            result=await app.reply_vtuber({'author':'viewer','text':'please dance disco','avatar_can_dance':False})
            self.assertIsNone(result['avatar_motion'],'Live2D and user tracking must not be overridden')
        with patch.object(app,'llm',model),patch.object(app,'get_settings',return_value={'response_restriction_level':'off'}),patch.object(app.app.state,'tracking_only',False,create=True):
            result=await app.chat({'text':'please dance twist','ai_vtuber':True,'avatar_can_dance':True,'defer_audio':True})
            self.assertEqual(result['avatar_motion'],'twist')

    async def test_cleanup_applies_to_companion_and_viewer_dialogue(self):
        text='*leans in with a wink* Hello there. *(adjusts mic)*'
        self.assertEqual(LLM._spoken_reply(text),'Hello there.')
        with tempfile.TemporaryDirectory() as folder:
            llm=LLM(Path(folder)/'memory.json');llm.user_address='maam'
            with patch.object(llm,'_request_raw',return_value='*winks* Hello, Master.'):
                self.assertEqual(llm.viewer_reply('Viewer','tell me a joke'),'Hello.')

    async def test_titles_greetings_and_saved_validation(self):
        self.assertEqual(greeting('sir',8),'Good morning, Sir.')
        self.assertEqual(greeting('maam',14),'Good afternoon, Ma’am.')
        self.assertEqual(greeting('none',20),'Good evening.')
        self.assertEqual(address_text('Hello, Master.','maam'),'Hello, Ma’am.')
        self.assertEqual(address_text('Master, hello.','none'),'hello.')
        self.assertEqual(address_text('Change the master volume.','maam'),'Change the master volume.')
        with patch.object(app,'get_settings',return_value={'user_address':'maam'}),patch.object(app.app.state,'tracking_only',False,create=True):
            result=await app.assistant_greeting();self.assertIn('Ma’am',result['reply'])
        result=await app.update_app_settings({'user_address':'invalid'})
        self.assertEqual(result.status_code,400)
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(app,'SETTINGS_FILE',Path(folder)/'settings.json'),patch.object(app,'llm',Mock()),patch.object(app,'tts',None),patch.object(app,'public_settings',side_effect=lambda value:value):
                result=await app.update_app_settings({'user_address':'maam'})
                self.assertTrue(result['ok']);self.assertEqual(app.get_settings()['user_address'],'maam')
                self.assertEqual(app.llm.user_address,'maam')

    async def test_selected_title_overrides_old_history(self):
        with tempfile.TemporaryDirectory() as folder:
            llm=LLM(Path(folder)/'memory.json');llm.user_address='maam'
            with patch.object(llm,'_request_raw',return_value='Of course, Master.') as request:
                self.assertEqual(llm._request([{'role':'user','content':'hello'}]),'Of course, Ma’am.')
                self.assertIn('Ma’am',request.call_args.args[0][-1]['content'])

    async def test_different_routines_and_followups(self):
        for style in ['disco','twist','march']:
            self.assertEqual(dance_action('can you dance '+style),style)
            self.assertEqual(dance_style_followup('switch to '+style,'groove'),style)
        current='groove';seen={current}
        for _ in range(5):current=dance_style_followup('try another move',current);seen.add(current)
        self.assertEqual(len(seen),6)
        self.assertEqual(dance_action('can you dance the tango'),'unsupported')
        self.assertEqual(dance_action('please do a floss dance'),'unsupported')
        self.assertIsNone(dance_style_followup('change the volume','groove'))

    async def test_short_vocalise_is_bounded_and_tuned(self):
        self.assertTrue(requested('Can you sing a little?'))
        self.assertTrue(requested('Can you sing Lalabie?'))
        from singing import named_song
        self.assertTrue(named_song('Can you sing Lalabie?'))
        self.assertFalse(named_song('Can you sing a little?'))
        self.assertFalse(requested('Please stop singing.'))
        self.assertFalse(requested('I heard someone sing yesterday'))
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'voice.wav';output=Path(folder)/'tune.wav';rate=24000
            sf.write(source,.2*np.sin(2*np.pi*220*np.arange(rate//2)/rate),rate)
            make_vocalise(source,output);data,sample_rate=sf.read(output)
            self.assertEqual(sample_rate,rate);self.assertTrue(3<len(data)/rate<6)
            self.assertTrue(np.isfinite(data).all());self.assertLessEqual(abs(data).max(),.96)
