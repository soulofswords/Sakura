import tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from llm import LLM
from assistant_commands import run_command
class CompanionFixTests(unittest.TestCase):
 def test_polite_browser_commands(self):
  with patch('assistant_commands.Path.is_file',return_value=True),patch('assistant_commands.subprocess.Popen') as launch:
   for text in ['hey can u open google chrome for me','Hey Jean, can you open Google Chrome for me please?']:
    self.assertEqual(run_command(text,True,'Jean'),'Opening Google Chrome.')
   self.assertEqual(run_command('Hey, can you open Microsoft Edge for me?',True,'Jean'),'Opening Microsoft Edge.')
   self.assertIn('msedge.exe',launch.call_args.args[0][0])
   self.assertIn('Enable computer access',run_command('hey can u open edge for me',False,'Jean'))
 def test_current_name_avatar_and_ephemeral_images(self):
  with tempfile.TemporaryDirectory() as folder:
   llm=LLM(Path(folder)/'memory.json');llm.history=[{'role':'assistant','content':'I am Sakura.'}];llm.set_assistant_name('Jean')
   with patch.object(llm,'_request',return_value='Yes, that is my avatar.') as request:
    llm.chat('Are you that girl?', 'screen', 'avatar')
    messages=request.call_args.args[0]
    self.assertEqual(messages[-1]['images'],['screen','avatar'])
    self.assertTrue(any('Your current name is Jean' in m['content'] for m in messages))
    self.assertTrue(any('currently selected digital avatar' in m['content'] for m in messages))
   self.assertNotIn('images',llm.memory_path.read_text())
