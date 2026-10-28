import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from agent_api import agent_router
from agent_connections import Connections
from agent_runtime import AgentRuntime


class AgentAPITests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        runtime=AgentRuntime(Connections(Path(self.folder.name)/'connections.json'));self.runtime=runtime
        patcher=patch('agent_api.runtime',runtime);patcher.start();self.addCleanup(patcher.stop)
        app=FastAPI();app.include_router(agent_router(lambda:Mock()))
        self.client=TestClient(app,base_url='http://127.0.0.1:8790',client=('127.0.0.1',35000))
        self.token=re.search(r"const token='([^']+)'",self.client.get('/agent').text)[1]
        self.headers={'X-Sakura-Agent':self.token}
    def test_cross_origin_and_missing_token_cannot_execute_or_configure(self):
        self.assertEqual(self.client.get('/agent').headers.get('x-frame-options'),'SAMEORIGIN')
        for headers in ({},{'X-Sakura-Agent':'bad'},{**self.headers,'Origin':'https://untrusted.example'},{**self.headers,'Sec-Fetch-Site':'cross-site'}):
            response=self.client.post('/api/agent/tasks',headers=headers,json={'goal':'Do stuff','workspace':self.folder.name})
            self.assertEqual(response.status_code,403)
        self.assertEqual(self.client.get('/agent',headers={'Origin':'https://untrusted.example'}).status_code,403)

    def test_new_native_and_schedule_routes_require_local_panel_authorization(self):
        for endpoint,payload in [('local-ai/runtime',{}),('local-ai/import',{'path':'secret.gguf'}),('local-ai/inspect',{'path':'C:/private'}),('local-ai/import-detected',{'path':'secret.gguf'}),
                                 ('local-ai/chat',{'messages':[]}),('automations',{'approved':True}),('library-sync/run',{'approved':True}),('memory',{'enabled':True}),('skills/learn',{'run_id':'a','name':'test'})]:
            self.assertEqual(self.client.post('/api/agent/'+endpoint,json=payload).status_code,403)
            self.assertEqual(self.client.post('/api/agent/'+endpoint,headers={**self.headers,'Origin':'https://outside.example'},json=payload).status_code,403)

    def test_telegram_api_requires_local_authorization(self):
        from telegram_bot import TelegramGateway
        bot=TelegramGateway(Path(self.folder.name)/'telegram.json')
        with patch('telegram_bot.gateway',bot):
            app=FastAPI();app.include_router(agent_router(lambda choice:Mock()))
        client=TestClient(app,base_url='http://127.0.0.1:8790',client=('127.0.0.1',35000))
        token=re.search(r"const token='([^']+)'",client.get('/agent').text)[1]
        headers={'X-Sakura-Agent':token}
        for denied in ({},{'X-Sakura-Agent':'wrong'},{**headers,'Origin':'https://outside.example'}):
            self.assertEqual(client.get('/api/agent/telegram',headers=denied).status_code,403)
            self.assertEqual(client.post('/api/agent/telegram',headers=denied,json={'enabled':False}).status_code,403)
        with patch('credentials.get_cloud_key',return_value=''):
            for payload in ({'enabled':True},{'enabled':False,'chat_ids':'bad'},{'enabled':False,'token':123},
                            {'enabled':False,'clear_token':'yes'},{'enabled':False,'command':'anything'}):
                self.assertEqual(client.post('/api/agent/telegram',headers=headers,json=payload).status_code,400)
            response=client.post('/api/agent/telegram',headers=headers,json={'enabled':False,'chat_ids':'42'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['chat_ids'],[42])
            self.assertNotIn('token',response.json())
            self.assertFalse(response.json()['running'])

    def test_owner_workflow_cannot_accept_command_or_path_injection(self):
        for extra in ({'command':'Remove-Item *'},{'root':'C:/Windows'},{'token':'not-owner'}):
            response=self.client.post('/api/agent/library-sync/run',headers=self.headers,json={'approved':True,**extra})
            self.assertEqual(response.status_code,400)

    def test_native_planner_does_not_call_external_provider_getter(self):
        with patch('agent_api.runtime.plan',return_value={'ok':True}) as plan:
            response=self.client.post('/api/agent/tasks/example/plan',headers=self.headers,json={'provider':'sakura-native'})
        from agent_local_ai import local_ai
        self.assertEqual(response.status_code,200)
        self.assertIs(plan.call_args.args[1],local_ai)
    def test_approval_decision_has_no_mutable_argument_override(self):
        run=self.client.post('/api/agent/tasks',headers=self.headers,json={'goal':'Hello test','workspace':self.folder.name}).json()
        proposal=self.client.post('/api/agent/tasks/'+run['id']+'/propose',headers=self.headers,json={'tool':'shell.run','arguments':{'command':'Write-Output original'}}).json()
        identifier=proposal['steps'][-1]['id']
        with patch('agent_runtime.run_process',return_value={'ok':True,'output':'original'}) as execute:
            response=self.client.post('/api/agent/actions/'+identifier+'/decision',headers=self.headers,json={'approve':True,'arguments':{'command':'changed'}})
        self.assertEqual(response.status_code,200)
        self.assertEqual(execute.call_args.args[0][-1],'Write-Output original')
        self.assertEqual(self.client.post('/api/agent/actions/'+identifier+'/decision',headers=self.headers,json={'approve':True}).status_code,400)
    def test_non_boolean_approval_is_rejected(self):
        self.assertEqual(self.client.post('/api/agent/actions/anything/decision',headers=self.headers,json={'approve':'yes'}).status_code,400)
    def test_non_loopback_client_cannot_load_panel_or_approve(self):
        app=FastAPI();app.include_router(agent_router(lambda:None))
        remote=TestClient(app,base_url='http://127.0.0.1:8790',client=('192.168.1.5',50000))
        self.assertEqual(remote.get('/agent').status_code,403)
    def test_tracking_only_product_cannot_use_agent(self):
        app=FastAPI();app.include_router(agent_router(lambda:None,lambda:False))
        client=TestClient(app,base_url='http://127.0.0.1',client=('127.0.0.1',50000))
        self.assertEqual(client.get('/agent').status_code,409)

    def test_planner_provider_is_selected_explicitly(self):
        selected=[]
        app=FastAPI();app.include_router(agent_router(lambda choice:(selected.append(choice) or object())))
        client=TestClient(app,base_url='http://127.0.0.1:8790',client=('127.0.0.1',35000))
        token=re.search(r"const token='([^']+)'",client.get('/agent').text)[1]
        with patch('agent_api.runtime.plan',return_value={'ok':True}) as plan:
            response=client.post('/api/agent/tasks/example/plan',headers={'X-Sakura-Agent':token},json={'provider':'gemini'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(selected,['gemini'])
        self.assertEqual(plan.call_args.args[0],'example')

    def test_unconfigured_planner_provider_returns_clear_error(self):
        app=FastAPI();app.include_router(agent_router(lambda choice:(_ for _ in ()).throw(ValueError('Google Gemini is not configured.'))))
        client=TestClient(app,base_url='http://127.0.0.1:8790',client=('127.0.0.1',35000))
        token=re.search(r"const token='([^']+)'",client.get('/agent').text)[1]
        response=client.post('/api/agent/tasks/example/plan',headers={'X-Sakura-Agent':token},json={'provider':'gemini'})
        self.assertEqual(response.status_code,400)
        self.assertIn('not configured',response.json()['detail'])

    def test_saved_task_history_can_be_cleared_through_local_agent_api(self):
        self.client.post('/api/agent/tasks',headers=self.headers,json={'goal':'Test persistent history','workspace':self.folder.name})
        self.assertTrue(self.runtime.runs)
        response=self.client.delete('/api/agent/tasks',headers=self.headers)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json(),{'ok':True})
        self.assertFalse(self.runtime.runs)

    def test_google_calendar_connect_opens_the_system_browser(self):
        with patch('agent_api.google_calendar.authorize',return_value='https://accounts.google.com/o/oauth2/v2/auth?test=1'), \
             patch('webbrowser.open',return_value=True) as open_browser:
            response=self.client.post('/api/agent/calendar/connect',headers=self.headers,json={})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()['opened'])
        open_browser.assert_called_once_with('https://accounts.google.com/o/oauth2/v2/auth?test=1',1,True)

    def test_google_calendar_is_prominent_and_directly_reachable_in_agent_workspace(self):
        page=self.client.get('/agent').text
        self.assertIn('id="calendar-open"',page)
        self.assertIn('id="google-calendar"',page)
        self.assertIn('Sign in with Google',page)
        self.assertNotIn('id="calendar-client"',page)
        self.assertNotIn('Set up Google Calendar sign-in',page)
        self.assertNotIn('calendar-save',page)
        self.assertIn('Schedule · next 7 days',page)
        self.assertIn('id="calendar-propose"',page)
        self.assertLess(page.index('id="google-calendar"'),page.index('<section class="card"><h2>Connections</h2>'))

    def test_google_calendar_client_settings_require_agent_local_token(self):
        with patch('agent_api.google_calendar.configure',return_value={'configured':True}) as configure:
            response=self.client.post('/api/agent/calendar/configure',headers=self.headers,
                                      json={'client_id':'desktop.apps.googleusercontent.com','client_secret':''})
        self.assertEqual(response.status_code,200)
        configure.assert_called_once_with('desktop.apps.googleusercontent.com','')
        self.assertEqual(self.client.post('/api/agent/calendar/configure',json={'client_id':'x'}).status_code,403)

    def test_calendar_agenda_reads_only_after_connection_and_limits_to_seven_days(self):
        with patch('agent_api.google_calendar.status',return_value={'connected':True}), \
             patch('agent_api.google_calendar.list_events',return_value={'ok':True,'events':[]}) as list_events:
            response=self.client.get('/api/agent/calendar/agenda',headers=self.headers)
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()['ok'])
        bounds=list_events.call_args.kwargs
        from datetime import datetime
        start=datetime.fromisoformat(bounds['time_min']);end=datetime.fromisoformat(bounds['time_max'])
        self.assertEqual((end-start).days,7)
        self.assertEqual(bounds['max_results'],50)

    def test_calendar_agenda_requires_sign_in(self):
        with patch('agent_api.google_calendar.status',return_value={'connected':False}):
            response=self.client.get('/api/agent/calendar/agenda',headers=self.headers)
        self.assertEqual(response.status_code,400)
        self.assertIn('Connect Google Calendar',response.json()['detail'])

    def test_schedule_form_only_proposes_event_and_waits_for_approval(self):
        with patch('agent_calendar.google_calendar.status',return_value={'connected':True}), \
             patch('agent_calendar.google_calendar.config_fingerprint',return_value='config-a'), \
             patch('agent_calendar.google_calendar.create_event') as create:
            response=self.client.post('/api/agent/calendar/propose',headers=self.headers,json={
                'summary':'Planning session','start':'2026-10-23T10:00:00Z','end':'2026-10-23T10:30:00Z'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['status'],'awaiting_approval')
        self.assertEqual(response.json()['steps'][-1]['tool'],'calendar.events.create')
        self.assertEqual(response.json()['steps'][-1]['status'],'pending')
        create.assert_not_called()
