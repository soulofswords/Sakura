import ast
import base64
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
import tempfile
from unittest.mock import patch,Mock
from PIL import Image, ImageDraw
from llm import LLM

class ScreenMemoryTests(unittest.TestCase):
    def test_video_timeline_used_after_screen_moves_on_and_expires(self):
        with tempfile.TemporaryDirectory() as directory:
            model=LLM(Path(directory)/'memory.json')
            with patch('llm.time.monotonic',return_value=100),patch.object(model,'_request',return_value='A red car turns left, then stops beside a tree.') as infer:
                self.assertTrue(model.observe_screen('latest',['earlier','middle','latest']))
                self.assertTrue(infer.call_args.kwargs['summarizing'])
                self.assertEqual(infer.call_args.args[0][-1]['images'],['earlier','middle','latest'])
            with patch('llm.time.monotonic',return_value=110),patch.object(model,'_request') as infer:
                self.assertFalse(model.observe_screen('image'));infer.assert_not_called()
            with patch('llm.time.monotonic',return_value=125),patch.object(model,'_request',return_value='The car stopped by a tree.') as infer:
                model.chat('What happened in that video?')
                sent=infer.call_args.args[0]
                self.assertTrue(any('red car turns left' in m['content'] for m in sent))
                self.assertFalse(any(m.get('images') for m in sent),'No old images retained in prompts')
            self.assertNotIn('_screen_notes',model.memory_path.read_text())
            with patch('llm.time.monotonic',return_value=701):self.assertEqual(model._screen_timeline_context(),'')

    def test_clear_during_observation_cannot_restore_discarded_notes(self):
        with tempfile.TemporaryDirectory() as directory:
            model=LLM(Path(directory)/'memory.json')
            def infer(*args,**kwargs):
                model.clear_history();return 'Stale screen observation'
            with patch.object(model,'_request',side_effect=infer):self.assertFalse(model.observe_screen('image'))
            self.assertEqual(model._screen_notes,[])
            with patch.object(model,'_request',return_value='[NOTHING]'):self.assertFalse(model.observe_screen('image'))

class ScreenMemoryEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_observer_returns_no_speech_or_conversation(self):
        import app as server
        image=io.BytesIO();Image.new('RGB',(8,8)).save(image,format='JPEG')
        encoded=base64.b64encode(image.getvalue()).decode()
        model=Mock();model.observe_screen.return_value=True
        with patch.object(server,'llm',model),patch.object(server,'get_settings',return_value={}),patch.object(server,'get_vision_status',return_value={'ready':True}),patch('screen_audio.listener.context',return_value=''):
            result=await server.chat({'text':'Silent screen timeline observation','screen_observation':True,'screen_image':encoded,'screen_frames':[encoded],'defer_audio':True})
            self.assertEqual(result,{'recorded':True});model.chat.assert_not_called();model.remember_exchange.assert_not_called()


class ScreenSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree=ast.parse((Path(__file__).parents[1]/'desktop.py').read_text(encoding='utf-8'))
        method=next(node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name=='screen_snapshot')
        module=ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[]));namespace={}
        exec(compile(module,'desktop.py','exec'),namespace)
        cls.capture=staticmethod(namespace['screen_snapshot'])

    def test_screen_permission_required(self):
        with patch('PIL.ImageGrab.grab') as grab:
            self.assertIsNone(self.capture(SimpleNamespace(screen_access=False)))
            grab.assert_not_called()

    def test_visible_screen_is_not_masked_by_maximized_companion(self):
        screen=Image.new('RGB',(1920,1080),(190,220,240))
        ImageDraw.Draw(screen).rectangle((600,200,1300,800),fill=(230,90,70))
        with patch('PIL.ImageGrab.grab',return_value=screen) as grab:
            encoded=self.capture(SimpleNamespace(screen_access=True))
        captured=Image.open(io.BytesIO(base64.b64decode(encoded)))
        self.assertEqual(captured.size,(1600,900))
        self.assertGreater(captured.getpixel((800,450))[0],180)
        self.assertGreater(captured.getpixel((100,100))[1],180)
        grab.assert_called_once()

if __name__=='__main__':unittest.main()
