import unittest

from agent_evals import SCENARIOS, run_all, run_scenario


class AgentEvaluationGateTests(unittest.TestCase):
    """The scenarios are the contract; a regression in approval or recovery fails this test."""

    def test_the_suite_covers_every_agent_promise(self):
        names = [name for name, _ in SCENARIOS]
        self.assertEqual(len(names), len(set(names)), 'two scenarios share a name')
        for required in ('auto-continue reads, a human approves writes',
                         'existing files are never overwritten',
                         'a stale approved edit is blocked',
                         'shell commands never run unattended',
                         'an unproven finish is checked and retried',
                         'image evidence needs approval first',
                         'memory gives pointers, not transcripts',
                         'a tampered pending action is refused',
                         'workspace escapes are refused'):
            self.assertIn(required, names)

    def test_every_scenario_passes_and_reports_its_own_evidence(self):
        results = run_all()
        self.assertEqual(len(results), len(SCENARIOS))
        failed = [item['name'] + ' — ' + item['evidence'] for item in results if not item['passed']]
        self.assertEqual(failed, [], 'failing Agent scenarios:\n' + '\n'.join(failed))
        for item in results:
            self.assertGreaterEqual(len(item['evidence']), 10, item['name'])
            self.assertLessEqual(len(item['evidence']), 500, item['name'])

    def test_a_broken_scenario_is_reported_as_a_failure_not_a_crash(self):
        def deliberately_broken(runtime, root):
            assert False, 'the scenario itself is wrong'
        outcome = run_scenario(deliberately_broken)
        self.assertFalse(outcome['passed'])
        self.assertIn('the scenario itself is wrong', outcome['evidence'])
