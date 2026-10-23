import unittest
from unittest.mock import patch,Mock
from ollama_runtime import list_models
class Models(unittest.TestCase):
 def test_migrated_names_and_runner_aliases_are_not_user_copies(self):
  r=Mock();r.json.return_value={'models':[{'name':'qwen:4b','size':3,'digest':'old'},{'name':'qwen:4b','size':4,'digest':'new'},{'name':'llamacpp:new','size':4,'digest':'new'},{'name':'my-custom:latest','size':4,'digest':'new'}]}
  with patch('ollama_runtime.server_for_folder',return_value='http://test'),patch('ollama_runtime.requests.get',return_value=r):
   self.assertEqual(list_models(),[{'name':'qwen:4b','size':4},{'name':'my-custom:latest','size':4}])
if __name__=='__main__':unittest.main()
