"""Safety contracts for reviewed PDF exports."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sakura_pdf import write_pdf


class PdfWriterTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'report.pdf'

    def test_creates_a_pdf_and_never_overwrites_an_existing_file(self):
        result = write_pdf(self.path, 'Hello from Sakura.', 'Greeting')
        self.assertTrue(self.path.read_bytes().startswith(b'%PDF-'))
        self.assertEqual(result['path'], str(self.path))
        original = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            write_pdf(self.path, 'Replacement')
        self.assertEqual(self.path.read_bytes(), original)

    def test_atomic_publish_refuses_a_file_created_during_render(self):
        import sakura_pdf
        real_link = sakura_pdf.os.link

        def collide(source, target):
            Path(target).write_bytes(b'user document')
            return real_link(source, target)

        with patch.object(sakura_pdf.os, 'link', side_effect=collide):
            with self.assertRaisesRegex(ValueError, 'created while Sakura'):
                write_pdf(self.path, 'Hello')
        self.assertEqual(self.path.read_bytes(), b'user document')
        self.assertFalse(list(Path(self.folder.name).glob('*.sakura-pdf.tmp')))


if __name__ == '__main__':
    unittest.main()
