"""The bounded backend watcher lives in desktop.py, which cannot be imported here
because constructing that module starts Qt. Its one decision function is compiled out
of the source instead, the same way the other desktop harnesses pull a single function."""
import ast
import time
from pathlib import Path


def _load(name):
    tree = ast.parse(Path('desktop.py').read_text(encoding='utf-8'))
    node = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == name)
    namespace = {'time': time, 'BACKEND_RESTART_LIMIT': 2, 'BACKEND_PROBE_SECONDS': 15}
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'desktop.py', 'exec'), namespace)
    return namespace[name]


class FakeStop:
    """A watch loop that ticks a fixed number of times, then reports the window closing."""

    def __init__(self, ticks):
        self.ticks = ticks

    def is_set(self):
        return self.ticks <= 0

    def wait(self, _interval):
        self.ticks -= 1
        return self.ticks <= 0


def run(probe, restart, ticks=6):
    notes, reloads = [], []
    outcome = _load('supervise_backend')(probe, restart, lambda: reloads.append(1), notes.append,
                                         FakeStop(ticks), limit=2, interval=0)
    return outcome, notes, reloads


def test_a_backend_that_answers_is_never_restarted():
    def never():
        raise AssertionError('A healthy backend must not be restarted.')

    outcome, notes, reloads = run(lambda: True, never)
    assert (outcome, notes, reloads) == ('stopped', [], [])


def test_a_dead_backend_comes_back_once_and_the_page_is_reloaded():
    state = {'answering': False, 'restarts': 0}

    def restart():
        state['restarts'] += 1
        state['answering'] = True
        return True

    outcome, notes, reloads = run(lambda: state['answering'], restart)
    assert outcome == 'recovered' and state['restarts'] == 1 and reloads == [1]
    assert '1 of 2' in notes[0]


def test_a_fault_that_survives_two_restarts_stops_trying_and_says_so():
    restarts = []
    outcome, notes, reloads = run(lambda: False, lambda: restarts.append(1) or False, ticks=20)
    assert outcome == 'gave-up' and len(restarts) == 2 and reloads == []
    assert 'Close and reopen Sakura' in notes[0] and 'nothing else was restarted' in notes[0]


def test_the_probe_only_accepts_this_installations_own_backend():
    source = Path('desktop.py').read_text(encoding='utf-8')
    body = source[source.index('def backend_answers('):source.index('def _note_backend(')]
    assert 'sakura-anime-assistant' in body and 'INSTALLATION_ID' in body and 'EDITION' in body
