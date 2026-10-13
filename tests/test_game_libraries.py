import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import steam_commands as commands
class LibraryTests(unittest.TestCase):
 def test_installed_library_discovery(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);steam=root/'Steam';apps=steam/'steamapps';apps.mkdir(parents=True)
   (apps/'appmanifest_42.acf').write_text('"appid" "42"\n"name" "Test Racer"')
   epic=root/'Epic/EpicGamesLauncher/Data/Manifests';epic.mkdir(parents=True)
   (epic/'test.item').write_text(json.dumps({'AppName':'TestEpic','DisplayName':'Test Adventure','InstallLocation':str(root)}))
   with patch.object(commands,'steam_executable',return_value=steam/'steam.exe'),patch.dict('os.environ',{'PROGRAMDATA':folder}):
    games=commands.installed_games()
   self.assertEqual({g['name'] for g in games},{'Test Racer','Test Adventure'})
 def test_epic_permissions_and_dispatch(self):
  game={'name':'Test Adventure','store':'epic','url':'com.epicgames.launcher://apps/TestEpic?action=launch&silent=true'}
  with patch.object(commands,'installed_games',return_value=[game]),patch.object(commands,'epic_executable',return_value=Path('EpicGamesLauncher.exe')),patch.object(commands.subprocess,'Popen') as launch:
   self.assertIn('Enable computer access',commands.run_steam_command('play test adventure from epic',False));launch.assert_not_called()
   self.assertIn('Launching Test Adventure',commands.run_steam_command('play test adventure from epic',True));launch.assert_called_once_with(['EpicGamesLauncher.exe',game['url']],shell=False)
 def test_installed_steam_dispatch(self):
  game={'name':'Test Racer','store':'steam','url':'steam://rungameid/42'}
  with patch.object(commands,'installed_games',return_value=[game]),patch.object(commands,'steam_executable',return_value=Path('steam.exe')),patch.object(commands.subprocess,'Popen') as launch:
   self.assertIn('Launching Test Racer',commands.run_steam_command('play test racer from steam',True));self.assertEqual(launch.call_args.args[0][1],game['url'])

 def test_spoken_left_for_dead_matches_installed_title(self):
  from assistant_commands import run_command
  game={'name':'Left 4 Dead 2','store':'steam','url':'steam://rungameid/550'}
  with patch.object(commands,'installed_games',return_value=[game]),patch.object(commands,'steam_executable',return_value=Path('steam.exe')),patch.object(commands.subprocess,'Popen') as launch:
   for phrase in ['open left for dead 2','play left four dead two from steam','Sakura, can you open left for dead two please?','launch l4d2']:
    self.assertEqual(run_command(phrase,True),'Launching Left 4 Dead 2 from Steam.')
    self.assertEqual(launch.call_args.args[0][1],game['url'])

 def test_open_epic_launcher_directly(self):
  from assistant_commands import run_command
  with patch.object(commands,'epic_executable',return_value=Path('EpicGamesLauncher.exe')),patch.object(commands.subprocess,'Popen') as launch:
   self.assertEqual(run_command('Sakura, open epic games launcher',True),'Opening Epic Games Launcher.')
   launch.assert_called_once_with(['EpicGamesLauncher.exe'],shell=False)
