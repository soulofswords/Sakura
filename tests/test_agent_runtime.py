import copy
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock,patch

from agent_connections import Connections,bounded_schema
from agent_runtime import AgentRuntime,run_process,_decode_plan,_skill_names


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
        audit=self.runtime.audit.recent()
        self.assertEqual([r['status'] for r in audit],['completed','started'])
        self.assertNotIn('Private engineering CV',json.dumps(audit))
        self.assertNotIn('notes.txt',json.dumps(audit))
        with self.assertRaises(ValueError):self.runtime.decide(action['id'],True)
    def test_a_long_file_can_be_read_on_to_the_end(self):
        """A 69 KB README once trapped the planner on its first 20000 characters: it proposed the
        same read four times and the loop guard blocked the task. Each call now says how far it got
        and hands back the offset for the rest, and the notice leads the result because older steps
        are kept only as their first 1500 characters."""
        path=self.root/'README.md';path.write_text('x'*25000+'SETUP STEPS HERE',encoding='utf-8')
        first=self.runtime.decide(self.action('files.read',{'path':'README.md'})['id'],True)['action']['result']
        self.assertEqual(len(first['text']),20000)
        self.assertTrue(first['more_to_read'])
        self.assertFalse(first['extraction_incomplete'])
        self.assertEqual(first['reading'],'characters 0 to 20000 of 25016')
        self.assertIn('more_to_read',json.dumps(first)[:200])
        second=self.runtime.decide(self.action('files.read',{'path':'README.md','from_character':first['next_from_character']})['id'],True)['action']['result']
        self.assertEqual(second['reading'],'characters 20000 to 25016 of 25016')
        self.assertFalse(second['more_to_read'])
        self.assertEqual(second['next_from_character'],'')
        self.assertTrue(second['text'].endswith('SETUP STEPS HERE'))
        from agent_loop_guard import inspect as loop_check
        completed=[{'tool':'files.read','arguments':{'path':'README.md'},'status':'completed'},
                   {'tool':'files.read','arguments':{'path':'README.md','from_character':20000},'status':'completed'}]
        self.assertFalse(loop_check(completed,'files.read',{'path':'README.md','from_character':40000})['blocked'])
    def test_setup_files_without_a_known_extension_are_still_readable(self):
        """The 4B planner paged the cloned README correctly, then stopped the task on .env.example
        because the uploader's extension list has no entry for it; setup files carry such names."""
        (self.root/'.env.example').write_text('MAPS_API_KEY=\n',encoding='utf-8')
        (self.root/'Dockerfile').write_text('FROM node:20\n',encoding='utf-8')
        for name in ('.env.example','Dockerfile'):
            result=self.runtime.decide(self.action('files.read',{'path':name})['id'],True)['action']['result']
            self.assertTrue(result['ok'],name)
            self.assertEqual(result['reading'],'characters 0 to %d of %d'%(len(result['text']),len(result['text'])),name)
        (self.root/'secret.exe').write_bytes(b'\0MZ\0\0binary')
        failed=self.runtime.decide(self.action('files.read',{'path':'secret.exe'})['id'],True)['action']
        self.assertEqual(failed['status'],'failed')
        self.assertIn('binary',failed['result']['error'].lower())
    def test_auto_approval_is_limited_to_observing_tools(self):
        """Delegation calls _decide directly, so the guard cannot trust its caller."""
        action=self.action('files.write',{'path':'Draft.md','content':'# Notes'})
        with self.assertRaises(ValueError):self.runtime._decide(action['id'],True,auto=True)
        self.assertFalse((self.root/'Draft.md').exists())
        self.assertEqual(self.runtime.state(self.run['id'])['steps'][-1]['status'],'pending')
        self.runtime.decide(action['id'],False)
        (self.root/'notes.txt').write_text('read only',encoding='utf-8')
        read=self.action('files.read',{'path':'notes.txt'})
        self.assertEqual(self.runtime._decide(read['id'],True,auto=True)['action']['status'],'completed')
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
    def test_xlsx_write_is_reviewed_then_written_with_native_cell_types(self):
        import xml.etree.ElementTree as ET
        import zipfile
        output=self.root/'Scores.xlsx'
        action=self.action('files.sheet.create',{'path':output.name,'sheet_name':'Scores',
            'rows':[['Name','Score'],['Alice',30],['Total',['formula','=SUM(B2:B2)']]]})
        self.assertFalse(output.exists());self.assertEqual(action['status'],'pending')
        self.assertEqual(action['preview']['rows'],3)
        self.assertIn('Alice | 30',action['preview']['preview'])
        self.assertNotIn('bindings',action)
        result=self.runtime.decide(action['id'],True)
        self.assertEqual(result['action']['status'],'completed')
        self.assertTrue(output.is_file())
        ns='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
        with zipfile.ZipFile(output) as package:
            sheet=ET.fromstring(package.read('xl/worksheets/sheet1.xml'))
        cells={cell.get('r'):cell for cell in sheet.iter(ns+'c')}
        self.assertEqual(cells['A2'].get('t'),'inlineStr')
        self.assertIsNone(cells['B2'].get('t'))
        self.assertEqual(cells['B3'].find(ns+'f').text,'SUM(B2:B2)')
        with self.assertRaisesRegex(ValueError,'already exists'):
            self.runtime.propose(self.run['id'],'files.sheet.create',{'path':output.name,'rows':[['x']]})
    def test_xlsx_write_refuses_a_bad_cell_before_review(self):
        with self.assertRaisesRegex(ValueError,'real number'):
            self.action('files.sheet.create',{'path':'bad.xlsx','rows':[['ok',['number','not a number']]]})
        with self.assertRaisesRegex(ValueError,'formula'):
            self.action('files.sheet.create',{'path':'bad.xlsx','rows':[[['formula','=']]]})
        with self.assertRaisesRegex(ValueError,'.xlsx'):
            self.action('files.sheet.create',{'path':'bad.csv','rows':[['x']]})
    def test_text_edit_shows_diff_and_applies_after_approval(self):
        path=self.root/'notes.txt';path.write_text('one\ntwo\nthree\n',encoding='utf-8')
        action=self.action('files.text.edit',{'path':'notes.txt','replacements':[{'old':'two','new':'TWO','count':1}]})
        self.assertEqual(action['status'],'pending')
        self.assertIn('-two\n+TWO',action['preview']['diff'])
        self.assertNotIn('-one',action['preview']['diff'])
        result=self.runtime.decide(action['id'],True)
        self.assertEqual(result['action']['status'],'completed')
        self.assertEqual(path.read_text(encoding='utf-8'),'one\nTWO\nthree\n')
    def test_text_edit_stale_after_late_file_change_and_never_writes(self):
        path=self.root/'notes.txt';path.write_text('one\ntwo\n',encoding='utf-8')
        action=self.action('files.text.edit',{'path':'notes.txt','replacements':[{'old':'two','new':'TWO','count':1}]})
        path.write_text('one\ntwo changed\n',encoding='utf-8')
        result=self.runtime.decide(action['id'],True)
        self.assertEqual(result['action']['status'],'failed')
        self.assertIn('no longer current',result['action']['result']['error'])
        self.assertEqual(path.read_text(encoding='utf-8'),'one\ntwo changed\n')
    def test_text_create_refuses_existing_paths_and_docx_suffix(self):
        (self.root/'exists.txt').write_text('keep',encoding='utf-8')
        with self.assertRaises(ValueError):self.action('files.text.create',{'path':'exists.txt','content':'new'})
        with self.assertRaisesRegex(ValueError,'files.write'):self.action('files.text.create',{'path':'bad.docx','content':'new'})
        action=self.action('files.text.create',{'path':'new.md','content':'# Created\n'})
        result=self.runtime.decide(action['id'],True)
        self.assertEqual(result['action']['status'],'completed')
    def test_text_patch_applies_reviewed_hunk(self):
        path=self.root/'notes.txt';path.write_text('a\nb\nc\n',encoding='utf-8')
        patch='--- a/notes.txt\n+++ b/notes.txt\n@@ -1,3 +1,3 @@\n a\n-b\n+B\n c\n'
        action=self.action('files.text.patch',{'path':'notes.txt','patch_text':patch})
        self.assertIn('+B',action['preview']['diff'])
        self.assertEqual(self.runtime.decide(action['id'],True)['action']['status'],'completed')
        self.assertEqual(path.read_text(encoding='utf-8'),'a\nB\nc\n')
    def test_text_edit_ui_mutation_of_arguments_is_blocked(self):
        path=self.root/'notes.txt';path.write_text('one\ntwo\n',encoding='utf-8')
        action=self.action('files.text.edit',{'path':'notes.txt','replacements':[{'old':'two','new':'TWO','count':1}]})
        with self.runtime.lock:stored=self.runtime.actions.get(action['id'])
        if stored:stored['arguments']['replacements'][0]['new']='EVIL'
        else:action['arguments']['replacements'][0]['new']='EVIL'
        result=self.runtime.decide(action['id'],True)
        self.assertEqual(result['action']['status'],'failed')
        self.assertEqual(path.read_text(encoding='utf-8'),'one\ntwo\n')
    def test_auto_continue_never_approves_a_text_edit(self):
        path=self.root/'notes.txt';path.write_text('one\n',encoding='utf-8')
        model=Mock();model._request_raw.return_value=json.dumps(
            {'tool':'files.text.edit','arguments':{'path':'notes.txt','replacements':[{'old':'one','new':'two','count':1}]},'reason':'Rename a line'})
        with patch.object(self.runtime,'_execute') as execute:
            result=self.runtime.plan(self.run['id'],model)
        execute.assert_not_called();self.assertEqual(result['status'],'awaiting_approval')
        self.assertEqual(path.read_text(encoding='utf-8'),'one\n')
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
    def test_repo_clone_refuses_a_hostile_url_and_an_escaping_folder(self):
        with self.assertRaisesRegex(ValueError,'https'):self.action('repo.clone',{'url':'ext::sh -c whoami'})
        with self.assertRaisesRegex(ValueError,'https'):self.action('repo.clone',{'url':'--upload-pack=evil'})
        with self.assertRaisesRegex(ValueError,'https'):self.action('repo.clone',{'url':'git@github.com:a/b.git'})
        with self.assertRaisesRegex(ValueError,'workspace'):self.action('repo.clone',{'url':'https://github.com/openai/codex','folder':'../escape'})
        self.assertEqual(self.runtime.state(self.run['id'])['steps'],[])
    def test_a_clone_folder_written_as_a_full_path_is_read_as_the_name_it_means(self):
        """A local planner names the clone folder as a path. The clone always lands inside the task
        workspace, so the component it meant is taken from that path whether or not it pointed there,
        the workspace itself leaves the repository to name the folder, and a path that ends in
        nothing is still refused."""
        inside=self.action('repo.clone',{'url':'https://github.com/openai/codex','folder':str(self.root/'codex')})
        self.assertEqual(inside['arguments']['folder'],'codex')
        with self.runtime.lock:self.assertEqual(self.runtime.actions[inside['id']]['bindings']['target'],str(self.root/'codex'))
        self.runtime.decide(inside['id'],False)
        elsewhere=self.action('repo.clone',{'url':'https://github.com/openai/codex','folder':'C:\\Users\\someone\\projects\\codex'})
        self.assertEqual(elsewhere['arguments']['folder'],'codex')
        with self.runtime.lock:self.assertEqual(self.runtime.actions[elsewhere['id']]['bindings']['target'],str(self.root/'codex'))
        self.runtime.decide(elsewhere['id'],False)
        itself=self.action('repo.clone',{'url':'https://github.com/bilawalsidhu/gods-eye-view','folder':str(self.root)})
        self.assertEqual(itself['arguments']['folder'],'gods-eye-view')
        with self.runtime.lock:self.assertEqual(self.runtime.actions[itself['id']]['bindings']['target'],str(self.root/'gods-eye-view'))
        self.runtime.decide(itself['id'],False)
        with self.assertRaisesRegex(ValueError,'plain name inside the task workspace'):
            self.runtime.propose(self.run['id'],'repo.clone',{'url':'https://github.com/openai/codex','folder':'C:\\'})
        with self.assertRaisesRegex(ValueError,"The folder it was given was"):
            self.runtime.propose(self.run['id'],'repo.clone',{'url':'https://github.com/openai/codex','folder':'nested/../'})
    def test_repo_clone_replaces_only_an_interrupted_clone_and_says_so(self):
        taken=self.root/'taken';taken.mkdir();(taken/'keep.txt').write_text('mine',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'holds files'):
            self.action('repo.clone',{'url':'https://github.com/bilawalsidhu/gods-eye-view','folder':'taken'})
        self.assertEqual((taken/'keep.txt').read_text(encoding='utf-8'),'mine')
        self.setUp();fresh=self.action('repo.clone',{'url':'https://github.com/bilawalsidhu/gods-eye-view','folder':'other'})
        self.assertEqual(fresh['preview']['removes_unfinished_clone'],'nothing is removed')
        self.setUp();dead=self.root/'god-view'
        (dead/'.git').mkdir(parents=True);(dead/'.git'/'config').write_text('partial',encoding='utf-8')
        action=self.action('repo.clone',{'url':'https://github.com/bilawalsidhu/gods-eye-view','folder':'god-view'})
        self.assertEqual(action['status'],'pending')
        self.assertIn('interrupted',action['preview']['removes_unfinished_clone'])
        self.assertIn('deleted first',action['preview']['removes_unfinished_clone'])
    def test_a_resumed_task_recognises_the_clone_it_already_made(self):
        """The second time this task resumed, the planner re-proposed its own clone and the step failed
        because the folder already held the repository. That read as missing work, so it went hunting
        for another folder name and would have downloaded the same hundred megabytes again."""
        landed=self.root/'gods-eye-view';landed.mkdir();(landed/'README.md').write_text('setup',encoding='utf-8');(landed/'.git').mkdir()
        url='https://github.com/bilawalsidhu/gods-eye-view'
        with patch('repo_tools.already_cloned',return_value=True),patch('repo_tools.survey',return_value=(2,['README.md'])),\
             patch('repo_tools.clone',side_effect=AssertionError('nothing may be downloaded a second time')):
            action=self.action('repo.clone',{'url':url,'folder':'gods-eye-view'})
            self.assertIn('already a copy of that repository',action['preview']['already_present'])
            self.assertEqual(action['preview']['removes_unfinished_clone'],'nothing is removed')
            result=self.runtime.decide(action['id'],True)
        step=result['action']
        self.assertEqual(step['status'],'completed')
        self.assertTrue(step['result']['already_cloned'])
        self.assertEqual(step['result']['top_level'],['README.md'])
        self.assertIn('already in that folder',step['result']['note'])
        # Proposing that same clone a second time is refused instead of completed again, because a
        # fresh step each time let the 4B planner repeat the clone until the loop guard blocked it.
        with patch('repo_tools.already_cloned',return_value=True):
            with self.assertRaisesRegex(ValueError,'already cloned'):
                self.runtime.propose(self.run['id'],'repo.clone',{'url':url+'.git','folder':'gods-eye-view'})
        self.assertEqual(len(self.runtime.state(self.run['id'])['steps']),1)
    def test_the_existing_clone_is_matched_only_by_its_own_repository_url(self):
        """Deciding that a folder already is this repository reads its git origin, and a loose match
        would let a setup task work on top of someone else's files and report them as the clone."""
        import repo_tools
        folder=self.root/'viewer';folder.mkdir()
        wanted='https://github.com/a/b'
        with patch('repo_tools.git_executable',return_value='git'):
            for stored,expected in [(wanted+'.git',True),(wanted,True),(wanted+' ',True),(wanted.replace('/a/b','/a/c'),False),
                                    ('git@github.com:a/b.git',False),('',False),('not a url at all',False)]:
                outcome=Mock(returncode=0 if stored else 1,stdout=stored+'\n',stderr='')
                with patch('repo_tools.subprocess.run',return_value=outcome):
                    self.assertEqual(repo_tools.already_cloned(folder,wanted),expected,stored)
            with patch('repo_tools.subprocess.run',side_effect=OSError('git vanished')):
                self.assertFalse(repo_tools.already_cloned(folder,wanted))
            self.assertFalse(repo_tools.already_cloned(self.root/'nowhere',wanted))
    def test_a_second_clone_proposal_is_answered_with_words_not_a_blocked_task(self):
        """The guard stops a task after three identical proposals, and the resumed setup task proposed
        its clone five times. The refusal happens before the guard so the planner gets the sentence it
        needs to move on, and a folder that no longer holds the repository is still free to clone."""
        url='https://github.com/openai/codex'
        def draft(tool,args):return json.dumps({'tool':tool,'arguments':args,'reason':'step','plan':'next'})
        action=self.action('repo.clone',{'url':url,'folder':'codex'})
        with patch('repo_tools.clone',return_value={'ok':True,'url':url,'folder':'codex','files':1,
                                                    'top_level':['README.md'],'message':'Cloned.'}):
            self.runtime.decide(action['id'],True)
        first=self.runtime.state(self.run['id'])
        self.assertEqual(first['steps'][-1]['status'],'completed')
        self.assertEqual(len(first['steps']),1)
        (self.root/'notes.txt').write_text('install with npm',encoding='utf-8')
        model=Mock()
        model._request_raw.side_effect=[draft('repo.clone',{'url':url,'folder':'codex'}),
                                        draft('files.read',{'path':'notes.txt'}),
                                        draft('files.write',{'path':'Setup.md','content':'# notes'})]
        with patch('repo_tools.already_cloned',return_value=True):
            moved=self.runtime.plan(self.run['id'],model)
        self.assertNotEqual(moved['status'],'blocked')
        self.assertEqual([step['tool'] for step in moved['steps']],['repo.clone','files.read','files.write'])
        self.assertEqual(moved['steps'][1]['status'],'completed')
        self.assertEqual(moved['steps'][-1]['status'],'pending')
    def test_a_second_read_of_the_same_page_is_answered_with_the_next_offset(self):
        """Re-reading one README from the start four times is what got the setup task blocked, so the
        repeat is refused before the guard with the offset the planner has not asked for yet."""
        (self.root/'README.md').write_text('x'*25000+'END',encoding='utf-8')
        first=self.runtime.decide(self.action('files.read',{'path':'README.md'})['id'],True)['action']['result']
        self.assertTrue(first['more_to_read'])
        def draft(tool,args):return json.dumps({'tool':tool,'arguments':args,'reason':'step','plan':'next'})
        model=Mock()
        model._request_raw.side_effect=[draft('files.read',{'path':'README.md'}),
                                        draft('files.read',{'path':'README.md','from_character':first['next_from_character']}),
                                        draft('files.write',{'path':'Setup.md','content':'# notes'})]
        state=self.runtime.plan(self.run['id'],model)
        self.assertNotEqual(state['status'],'blocked')
        self.assertEqual(state['status'],'awaiting_approval')
        self.assertEqual([step['tool'] for step in state['steps']],['files.read','files.read','files.write'])
        self.assertTrue(state['steps'][1]['result']['reading'].startswith('characters 20000 to '))
        self.assertEqual(state['steps'][-1]['status'],'pending')
    def test_repo_clone_is_auto_approved_then_only_writes_files(self):
        model=Mock();model._request_raw.return_value=json.dumps(
            {'tool':'repo.clone','arguments':{'url':'https://github.com/openai/codex'},
             'reason':'Fetch the project source','plan':'Read the README, then propose the install command'})
        landed=[]
        def capture(url,target,cancel_event=None):
            landed.append(Path(target))
            return {'ok':True,'url':url,'folder':str(target),'files':3,'top_level':['README.md'],'message':'Cloned.'}
        with patch('repo_tools.clone',side_effect=capture):
            result=self.runtime.plan(self.run['id'],model)
        step=result['steps'][-1]
        self.assertEqual(step['tool'],'repo.clone')
        self.assertEqual(step['status'],'completed')
        self.assertEqual(landed,[self.root.resolve()/'codex']*3)
        self.assertEqual(result['status'],'blocked')
        self.assertEqual(result['steps'][-1]['result']['top_level'],['README.md'])
    def test_a_dead_planner_call_is_recorded_as_failed_not_quietly_ready(self):
        model=Mock();model._request_raw.side_effect=ConnectionResetError(10054,'software caused connection abort')
        with self.assertRaises(ConnectionResetError):self.runtime.plan(self.run['id'],model)
        state=self.runtime.state(self.run['id'])
        self.assertEqual(state['status'],'failed')
        self.assertIn('planning request never came back',state['summary'])
        self.assertIn('ConnectionReset',state['planner_error'])
        self.assertEqual(state['steps'],[])
        model._request_raw.side_effect=None
        model._request_raw.return_value=json.dumps(
            {'tool':'files.write','arguments':{'path':'Draft.md','content':'# Notes'},'reason':'Draft the summary'})
        self.assertEqual(self.runtime.plan(self.run['id'],model)['status'],'awaiting_approval')
    def test_several_skills_are_attached_and_an_unselected_one_is_picked_from_the_goal(self):
        self.runtime.skills.save('clone-and-build','Clone the git repository, install its dependencies and run the build command.')
        self.runtime.skills.save('readme-summary','Read the README of a project and summarize its setup steps.')
        draft=json.dumps({'tool':'files.write','arguments':{'path':'Draft.md','content':'# Notes'},'reason':'Draft the summary'})
        def names(model):
            return [item['name'] for item in json.loads(model._request_raw.call_args.args[0][1]['content']).get('user_selected_procedures',[])]
        chosen=Mock();chosen._request_raw.return_value=draft
        self.runtime.plan(self.runtime.new_run('Read and summarize my document',str(self.root))['id'],chosen,
                          ['clone-and-build','readme-summary'])
        self.assertEqual(names(chosen),['clone-and-build','readme-summary'])
        unpicked=Mock();unpicked._request_raw.return_value=draft
        self.runtime.plan(self.runtime.new_run('Read and summarize my document',str(self.root))['id'],unpicked)
        self.assertEqual(names(unpicked),['readme-summary'])
        rejected=Mock();rejected._request_raw.return_value=draft
        with self.assertRaisesRegex(ValueError,'Missing required skill'):
            self.runtime.plan(self.runtime.new_run('Read and summarize my document',str(self.root))['id'],rejected,['no-such-skill'])
    def test_skill_selection_normalises_names_and_limits_the_count(self):
        self.assertEqual(_skill_names('cv-polish'),['cv-polish'])
        self.assertEqual(_skill_names(['clone-and-build',' clone-and-build ','readme-summary','']),['clone-and-build','readme-summary'])
        for empty in ('',[],None,{}):self.assertEqual(_skill_names(empty),[])
        with self.assertRaisesRegex(ValueError,'at most 8'):_skill_names(['skill-%d'%index for index in range(9)])
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
    def test_pause_stops_planning_and_resume_grants_more_steps(self):
        from agent_runtime import MAX_RUN_STEPS
        self.assertEqual(self.runtime.pause(self.run['id'])['status'],'paused')
        model=Mock()
        with self.assertRaisesRegex(ValueError,'Resume this task'):self.runtime.plan(self.run['id'],model)
        with patch.object(self.runtime,'plan',return_value={'status':'ready'}) as plan:
            self.runtime.resume(self.run['id'],model,'',10)
        plan.assert_called_once()
        self.assertEqual(self.runtime.runs[self.run['id']]['max_steps'],MAX_RUN_STEPS+10)
        self.assertEqual(self.runtime.state(self.run['id'])['status'],'ready')
    def test_pausing_or_resuming_around_an_approval_respects_the_pending_click(self):
        run=self.runtime.new_run('Approve first',str(self.root))
        pending=self.runtime.propose(run['id'],'files.list',{'path':'.'})['steps'][-1]
        self.runtime.runs[run['id']]['status']='awaiting_approval'
        with self.assertRaisesRegex(ValueError,'pending step'):self.runtime.pause(run['id'])
        with self.assertRaisesRegex(ValueError,'approval'):self.runtime.resume(run['id'],Mock())
        self.runtime.decide(pending['id'],False)
    def test_step_budget_stops_new_steps_until_resumed_with_more(self):
        with self.runtime.lock:self.runtime.runs[self.run['id']]['max_steps']=2
        for _ in range(2):
            step=self.action('files.list',{'path':'.'})
            self.runtime.decide(step['id'],False)
        with self.assertRaisesRegex(ValueError,'step budget'):self.action('files.list',{'path':'.'})
        with patch.object(self.runtime,'plan',return_value={'status':'ready'}):
            self.runtime.resume(self.run['id'],Mock(),'',3)
        self.action('files.list',{'path':'.'})
    def test_paused_task_survives_a_restart(self):
        store=self.root/'pause-history.json'
        runtime=AgentRuntime(Connections(self.root/'pause-connections.json'),store_path=store)
        run=runtime.new_run('Long task',str(self.root))
        runtime.pause(run['id'])
        restored=AgentRuntime(Connections(self.root/'pause-connections.json'),store_path=store)
        self.assertEqual(restored.state(run['id'])['status'],'paused')
        with patch.object(restored,'plan',return_value={'status':'ready'}):
            restored.resume(run['id'],Mock(),'',0)
        self.assertEqual(restored.state(run['id'])['status'],'ready')
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
        # The ComfyUI tools are in the catalog on a PC that has an install, so this check has to
        # take that away to test the promise it actually makes: with nothing that can draw, admit it.
        model=Mock()
        run=self.runtime.new_run('Generate an image of a boy reading',str(self.root))
        with patch('comfy_tools.available',return_value=False):
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
    def test_done_claim_needs_an_independent_reviewer_verdict(self):
        model=Mock();model._request_raw.side_effect=[
            json.dumps({'done':True,'summary':'The draft is saved.'}),
            json.dumps({'verified':True,'reason':'The approved write result shows the file was created.'})]
        result=self.runtime.plan(self.run['id'],model)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['verification'],'verified')
    def test_reviewer_rejection_keeps_the_task_open_and_blocks_after_three_claims(self):
        model=Mock()
        for cycle in range(3):
            model._request_raw.side_effect=[
                json.dumps({'done':True,'summary':'All set.'}),
                json.dumps({'verified':False,'reason':'The requested file was never read in the steps.'})]
            result=self.runtime.plan(self.run['id'],model)
            if cycle<2:
                self.assertEqual(result['status'],'ready')
                self.assertIn('never read',result['verification_feedback'])
            else:
                self.assertEqual(result['status'],'blocked')
                self.assertIn('three finish claims',result['summary'])
        second=model._request_raw.call_args_list[2].args[0][1]['content']
        self.assertIn('reviewer_feedback',json.loads(second))
    def test_unusable_reviewer_reply_completes_with_an_honest_note(self):
        model=Mock();model._request_raw.side_effect=[
            json.dumps({'done':True,'summary':'Done.'}),'not json at all']
        result=self.runtime.plan(self.run['id'],model)
        self.assertEqual(result['status'],'completed')
        self.assertIn('not independently checked',result['verification'])
    def test_reviewer_is_not_called_for_future_work_claims(self):
        model=Mock();model._request_raw.return_value=json.dumps({'done':True,'summary':'Next step will generate it.'})
        self.runtime.plan(self.run['id'],model)
        self.assertEqual(model._request_raw.call_count,1)
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
    def test_command_output_pipe_closes_on_success_and_timeout(self):
        import subprocess
        original=subprocess.Popen
        processes=[]
        def launch(*args,**kwargs):
            process=original(*args,**kwargs);processes.append(process);return process
        with patch('agent_runtime.subprocess.Popen',side_effect=launch):
            result=run_process([sys.executable,'-c','print("pipe test")'],self.root)
            self.assertIn('pipe test',result['output'])
            run_process([sys.executable,'-c','import time;time.sleep(10)'],self.root,timeout=.15)
        self.assertTrue(all(process.stdout is None or process.stdout.closed for process in processes))
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

    def test_agent_chat_turns_are_stored_with_their_task(self):
        first=self.runtime.record_message(self.run['id'],'user','Did you read the file?')
        self.assertEqual([turn['role'] for turn in first['messages']],['user'])
        second=self.runtime.record_message(self.run['id'],'sakura','Yes, I read notes.txt.')
        self.assertEqual([turn['text'] for turn in second['messages']],
                         ['Did you read the file?','Yes, I read notes.txt.'])
        self.assertEqual(self.runtime.state(self.run['id'])['messages'],second['messages'])
        self.assertIsNone(self.runtime.record_message(self.run['id'],'sakura','   '))
        self.assertIsNone(self.runtime.record_message('missing-task','user','hello'))
        for index in range(45):self.runtime.record_message(self.run['id'],'user','Filler '+str(index))
        stored=self.runtime.state(self.run['id'])['messages']
        self.assertEqual(len(stored),40)
        self.assertEqual(stored[-1]['text'],'Filler 44')

    def test_rename_and_pin_belong_to_the_task_and_survive_a_reload(self):
        renamed=self.runtime.rename(self.run['id'],'  Notes digest  ')
        self.assertEqual(renamed['title'],'Notes digest')
        self.assertEqual(renamed['goal'],'Read and summarize my document')
        self.assertIsNone(self.runtime.rename(self.run['id'],'   '))
        self.assertIsNone(self.runtime.rename('missing-task','Anything'))
        self.assertTrue(self.runtime.set_pinned(self.run['id'],True)['pinned'])
        reloaded=AgentRuntime(Connections(self.root/'connections.json'))
        shown=next(run for run in reloaded.states() if run['id']==self.run['id'])
        self.assertEqual(shown['title'],'Notes digest')
        self.assertTrue(shown['pinned'])
        self.assertFalse(self.runtime.set_pinned(self.run['id'],False)['pinned'])

    def test_delete_removes_one_task_from_the_list_and_the_archive(self):
        keeper=self.runtime.new_run('Keep this one',str(self.root))['id']
        self.assertTrue(self.runtime.delete_run(self.run['id']))
        self.assertFalse(self.runtime.delete_run(self.run['id']))
        self.assertEqual([run['id'] for run in self.runtime.states()],[keeper])
        # The store merges whatever is already on disk, so a later save must not resurrect the record.
        self.runtime.new_run('A task saved after the delete',str(self.root))
        self.assertNotIn(self.run['id'],[run['id'] for run in self.runtime.states()])
        with self.assertRaises(ValueError):self.runtime.history.read(self.run['id'])
        self.assertEqual(self.runtime.history.read(keeper)['id'],keeper)

    def test_a_task_that_is_still_working_refuses_to_be_deleted(self):
        busy=self.runtime.new_run('Wait on an approval',str(self.root))['id']
        self.runtime.propose(busy,'files.write',{'path':'draft.md','content':'# Notes'})
        with self.assertRaises(ValueError):self.runtime.delete_run(busy)
        self.assertIn(busy,[run['id'] for run in self.runtime.states()])
        self.runtime.active_runs.add(busy)
        self.runtime.runs[busy]['status']='ready'
        with self.assertRaises(ValueError):self.runtime.delete_run(busy)

    def test_task_brief_states_only_what_the_record_contains(self):
        self.assertEqual(self.runtime.conversation_context('missing-task'),'')
        path=self.root/'notes.txt';path.write_text('PRIVATE-ONE\n',encoding='utf-8')
        read=self.action('files.read',{'path':'notes.txt'})
        self.runtime.decide(read['id'],False)
        self.action('files.write',{'path':'Draft.md','content':'# Notes'})
        brief=self.runtime.conversation_context(self.run['id'])
        self.assertIn(self.run['goal'],brief)
        self.assertIn('files.read: rejected',brief)
        self.assertIn('Waiting for the user to approve: files.write',brief)
        self.assertNotIn('PRIVATE-ONE',brief)
        self.assertLessEqual(len(brief),1400)
        self.runtime.decide(self.runtime.state(self.run['id'])['steps'][-1]['id'],False)
        self.assertNotIn('Waiting for the user to approve',self.runtime.conversation_context(self.run['id']))

    def test_a_compacted_catalog_still_names_the_arguments_a_step_may_use(self):
        """The schema is the bulk a small context cannot carry; the key names are what a model cannot
        invent. One local planner sent repo.clone {"url":…,"destination":…} because 'folder' was never
        shown to it, and another copied a "url*" marker I had invented, so the names must appear as
        plain strings the draft can use verbatim."""
        compacted=self.runtime._compact_plan_context({'goal':'Set up this repository','tools':self.runtime.catalog()})
        shown=next(item for item in compacted['tools'] if item['name']=='repo.clone')
        self.assertEqual(shown['takes'],['url','folder'])
        self.assertEqual(shown['required'],['url'])
        self.assertTrue(all(len(item['description'])<=70 for item in compacted['tools']))
        self.assertNotIn('inputSchema',json.dumps(compacted))
        self.assertFalse([name for item in compacted['tools'] for name in item.get('takes',[])
                          if any(mark in name for mark in '*|:,')])
        # The draft the planner owes has a key named arguments, so the catalog must not use that word.
        self.assertNotIn('arguments',json.dumps(compacted))
        full=len(json.dumps({'tools':self.runtime.catalog()},ensure_ascii=False).encode('utf-8'))
        self.assertLess(len(json.dumps(compacted,ensure_ascii=False).encode('utf-8')),full)

    def test_a_planner_that_misfiles_its_arguments_is_shown_the_error_and_asks_again(self):
        """A small model used to end the turn with a schema rejection the user had to click through.
        One retry that quotes the rejection back is enough for it to answer with a real step."""
        model=Mock();model.provider='gemini';model.context_length=200_000
        model._request_raw.side_effect=[
            json.dumps({'tool':'files.write','arguments':{'path':'Draft.md','text':'# Notes'},'reason':'A first draft'}),
            json.dumps({'tool':'files.write','arguments':{'path':'Draft.md','content':'# Notes'},'reason':'A first draft'})]
        state=self.runtime.plan(self.run['id'],model)
        self.assertEqual(Path(state['steps'][-1]['arguments']['path']).name,'Draft.md')
        self.assertEqual(state['steps'][-1]['arguments']['content'],'# Notes')
        self.assertEqual(state['steps'][-1]['status'],'pending')
        second=json.loads(model._request_raw.call_args_list[1].args[0][1]['content'])
        self.assertIn('The step for files.write was not accepted',json.dumps(second.get('reviewer_feedback','')))
        self.assertNotIn('reviewer_feedback',json.loads(model._request_raw.call_args_list[0].args[0][1]['content']))

    def test_a_planner_stuck_on_the_same_unusable_step_reports_instead_of_erroring(self):
        """A resumed setup task answered the refusal with the same refused step three times over. That
        is a stalled plan, not a failed request, so the task keeps the words instead of a popup."""
        model=Mock();model.provider='gemini';model.context_length=200_000
        model._request_raw.return_value=json.dumps(
            {'tool':'files.write','arguments':{'path':'Draft.md','text':'# Notes'},'reason':'A first draft'})
        state=self.runtime.plan(self.run['id'],model)
        self.assertEqual(state['status'],'ready')
        self.assertEqual(state['steps'],[])
        self.assertIn('I stopped rather than run that again',state['summary'])
        self.assertIn('was not accepted',state['summary'])
        self.assertIn('Tell me in the chat',state['summary'])

    def test_a_step_with_an_unknown_argument_is_told_what_it_may_use(self):
        with self.assertRaisesRegex(ValueError,r"The step for repo\.clone was not accepted: Additional properties are not allowed \('destination' was unexpected\) Its allowed arguments are folder, url \(required: url\)"):
            self.runtime.propose(self.run['id'],'repo.clone',{'url':'https://github.com/openai/codex','destination':'viewer'})
        self.assertEqual(self.runtime.state(self.run['id'])['steps'],[])

    def test_a_small_local_planner_loses_catalog_detail_not_the_setup_rules(self):
        model=Mock();model.provider='ollama';model.context_length=8192
        model._request_raw.return_value=json.dumps(
            {'tool':'files.list','arguments':{'path':'.'},'reason':'See what is in the folder'})
        self.runtime.plan(self.run['id'],model)
        instruction=model._request_raw.call_args.args[0][0]['content']
        sent=json.loads(model._request_raw.call_args.args[0][1]['content'])
        for clause in ('repo.clone','timeout_seconds','app.diagnostics'):
            self.assertIn(clause,instruction)
        self.assertTrue(all('inputSchema' not in tool for tool in sent['tools']))
        self.assertIn('files.read',{tool['name'] for tool in sent['tools']})

    def test_plan_payload_is_left_whole_for_cloud_and_unknown_budgets(self):
        context={'tools':[{'name':'files.read','description':'read','inputSchema':{'type':'object'}}]}
        cloud=Mock();cloud.provider='gemini';cloud.context_length=8192
        self.assertIs(self.runtime._fit_plan_context(cloud,'rule text',context,self.run['id']),context)
        roomy=Mock();roomy.provider='ollama';roomy.context_length=200_000
        self.assertIs(self.runtime._fit_plan_context(roomy,'rule text',context,self.run['id']),context)
        native=Mock();native.provider='';native.context_length=8192
        compacted=self.runtime._fit_plan_context(native,'rule text '*2000,context,self.run['id'])
        self.assertIsNot(compacted,context)
        self.assertNotIn('inputSchema',json.dumps(compacted))
        self.assertEqual(compacted['tools'][0]['name'],'files.read')

    def test_a_task_needs_a_folder_and_never_defaults_to_the_app_install(self):
        """Path('') resolves to the process CWD, which for the shipped launcher is Sakura's own
        folder, so an absent workspace would have let a task read and edit the application itself."""
        for blank in ('', '   ', None, 0, ['x']):
            with self.assertRaisesRegex(ValueError,'workspace folder'):self.runtime.new_run('A task with no folder',blank)
        self.assertEqual(len(self.runtime.runs),1)
        (self.root/'not-a-folder.txt').write_text('x',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'existing workspace folder'):self.runtime.new_run('Not a folder',str(self.root/'not-a-folder.txt'))
        self.assertEqual(len(self.runtime.runs),1)


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
