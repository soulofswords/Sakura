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
  import base64
  from io import BytesIO
  from PIL import Image
  def frame(color):
   image=Image.new('RGB',(320,200),color);buffer=BytesIO();image.save(buffer,format='PNG')
   return base64.b64encode(buffer.getvalue()).decode()
  with tempfile.TemporaryDirectory() as folder:
   llm=LLM(Path(folder)/'memory.json');llm.history=[{'role':'assistant','content':'I am Sakura.'}];llm.set_assistant_name('Jean')
   with patch.object(llm,'_request',return_value='Yes, that is my avatar.') as request:
    llm.chat('Are you that girl?', frame('navy'), frame('coral'))
    messages=request.call_args.args[0]
    # Screen and avatar travel as one labelled side-by-side frame, not two images.
    images=messages[-1]['images']
    self.assertEqual(len(images),1)
    with Image.open(BytesIO(base64.b64decode(images[0]))) as combined:
     self.assertGreater(combined.width,320)
     self.assertGreater(combined.height,200)
    self.assertTrue(any('Your current name is Jean' in m['content'] for m in messages))
    self.assertTrue(any('SCREEN on the left and YOUR AVATAR on the right' in m['content'] for m in messages))
   self.assertNotIn('images',llm.memory_path.read_text())
