import unittest
from pathlib import Path
from unittest.mock import patch
from assistant_commands import run_command


class SteamCommandsTests(unittest.TestCase):
    def test_permission_required(self):
        with patch('steam_commands.subprocess.Popen') as launch:
            self.assertIn('Enable computer access', run_command('open steam', False))
            self.assertIn('Enable computer access', run_command('play forza horizon 6', False))
            launch.assert_not_called()

    @patch('steam_commands.steam_executable', return_value=Path('Steam/steam.exe'))
    @patch('steam_commands.subprocess.Popen')
    def test_verified_library_game(self, launch, _):
        for phrase in ['open steam and run forza horizon 6 from the steam library list', 'play forza horizon 6', 'launch forzahorizon6_loader']:
            self.assertEqual(run_command(phrase, True), 'Launching Forza Horizon 6 from Steam.')
            self.assertEqual(launch.call_args.args[0][1], 'steam://rungameid/13725072842037395456')
            self.assertFalse(launch.call_args.kwargs['shell'])

    @patch('steam_commands.steam_executable', return_value=Path('Steam/steam.exe'))
    @patch('steam_commands.subprocess.Popen')
    def test_open_steam(self, launch, _):
        self.assertEqual(run_command('open steam', True), 'Opening your Steam library.')
        self.assertEqual(launch.call_args.args[0][1], 'steam://open/library')

    def test_unknown_steam_game_does_not_launch(self):
        with patch('steam_commands.subprocess.Popen') as launch:
            self.assertIn("don't have a verified", run_command('play imaginary game from steam', True))
            self.assertIsNone(run_command('tell me about racing games', True))
            launch.assert_not_called()
