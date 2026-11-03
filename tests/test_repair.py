"""Tests for Sakura's own repair modules: diagnostics stays read-only, repairs back up, and both refuse anything outside the app folder."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import repair_actions
import repair_diagnostics as diagnostics


class Sandbox(unittest.TestCase):
    """A fake installed app, plus an optional fake source tree it was refreshed from."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='sakura-repair-'))
        self.app = self.root / 'app'
        (self.app / 'desktop-profile').mkdir(parents=True)
        (self.app / 'static' / 'js').mkdir(parents=True)
        (self.app / 'models').mkdir()
        (self.app / 'logs').mkdir()
        (self.app / 'settings.json').write_text('{"selected_model":"hana"}', encoding='utf-8')
        (self.app / 'desktop-profile' / 'agent-skills.json').write_text('[{"name":"one"}]', encoding='utf-8')
        (self.app / 'desktop-profile' / 'agent-learning.json').write_text('{"version":1,"procedures":[]}', encoding='utf-8')
        (self.app / 'model_viewer.py').write_text('VALUE = 1\n', encoding='utf-8')
        (self.app / 'static' / 'js' / 'viewer.js').write_text('const a = 1;\n', encoding='utf-8')
        (self.app / 'models' / 'note.py').write_text('print(1)\n', encoding='utf-8')
        self.source = self.root / 'source'
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        targets = [module for module in (diagnostics, repair_actions) if hasattr(module, 'BASE_DIR')]
        self.previous = [(module, module.BASE_DIR) for module in targets]
        for module in targets:
            module.BASE_DIR = self.app
        repair_actions.BACKUP_ROOT = self.app / 'logs' / 'repair-backups'
        self.addCleanup(self._restore_paths)

    def _restore_paths(self):
        for module, value in self.previous:
            module.BASE_DIR = value
        repair_actions.BACKUP_ROOT = Path('unused')


class DiagnosticsTests(Sandbox):
    def test_snapshot_reports_the_app_without_writing_anything(self):
        before = {path.name: path.stat().st_mtime_ns for path in self.app.rglob('*') if path.is_file()}
        closed = {'state': 'closed'}
        with patch.object(diagnostics, '_probe', return_value=closed):
            result = diagnostics.snapshot(include_http=False)
        self.assertEqual(result['identity']['edition'], diagnostics.EDITION)
        for section in ('liveness', 'drift', 'state', 'engines', 'logs'):
            self.assertIn(section, result)
        self.assertEqual({path.name: path.stat().st_mtime_ns for path in self.app.rglob('*') if path.is_file()}, before)

    def test_drift_names_the_files_the_running_copy_is_missing(self):
        self.source.mkdir()
        (self.source / 'static' / 'js').mkdir(parents=True)
        (self.source / 'viewer_helper.py').write_text('print("new")\n', encoding='utf-8')
        (self.source / 'static' / 'js' / 'viewer.js').write_text('const a = 2;\n', encoding='utf-8')
        with patch.object(diagnostics, 'source_root', return_value=self.source):
            result = diagnostics.drift()
        self.assertTrue(result['comparable'])
        self.assertIn('viewer_helper.py', result['missing_in_app'])
        self.assertEqual(result['stale_in_app'][0]['path'], str(Path('static') / 'js' / 'viewer.js'))
        self.assertTrue(result['out_of_date'])

    def test_running_from_the_source_tree_reports_nothing_to_compare(self):
        with patch.object(diagnostics, 'source_root', return_value=self.app.resolve()):
            result = diagnostics.drift()
        self.assertFalse(result['comparable'])
        self.assertTrue(result['running_from_source'])

    def test_broken_state_is_counted_and_flagged_repairable(self):
        (self.app / 'settings.json').write_text('{"selected_model":"hana","voice"', encoding='utf-8')
        result = diagnostics.state()
        broken = [item for item in result['files'] if not item.get('readable', True)]
        self.assertEqual([item['path'] for item in broken], ['settings.json'])
        self.assertTrue(broken[0]['repairable'])
        self.assertTrue(broken[0]['salvageable'])
        self.assertEqual(result['broken_count'], 1)

    def test_healthy_sqlite_is_not_reported_as_damage(self):
        import sqlite3
        path = self.app / 'desktop-profile' / 'agent-knowledge.sqlite3'
        with sqlite3.connect(path) as connection:
            connection.execute('CREATE TABLE notes (body text)')
        record = [item for item in diagnostics.state()['files'] if item['path'].endswith('knowledge.sqlite3')][0]
        self.assertTrue(record['ok'])
        self.assertEqual(diagnostics.state()['broken_count'], 0)

    def test_liveness_only_reports_ports_that_answer_and_labels_foreign_apps(self):
        answered = {'state': 'open', 'body': json.dumps({'application': 'sakura-anime-assistant',
                                                         'edition': diagnostics.EDITION,
                                                         'installation': 'other-installation'})}
        with patch.object(diagnostics, '_probe', return_value=answered), patch.object(diagnostics, 'PORT_RANGE', range(8766, 8767)):
            result = diagnostics.liveness()
            snapshot = diagnostics.snapshot(['liveness'])
        self.assertEqual(result['healthy_backend_count'], 0)
        self.assertEqual(result['other_installation_ports'], [8766])
        self.assertIn('different installation folder', snapshot['problems'][0])

    def test_log_tail_is_bounded_and_marks_problem_lines(self):
        (self.app / 'logs' / 'app.log').write_text('ok\nTraceback (most recent call last):\n', encoding='utf-8')
        result = diagnostics.logs(lines=5)
        self.assertEqual(result['files'][0]['recent_problem_lines'], ['Traceback (most recent call last):'])


class SalvageTests(unittest.TestCase):
    def test_a_truncated_object_keeps_its_complete_members(self):
        text = '{"enabled": true, "procedures": [{"id": "a"}, {"id": "b"}, {"id": "c'
        value = diagnostics.salvage_json(text)
        self.assertEqual(value, {'enabled': True, 'procedures': [{'id': 'a'}, {'id': 'b'}]})

    def test_a_truncated_array_keeps_whole_elements_only(self):
        value = diagnostics.salvage_json('[{"id":1},{"id":2},{"id"')
        self.assertEqual(value, [{'id': 1}, {'id': 2}])

    def test_braces_inside_strings_do_not_cut_the_document(self):
        value = diagnostics.salvage_json('{"note": "he said {not json}, then left", "x": 1}, {"junk"')
        self.assertEqual(value, {'note': 'he said {not json}, then left', 'x': 1})

    def test_valid_and_hopeless_input(self):
        self.assertEqual(diagnostics.salvage_json('{"a": 1}'), {'a': 1})
        self.assertIsNone(diagnostics.salvage_json('BinaryFileHeader\x00\x01'))
        self.assertIsNone(diagnostics.salvage_json(''))


class PatchTests(Sandbox):
    def test_only_app_code_is_patchable(self):
        for relative in ('model_viewer.py', str(Path('static') / 'js' / 'viewer.js'), 'requirements.txt'):
            self.assertTrue(repair_actions.patchable(relative), relative)
        for relative in (str(Path('models') / 'note.py'), 'repair_actions.py', 'repair_diagnostics.py',
                         'agent_permissions.py', 'settings.json', str(Path('static') / 'art.pmx')):
            self.assertFalse(repair_actions.patchable(relative), relative)

    def test_paths_that_leave_the_app_folder_are_refused(self):
        for relative in ('C:/Windows/win.py', '../outside.py', str(Path('..') / 'app' / 'model_viewer.py')):
            with self.assertRaises(ValueError):
                repair_actions._resolve(relative)

    def test_a_reviewed_patch_writes_and_saves_the_previous_file(self):
        plan = repair_actions.plan_patch('model_viewer.py',
                                        [{'old': 'VALUE = 1', 'new': 'VALUE = 2', 'count': 1}])
        self.assertIn('+VALUE = 2', plan['preview']['diff'])
        result = repair_actions.apply(plan)
        self.assertTrue(result['ok'], result)
        self.assertEqual((self.app / 'model_viewer.py').read_text(encoding='utf-8'), 'VALUE = 2\n')
        self.assertTrue(result['restart_required'])
        saved = Path(result['backup'])
        self.assertEqual(saved.read_text(encoding='utf-8'), 'VALUE = 1\n')
        self.assertIn('repair-backups', str(saved).replace('\\', '/'))

    def test_a_late_edit_blocks_the_write(self):
        plan = repair_actions.plan_patch('model_viewer.py',
                                        [{'old': 'VALUE = 1', 'new': 'VALUE = 2', 'count': 1}])
        (self.app / 'model_viewer.py').write_text('VALUE = 9\n', encoding='utf-8')
        result = repair_actions.apply(plan)
        self.assertFalse(result['ok'])
        self.assertIn('changed after review', result['error'])
        self.assertEqual((self.app / 'model_viewer.py').read_text(encoding='utf-8'), 'VALUE = 9\n')

    def test_a_patch_cannot_reach_a_model_folder(self):
        with self.assertRaises(ValueError):
            repair_actions.plan_patch(str(Path('models') / 'note.py'),
                                     [{'old': 'print(1)', 'new': 'print(2)', 'count': 1}])


class StateRepairTests(Sandbox):
    def corrupt(self):
        (self.app / 'settings.json').write_text('{"volume": 40, "voice": "af_', encoding='utf-8')

    def test_rebuild_backs_up_the_unreadable_file_then_writes_the_known_shape(self):
        self.corrupt()
        plan = repair_actions.plan_state('settings.json', 'rebuild')
        self.assertEqual(plan['preview']['writes_bytes'], 2)
        result = repair_actions.apply(plan)
        self.assertTrue(result['ok'], result)
        self.assertEqual(json.loads((self.app / 'settings.json').read_text(encoding='utf-8')), {})
        self.assertEqual(Path(result['backup']).read_text(encoding='utf-8'), '{"volume": 40, "voice": "af_')

    def test_salvage_keeps_the_readable_part(self):
        (self.app / 'desktop-profile' / 'agent-skills.json').write_text('[{"name":"one"},{"name":"tw', encoding='utf-8')
        plan = repair_actions.plan_state(str(Path('desktop-profile') / 'agent-skills.json'), 'salvage')
        result = repair_actions.apply(plan)
        self.assertTrue(result['ok'], result)
        self.assertEqual(json.loads((self.app / 'desktop-profile' / 'agent-skills.json').read_text(encoding='utf-8')),
                         [{'name': 'one'}])

    def test_a_file_that_changed_after_review_is_left_alone(self):
        self.corrupt()
        plan = repair_actions.plan_state('settings.json', 'rebuild')
        (self.app / 'settings.json').write_text('{"volume": 41}', encoding='utf-8')
        result = repair_actions.apply(plan)
        self.assertFalse(result['ok'])
        self.assertEqual((self.app / 'settings.json').read_text(encoding='utf-8'), '{"volume": 41}')

    def test_browser_and_runtime_storage_are_never_repair_targets(self):
        (self.app / 'desktop-profile' / 'webdata.json').write_text('{', encoding='utf-8')
        with self.assertRaises(ValueError) as caught:
            repair_actions.plan_state(str(Path('desktop-profile') / 'webdata.json'), 'rebuild')
        self.assertIn('not app state', str(caught.exception))

    def test_a_state_file_the_diagnostics_do_not_list_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            repair_actions.plan_state('desktop-profile/agent-gone.json', 'rebuild')
        self.assertIn('app.diagnostics lists', str(caught.exception))

    def test_recreate_is_limited_to_the_databases_the_app_rebuilds(self):
        with self.assertRaises(ValueError):
            repair_actions.plan_state('settings.json', 'recreate')

    def test_restore_puts_a_saved_copy_back_over_corrupt_state(self):
        good = self.app / 'settings.json'
        good.write_text('{"volume": 40, "mode": "calm"}', encoding='utf-8')
        saved = repair_actions._copy_backup(good)
        good.write_text('{"volume": 40, "voice": "af_', encoding='utf-8')
        plan = repair_actions.plan_state('settings.json', 'restore',
                                         backup=str(saved.relative_to(repair_actions.BACKUP_ROOT)))
        result = repair_actions.apply(plan)
        self.assertTrue(result['ok'], result)
        self.assertEqual(json.loads(good.read_text(encoding='utf-8')), {'volume': 40, 'mode': 'calm'})
        with self.assertRaises(ValueError):
            repair_actions._backup_path('../../outside.json')

    def test_a_backup_that_is_itself_unreadable_is_refused(self):
        good = self.app / 'settings.json'
        good.write_text('{"volume"', encoding='utf-8')
        saved = repair_actions._copy_backup(good)
        with self.assertRaises(ValueError) as caught:
            repair_actions.plan_state('settings.json', 'restore',
                                      backup=str(saved.relative_to(repair_actions.BACKUP_ROOT)))
        self.assertIn('unreadable', str(caught.exception))

    def test_an_unknown_empty_shape_needs_an_explicit_kind(self):
        (self.app / 'desktop-profile' / 'agent-local-ai').mkdir()
        (self.app / 'desktop-profile' / 'agent-local-ai' / 'models.json').write_text('{"a": [1,', encoding='utf-8')
        with self.assertRaises(ValueError):
            repair_actions.plan_state(str(Path('desktop-profile') / 'agent-local-ai' / 'models.json'), 'rebuild')
        plan = repair_actions.plan_state(str(Path('desktop-profile') / 'agent-local-ai' / 'models.json'),
                                       'rebuild', empty_kind='object')
        self.assertEqual(json.loads(plan['write']), {})


class SyncAndRefreshTests(Sandbox):
    def build_source(self):
        self.source.mkdir(parents=True)
        (self.source / 'static' / 'js').mkdir(parents=True)
        (self.source / 'model_viewer.py').write_text('VALUE = 3\n', encoding='utf-8')
        (self.source / 'static' / 'js' / 'viewer.js').write_text('const a = 9;\n', encoding='utf-8')
        (self.source / 'brand_new.py').write_text('print("new")\n', encoding='utf-8')

    def test_sync_classifies_missing_and_stale_then_copies_with_backups(self):
        self.build_source()
        with patch.object(diagnostics, 'source_root', return_value=self.source):
            plan = repair_actions.plan_sync(['model_viewer.py', 'brand_new.py', 'static/js/viewer.js'])
            states = {item['path']: item['state'] for item in plan['changes']}
            self.assertEqual(states['model_viewer.py'], 'stale')
            self.assertEqual(states['brand_new.py'], 'missing')
            result = repair_actions.apply(plan)
        self.assertTrue(result['ok'], result)
        self.assertEqual((self.app / 'model_viewer.py').read_text(encoding='utf-8'), 'VALUE = 3\n')
        self.assertTrue((self.app / 'brand_new.py').is_file())
        copied = {item['path']: item for item in result['copied']}
        self.assertEqual(sorted(copied), ['brand_new.py', 'model_viewer.py', 'static/js/viewer.js'])
        self.assertIsNone(copied['brand_new.py']['backup'])
        self.assertTrue(copied['model_viewer.py']['backup'].endswith('model_viewer.py'))
        self.assertTrue(all(item['verified'] for item in result['copied']))
        self.assertIn('restart', result['message'])

    def test_sync_refuses_a_source_that_changed_after_review(self):
        self.build_source()
        with patch.object(diagnostics, 'source_root', return_value=self.source):
            plan = repair_actions.plan_sync(['model_viewer.py'])
            (self.source / 'model_viewer.py').write_text('VALUE = 4\n', encoding='utf-8')
            result = repair_actions.apply(plan)
        self.assertFalse(result['ok'])
        self.assertEqual((self.app / 'model_viewer.py').read_text(encoding='utf-8'), 'VALUE = 1\n')

    def test_a_locked_file_is_reported_instead_of_forced(self):
        self.build_source()
        real_copy = shutil.copy2
        with patch.object(diagnostics, 'source_root', return_value=self.source):
            plan = repair_actions.plan_sync(['model_viewer.py', 'brand_new.py'])

            def locked(origin, target, *args, **kwargs):
                # Only the publish step into the app folder fails, exactly as a
                # file the running window holds open would; backups still work.
                if str(origin).endswith('model_viewer.py') and 'repair-backups' not in str(target):
                    raise PermissionError(13, 'locked')
                return real_copy(origin, target, *args, **kwargs)
            with patch('repair_actions.shutil.copy2', side_effect=locked):
                result = repair_actions.apply(plan)
        self.assertEqual([item['path'] for item in result['failed']], ['model_viewer.py'])
        self.assertTrue((self.app / 'brand_new.py').is_file())

    def test_sync_says_nothing_when_the_files_already_match(self):
        self.build_source()
        shutil.copy2(self.source / 'model_viewer.py', self.app / 'model_viewer.py')
        with patch.object(diagnostics, 'source_root', return_value=self.source):
            with self.assertRaises(ValueError) as caught:
                repair_actions.plan_sync(['model_viewer.py'])
        self.assertIn('change nothing', str(caught.exception))

    def test_refresh_needs_a_script_and_never_runs_during_review(self):
        with patch.object(diagnostics, 'source_root', return_value=self.source):
            with self.assertRaises(ValueError) as caught:
                repair_actions.plan_refresh('companion')
        self.assertIn('refresh script', str(caught.exception))
        (self.source / 'tools').mkdir(parents=True)
        (self.source / 'tools' / 'create-local-products.py').write_text('print(1)\n', encoding='utf-8')
        with patch.object(diagnostics, 'source_root', return_value=self.source):
            plan = repair_actions.plan_refresh('companion')
            with self.assertRaises(ValueError):
                repair_actions.plan_refresh('combined')
        self.assertIn('create-local-products.py', plan['preview']['command'])
        self.assertFalse(self.app.joinpath('logs', 'ran').exists())

    def test_backups_listing_reports_the_saved_file(self):
        (self.app / 'settings.json').write_text('{', encoding='utf-8')
        repair_actions.apply(repair_actions.plan_state('settings.json', 'rebuild'))
        listing = repair_actions.backups()
        self.assertEqual(len(listing['backups']), 1)
        self.assertEqual(listing['backups'][0]['files'][0]['path'], 'settings.json')


if __name__ == '__main__':
    unittest.main()
