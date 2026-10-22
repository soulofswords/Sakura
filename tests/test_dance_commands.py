import unittest
from unittest.mock import Mock,patch
from dance_commands import dance_action,dance_reply,hand_action
import app

class DanceCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_show_hands_uses_both_unless_side_is_specified(self):
        for text,expected in [('show your hands','hands_both'),('Can you show me your hand?','hands_both'),
                              ('please raise both your hands','hands_both'),('show your left hand','hand_left'),
                              ('raise your right hand up','hand_right'),('I saw your hands',None),
                              ("don't show your hands",None),('show her hands',None)]:
            self.assertEqual(hand_action(text),expected,text)
        with patch.object(app,'get_settings',return_value={}),patch.object(app,'llm',Mock()),patch.object(app.app.state,'tracking_only',False,create=True):
            result=await app._chat_core({'text':'show your hands','avatar_can_dance':True,'defer_audio':True})
            self.assertEqual(result['avatar_motion'],'hands_both');self.assertIn('both',result['reply'])
            result=await app._chat_core({'text':'show your left hand','avatar_can_dance':False,'defer_audio':True})
            self.assertIsNone(result['avatar_motion']);self.assertIn('PMX',result['reply'])
            app.llm.chat.assert_not_called()
    async def test_explicit_requests_only(self):
        for text,expected in [('can you dance?','groove'),('Sakura dance','groove'),('please do a side step dance','step'),('show an arm wave dance','wave'),('stop dancing','stop'),('dance mat karo','stop'),('नाचो','groove'),('डांस करो','groove'),('kya tum dance kar sakti ho','groove'),('what is dance?',None),('I saw a dance yesterday',None)]:
            self.assertEqual(dance_action(text),expected,text)
    async def test_dance_acknowledges_only_supported_avatar(self):
        with patch.object(app,'get_settings',return_value={'selected_voice':'swara_hindi'}),patch.object(app,'llm',Mock()),patch.object(app.app.state,'tracking_only',False,create=True):
            result=await app._chat_core({'text':'can you dance?','avatar_can_dance':True,'defer_audio':True})
            self.assertEqual(result['avatar_motion'],'groove');self.assertIn('हाँ',result['reply']);app.llm.chat.assert_not_called()
            result=await app._chat_core({'text':'can you dance?','avatar_can_dance':False,'defer_audio':True})
            self.assertIsNone(result['avatar_motion']);self.assertIn('PMX',result['reply'])
            result=await app._chat_core({'text':'stop dancing','avatar_can_dance':True,'defer_audio':True})
            self.assertEqual(result['avatar_motion'],'stop')
        self.assertIn('Haan',dance_reply('groove','Hinglish'))

    async def test_dance_followup_and_action_memory(self):
        with patch.object(app,'get_settings',return_value={'selected_voice':'sakura_ava'}),patch.object(app,'llm',Mock()),patch.object(app.app.state,'tracking_only',False,create=True):
            result=await app._chat_core({'text':'make u dance','avatar_can_dance':True,'defer_audio':True})
            self.assertEqual(result['avatar_motion'],'groove');app.llm.remember_exchange.assert_called_once_with('make u dance',result['reply'])
            followup=await app._chat_core({'text':'just do what u have. i want to see that','avatar_can_dance':True,'defer_audio':True})
            self.assertEqual(followup['avatar_motion'],'groove');app.llm.chat.assert_not_called()
            app.app.state.last_avatar_action=None
