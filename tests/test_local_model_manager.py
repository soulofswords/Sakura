import unittest,json
from unittest.mock import patch,MagicMock
from local_model_manager import ModelManager
class ModelManagerTests(unittest.TestCase):
    def test_protected_model_cannot_be_deleted(self):
        with patch('local_model_manager.list_models') as listing:
            with self.assertRaises(ValueError):ModelManager().remove('gemma3:4b','',['gemma3:4b'])
            listing.assert_not_called()
    def test_only_selected_installed_model_is_deleted(self):
        with patch('local_model_manager.list_models',return_value=[{'name':'gemma3:4b'},{'name':'qwen3.8:27b'}]),patch('local_model_manager.server_for_folder',return_value='http://127.0.0.1:11434'),patch('local_model_manager.requests.delete') as delete:
            ModelManager().remove('gemma3:4b','',['qwen3.8:27b'])
            self.assertEqual(delete.call_args.kwargs['json'],{'model':'gemma3:4b'})
    def test_unknown_model_not_deleted(self):
        with patch('local_model_manager.list_models',return_value=[]),patch('local_model_manager.requests.delete') as delete:
            with self.assertRaises(ValueError):ModelManager().remove('missing:4b','',[])
            delete.assert_not_called()
    def test_download_rejects_invalid_names_and_parallel_downloads(self):
        manager=ModelManager()
        with self.assertRaises(ValueError):manager.download('https://example.com','')
        manager.job['running']=True
        with self.assertRaises(ValueError):manager.download('gemma3:4b','')
    def test_download_checks_vision_without_deleting_existing_models(self):
        manager=ModelManager();manager.job={'running':True}
        response=MagicMock();response.__enter__.return_value=response
        response.iter_lines.return_value=[json.dumps({'status':'success'}).encode()]
        show=MagicMock();show.json.return_value={'capabilities':['vision']}
        with patch('local_model_manager.requests.post',side_effect=[response,show]),patch('local_model_manager.requests.delete') as delete:
            manager._pull('http://127.0.0.1:11434','gemma3:4b')
            self.assertTrue(manager.status()['vision']);self.assertFalse(manager.status()['running']);delete.assert_not_called()
class RegistryTests(unittest.TestCase):
    def test_search_only_offers_local_vision_families(self):
        from local_model_manager import registry_search
        response=MagicMock();response.text=('<a href="/library/qwen3-vl">Qwen vision 2b 4b</a>'
            '<a href="/library/cloudy">vision cloud</a><a href="/library/embed">vision embedding</a>'
            '<a href="/library/text">text tools</a>')
        with patch('local_model_manager.requests.get',return_value=response) as get:
            result=registry_search('qwen')
            self.assertEqual([m['family'] for m in result['models']],['qwen3-vl'])
            self.assertEqual(get.call_args.kwargs['params'],{'q':'qwen','c':'vision'})
    def test_weight_variants_include_size_and_exclude_cloud_or_text(self):
        from local_model_manager import registry_search
        response=MagicMock();response.text=('<a href="/library/qwen3-vl:4b-q8_0">qwen 5.1GB Text, Image</a>'
            '<a href="/library/qwen3-vl:4b-q8_0">duplicate</a><a href="/library/qwen3-vl:cloud">Image</a>'
            '<a href="/library/qwen3-vl:text">Text</a>')
        with patch('local_model_manager.requests.get',return_value=response):
            result=registry_search(family='qwen3-vl')['models']
            self.assertEqual(len(result),1);self.assertEqual(result[0]['download'],'5.1GB')
        with self.assertRaises(ValueError):registry_search(family='../../other')
    def test_own_model_import_requires_local_gguf_files(self):
        from local_model_manager import import_gguf
        with self.assertRaises(ValueError):import_gguf(ModelManager(),'my-model',['missing.gguf'],'')
        with self.assertRaises(ValueError):import_gguf(ModelManager(),'https://host/model',[],'')

if __name__=='__main__':unittest.main()
