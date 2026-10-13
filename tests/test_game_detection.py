import unittest
from unittest.mock import patch
from game_detection import game_session
from game_detection import classify_game

class GameDetectionTests(unittest.TestCase):
    def test_alt_tab_keeps_game_session_until_process_exits(self):
        previous = {'detected': True, 'name': 'game.exe', 'pid': 123}
        with patch('game_detection.foreground_game', return_value={'detected': False, 'name': ''}), patch('game_detection.process_running', return_value=True):
            status = game_session(previous)
            self.assertTrue(status['detected'])
            self.assertFalse(status['foreground'])
        with patch('game_detection.foreground_game', return_value={'detected': False, 'name': ''}), patch('game_detection.process_running', return_value=False), patch('game_detection.running_library_game', return_value={'detected':False}):
            self.assertFalse(game_session(previous)['detected'])
    def test_games_in_libraries_and_fullscreen(self):
        self.assertTrue(classify_game(r'C:\Steam\steamapps\common\MyGame\game.exe'))
        self.assertTrue(classify_game(r'D:\Custom\game.exe', True))
        self.assertFalse(classify_game(r'C:\Windows\notepad.exe'))

    def test_excludes_fullscreen_browser_and_companion(self):
        for name in ['chrome.exe', 'msedge.exe', 'python.exe', 'discord.exe', 'obs64.exe']:
            self.assertFalse(classify_game('C:/Programs/' + name, True))

    def test_protected_game_detected_without_foreground_path(self):
        with patch('game_detection.foreground_game', return_value={'detected':False}), patch('game_detection.installed_game_process_names', return_value={'fallguys_client_game.exe'}), patch('game_detection.process_inventory', return_value=[{'pid':4760,'name':'FallGuys_client_game.exe'}]):
            self.assertEqual(game_session()['pid'],4760)
            self.assertTrue(game_session()['detected'])
