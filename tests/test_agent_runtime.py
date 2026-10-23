import copy
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock,patch

from agent_connections import Connections,bounded_schema
from agent_runtime import AgentRuntime,run_process,_decode_plan


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.root=Path(self.folder.name);self.runtime=AgentRuntime(Connections(self.root/'connections.json'))
        self.run=self.runtime.new_run('Read and summarize my document',str(self.root))
    def action(self,tool,args):
        return self.runtime.propose(self.run['id'],tool,args)['steps'][-1]
    def test_file_read_is_pending_until_exact_one_shot_approval(self):
        path=self.root/'notes.txt';path.write_text('Private engineering CV',encoding='utf-8')
        action=self.action('files.read',{'path':'notes.txt'})
        self.assertNotIn('Private engineering CV',json.dumps(action))
        self.assertEqual(action['status'],'pending')
        result=self.runtime.decide(action['id'],True)
        self.assertEqual(result['action']['result']['text'],'Private engineering CV')
        with self.assertRaises(ValueError):self.runtime.decide(action['id'],True)
    def test_docx_write_waits_for_approval_and_preserves_existing_files(self):
        output=self.root/'CV - Sakura Draft.docx'
        action=self.action('files.write',{'path':output.name,'content':'# Candidate\n## Experience\n- Improved service reliability.'})
        self.assertFalse(output.exists());self.assertEqual(action['status'],'pending')
        result=self.runtime.decide(action['id'],True)
        self.assertTrue(output.is_file());self.assertEqual(result['action']['status'],'completed')
        from docx import Document
        text='\n'.join(paragraph.text for paragraph in Document(output).paragraphs)
        self.assertIn('Candidate',text);self.assertIn('Improved service reliability.',text)
        with self.assertRaisesRegex(ValueError,'already exists'):
            self.runtime.propose(self.run['id'],'files.write',{'path':output.name,'content':'overwrite'})
    def test_rejected_command_is_never_executed(self):
        action=self.action('shell.run',{'command':'Write-Output hello'})
        with patch('agent_runtime.run_process') as execute:
            result=self.runtime.decide(action['id'],False)
        execute.assert_not_called();self.assertEqual(result['action']['status'],'rejected')
    def test_reviewed_command_and_cwd_are_frozen_against_ui_mutation(self):
        action=self.action('shell.run',{'command':'Write-Output hello'})
        action['arguments']['command']='unreviewed mutation'
        with patch('agent_runtime.run_process',return_value={'ok':True,'output':'hello'}) as execute:
            result=self.runtime.decide(action['id'],True)
        self.assertEqual(execute.call_args.args[0][-1],'Write-Output hello')
        self.assertEqual(execute.call_args.args[1],self.root.resolve())
        self.assertEqual(result['action']['status'],'completed')
    def test_modified_script_requires_new_approval_and_no_execution(self):
        path=self.root/'task.py';path.write_text('print("original")',encoding='utf-8')
        action=self.action('files.run',{'path':'task.py','args':[]})
        self.assertIn('original',action['preview']['script_excerpt'])
        path.write_text('print("changed")',encoding='utf-8')
        with patch('agent_runtime.run_process') as execute:result=self.runtime.decide(action['id'],True)
        execute.assert_not_called();self.assertEqual(result['action']['status'],'failed')
        self.assertIn('changed after review',result['action']['result']['error'])
    def test_outside_workspace_and_unknown_tools_cannot_be_proposed(self):
        for tool,args in [('files.read',{'path':'../outside.txt'}),('shell.run',{'command':'pwd','cwd':'..'}),('unknown',{})]:
            with self.assertRaises((ValueError,FileNotFoundError)):self.runtime.propose(self.run['id'],tool,args)
    def test_changed_mcp_connection_blocks_execution(self):
        config={'id':'a'*32,'name':'Demo','transport':'stdio','command':sys.executable,'args':[],'revision':'1'}
        self.runtime.connections.tools[config['id']]=[{'name':'echo','description':'Echo','inputSchema':{'type':'object','properties':{'text':{'type':'string'}},'required':['text']}}]
        with patch.object(self.runtime.connections,'get',return_value=config):
            action=self.action('mcp:'+config['id']+':echo',{'text':'approved'})
        with patch.object(self.runtime.connections,'get',return_value={**config,'revision':'2'}),patch('agent_runtime.mcp_request') as execute:
            result=self.runtime.decide(action['id'],True)
        execute.assert_not_called();self.assertEqual(result['action']['status'],'failed')
    def test_discovery_also_requires_approval(self):
        config={'id':'a'*32,'name':'Demo','transport':'stdio','command':sys.executable,'args':[]}
        with patch.object(self.runtime.connections,'get',return_value=config),patch('agent_runtime.mcp_request',return_value=[]) as connect:
            action=self.runtime.discover_proposal(config['id']);connect.assert_not_called()
            self.runtime.decide(action['id'],True);connect.assert_called_once()
    def test_cancelled_task_does_not_execute_pending_action(self):
        action=self.action('shell.run',{'command':'Write-Output hello'})
        self.runtime.cancel(self.run['id'])
        with patch('agent_runtime.run_process') as execute,self.assertRaises(ValueError):self.runtime.decide(action['id'],True)
        execute.assert_not_called()
    def test_planner_proposes_a_write_and_stops_before_action(self):
        model=Mock();model._request_raw.return_value=json.dumps(
            {'tool':'files.write','arguments':{'path':'draft.md','content':'# Plan\n\nApproved wording.'},'reason':'Save the draft'})
        with patch.object(self.runtime,'_execute') as execute:
            result=self.runtime.plan(self.run['id'],model)
        execute.assert_not_called();self.assertEqual(result['status'],'awaiting_approval')
        self.assertTrue(model._request_raw.call_args.kwargs['structured'])
        self.assertTrue(model._request_raw.call_args.kwargs['planning'])
        self.assertIn('brief, natural, respectful speech',model._request_raw.call_args.args[0][0]['content'])
        context=json.loads(model._request_raw.call_args.args[0][1]['content'])
        self.assertNotIn('inputSchema',json.dumps(context['tools']))
        self.assertIn('files.write',[item['name'] for item in context['tools']])
    def test_planner_runs_read_only_steps_without_a_click_then_stops_at_the_write(self):
        model=Mock()
        model._request_raw.side_effect=[
            json.dumps({'tool':'files.list','arguments':{'path':'.'},'reason':'Find the source','plan':'read it, then write'}),
            json.dumps({'tool':'files.read','arguments':{'path':'notes.txt'},'reason':'Read the source'}),
            json.dumps({'tool':'files.write','arguments':{'path':'out.md','content':'# Result\n\nFrom the notes.'},'reason':'Save it'})]
        (self.root/'notes.txt').write_text('Only approved facts',encoding='utf-8')
        result=self.runtime.plan(self.run['id'],model)
        self.assertEqual([step['tool'] for step in result['steps']],['files.list','files.read','files.write'])
        self.assertEqual([step['status'] for step in result['steps']],['completed','completed','pending'])
        self.assertEqual([bool(step.get('auto')) for step in result['steps']],[True,True,False])
        self.assertEqual(result['status'],'awaiting_approval')
        self.assertEqual(result['plan'],'read it, then write')
    def test_auto_continue_off_keeps_every_step_pending(self):
        run=self.runtime.new_run('Read my notes',str(self.root),auto_continue=False)
        model=Mock();model._request_raw.return_value=json.dumps({'tool':'files.list','arguments':{'path':'.'},'reason':'List the folder'})
        with patch.object(self.runtime,'_execute') as execute:
            result=self.runtime.plan(run['id'],model)
        execute.assert_not_called();self.assertEqual(result['steps'][0]['status'],'pending')
    def test_auto_continue_never_approves_a_shell_command(self):
        model=Mock();model._request_raw.return_value=json.dumps({'tool':'shell.run','arguments':{'command':'Remove-Item draft.md'},'reason':'Clean up'})
        with patch.object(self.runtime,'_execute') as execute:
            result=self.runtime.plan(self.run['id'],model)
        execute.assert_not_called();self.assertEqual(result['steps'][0]['status'],'pending')
    def test_planner_ignores_trailing_provider_text_after_one_valid_object(self):
        value=_decode_plan('{"tool":"files.list","arguments":{"path":"."},"reason":"Find resume"}\nprovider footer')
        self.assertEqual(value['tool'],'files.list')
    def test_image_request_is_not_marked_complete_without_image_tool(self):
        model=Mock()
        run=self.runtime.new_run('Generate an image of a boy reading',str(self.root))
        result=self.runtime.plan(run['id'],model)
        model._request_raw.assert_not_called()
        self.assertEqual(result['status'],'blocked')
        self.assertIn('no image-generation tool is connected',result['summary'])
        self.assertEqual(result['steps'],[])
    def test_planner_cannot_claim_completion_while_describing_future_work(self):
        model=Mock();model._request_raw.return_value=json.dumps({'done':True,'summary':'Proceeding to generate the image now.'})
        result=self.runtime.plan(self.run['id'],model)
        self.assertEqual(result['status'],'ready')
        self.assertIn('did not choose a supported action',result['summary'])
    def test_approved_harmless_script_really_runs_and_captures_output(self):
        script=self.root/'hello.py';script.write_text('print("approved test output")',encoding='utf-8')
        action=self.action('files.run',{'path':'hello.py'})
        result=self.runtime.decide(action['id'],True)
        self.assertEqual(result['action']['result']['exit_code'],0)
        self.assertIn('approved test output',result['action']['result']['output'])
    def test_timeout_stops_process_and_output_is_bounded(self):
        result=run_process([sys.executable,'-c','import time;time.sleep(10)'],self.root,timeout=.15)
        self.assertTrue(result['timed_out']);self.assertFalse(result['ok'])
        result=run_process([sys.executable,'-c','print("x"*90000)'],self.root)
        self.assertTrue(result['output_truncated']);self.assertEqual(len(result['output']),65536)
    def test_task_history_survives_restart_but_pending_approval_does_not(self):
        store=self.root/'history.json'
        runtime=AgentRuntime(Connections(self.root/'persisted-connections.json'),store_path=store)
        run=runtime.new_run('Read my notes',str(self.root))
        pending=runtime.propose(run['id'],'files.list',{'path':'.'})['steps'][-1]
        restored=AgentRuntime(Connections(self.root/'persisted-connections.json'),store_path=store)
        saved=restored.state(run['id'])
        self.assertEqual(saved['status'],'ready')
        self.assertEqual(saved['steps'][0]['status'],'interrupted')
        self.assertNotIn('bindings',saved['steps'][0])
        with self.assertRaisesRegex(ValueError,'no longer pending'):
            restored.decide(pending['id'],True)
        self.assertEqual(restored.clear_history(),{'ok':True})
        self.assertFalse(store.exists())
        self.assertEqual(AgentRuntime(Connections(self.root/'persisted-connections.json'),store_path=store).runs,{})


class RuntimeLimitsTests(unittest.TestCase):
    """The Agent panel must stay usable across a long session, not only in a first task."""

    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.root=Path(self.folder.name)
        self.store=self.root/'history.json'
        self.runtime=AgentRuntime(Connections(self.root/'connections.json'),store_path=self.store)

    def fill(self,status):
        for index in range(30):
            run=self.runtime.new_run(f'Task {index}',str(self.root))
            self.runtime.runs[run['id']]['status']=status

    def test_a_full_session_evicts_a_run_instead_of_refusing_new_work(self):
        self.fill('failed')
        before=len(self.runtime.runs)
        self.runtime.new_run('One more task',str(self.root))
        self.assertEqual(len(self.runtime.runs),before)

    def test_evicting_a_run_drops_its_stored_approvals(self):
        oldest=self.runtime.new_run('Oldest task',str(self.root))['id']
        self.runtime.propose(oldest,'files.list',{'path':'.'})
        self.assertTrue(any(action.get('run_id')==oldest for action in self.runtime.actions.values()))
        self.runtime.runs[oldest]['status']='completed'
        for index in range(30):self.runtime.new_run(f'Filler {index}',str(self.root))
        self.assertFalse(any(action.get('run_id')==oldest for action in self.runtime.actions.values()))

    def test_only_tasks_waiting_on_a_click_block_a_new_one(self):
        self.fill('awaiting_approval')
        self.runtime.runs[next(iter(self.runtime.runs))]['status']='running'
        with self.assertRaisesRegex(ValueError,'waiting for your approval'):
            self.runtime.new_run('Cannot start yet',str(self.root))

    def test_cancel_marks_the_step_record_not_only_the_action(self):
        run=self.runtime.new_run('Cancel me',str(self.root))
        pending=self.runtime.propose(run['id'],'files.list',{'path':'.'})['steps'][-1]
        cancelled=self.runtime.cancel(run['id'])
        self.assertEqual(cancelled['steps'][-1]['status'],'rejected')
        self.assertEqual(cancelled['status'],'cancelled')
        self.assertNotIn(pending['id'],self.runtime.actions)
        self.assertFalse(self.store.read_text(encoding='utf-8').count('"pending"'))

    def test_a_decided_action_is_forgotten_by_the_pending_table(self):
        run=self.runtime.new_run('Finish me',str(self.root))
        with self.runtime.lock:live=len(self.runtime.actions)
        action=self.runtime.propose(run['id'],'files.list',{'path':'.'})['steps'][-1]
        self.runtime.decide(action['id'],True)
        with self.runtime.lock:self.assertEqual(len(self.runtime.actions),live)

    def test_records_are_returned_without_tamper_check_internals(self):
        (self.root/'cv.txt').write_text('Real resume text',encoding='utf-8')
        run=self.runtime.new_run('Hide internals',str(self.root))
        self.runtime.propose(run['id'],'files.read',{'path':'cv.txt'})
        shown=self.runtime.state(run['id'])['steps'][-1]
        self.assertNotIn('bindings',shown);self.assertNotIn('approval_digest',shown);self.assertNotIn('schema_hash',shown)
        self.assertEqual([item['id'] for item in self.runtime.states()],
                         [item['id'] for item in self.runtime.runs.values()])
        live=[action for action in self.runtime.actions.values() if action.get('tool')=='files.read']
        self.assertIn('file_hash',live[0]['bindings'])
        self.runtime.decide(live[0]['id'],True)

    def test_the_history_file_stays_inside_its_budget(self):
        from agent_runtime import MAX_STORE_BYTES
        run=self.runtime.new_run('Oversized',str(self.root))
        action=self.runtime.propose(run['id'],'files.list',{'path':'.'})
        step=self.runtime.runs[run['id']]['steps'][-1]
        # A preview field that the old per-key truncation never covered.
        step['result']={'tools':[{'description':'y'*40000} for _ in range(200)]}
        self.runtime._save_runs()
        self.assertLessEqual(self.store.stat().st_size,MAX_STORE_BYTES)
        restored=AgentRuntime(Connections(self.root/'second-connections.json'),store_path=self.store)
        stored=restored.runs[run['id']]['steps'][-1]['result']['tools'][0]['description']
        self.assertLess(len(stored),40000);self.assertIn('Stored history truncated',stored)


class ConnectionTests(unittest.TestCase):
    def test_schema_cannot_fetch_an_unapproved_external_resource(self):
        with self.assertRaises(ValueError):bounded_schema({'$ref':'https://external.example/schema'})
        self.assertEqual(bounded_schema({'type':'object','properties':{'x':{'$ref':'#/$defs/x'}},'$defs':{'x':{'type':'string'}}})['type'],'object')
    def test_credentials_are_not_written_to_plaintext_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            registry=Connections(Path(folder)/'config.json')
            store={}
            with patch('agent_connections.secret_get',side_effect=lambda key:copy.deepcopy(store.get(key,{}))),patch('agent_connections.secret_set',side_effect=lambda key,value:store.update({key:value})):
                config=registry.save({'name':'Demo','transport':'http','url':'https://example.com/mcp','token':'private-api-value'})
                text=registry.path.read_text()
                self.assertNotIn('private-api-value',text)
                self.assertTrue(config['credential_set']);self.assertTrue(store)
                original=config['revision']
                changed=registry.save({**config,'token':'other-value'})
                self.assertNotEqual(changed['revision'],original)
    def test_embedded_url_credentials_and_remote_plain_http_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            registry=Connections(Path(folder)/'config.json')
            for url in ('http://remote.example/mcp','https://key@example.com/mcp','https://example.com/mcp?token=secret'):
                with self.assertRaises(ValueError):registry.save({'name':'Bad','url':url})
