from tests.generation_quality_isolation import GenerationQualityIsolation
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import app as server
from llm import LLM


class CameraVision(GenerationQualityIsolation,unittest.TestCase):
    def test_camera_label_and_no_image_memory(self):
        with tempfile.TemporaryDirectory() as folder:
            model=LLM(Path(folder)/'memory.json')
            with patch.object(model,'_request',return_value='You are holding a blue cup.') as request:
                model.chat('What am I holding?',camera_image='/9j/secretCameraImage')
                messages=request.call_args.args[0]
                self.assertEqual(messages[-1]['images'],['/9j/secretCameraImage'])
                self.assertTrue(any('CAMERA' in m['content'] for m in messages if m['role']=='system'))
            self.assertNotIn('secretCameraImage',model.memory_path.read_text())

    def test_camera_comments_quiet_after_chat_and_no_memory(self):
        with tempfile.TemporaryDirectory() as folder:
            model=LLM(Path(folder)/'memory.json')
            with patch('llm.time.monotonic',return_value=200), patch.object(model,'_request',return_value='Nice blue cup.') as request:
                model._last_direct_reply_at=190
                self.assertEqual(model.camera_reaction('/9j/camera'),'[QUIET]');request.assert_not_called()
                model._last_direct_reply_at=0
                self.assertEqual(model.camera_reaction('/9j/camera'),'Nice blue cup.')
                self.assertEqual(model.history,[])
                self.assertEqual(model.camera_reaction('/9j/camera'),'[QUIET]','Repeated comments suppressed')


class CameraEndpoint(GenerationQualityIsolation,unittest.IsolatedAsyncioTestCase):
    async def test_validation_routing_and_tracking_isolation(self):
        model=Mock();model.chat.return_value='I see a cup.';model.camera_reaction.return_value='[QUIET]'
        with patch.object(server,'llm',model), patch.object(server,'get_settings',return_value={}), patch.object(server,'get_vision_status',return_value={'ready':True}), patch.object(server.app.state,'tracking_only',False,create=True):
            invalid=await server._chat_core({'text':'hello','camera_image':'not a jpeg','defer_audio':True})
            self.assertEqual(invalid.status_code,400);model.chat.assert_not_called()
            reply=await server._chat_core({'text':'What am I holding?','camera_image':'/9j/','defer_audio':True})
            self.assertEqual(reply['reply'],'I see a cup.')
            self.assertEqual(model.chat.call_args.kwargs['camera_image'],'/9j/')
            reaction=await server._chat_core({'text':'Camera comment','camera_image':'/9j/','camera_reaction':True})
            self.assertEqual(reaction['reply'],'[QUIET]')
            model.camera_reaction.return_value='{"reply":"Oh, you brought your headphones!","emotion":"surprised"}'
            reaction=await server._chat_core({'text':'Camera comment','camera_image':'/9j/','camera_reaction':True})
            self.assertEqual(reaction['reply'],'Oh, you brought your headphones!')
            self.assertEqual(reaction['emotion'],'surprised')
            model.camera_reaction.return_value='{"reply":"broken"'
            reaction=await server._chat_core({'text':'Camera comment','camera_image':'/9j/','camera_reaction':True})
            self.assertEqual(reaction['reply'],'[QUIET]','Never speak malformed structured output')
            with patch.object(server.app.state,'tracking_only',True):
                result=await server._chat_core({'text':'hello','camera_image':'/9j/'})
                self.assertEqual(result.status_code,409)


if __name__=='__main__':unittest.main()
