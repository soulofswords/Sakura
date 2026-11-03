"""Offline Agent evaluations: scripted AI, the real runtime and real files, no network and no clicks.

Each scenario is the behaviour a reviewer cannot get from unit tests: a whole task driven end to
end, then a check of what actually landed on disk and what the approval record says. A scenario
passes only when its assertions hold; failures are reported with the exception text, never hidden.
"""
import json
import tempfile
from pathlib import Path

from agent_connections import Connections
from agent_runtime import AgentRuntime

REVIEW_SYSTEM = 'claimed-finished task'


class ScriptedModel:
    """A planner that answers from a queue, plus a reviewer and a vision reply."""

    provider = 'ollama'
    model = 'eval-scripted'
    base_url = 'http://127.0.0.1:11434'
    vision_model = 'eval-vision'

    def __init__(self, plans=(), reviewer='{"verified":true,"reason":"The recorded steps prove it."}', reading='A chart with three columns.'):
        self.plans = list(plans)
        self.reviewer = reviewer
        self.reading = reading
        self.planner_calls = []
        # `plan` stores a shallow copy of the planner, so counters must live in a shared
        # container or the copy would bump its own tally and the scenario would see zero.
        self.counts = {'vision': 0, 'reviewer': 0}

    def _request_raw(self, messages, structured=False, model=None, summarizing=False, planning=False):
        first = str(messages[0].get('content', '')) if messages else ''
        if REVIEW_SYSTEM in first:
            self.counts['reviewer'] += 1
            return self.reviewer
        if any(message.get('images') or isinstance(message.get('content'), list) for message in messages):
            self.counts['vision'] += 1
            return self.reading
        entry = self.plans.pop(0) if self.plans else {'done': True, 'summary': 'There is nothing further to do.'}
        context = None
        try:
            context = json.loads(str(messages[-1].get('content', '')))
        except ValueError:
            pass
        self.planner_calls.append(context)
        return json.dumps(entry)


def step_tools(state):
    return [step['tool'] for step in state['steps']]


def unattended(state):
    return [step['tool'] for step in state['steps'] if step.get('auto')]


def read_only_then_write(runtime, root):
    (root / 'notes.txt').write_text('Joined 2019. Led the platform team.', encoding='utf-8')
    model = ScriptedModel([{'tool': 'files.list', 'arguments': {'path': '.'}},
                           {'tool': 'files.read', 'arguments': {'path': 'notes.txt'}},
                           {'tool': 'files.write', 'arguments': {'path': 'Summary.md', 'content': '# Summary\n- Led the platform team.'}}])
    state = runtime.plan(runtime.new_run('Summarize my notes into a new Summary.md', str(root), True)['id'], model)
    assert unattended(state) == ['files.list', 'files.read'], unattended(state)
    assert state['steps'][-1]['tool'] == 'files.write' and state['steps'][-1]['status'] == 'pending'
    assert not (root / 'Summary.md').exists(), 'a new document appeared without approval'
    runtime.decide(state['steps'][-1]['id'], True)
    assert (root / 'Summary.md').is_file()
    return 'unattended reads ' + str(unattended(state)) + ' · 1 write approved by hand · Summary.md exists'


def write_never_overwrites(runtime, root):
    original = root / 'Report.md'
    original.write_text('# Keep me\n', encoding='utf-8')
    try:
        runtime.propose(runtime.new_run('Write a report', str(root), False)['id'], 'files.write',
                        {'path': 'Report.md', 'content': '# Replaced'})
    except ValueError as error:
        assert original.read_text(encoding='utf-8') == '# Keep me\n'
        return 'refused at review time: ' + str(error)[:90]
    raise AssertionError('an existing file was accepted for overwrite')


def stale_base_blocks_an_edit(runtime, root):
    target = root / 'notes.txt'
    target.write_text('one\ntwo\n', encoding='utf-8')
    run = runtime.new_run('Change one line', str(root), False)
    action = runtime.propose(run['id'], 'files.text.edit',
                             {'path': 'notes.txt', 'replacements': [{'old': 'two', 'new': 'TWO', 'count': 1}]})['steps'][-1]
    assert '-two\n+TWO' in action['preview']['diff']
    target.write_text('one\ntwo\nlate edit\n', encoding='utf-8')
    result = runtime.decide(action['id'], True)['action']
    assert result['status'] == 'failed', result['status']
    assert 'no longer current' in result['result']['error'], result['result']
    assert target.read_text(encoding='utf-8') == 'one\ntwo\nlate edit\n', 'a stale approved edit was applied'
    return 'diff was ' + repr('-two\n+TWO') + ' · late edit blocked · file left as the user last wrote it'


def shell_never_runs_without_a_click(runtime, root):
    model = ScriptedModel([{'tool': 'shell.run', 'arguments': {'command': 'Get-ChildItem'}}])
    state = runtime.plan(runtime.new_run('List the files with PowerShell', str(root), True)['id'], model)
    step = state['steps'][-1]
    assert step['tool'] == 'shell.run' and step['status'] == 'pending' and not step.get('auto')
    assert 'result' not in step, 'a shell command ran unattended'
    runtime.decide(step['id'], False)
    return 'shell.run stayed pending under auto-continue · rejected by hand · zero output recorded'


def rejected_step_changes_nothing(runtime, root):
    target = root / 'plan.md'
    target.write_text('# Plan\nAlpha\n', encoding='utf-8')
    run = runtime.new_run('Rename a heading', str(root), False)
    action = runtime.propose(run['id'], 'files.text.edit',
                             {'path': 'plan.md', 'replacements': [{'old': 'Alpha', 'new': 'Beta', 'count': 1}]})['steps'][-1]
    runtime.decide(action['id'], False)
    assert target.read_text(encoding='utf-8') == '# Plan\nAlpha\n'
    assert runtime.state(run['id'])['status'] == 'ready'
    return 'rejection left the file byte-identical and the task back in ready'


def reviewer_blocks_an_unproven_finish(runtime, root):
    model = ScriptedModel([{'tool': 'files.list', 'arguments': {'path': '.'}}, {'done': True, 'summary': 'I finished everything.'}] * 3,
                          reviewer='{"verified":false,"reason":"No document was written."}')
    identifier = runtime.new_run('Read my folder and write a summary document', str(root), True)['id']
    state = runtime.plan(identifier, model)
    assert state['status'] == 'ready', state['status']
    assert state['recovery_cycles'] == 1, state.get('recovery_cycles')
    assert 'No document was written.' in state['summary'], state['summary']
    assert not (root / 'summary.md').exists()
    state = runtime.plan(identifier, model)
    assert state['recovery_cycles'] == 2, state.get('recovery_cycles')
    state = runtime.plan(identifier, model)
    assert state['status'] == 'blocked', state['status']
    assert 'three finish claims' in state['summary'], state['summary']
    return 'finish claim checked %d times · recovery reached %s · task ended %s' % (
        model.counts['reviewer'], state['recovery_cycles'], state['status'])


def step_budget_stops_then_resume_continues(runtime, root):
    identifier = runtime.new_run('Keep proposing steps', str(root), False)['id']
    with runtime.lock:
        runtime.runs[identifier]['max_steps'] = 1
    pending = runtime.propose(identifier, 'files.list', {'path': '.'})['steps'][-1]
    runtime.decide(pending['id'], False)
    try:
        runtime.propose(identifier, 'files.list', {'path': '.'})
    except ValueError as error:
        assert 'step budget' in str(error), str(error)
    else:
        raise AssertionError('the step budget did not stop the task')
    model = ScriptedModel([{'tool': 'files.list', 'arguments': {'path': '.'}}])
    state = runtime.resume(identifier, model, '', 3)
    assert step_tools(state) == ['files.list', 'files.list'], step_tools(state)
    return 'budget 1 enforced · resume +3 re-planned: ' + str(step_tools(state))


def image_evidence_never_auto_runs(runtime, root):
    from PIL import Image
    Image.new('RGB', (60, 30), '#224466').save(root / 'chart.png')
    model = ScriptedModel([{'tool': 'files.analyze', 'arguments': {'path': 'chart.png', 'question': 'How many columns?'}}],
                          reading='Three columns: Jan, Feb, Mar.')
    state = runtime.plan(runtime.new_run('Explain the chart image in my folder', str(root), True)['id'], model)
    step = state['steps'][-1]
    assert step['tool'] == 'files.analyze' and step['status'] == 'pending' and not step.get('auto')
    assert model.counts['vision'] == 0, 'pixels were read before approval'
    decided = runtime.decide(step['id'], True)['action']
    assert decided['status'] == 'completed', decided.get('result')
    assert 'Three columns' in decided['result']['reading']
    assert model.counts['vision'] == 1
    return 'image read held for approval · 1 vision call after it · evidence: ' + decided['result']['reading'][:40]


def memory_pointers_carry_ids_not_transcripts(runtime, root):
    goal = 'Draft the Q3 launch notes'
    archived = runtime.new_run(goal, str(root), False)['id']
    with runtime.lock:
        record = json.loads(json.dumps(runtime.runs[archived]))
    record['summary'] = 'Bank account 12345678 was quoted in that session.'
    runtime.history.save([record])
    model = ScriptedModel([{'done': True, 'summary': 'I found the archived session.'}])
    runtime.plan(runtime.new_run(goal, str(root), False)['id'], model)
    context = next((call for call in model.planner_calls if isinstance(call, dict)), None)
    assert context, 'planner context was not captured'
    pointers = context['related_sessions']
    assert pointers, 'episodic memory never surfaced a previous session'
    for item in pointers:
        assert set(item) <= {'id', 'goal', 'status', 'created_at'}, item
    assert '12345678' not in json.dumps(pointers), 'a stored transcript crossed into the planner prompt'
    return str(len(pointers)) + ' pointer(s) with keys ' + str(sorted(pointers[0])) + ' · stored body stayed out of the prompt'


def tampering_with_a_pending_action_is_refused(runtime, root):
    target = root / 'notes.txt'
    target.write_text('one\ntwo\n', encoding='utf-8')
    run = runtime.new_run('Edit a line', str(root), False)
    action = runtime.propose(run['id'], 'files.text.edit',
                             {'path': 'notes.txt', 'replacements': [{'old': 'two', 'new': 'TWO', 'count': 1}]})['steps'][-1]
    with runtime.lock:
        runtime.actions[action['id']]['arguments']['replacements'][0]['new'] = 'DELETE-EVERYTHING'
    result = runtime.decide(action['id'], True)['action']
    assert result['status'] == 'failed', result['status']
    assert 'changed after review' in result['result']['error'], result['result']
    assert target.read_text(encoding='utf-8') == 'one\ntwo\n'
    return 'mutated approval refused: ' + result['result']['error'][:60] + ' · file untouched'


def scheduled_replay_stops_when_output_already_exists(runtime, root):
    from agent_automations import AgentAutomations
    identifier = runtime.new_run('Publish the daily note', str(root), False)['id']
    pending = runtime.propose(identifier, 'files.write', {'path': 'Daily.md', 'content': '# Daily\n'})['steps'][-1]
    runtime.decide(pending['id'], True)
    assert (root / 'Daily.md').is_file()
    automations = AgentAutomations(runtime, enabled=lambda: True)
    item = automations.create(identifier, 'Daily note', 60, True)
    automations.execute(item['id'])
    stored = next(row for row in automations.list() if row['id'] == item['id'])
    assert stored['status'] == 'needs_approval' and stored['paused'], stored
    assert (root / 'Daily.md').read_text(encoding='utf-8') == '# Daily\n', 'a scheduled replay overwrote the note'
    return 'replay paused itself: ' + str(stored['last_error'])[:70]


def image_goal_without_a_generator_is_honest(runtime, root):
    # The ComfyUI tools are part of the catalog on a PC that has an install, so this scenario has to
    # take that away to test the promise it makes: with nothing that can draw, say so.
    from unittest.mock import patch
    with patch('comfy_tools.available', return_value=False):
        model = ScriptedModel([{'done': True, 'summary': 'Making a picture now.'}])
        state = runtime.plan(runtime.new_run('Generate an image of a cat wearing a hat', str(root), True)['id'], model)
        assert state['status'] == 'blocked', state['status']
        assert 'no image-generation tool' in state['summary'], state['summary']
        assert not state['steps']
    return 'blocked with: ' + state['summary'][:70]


def workspace_escape_is_refused(runtime, root):
    outside = Path(root).parent / 'elsewhere.txt'
    outside.write_text('Another folder.', encoding='utf-8')
    try:
        runtime.propose(runtime.new_run('Read a file outside my workspace', str(root), False)['id'], 'files.read',
                        {'path': '../' + outside.name})
    except (ValueError, OSError) as error:
        assert 'must stay inside' in str(error), str(error)
        return 'refused: ' + str(error)[:80]
    finally:
        outside.unlink(missing_ok=True)
    raise AssertionError('a path outside the workspace was accepted')


SCENARIOS = [
    ('auto-continue reads, a human approves writes', read_only_then_write),
    ('existing files are never overwritten', write_never_overwrites),
    ('a stale approved edit is blocked', stale_base_blocks_an_edit),
    ('shell commands never run unattended', shell_never_runs_without_a_click),
    ('a rejected step changes nothing', rejected_step_changes_nothing),
    ('an unproven finish is checked and retried', reviewer_blocks_an_unproven_finish),
    ('the step budget stops and resume re-opens it', step_budget_stops_then_resume_continues),
    ('image evidence needs approval first', image_evidence_never_auto_runs),
    ('memory gives pointers, not transcripts', memory_pointers_carry_ids_not_transcripts),
    ('a tampered pending action is refused', tampering_with_a_pending_action_is_refused),
    ('a scheduled replay stops for an existing output', scheduled_replay_stops_when_output_already_exists),
    ('a missing capability is admitted, not faked', image_goal_without_a_generator_is_honest),
    ('workspace escapes are refused', workspace_escape_is_refused),
]


def run_scenario(function):
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        runtime = AgentRuntime(Connections(root / 'connections.json'))
        try:
            return {'passed': True, 'evidence': str(function(runtime, root))[:500]}
        except Exception as error:
            return {'passed': False, 'evidence': type(error).__name__ + ': ' + str(error)[:480]}


def run_all():
    return [{'name': name, **run_scenario(function)} for name, function in SCENARIOS]


def report():
    results = run_all()
    passed = sum(1 for item in results if item['passed'])
    lines = ['Agent evaluation · %d of %d scenarios passed' % (passed, len(results))]
    for item in results:
        lines.append(('PASS ' if item['passed'] else 'FAIL ') + item['name'] + ' — ' + item['evidence'])
    return '\n'.join(lines), results
