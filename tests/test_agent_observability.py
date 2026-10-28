import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_connections import Connections
from agent_observability import Trace, summarize
from agent_runtime import AgentRuntime


class TraceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.trace = Trace(self.root / 'agent-trace.jsonl')

    def test_every_lifecycle_move_is_appended_as_one_parseable_line(self):
        runtime = AgentRuntime(Connections(self.root / 'connections.json'))
        (self.root / 'notes.txt').write_text('one\ntwo\n', encoding='utf-8')
        run = runtime.new_run('Edit a line', str(self.root), False)
        action = runtime.propose(run['id'], 'files.text.edit',
                                 {'path': 'notes.txt', 'replacements': [{'old': 'two', 'new': 'TWO', 'count': 1}]})['steps'][-1]
        runtime.decide(action['id'], False)
        runtime.pause(run['id'])
        kinds = [row['kind'] for row in self.trace.tail(20)]
        self.assertEqual(kinds, ['task', 'propose', 'decision', 'control'])
        decision = [row for row in self.trace.tail(20) if row['kind'] == 'decision'][0]
        self.assertEqual(decision['status'], 'rejected')
        self.assertFalse(decision['approve'])
        self.assertEqual(decision['tool'], 'files.text.edit')

    def test_completed_steps_record_the_time_they_took(self):
        runtime = AgentRuntime(Connections(self.root / 'connections.json'))
        (self.root / 'notes.txt').write_text('one\n', encoding='utf-8')
        run = runtime.new_run('Read a file', str(self.root), False)
        action = runtime.propose(run['id'], 'files.read', {'path': 'notes.txt'})['steps'][-1]
        step = runtime.decide(action['id'], True)['run']['steps'][-1]
        self.assertIsInstance(step['finished_at'], float)
        self.assertGreaterEqual(step['seconds'], 0)
        decision = [row for row in self.trace.tail(10) if row['kind'] == 'decision'][0]
        self.assertEqual(decision['status'], 'completed')
        self.assertGreaterEqual(decision['seconds'], 0)

    def test_the_tail_keeps_the_newest_lines_and_ignores_a_torn_one(self):
        for index in range(5):
            self.trace.record('task', 'run-%d' % index, chars=index)
        with (self.root / 'agent-trace.jsonl').open('a', encoding='utf-8', newline='\n') as handle:
            handle.write('{"kind":"task","ru\n')
        rows = self.trace.tail(3)
        self.assertEqual([row['run'] for row in rows], ['run-2', 'run-3', 'run-4'])
        self.assertTrue(all(row['kind'] == 'task' for row in rows))

    def test_rotation_bounds_the_file_and_leaves_it_readable(self):
        with patch('agent_observability.MAX_BYTES', 600), patch('agent_observability.KEEP_AFTER_ROTATE', 300):
            for index in range(80):
                self.trace.record('decision', 'run-%03d' % index, tool='files.read', seconds=index)
        data = (self.root / 'agent-trace.jsonl').read_bytes()
        self.assertLess(len(data), 600)
        rows = [json.loads(line) for line in data.decode('utf-8').splitlines()]
        self.assertTrue(all(row['kind'] == 'decision' for row in rows))
        self.assertEqual(rows[-1]['run'], 'run-079')

    def test_a_bad_target_can_never_break_the_work_being_observed(self):
        blocked = Trace(self.root)  # a folder, so every open for read or append fails
        blocked.record('task', 'run-1', chars=4)
        self.assertEqual(blocked.tail(5), [])

    def test_only_known_kinds_and_short_fields_are_written(self):
        self.trace.record('secrets', 'run-1', payload='x' * 5000)
        self.trace.record('task', 'run-1', goal='x' * 5000, **{'not an identifier': 1})
        rows = self.trace.tail(10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['goal']), 120)


class SummarizeTests(unittest.TestCase):
    def runs(self):
        return [
            {'id': 'a', 'status': 'completed', 'verification': 'verified', 'max_steps': 10, 'recovery_cycles': 0,
             'planner_selection': {'provider': 'ollama', 'model': 'qwen3:4b'},
             'steps': [{'tool': 'files.read', 'status': 'completed', 'auto': True, 'created_at': 1, 'seconds': 2.5},
                       {'tool': 'files.write', 'status': 'failed', 'created_at': 2, 'seconds': 0.5},
                       {'tool': 'files.read', 'status': 'completed', 'created_at': time.time(), 'seconds': 1}]},
            {'id': 'b', 'status': 'blocked', 'max_steps': 2, 'recovery_cycles': 3,
             'planner_selection': {'provider': 'gemini', 'model': 'gemini-flash-latest'},
             'steps': [{'tool': 'shell.run', 'status': 'rejected', 'created_at': 3},
                       {'tool': 'files.list', 'status': 'pending'}]},
        ]

    def test_counts_rates_and_latency_come_straight_from_the_step_records(self):
        summary = summarize(self.runs(), 900)
        self.assertEqual(summary['tasks']['total'], 2)
        self.assertEqual(summary['tasks']['status_completed'], 1)
        self.assertEqual(summary['tasks']['status_blocked'], 1)
        steps = summary['steps']
        self.assertEqual(steps['total'], 5)
        self.assertEqual((steps['completed'], steps['failed'], steps['rejected'], steps['pending']), (2, 1, 1, 1))
        self.assertEqual(steps['auto_ran'], 1)
        self.assertEqual(steps['approval_rate'], round(3 / 4, 4))
        self.assertEqual(steps['failure_rate'], round(1 / 3, 4))
        self.assertEqual(summary['recent_steps'], {'total': 1, 'completed': 1, 'failed': 0})
        self.assertEqual(summary['seconds']['median'], 1.0)
        self.assertEqual(summary['seconds']['slowest'][0], 'files.read')
        self.assertEqual(summary['seconds']['slowest'][1], 2.5)
        review = summary['review']
        self.assertEqual((review['verified'], review['recovery_cycles'], review['step_budget_exhausted']), (1, 3, 1))
        self.assertEqual(summary['by_tool'][0]['tool'], 'files.read')
        self.assertEqual(summary['by_tool'][0]['steps'], 2)
        self.assertEqual({item['planner'] for item in summary['planners']}, {'ollama qwen3:4b', 'gemini gemini-flash-latest'})

    def test_an_empty_history_reports_zeros_instead_of_crashing(self):
        summary = summarize([], 900)
        self.assertEqual(summary['tasks']['total'], 0)
        self.assertEqual(summary['steps']['approval_rate'], 0.0)
        self.assertIsNone(summary['seconds']['median'])
        self.assertIsNone(summary['seconds']['slowest'])


class RuntimeMetricsTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.runtime = AgentRuntime(Connections(self.root / 'connections.json'))

    def test_metrics_clamp_the_window_and_point_at_the_local_trace_file(self):
        run = self.runtime.new_run('Inspect my folder', str(self.root), False)
        self.runtime.propose(run['id'], 'files.list', {'path': '.'})
        for asked, expected in ((None, 900), ('bad', 900), (1, 60), (10 ** 9, 86400)):
            metrics = self.runtime.metrics(asked)
            self.assertEqual(metrics['summary']['window_seconds'], expected)
        self.assertEqual(metrics['open_tasks'], 1)
        self.assertEqual(Path(metrics['trace_file']).name, 'agent-trace.jsonl')
        self.assertTrue(any(row['kind'] == 'propose' for row in metrics['recent']))

    def test_clearing_history_removes_the_trace_too(self):
        self.runtime.new_run('Inspect my folder', str(self.root), False)
        self.assertTrue(self.trace_path().exists())
        self.runtime.clear_history()
        self.assertFalse(self.trace_path().exists())

    def trace_path(self):
        return self.root / 'agent-trace.jsonl'
