import copy
import time
import unittest
from unittest.mock import Mock,patch
from urllib.parse import parse_qs,urlparse

from agent_linkedin import LinkedIn


class LinkedInTests(unittest.TestCase):
    def setUp(self):
        self.saved={};self.linkedin=LinkedIn()
        for target,fn in [('agent_linkedin.secret_get',lambda slot:copy.deepcopy(self.saved)),('agent_linkedin.secret_set',lambda slot,value:self.saved.update(value) if value else self.saved.clear())]:
            item=patch(target,side_effect=fn);item.start();self.addCleanup(item.stop)
        self.linkedin.configure('test-client','test-secret','http://127.0.0.1:8790/api/agent/linkedin/callback')
    def test_oauth_uses_one_shot_state_and_stores_token_protected(self):
        url=self.linkedin.authorize();params=parse_qs(urlparse(url).query)
        self.assertEqual(params['scope'],['openid profile email w_member_social']);self.assertNotIn('test-secret',url)
        response=Mock(status_code=200);response.json.return_value={'access_token':'private-token','expires_in':3600,'scope':'openid profile w_member_social'}
        with patch('agent_linkedin.requests.post',return_value=response) as exchange:
            self.assertTrue(self.linkedin.callback(params['state'][0],'test-code')['connected'])
            self.assertEqual(exchange.call_args.kwargs['data']['client_secret'],'test-secret')
            with self.assertRaises(ValueError):self.linkedin.callback(params['state'][0],'test-code')
        self.assertNotIn('private-token',str(self.linkedin.status()))
    def test_wrong_state_never_exchanges_code(self):
        self.linkedin.authorize()
        with patch('agent_linkedin.requests.post') as exchange,self.assertRaises(ValueError):self.linkedin.callback('wrong','code')
        exchange.assert_not_called()
    def test_publish_uses_exact_text_visibility_account_and_no_retry(self):
        self.saved.update(access_token='private-token',expires_at=time.time()+3600,scopes=['w_member_social'],profile={'sub':'member-123','name':'Test Member'})
        response=Mock(status_code=201,headers={'x-restli-id':'urn:li:share:test'})
        with patch('agent_linkedin.requests.post',return_value=response) as post:
            result=self.linkedin.publish('My exact approved post.','CONNECTIONS')
        self.assertTrue(result['published']);self.assertEqual(post.call_count,1)
        payload=post.call_args.kwargs['json'];self.assertEqual(payload['commentary'],'My exact approved post.')
        self.assertEqual(payload['visibility'],'CONNECTIONS');self.assertEqual(payload['author'],'urn:li:person:member-123')
    def test_messaging_is_not_claimed_as_granted_by_signin(self):
        self.assertIn('Requires',self.linkedin.status()['messages'])
