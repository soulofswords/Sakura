import unittest
from unittest.mock import Mock,patch
from cloud_diagnostics import discover,test_generation as generation,provider_error

def response(data,status=200):
    result=Mock(status_code=status);result.json.return_value=data;return result

class DiagnosticTests(unittest.TestCase):
    def test_discovery_endpoint_uses_only_selected_provider_and_never_saves_key(self):
        import app
        from local_client import TestClient
        with patch.object(app.app.state,'tracking_only',False,create=True),patch('cloud_diagnostics.discover',return_value=['gpt-4.1-mini']) as discover,patch.object(app,'save_settings') as save:
            result=TestClient(app.app).post('/api/llm/models',json={'provider':'openai','api_key':'private-unsaved-example'})
            self.assertEqual(result.status_code,200,result.text);self.assertEqual(result.json()['models'],['gpt-4.1-mini'])
            self.assertEqual(discover.call_args.args[:2],('openai','private-unsaved-example'));save.assert_not_called()
            self.assertNotIn('private-unsaved-example',result.text)

    def test_catalog_provider_bound_and_filtered(self):
        with patch('cloud_diagnostics.requests.request',return_value=response({'models':[{'name':'models/gemini-flash-test','supportedGenerationMethods':['generateContent']},{'name':'models/gemini-tts','supportedGenerationMethods':['generateContent']}]})) as request:
            self.assertEqual(discover('gemini','test-google-key'),['gemini-flash-test'])
            self.assertIn('generativelanguage.googleapis.com',request.call_args.args[1]);self.assertEqual(request.call_args.kwargs['headers'],{'x-goog-api-key':'test-google-key'})
            self.assertFalse(request.call_args.kwargs['allow_redirects'])
        with patch('cloud_diagnostics.requests.request',return_value=response({'data':[{'id':'gpt-4.1-mini'},{'id':'tts-1'},{'id':'gpt-audio'}]})) as request:
            self.assertEqual(discover('openai','test-openai-key'),['gpt-4.1-mini'])
            self.assertEqual(request.call_args.kwargs['headers'],{'Authorization':'Bearer test-openai-key'})

    def test_custom_catalog_does_not_require_model_id(self):
        with patch('cloud_diagnostics.requests.request',return_value=response({'data':[{'id':'company/model:version'}]})) as request:
            self.assertEqual(discover('compatible','custom-key',endpoint='https://custom.example/v1'),['company/model:version'])
            self.assertEqual(request.call_args.args[1],'https://custom.example/v1/models')

    def test_small_generation_is_real_generation_not_model_lookup(self):
        with patch('cloud_diagnostics.requests.request',return_value=response({'candidates':[{'content':{'parts':[{'text':'OK'}]}}]})) as request:
            self.assertIn('Passed',generation('gemini','key','gemini-test'))
            self.assertEqual(request.call_args.args[0],'POST');self.assertTrue(request.call_args.args[1].endswith(':generateContent'))
            self.assertEqual(request.call_args.kwargs['json']['generationConfig']['maxOutputTokens'],64)
        with patch('cloud_diagnostics.requests.request',return_value=response({'choices':[{'message':{'content':'OK'}}]})) as request:
            generation('openai','key','gpt-4.1-mini')
            self.assertEqual(request.call_args.kwargs['json']['max_completion_tokens'],32)

    def test_quota_detail_and_redaction(self):
        failure=response({'error':{'code':'insufficient_quota','type':'insufficient_quota','message':'No credit for secret-key and sk-proj-privateValue'}},429)
        message=provider_error('openai',failure,'secret-key')
        self.assertIn('billing/quota',message);self.assertNotIn('secret-key',message);self.assertNotIn('sk-proj-privateValue',message)
        with patch('cloud_diagnostics.requests.request',return_value=failure) as request:
            with self.assertRaisesRegex(ValueError,'insufficient_quota'):generation('openai','secret-key','gpt-4.1-mini')
            self.assertEqual(request.call_count,1)
