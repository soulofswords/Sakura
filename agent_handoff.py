"""Explicit chat handoff into the approval-gated Agent runtime.

Only a deliberate "agent: ..." or "computer: ..." prefix creates a task. The
handoff never executes a tool; planning and every action still need the Agent
panel, so a voice transcription cannot become an unreviewed command.
"""
import re
from pathlib import Path

TRIGGER=re.compile(r'^\s*(?:agent|computer)\s*[:\-]\s*(?P<goal>.{3,4000})$',re.I|re.S)


def goal_for(text):
    match=TRIGGER.match(text or '')
    return match.group('goal').strip() if match else ''


def start(text,workspace=None):
    goal=goal_for(text)
    if not goal:return None
    from agent_runtime import runtime
    root=Path(workspace).expanduser() if workspace else Path.home()
    run=runtime.new_run(goal,str(root))
    return {'reply':'I opened an Agent task for that. Open the Agent panel to plan it and approve each step; nothing has run yet.',
            'agent_run':run['id'],'audio':None}
