"""Offscreen chooser tests; does not establish native macOS compatibility."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QDialog,QMessageBox,QLineEdit
import startup_macos as startup

application=QApplication.instance() or QApplication([])
class ChooserTests(unittest.TestCase):
    def test_vtuber_does_not_check_or_download_ai(self):
        dialog=startup.Chooser()
        with patch.object(startup,'installed') as check:
            dialog.choose('vtuber');check.assert_not_called()
        self.assertEqual(dialog.mode,'vtuber');dialog.close()
    def test_declining_local_setup_cannot_select_local(self):
        dialog=startup.Chooser()
        with patch.object(startup,'installed',return_value=False),patch.object(QMessageBox,'question',return_value=QMessageBox.No):dialog.choose('local')
        self.assertIsNone(dialog.mode);dialog.close()
    def test_cancelled_download_cannot_select_local(self):
        dialog=startup.Chooser()
        with patch.object(startup,'installed',return_value=False),patch.object(QMessageBox,'question',return_value=QMessageBox.Yes),patch.object(startup.Download,'exec',return_value=QDialog.Rejected):dialog.choose('local')
        self.assertIsNone(dialog.mode);dialog.close()
    def test_existing_local_model_skips_download(self):
        dialog=startup.Chooser()
        with patch.object(startup,'installed',return_value=True),patch.object(startup.Download,'exec') as download:
            dialog.choose('local');download.assert_not_called()
        self.assertEqual(dialog.mode,'local');dialog.close()
    def test_gemini_key_is_masked_and_selects_gemini(self):
        dialog=startup.Chooser();dialog.key.setText('sk-proj-fixture-not-a-credential')
        self.assertEqual(dialog.key.echoMode(),QLineEdit.Password)
        dialog.choose('gemini');self.assertEqual(dialog.mode,'gemini');dialog.close()

if __name__=='__main__':unittest.main()
