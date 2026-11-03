import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import ocr

PHRASE = 'Sakura reads this line 24680'


def _sample(folder, name='page.png', phrase=PHRASE):
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new('RGB', (960, 220), 'white')
    ImageDraw.Draw(image).text((30, 70), phrase, font=ImageFont.truetype('arial.ttf', 46), fill='black')
    path = Path(folder) / name
    image.save(path)
    return path


@unittest.skipUnless(ocr.engine_name(), 'windows OCR engine is not installed')
class OcrTests(unittest.TestCase):
    def test_reads_text_verbatim_from_a_png(self):
        with TemporaryDirectory() as folder:
            result = ocr.read_image(_sample(folder))
        self.assertTrue(result['ok'])
        self.assertEqual(result['engine'], 'windows-ocr')
        self.assertIn('Sakura', result['text'])
        self.assertIn('24680', result['text'])
        self.assertFalse(result['truncated'])
        self.assertIn('untrusted', result['note'])

    def test_converts_a_webp_before_decoding(self):
        from PIL import Image
        with TemporaryDirectory() as folder:
            path = _sample(folder)
            webp = path.with_suffix('.webp')
            Image.open(path).save(webp, 'WEBP')
            self.assertIn('Sakura', ocr.read_image(webp)['text'])

    def test_reads_jpeg_bytes_the_way_a_screen_snapshot_arrives(self):
        from PIL import Image
        with TemporaryDirectory() as folder:
            path = _sample(folder)
            jpeg = path.with_suffix('.jpg')
            Image.open(path).convert('RGB').save(jpeg, 'JPEG')
            result = ocr.read_bytes(jpeg.read_bytes(), '.jpg')
        self.assertIn('24680', result['text'])
        self.assertTrue(result['language'])

    def test_locates_a_word_box_on_a_real_screen(self):
        sample = Path(__file__).with_name('screen-vision-sample.jpg')
        matches = ocr.locate('NUMBER', sample.read_bytes(), '.jpg')
        self.assertTrue(matches)
        box = matches[0]
        self.assertEqual(box['score'], 3)
        self.assertLess(box['x'], 60)
        self.assertTrue(100 < box['y'] < 190)
        self.assertGreater(box['width'], 50)

    def test_refuses_a_non_image(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'notes.txt'
            path.write_text('plain text', encoding='utf-8')
            with self.assertRaises(ValueError):
                ocr.read_image(path)


if __name__ == '__main__':
    unittest.main()
