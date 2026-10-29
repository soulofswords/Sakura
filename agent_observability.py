"""Agent telemetry: a bounded local event trace plus the numbers the panel reports.

Nothing here can fail a task. The trace is the only durable record of *when* a step
ran, and the summary is derived from the live task records, so clearing the trace file
loses no capability and changes no behaviour.
"""
import json
import threading
import time
from pathlib import Path

MAX_LINE_BYTES = 1200
MAX_BYTES = 2_000_000
KEEP_AFTER_ROTATE = 1_000_000
KINDS = ('task', 'propose', 'decision', 'plan', 'reviewer', 'control', 'automation', 'usage')


def _short(value, limit=120):
    if isinstance(value, str):
        return value[:limit]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    if isinstance(value, bool):
        return value
    return str(value)[:limit]


class Trace:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.lock = threading.Lock()

    def record(self, kind, run_id='', **fields):
        """Append one event. Telemetry must never raise into the work it observes."""
        if self.path is None or kind not in KINDS:
            return
        try:
            line = {'t': round(time.time(), 3), 'kind': kind, 'run': _short(run_id, 64)}
            line.update({key: _short(value) for key, value in fields.items() if key.isidentifier()})
            encoded = json.dumps(line, ensure_ascii=False, separators=(',', ':'))
            if len(encoded.encode('utf-8')) > MAX_LINE_BYTES:
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.lock, self.path.open('a', encoding='utf-8', newline='\n') as handle:
                handle.write(encoded + '\n')
                size = handle.tell()
            # Rotate only after the append handle is closed: Windows refuses a second
            # open of a file this same thread still holds for writing.
            if size > MAX_BYTES:
                with self.lock:
                    self._rotate()
        except Exception:
            pass

    def _rotate(self):
        """Keep the newest tail so a long session cannot grow the profile folder forever."""
        try:
            data = self.path.read_bytes()
            tail = data[-KEEP_AFTER_ROTATE:]
            cut = tail.find(b'\n')
            if 0 <= cut < len(tail) - 1:
                tail = tail[cut + 1:]
            temp = self.path.with_suffix('.trace.tmp')
            temp.write_bytes(tail)
            temp.replace(self.path)
        except OSError:
            pass

    def tail(self, limit=40):
        if self.path is None:
            return []
        try:
            with self.lock, self.path.open('rb') as handle:
                handle.seek(0, 2)
                size = handle.tell()
                handle.seek(max(0, size - 65536))
                rows = handle.read().decode('utf-8', 'replace').splitlines()
        except OSError:
            return []
        result = []
        needed = max(1, min(int(limit), 200))
        for row in reversed(rows):
            if len(result) == needed:
                break
            try:
                item = json.loads(row)
            except ValueError:
                continue  # A torn final line is a real crash artefact; the events around it still count.
            if isinstance(item, dict):
                result.append(item)
        result.reverse()
        return result

    def clear(self):
        try:
            if self.path:
                self.path.unlink(missing_ok=True)
        except OSError:
            pass


def _rate(numerator, denominator):
    return round(numerator / denominator, 4) if denominator else 0.0


def _percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int(fraction * len(ordered)))], 2)


def summarize(runs, window_seconds=900):
    """Aggregate the recorded steps of these task transcripts; no model call, no I/O."""
    runs = [item for item in runs if isinstance(item, dict)]
    now = time.time()
    tasks = {}
    steps = []
    for run in runs:
        status = str(run.get('status') or 'unknown')
        tasks[status] = tasks.get(status, 0) + 1
        for step in run.get('steps') or []:
            if isinstance(step, dict):
                steps.append((run, step))
    counts = {}
    durations = {}
    by_tool = {}
    for run, step in steps:
        status = str(step.get('status') or 'pending')
        counts[status] = counts.get(status, 0) + 1
        tool = str(step.get('tool') or '')[:80]
        entry = by_tool.setdefault(tool, {'tool': tool, 'steps': 0, 'completed': 0, 'failed': 0, 'rejected': 0, 'auto': 0})
        entry['steps'] += 1
        if status in ('completed', 'failed', 'rejected'):
            entry[status] += 1
        if step.get('auto'):
            entry['auto'] += 1
        elapsed = step.get('seconds')
        if not isinstance(elapsed, (int, float)) or isinstance(elapsed, bool):
            created, finished = step.get('created_at'), step.get('finished_at')
            elapsed = finished - created if isinstance(created, (int, float)) \
                and isinstance(finished, (int, float)) and finished >= created else None
        if isinstance(elapsed, (int, float)) and not isinstance(elapsed, bool) and elapsed >= 0:
            durations.setdefault(tool, []).append(float(elapsed))
    decided = counts.get('completed', 0) + counts.get('failed', 0) + counts.get('rejected', 0) + counts.get('cancelled', 0)
    ran = counts.get('completed', 0) + counts.get('failed', 0)
    recent = [step for _, step in steps if isinstance(step.get('created_at'), (int, float))
              and now - step['created_at'] <= window_seconds]
    all_times = [value for items in durations.values() for value in items]
    slowest = max(((tool, items) for tool, items in durations.items()), key=lambda pair: max(pair[1]), default=None)
    verifications = {}
    recovery = 0
    exhausted = 0
    planners = {}
    for run in runs:
        label = str(run.get('verification') or 'not_finished')[:60]
        verifications[label] = verifications.get(label, 0) + 1
        recovery += int(run.get('recovery_cycles') or 0)
        if len(run.get('steps') or []) >= int(run.get('max_steps') or 0) and run.get('status') not in ('completed', 'cancelled'):
            exhausted += 1
        selection = run.get('planner_selection') or {}
        name = (str(selection.get('provider') or 'local') + ' ' + str(selection.get('native_model') or selection.get('model') or '')).strip()
        planners[name] = planners.get(name, 0) + 1
    return {
        'window_seconds': window_seconds,
        'tasks': {'total': len(runs), **{'status_' + key: value for key, value in sorted(tasks.items())}},
        'steps': {'total': len(steps), 'completed': counts.get('completed', 0), 'failed': counts.get('failed', 0),
                  'rejected': counts.get('rejected', 0), 'pending': counts.get('pending', 0),
                  'running': counts.get('running', 0), 'expired': counts.get('expired', 0),
                  'auto_ran': sum(1 for _, step in steps if step.get('auto')),
                  'approval_rate': _rate(decided - counts.get('rejected', 0), decided),
                  'failure_rate': _rate(counts.get('failed', 0), ran)},
        'recent_steps': {'total': len(recent),
                         'completed': sum(1 for step in recent if step.get('status') == 'completed'),
                         'failed': sum(1 for step in recent if step.get('status') == 'failed')},
        'by_tool': sorted(by_tool.values(), key=lambda item: (-item['steps'], item['tool']))[:14],
        'seconds': {'median': _percentile(all_times, 0.5), 'p95': _percentile(all_times, 0.95),
                    'slowest': (slowest[0], round(max(slowest[1]), 2)) if slowest else None},
        'review': {'verified': verifications.get('verified', 0), 'unverified': verifications.get('not_verified', 0),
                   'recovery_cycles': recovery, 'step_budget_exhausted': exhausted,
                   'verification_states': verifications},
        'planners': [{'planner': key, 'tasks': value} for key, value in sorted(planners.items(), key=lambda pair: -pair[1])[:6]],
    }
