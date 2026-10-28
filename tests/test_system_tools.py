import asyncio,tempfile,unittest,time
from pathlib import Path
from unittest.mock import patch
from assistant_commands import run_command
from assistant_tools import classify,handle_command,runs

class ToolTests(unittest.TestCase):
 def test_fixed_action_names_and_argument_limits(self):
  for text in ['pc status','show cpu usage',"what's my ram usage"]:self.assertEqual(classify(text)[0],'system.status')
  self.assertEqual(classify('set volume to 32%'),('audio.volume',{'action':'set','value':32}))
  self.assertEqual(classify('mute volume'),('audio.volume',{'action':'mute'}))
  self.assertIsNone(classify('why does volume change?'))
  with self.assertRaises(ValueError):classify('set volume to 101')
 def test_permission_and_failures_do_not_claim_success(self):
  with patch('assistant_tools.execute') as execute:
   self.assertIn('Enable',run_command('set volume to 30%',False));execute.assert_not_called()
  with patch('assistant_tools.execute',side_effect=RuntimeError('No audio device')):
   self.assertIn('No audio device',run_command('set volume to 30%',True))
 def test_workflow_preflight_prevents_partial_unknown_or_unauthorized_actions(self):
  with patch('assistant_commands.open_installed_app') as launch,patch('assistant_tools.execute') as execute:
   self.assertIn('No actions',run_command('open calculator then erase everything',True));launch.assert_not_called()
   self.assertIn('No actions',run_command('open calculator then set volume to 30%',False));launch.assert_not_called();execute.assert_not_called()
   self.assertIn('five actions',run_command(' then '.join(['pc status']*6),True))
 def test_order_verified_result_and_stop_on_failure(self):
  with patch('assistant_commands.open_installed_app',return_value='Opening calculator.') as launch,patch('assistant_tools.execute',return_value={'ok':True,'reply':'Volume is 30 percent.','data':{'percent':30}}) as execute:
   reply=run_command('open calculator and then set volume to 30%',True)
   self.assertIn('Opening calculator.',reply);self.assertIn('30 percent',reply)
   self.assertEqual(runs()[-1]['status'],'completed');self.assertEqual(len(runs()[-1]['steps']),2)
  with patch('assistant_commands.open_installed_app',return_value="I couldn't find missing installed on this computer."),patch('assistant_tools.execute') as execute:
   self.assertIn('Remaining steps',run_command('open missing then set volume to 30%',True));execute.assert_not_called();self.assertEqual(runs()[-1]['status'],'failed')
 def test_cancel_stops_before_next_step(self):
  from assistant_tools import cancel_run
  def first(*args):
   self.assertTrue(cancel_run())
   return {'ok':True,'reply':'First action completed.'}
  with patch('assistant_tools.execute',side_effect=first) as execute:
   self.assertIn('Remaining steps',run_command('pc status then set volume to 30%',True))
   self.assertEqual(execute.call_count,1);self.assertEqual(runs()[-1]['status'],'cancelled')
 def test_timer_sequence_not_swallowed_by_reminder_parser(self):
  from assistant_reminders import Reminders
  with tempfile.TemporaryDirectory() as folder,patch('assistant_reminders.reminders',Reminders(Path(folder)/'timers.json')) as timers,patch('assistant_tools.execute',return_value={'ok':True,'reply':'Volume is 20 percent.'}) as execute:
   reply=run_command('start a timer for 2 minutes then set volume to 20%',True)
   self.assertIn('Timer set',reply);self.assertIn('20 percent',reply);self.assertEqual(len(timers.list()),1);execute.assert_called_once()
 def test_read_only_file_search_scoped_to_explicit_folder(self):
  from system_tools import find_files
  with tempfile.TemporaryDirectory() as folder:
   home=Path(folder);(home/'Downloads').mkdir();(home/'Downloads'/'Report.txt').write_text('test');(home/'Downloads'/'nested').mkdir();(home/'Downloads'/'nested'/'report-secret.txt').write_text('test')
   with patch('system_tools.Path.home',return_value=home):
    self.assertEqual([x['name'] for x in find_files('report','downloads')['files']],['Report.txt'])
    with self.assertRaises(ValueError):find_files('../','downloads')
    with self.assertRaises(ValueError):find_files('report','system')
 def test_no_match_on_ordinary_conversation(self):
  self.assertIsNone(handle_command('I finished work then went home',True))
  self.assertIn('five',run_command('show capabilities'))
 def test_background_sequence_reports_each_step_without_blocking(self):
  from assistant_commands import background_sequence
  from assistant_tools import run_state
  with patch('assistant_tools.execute',return_value={'ok':True,'reply':'Volume is 30 percent.'}):
   started=background_sequence('pc status then set volume to 30%',True)
   self.assertTrue(started and started['id'])
   self.assertEqual(started['steps'],2)
   state=run_state(started['id'])
   for _ in range(200):
    if state['status']!='running':break
    time.sleep(0.01)
    state=run_state(started['id'])
   self.assertEqual(state['status'],'completed')
   self.assertEqual([step['reply'] for step in state['steps']],['Volume is 30 percent.','Volume is 30 percent.'])
 def test_background_sequence_ignores_ordinary_conversation(self):
  from assistant_commands import background_sequence
  self.assertIsNone(background_sequence('I finished work then went home',True))
 def test_background_sequence_keeps_preflight_refusals(self):
  from assistant_commands import background_sequence
  with patch('assistant_commands.open_installed_app') as launch,patch('assistant_tools.execute') as execute:
   self.assertIn('No actions',background_sequence('open calculator then erase everything',True)['error'])
   self.assertIn('No actions',background_sequence('open calculator then set volume to 30%',False)['error'])
   launch.assert_not_called();execute.assert_not_called()

class ToolEndpoints(unittest.IsolatedAsyncioTestCase):
 async def test_phone_permissions_and_allowlist(self):
  import app
  with patch.object(app,'get_settings',return_value={'computer_control_enabled':True}),patch('assistant_tools.execute') as execute:
   self.assertEqual((await app.assistant_device_action({'phone':True,'action':'system.status'})).status_code,403);execute.assert_not_called()
  with patch.object(app,'get_settings',return_value={'computer_control_enabled':True,'phone_system_access_enabled':True}),patch('assistant_tools.execute',return_value={'ok':True}) as execute:
   self.assertEqual(await app.assistant_device_action({'phone':True,'action':'system.status'}),{'ok':True})
   self.assertEqual((await app.assistant_device_action({'phone':True,'action':'audio.volume','operation':'set','value':float('nan')})).status_code,400)
   self.assertEqual((await app.assistant_device_action({'phone':True,'action':'shell'})).status_code,400)
 async def test_clipboard_has_separate_opt_in_and_bounded_text(self):
  import app
  with patch.object(app,'get_settings',return_value={'computer_control_enabled':True}),patch('native_clipboard.read_text') as read:
   self.assertEqual((await app.assistant_device_action({'phone':True,'action':'clipboard.read'})).status_code,403);read.assert_not_called()
  with patch.object(app,'get_settings',return_value={'phone_clipboard_enabled':True}),patch('native_clipboard.read_text',return_value='explicit test'):
   self.assertEqual((await app.assistant_device_action({'phone':True,'action':'clipboard.read'}))['text'],'explicit test')
   self.assertEqual((await app.assistant_device_action({'phone':True,'action':'clipboard.write','text':'x'*4097})).status_code,400)
if __name__=='__main__':unittest.main()
