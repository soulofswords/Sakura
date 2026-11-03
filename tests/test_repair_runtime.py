"""How the Agent is allowed to look at and repair the app it runs inside."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_connections import Connections
from agent_runtime import AgentRuntime
import repair_actions
import repair_diagnostics as diagnostics


class AppRepairRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        base = Path(self.folder.name)
        self.workspace = base / 'workspace'
        self.workspace.mkdir()
        self.app = base / 'app'
        (self.app / 'desktop-profile').mkdir(parents=True)
        (self.app / 'static' / 'js').mkdir(parents=True)
        (self.app / 'logs').mkdir()
        (self.app / 'settings.json').write_text('{"volume": 40, "voice": "af_', encoding='utf-8')
        (self.app / 'desktop-profile' / 'agent-skills.json').write_text('[{"name":"one"}]', encoding='utf-8')
        (self.app / 'model_viewer.py').write_text('OFFSET = 1\n', encoding='utf-8')
        (self.app / 'static' / 'js' / 'viewer.js').write_text('const a = 1;\n', encoding='utf-8')
        self.previous = [(diagnostics, diagnostics.BASE_DIR), (repair_actions, repair_actions.BASE_DIR)]
        diagnostics.BASE_DIR = self.app
        repair_actions.BASE_DIR = self.app
        repair_actions.BACKUP_ROOT = self.app / 'logs' / 'repair-backups'
        self.addCleanup(self._restore)
        self.runtime = AgentRuntime(Connections(base / 'connections.json'))
        self.run = self.runtime.new_run('My companion is broken, fix the app', str(self.workspace))

    def _restore(self):
        for module, value in self.previous:
            module.BASE_DIR = value

    def action(self, tool, args):
        return self.runtime.propose(self.run['id'], tool, args)['steps'][-1]

    def finish(self, action):
        return self.runtime.decide(action['id'], True)['action']

    def test_diagnostics_run_without_a_click_and_answer_for_the_app_only(self):
        with patch.object(diagnostics, '_probe', return_value={'state': 'closed'}):
            action = self.action('app.diagnostics', {'section': 'state'})
            self.assertEqual(action['status'], 'pending')
            result = self.runtime._decide(action['id'], True, auto=True)['action']['result']
        self.assertTrue(result['ok'])
        self.assertEqual(result['identity']['root'], str(self.app))
        self.assertEqual([item['path'] for item in result['state']['files'] if not item.get('readable', True)],
                         ['settings.json'])
        self.assertIn('saved-state file cannot be read', ' '.join(result['problems']))
        self.assertFalse(list((self.app / 'logs' / 'repair-backups').glob('*')))

    def test_a_source_repair_shows_its_diff_and_waits_for_the_click(self):
        action = self.action('app.source.patch',
                            {'path': 'model_viewer.py',
                             'replacements': [{'old': 'OFFSET = 1', 'new': 'OFFSET = 2', 'count': 1}]})
        self.assertEqual(action['status'], 'pending')
        self.assertIn('+OFFSET = 2', action['preview']['diff'])
        self.assertIn('restart', action['preview']['warning'].lower())
        self.assertEqual((self.app / 'model_viewer.py').read_text(encoding='utf-8'), 'OFFSET = 1\n')
        finished = self.finish(action)
        self.assertEqual(finished['status'], 'completed')
        self.assertEqual((self.app / 'model_viewer.py').read_text(encoding='utf-8'), 'OFFSET = 2\n')
        saved = Path(finished['result']['backup'])
        self.assertEqual(saved.read_text(encoding='utf-8'), 'OFFSET = 1\n')
        self.assertTrue(finished['result']['restart_required'])

    def test_a_late_change_to_the_app_file_blocks_the_repair(self):
        action = self.action('app.source.patch',
                            {'path': 'static/js/viewer.js',
                             'replacements': [{'old': 'const a = 1;', 'new': 'const a = 2;', 'count': 1}]})
        # The reviewed text is still present, so only the hash guard can stop this.
        (self.app / 'static' / 'js' / 'viewer.js').write_text('const a = 1;\nvar b = 7;\n', encoding='utf-8')
        finished = self.finish(action)
        self.assertEqual(finished['status'], 'failed')
        self.assertIn('changed after review', finished['result']['error'])
        self.assertEqual((self.app / 'static' / 'js' / 'viewer.js').read_text(encoding='utf-8'),
                         'const a = 1;\nvar b = 7;\n')

    def test_the_guard_rails_and_shared_folders_are_not_patchable(self):
        for relative, reason in [('repair_actions.py', 'source .py'), ('agent_permissions.py', 'source .py'),
                                 (str(Path('desktop-profile') / 'x.py'), 'static')]:
            with self.assertRaises(ValueError) as caught:
                self.runtime.propose(self.run['id'], 'app.source.patch',
                                     {'path': relative,
                                      'replacements': [{'old': 'a', 'new': 'b', 'count': 1}]})
            self.assertIn('app source', str(caught.exception).lower())

    def test_a_state_repair_is_reviewed_with_its_effect_then_backs_up(self):
        action = self.action('app.state.repair', {'path': 'settings.json', 'mode': 'rebuild'})
        self.assertEqual(action['status'], 'pending')
        self.assertIn('repair-backups', json.dumps(action['preview']))
        self.assertIn('Nothing is restarted', action['preview']['warning'])
        finished = self.finish(action)
        self.assertEqual(finished['status'], 'completed')
        self.assertEqual(json.loads((self.app / 'settings.json').read_text(encoding='utf-8')), {})
        self.assertEqual(Path(finished['result']['backup']).read_text(encoding='utf-8'), '{"volume": 40, "voice": "af_')
        self.assertIn('unreadable original', finished['result']['message'])

    def test_a_state_file_the_app_does_not_own_cannot_be_selected(self):
        (self.app / 'desktop-profile' / 'LocalFile.json').write_text('{', encoding='utf-8')
        with self.assertRaises(ValueError) as caught:
            self.action('app.state.repair', {'path': 'desktop-profile/LocalFile.json', 'mode': 'rebuild'})
        self.assertIn('browser or runtime storage', str(caught.exception))

    def test_sync_and_refresh_only_describe_themselves_until_approved(self):
        source = Path(self.folder.name) / 'source'
        (source / 'static' / 'js').mkdir(parents=True)
        (source / 'model_viewer.py').write_text('OFFSET = 9\n', encoding='utf-8')
        (source / 'static' / 'js' / 'viewer.js').write_text('const a = 1;\n', encoding='utf-8')
        with patch.object(diagnostics, 'source_root', return_value=source):
            stale = self.action('app.files.sync', {'paths': ['model_viewer.py', 'static/js/viewer.js']})
            self.assertEqual(stale['status'], 'pending')
            states = {item['path']: item['state'] for item in stale['preview']['files']}
            self.assertEqual(states, {'model_viewer.py': 'stale', 'static/js/viewer.js': 'already current'})
            finished = self.finish(stale)
        self.assertEqual(finished['status'], 'completed')
        self.assertEqual((self.app / 'model_viewer.py').read_text(encoding='utf-8'), 'OFFSET = 9\n')
        self.assertFalse((source / 'model_viewer.py').read_text(encoding='utf-8') == 'OFFSET = 1\n')

    def test_refresh_previews_the_command_without_running_it(self):
        source = Path(self.folder.name) / 'source'
        (source / 'tools').mkdir(parents=True)
        (source / 'tools' / 'create-local-products.py').write_text('print(1)\n', encoding='utf-8')
        with patch.object(diagnostics, 'source_root', return_value=source):
            action = self.action('app.redeploy', {'edition': 'companion'})
        self.assertEqual(action['status'], 'pending')
        self.assertIn('create-local-products.py', action['preview']['command'])
        self.assertIn('minutes', action['preview']['warning'])
        self.assertFalse((self.app / 'logs' / 'ran').exists())

    def test_repair_events_are_written_to_the_trace(self):
        action = self.action('app.state.repair', {'path': 'settings.json', 'mode': 'rebuild'})
        self.finish(action)
        trace = self.runtime.trace.path
        self.assertIsNotNone(trace)
        lines = [json.loads(line) for line in Path(trace).read_text(encoding='utf-8').splitlines()]
        self.assertIn('repair', {line['kind'] for line in lines})


if __name__ == '__main__':
    unittest.main()
