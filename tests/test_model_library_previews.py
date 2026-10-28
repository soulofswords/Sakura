import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from PIL import Image

from model_library import ModelLibrary
from model_library_previews import live2d_preview,turntable_frames


class PreviewTests(unittest.TestCase):
    def test_live2d_prefers_portrait_and_excludes_referenced_texture(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            Image.new('RGB',(32,32),'red').save(root/'atlas.png')
            (root/'model.model3.json').write_text(json.dumps({'FileReferences':{'Textures':['atlas.png']}}))
            output=root/'out.webp'
            self.assertFalse(live2d_preview(root,output))
            Image.new('RGB',(32,64),'blue').save(root/'preview.png')
            self.assertTrue(live2d_preview(root,output))
            with Image.open(output) as image:
                self.assertEqual(image.size,(512,512))
                self.assertGreater(image.convert('RGB').getpixel((256,256))[2],200)

    def test_turntable_preserves_multiple_rendered_frames_in_loop(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for index in range(12):
                Image.new('RGB',(20,20),(index*20,0,0)).save(root/f'frame-{index:03d}.png')
            turntable_frames(root,root/'preview.webp')
            with Image.open(root/'preview.webp') as image:
                self.assertEqual(image.n_frames,12)
                self.assertEqual(image.info['loop'],0)

    def test_preview_download_rejects_non_raster_and_oversized_content(self):
        for payload in (b'<html>sign in</html>',b'RIFF1234WEBP'+b'0'*8_000_000):
            response=Mock(status_code=200);response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
            response.iter_content.return_value=[payload]
            transport=Mock();transport.get.return_value=response
            client=ModelLibrary('unused',lambda:{'url':'http://localhost','token':'test'},transport)
            with self.assertRaises(ValueError):client.preview('test')

    def test_preview_download_uses_authenticated_library_path(self):
        content=io.BytesIO();Image.new('RGB',(16,16),'blue').save(content,format='WEBP')
        response=Mock(status_code=200);response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.iter_content.return_value=[content.getvalue()]
        transport=Mock();transport.get.return_value=response
        client=ModelLibrary('unused',lambda:{'url':'http://localhost','token':'private-session'},transport,allow_loopback=True)
        self.assertEqual(client.preview('character'),content.getvalue())
        self.assertEqual(transport.get.call_args.args[0],'http://localhost/v1/models/character/preview')
        self.assertEqual(transport.get.call_args.kwargs['headers']['Authorization'],'Bearer private-session')
