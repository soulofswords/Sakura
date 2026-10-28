"""Run the offline Agent evaluation suite and report what the Agent actually proved.

No model download, no network and no clicks: scripted AI drives the real runtime over real
temporary workspaces. Exit code is non-zero when any scenario fails, so this is a gate.
"""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from agent_evals import report


def main():
    text, results = report()
    print(text)
    destination = root / 'audit-results'
    destination.mkdir(exist_ok=True)
    payload = {'passed': sum(1 for item in results if item['passed']), 'total': len(results), 'scenarios': results}
    (destination / 'agent-evaluations.json').write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    print('Wrote ' + str(destination / 'agent-evaluations.json'))
    return 0 if payload['passed'] == payload['total'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
