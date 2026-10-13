import unittest
from unittest.mock import Mock,patch
from dance_commands import dance_action,dance_reply
import app

class DanceCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_requests_only(self):
        for text,expected in [('can you dance?','groove'),('Sakura dance','groove'),('please do a side step dance','step'),('show an arm wave dance','wave'),('stop dancing','stop'),('dance mat karo','stop'),('नाचो','groove'),('डांस करो','groove'),('kya tum dance kar sakti ho','groove'),('what is dance?',None),('I saw a dance yesterday',None)]:
            self.assertEqual(dance_action(text),expected,text)
    async def test_dance_acknowledges_only_supported_avatar(self):
        with patch.object(app,'get_settings',return_value={'selected_voice':'swara_hindi'}),patch.object(app,'llm',Mock()),patch.object(app.app.state,'tracking_only',False,create=True):
            result=await app.chat({'text':'can you dance?','avatar_can_dance':True,'defer_audio':True})
            self.assertEqual(result['avatar_motion'],'groove');self.assertIn('हाँ',result['reply']);app.llm.chat.assert_not_called()
            result=await app.chat({'text':'can you dance?','avatar_can_dance':False,'defer_audio':True})
            self.assertIsNone(result['avatar_motion']);self.assertIn('PMX',result['reply'])
            result=await app.chat({'text':'stop dancing','avatar_can_dance':True,'defer_audio':True})
            self.assertEqual(result['avatar_motion'],'stop')
        self.assertIn('Haan',dance_reply('groove','Hinglish'))
