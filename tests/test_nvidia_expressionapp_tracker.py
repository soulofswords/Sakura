import json
import tempfile
import unittest
from pathlib import Path

from nvidia_ar_tracker import AR_EXPRESSION_NAMES
from nvidia_expressionapp_tracker import ExpressionAppTracker


class ExpressionAppTrackerTests(unittest.TestCase):
    def test_validates_dlc_folder_without_running_executable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'ExpressionApp.exe').touch()
            (root / 'models').mkdir()
            self.assertEqual(ExpressionAppTracker.validate_folder(root), root.resolve())

    def test_resolves_mxtracker_parent_to_v2_engine(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            v2 = root / 'v2'
            (v2 / 'models').mkdir(parents=True)
            (v2 / 'ExpressionApp.exe').touch()
            self.assertEqual(ExpressionAppTracker.validate_folder(root), v2.resolve())

    def test_requires_expressionapp_and_models(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, 'ExpressionApp.exe'):
                ExpressionAppTracker.validate_folder(temp)

    def test_decodes_expressionapp_null_terminated_53_channel_json(self):
        values = [0.0] * len(AR_EXPRESSION_NAMES)
        values[AR_EXPRESSION_NAMES.index('CheekPuff_L')] = .75
        encoded = json.dumps({'exp': values}).encode() + b'\0'
        decoded = ExpressionAppTracker.decode_packet(encoded)
        self.assertEqual(len(decoded), 53)
        self.assertEqual(decoded['CheekPuff_L'], .75)

    def test_rejects_incomplete_or_invalid_expression_packets(self):
        with self.assertRaisesRegex(ValueError, 'full blendshape'):
            ExpressionAppTracker.decode_packet(b'{"exp":[0,0]}\0')


if __name__ == '__main__':
    unittest.main()
