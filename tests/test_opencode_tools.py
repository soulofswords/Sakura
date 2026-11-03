"""A coding subtask can be handed to the OpenCode program on this PC, but never silently."""
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import opencode_tools as oc
from agent_connections import Connections
from agent_runtime import AUTO_RUN_TOOLS, AgentRuntime


class PlanTests(unittest.TestCase):
    def test_an_instruction_is_kept_word_for_word_until_it_is_rejected_or_handed_over(self):
        checked = oc.plan('  Rewrite parser.py to stop swallowing empty lines  ')
        self.assertEqual(checked['task'], 'Rewrite parser.py to stop swallowing empty lines')
        self.assertEqual(checked['model'], '')
        self.assertEqual(oc.plan('add tests', 'freellmapi/aion-2.0')['model'], 'freellmapi/aion-2.0')

    def test_a_prompt_cannot_smuggle_one_of_opencodes_own_options(self):
        for refused in ['', '   ', '--auto', '-m freellmapi/x', 'a' * (oc.MAX_TASK_CHARACTERS + 1),
                        'line one\n\x07secret']:
            with self.subTest(refused):
                with self.assertRaises(ValueError):
                    oc.plan(refused)
        for model in ['-m', 'not a model', 'provider/model extra', 'x' * 151]:
            with self.subTest(model):
                with self.assertRaisesRegex(ValueError, 'provider/model'):
                    oc.plan('do the thing', model)

    def test_the_time_budget_stays_inside_the_bounded_range(self):
        self.assertEqual(oc.timeout_seconds(None), oc.DEFAULT_TIMEOUT_SECONDS)
        self.assertEqual(oc.timeout_seconds(5), oc.MIN_TIMEOUT_SECONDS)
        self.assertEqual(oc.timeout_seconds(99999), oc.MAX_TIMEOUT_SECONDS)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.runtime = AgentRuntime(Connections(self.root / 'connections.json'))
        self.run = self.runtime.new_run('Refactor the parser module', str(self.root))
        self.program = self.root / 'opencode.exe'
        self.program.write_bytes(b'fake program')
        self.binary = patch.object(oc, 'binary', return_value=self.program)
        self.binary.start()
        self.addCleanup(self.binary.stop)

    def test_the_reviewer_sees_the_exact_instruction_folder_and_program(self):
        action = self.runtime._prepare(self.run, 'opencode.run',
                                       {'task': 'Split handler.py into a module and keep its tests passing',
                                        'cwd': '.', 'model': 'freellmapi/aion-2.0'})
        self.assertEqual(action['preview']['task'], 'Split handler.py into a module and keep its tests passing')
        self.assertEqual(Path(action['preview']['cwd']), self.root)
        self.assertEqual(action['preview']['program'], str(self.program.resolve()))
        self.assertEqual(action['preview']['model'], 'freellmapi/aion-2.0')
        self.assertEqual(action['preview']['timeout_seconds'], oc.DEFAULT_TIMEOUT_SECONDS)
        self.assertIn('not a sandbox', action['preview']['warning'])
        self.assertEqual(action['bindings']['program']['program'], str(self.program.resolve()))
        self.assertEqual(action['bindings']['program']['size'], self.program.stat().st_size)

    def test_the_folder_it_works_in_cannot_be_traded_for_one_outside_the_workspace(self):
        with self.assertRaises(ValueError):
            self.runtime._prepare(self.run, 'opencode.run', {'task': 'do it', 'cwd': '..'})
        with self.assertRaises(ValueError):
            self.runtime._prepare(self.run, 'opencode.run', {'task': 'do it', 'cwd': str(self.root.parent)})

    def test_handing_over_is_never_automatic_even_with_auto_continue_and_full_access(self):
        self.assertNotIn('opencode.run', AUTO_RUN_TOOLS)
        action = self.runtime._prepare(self.run, 'opencode.run', {'task': 'add a test for the parser'})
        self.assertFalse(self.runtime._auto_allowed(action))

    def test_it_is_handed_to_the_program_with_the_instruction_and_never_with_auto_approval(self):
        action = self.runtime._prepare(self.run, 'opencode.run',
                                       {'task': 'Rename the config loader everywhere', 'model': 'freellmapi/auto'})
        with patch('agent_runtime.run_process',
                   return_value={'ok': True, 'exit_code': 0, 'output': 'renamed in 4 files'}) as run_process:
            result = self.runtime._execute(action, self.run)
        argv = run_process.call_args.args[0]
        self.assertEqual(argv[:3], [str(self.program), 'run', 'Rename the config loader everywhere'])
        self.assertEqual(argv[argv.index('--dir') + 1], str(self.root))
        self.assertEqual(argv[argv.index('-m') + 1], 'freellmapi/auto')
        self.assertNotIn('--auto', argv)
        self.assertTrue(result['ok'])
        self.assertIn('renamed in 4 files', result['output'])
        self.assertIn('read or diff', result['note'])

    def test_the_run_gets_its_own_data_directory_instead_of_the_users_unreadable_one(self):
        # OpenCode keeps its session database under XDG_DATA_HOME, and on this PC that file fails
        # every subcommand, so a delegation using the user's store died before it opened a file.
        # A directory of Sakura's keeps the run working and keeps its sessions out of the history
        # the user browses in their own terminal. Configuration and keys are not moved.
        action = self.runtime._prepare(self.run, 'opencode.run', {'task': 'add a lint script'})
        wanted = self.root / 'opencode-data'
        with patch.object(oc, 'storage_dir', return_value=wanted), \
                patch('agent_runtime.run_process',
                      return_value={'ok': True, 'exit_code': 0, 'output': 'linted'}) as run_process:
            result = self.runtime._execute(action, self.run)
        environment = run_process.call_args.kwargs['env']
        self.assertEqual(environment['XDG_DATA_HOME'], str(wanted))
        self.assertEqual(result['data_dir'], str(wanted))
        self.assertTrue(wanted.is_dir())
        # A copy of the real environment: a bare one would leave OpenCode without PATH or a home.
        self.assertTrue(set(os.environ).issubset(set(environment)))

    def test_a_program_that_exits_badly_or_runs_out_of_time_is_reported_as_incomplete(self):
        action = self.runtime._prepare(self.run, 'opencode.run', {'task': 'fix the flaky test'})
        with patch('agent_runtime.run_process', return_value={'ok': False, 'exit_code': 2, 'output': 'permission denied'}):
            failed = self.runtime._execute(action, self.run)
        self.assertIn('exited with code 2', failed['error'])
        with patch('agent_runtime.run_process', return_value={'ok': False, 'exit_code': -1, 'timed_out': True, 'output': ''}):
            late = self.runtime._execute(action, self.run)
        self.assertIn('still working', late['error'])

    def test_a_replacement_program_or_folder_after_review_forces_a_new_proposal(self):
        action = self.runtime._prepare(self.run, 'opencode.run', {'task': 'add a changelog file'})
        self.program.write_bytes(b'tampered program')
        with patch('agent_runtime.run_process') as run_process:
            with self.assertRaisesRegex(ValueError, 'changed after review'):
                self.runtime._execute(action, self.run)
            run_process.assert_not_called()

    def test_no_opencode_means_no_step_is_proposed(self):
        with patch.object(oc, 'binary', return_value=None):
            with self.assertRaisesRegex(ValueError, 'not installed'):
                self.runtime._prepare(self.run, 'opencode.run', {'task': 'split the module'})


class InstalledProgramTests(unittest.TestCase):
    def setUp(self):
        self.program = Path(oc.binary() or '')
        if not self.program.is_file():
            self.skipTest('OpenCode is not installed on this PC.')

    def test_the_located_program_is_a_file_that_reports_a_version(self):
        from agent_runtime import run_process
        result = run_process([str(self.program), '--version'], self.program.parent, 60)
        self.assertTrue(result['ok'], result['output'])
        self.assertRegex(result['output'].strip(), r'^\d+\.\d+\.\d+')

    def test_the_real_multi_hundred_megabyte_binary_binds_without_a_step_being_refused(self):
        """The npm build is one large executable, so the 20 MB cap on a hashed run file used to
        reject every real proposal; the identity has to be taken without reading it."""
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        runtime = AgentRuntime(Connections(root / 'connections.json'))
        run = runtime.new_run('Refactor with OpenCode', str(root))
        action = runtime._prepare(run, 'opencode.run', {'task': 'read the readme and report its title'})
        self.assertEqual(action['bindings']['program']['program'], str(self.program.resolve()))
        self.assertGreater(action['bindings']['program']['size'], 20 * 1024 * 1024)
        self.assertFalse(runtime._auto_allowed(action))


if __name__ == '__main__':
    unittest.main()
