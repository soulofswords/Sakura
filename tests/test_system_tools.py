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
  for text in ['increase volume','raise the volume a bit','turn the volume up','turn it up','louder']:
   self.assertEqual(classify(text),('audio.volume',{'action':'up'}),text)
  for text in ['decrease volume','lower the volume','reduce volume please','turn the volume down','turn it down','a bit quieter']:
   self.assertEqual(classify(text),('audio.volume',{'action':'down'}),text)
  self.assertIsNone(classify('why does volume change?'))
  with self.assertRaises(ValueError):classify('set volume to 101')
 def test_spoken_value_phrasing_and_device_followup(self):
  from assistant_tools import device_followup,device_mention
  for text in ['set the volume to 50','make the volume 50 percent','turn the volume to 50 percent',
               'change volume to 50','make the volume 50']:
   self.assertEqual(classify(text),('audio.volume',{'action':'set','value':50}),text)
  for text in ['set brightness to 40','make the brightness 40 percent','turn the brightness to 40']:
   self.assertEqual(classify(text),('display.brightness',{'action':'set','value':40}),text)
  # A directional verb still means an absolute level when the speaker names one;
  # "increase the volume to 50" must never fall through to the conversational model.
  for text,value in [('Increase the volume to 50 percent.',50),('raise the volume to 70',70),
                     ('decrease the volume to 20 percent',20),('lower the volume to 30',30),
                     ('turn the volume down to 25',25),('bring the volume up to 50',50),
                     ('bump the volume up to 50',50),('boost the sound to 40 percent',40)]:
   self.assertEqual(classify(text),('audio.volume',{'action':'set','value':value}),text)
  for text,value in [('increase the brightness to 40 percent',40),('turn the brightness down to 20',20)]:
   self.assertEqual(classify(text),('display.brightness',{'action':'set','value':value}),text)
  for text,action in [('increase the volume','up'),('turn up the volume','up'),('turn the volume down','down')]:
   self.assertEqual(classify(text),('audio.volume',{'action':action}),text)
  with self.assertRaises(ValueError):classify('increase the volume to 150 percent')
  self.assertEqual(device_mention('can u increase the volume a bit'),'volume')
  self.assertEqual(device_mention('make the screen brighter'),'brightness')
  self.assertIsNone(device_mention('what is on my screen'))
  self.assertEqual(device_followup('make it 50 percent','volume'),'set volume to 50')
  self.assertEqual(device_followup('make it 50 directly','volume'),'set volume to 50')
  self.assertEqual(device_followup('set it to 50','brightness'),'set brightness to 50')
  self.assertEqual(device_followup('increase it to 50 percent','volume'),'set volume to 50')
  self.assertEqual(device_followup('please turn it down to 20','volume'),'set volume to 20')
  self.assertIsNone(device_followup('make it 50 percent',None))
  with self.assertRaises(ValueError):device_followup('make it 101 percent','volume')
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
 def test_clipboard_capture_keeps_the_text_and_drops_the_command_words(self):
  for text,expected in [('copy hello world to clipboard','hello world'),
                        ('copy hello world to the clipboard','hello world'),
                        ('put the answer the clipboard','the answer'),
                        ('copy Hello World to clipboard','Hello World')]:
   self.assertEqual(classify(text),('clipboard.write',{'text':expected}),text)
  self.assertEqual(classify('read clipboard'),('clipboard.read',{}))
 def test_plain_clipboard_use_needs_no_computer_access(self):
  import assistant_tools
  for action in ('clipboard.read','clipboard.write','clipboard.transform'):
   self.assertIn(action,assistant_tools._NO_PERMISSION)
  self.assertNotIn('clipboard.ai_transform',assistant_tools._NO_PERMISSION)
 def test_media_keys_route_globally_not_through_the_focused_window(self):
  for text,key in [('press playpause','playpause'),('hit next track','nexttrack'),
                   ('press the media key play_pause','playpause'),('press volume down','volumedown')]:
   self.assertEqual(classify(text),('media.press',{'key':key}),text)
  self.assertEqual(classify('press ctrl s'),('desktop.press',{'combo':'ctrl s'}))
  with patch('desktop_control.execute_action',return_value={'ok':True,'reply':'Pressed playpause.','data':{}}) as execute:
   self.assertEqual(run_command('press playpause',True),'Pressed playpause.')
  execute.assert_called_once_with('media.press',{'key':'playpause'})
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
 async def test_follow_up_percentage_targets_the_device_just_discussed(self):
  import app as server
  from command_approval import consume
  from assistant_tools import DeviceContext
  previous=getattr(server.app.state,'device_context',None)
  server.app.state.device_context=DeviceContext()
  server.app.state.device_context.resolve('volume','desktop')
  try:
   with patch.object(server,'get_settings',return_value={'computer_control_enabled':True,'response_restriction_level':'off'}),patch('assistant_tools.execute') as execute:
    result=await server.chat({'text':'make it 50 percent','defer_audio':True})
   self.assertIn('Review this PC action',result['reply'])
   self.assertIn('set volume to 50',result['reply'])
   execute.assert_not_called()
   self.assertIsNone(consume(result['command_approval'],False))
  finally:
   if previous is None:del server.app.state.device_context
   else:server.app.state.device_context=previous
 async def test_reviewing_a_kill_for_a_dead_process_answers_honestly(self):
  # propose() re-checks the process identity before storing an approval; a PID that is
  # gone must return the refusal, not a 500, and must leave nothing waiting to execute.
  import app as server
  from command_approval import _pending
  before=set(_pending)  # an earlier test may still hold an approval; this one must add none
  from process_tools import inspect_target
  def dead(pid):
   raise ValueError('That process no longer exists. Refresh the process list.')
  try:
   with patch('process_tools.inspect_target',side_effect=dead),patch.object(server,'get_settings',return_value={'computer_control_enabled':True,'response_restriction_level':'off'}),patch('assistant_tools.execute') as execute:
    result=await server.chat({'text':'kill process 999999','defer_audio':True})
   self.assertEqual(result['reply'],'That process no longer exists. Refresh the process list.')
   self.assertEqual(result['response_kind'],'clarification')
   self.assertNotIn('command_approval',result)
   self.assertEqual(set(_pending),before)
   execute.assert_not_called()
   # The Medium route proposes separately, so it has to refuse the same way.
   with patch('process_tools.inspect_target',side_effect=dead),patch.object(server,'get_settings',return_value={'computer_control_enabled':True,'response_restriction_level':'medium'}),patch('assistant_tools.execute') as execute:
    medium=await server.chat({'text':'kill process 999999','defer_audio':True})
   self.assertEqual(medium['reply'],'That process no longer exists. Refresh the process list.')
   self.assertEqual(medium['response_kind'],'clarification')
   self.assertEqual(set(_pending),before)
   execute.assert_not_called()
  finally:
   with patch('process_tools.inspect_target',side_effect=dead):
    _pending.clear()
 async def test_clipboard_has_separate_opt_in_and_bounded_text(self):
  import app
  with patch.object(app,'get_settings',return_value={'computer_control_enabled':True}),patch('native_clipboard.read_text') as read:
   self.assertEqual((await app.assistant_device_action({'phone':True,'action':'clipboard.read'})).status_code,403);read.assert_not_called()
  with patch.object(app,'get_settings',return_value={'phone_clipboard_enabled':True}),patch('native_clipboard.read_text',return_value='explicit test'):
   self.assertEqual((await app.assistant_device_action({'phone':True,'action':'clipboard.read'}))['text'],'explicit test')
   self.assertEqual((await app.assistant_device_action({'phone':True,'action':'clipboard.write','text':'x'*4097})).status_code,400)
if __name__=='__main__':unittest.main()
