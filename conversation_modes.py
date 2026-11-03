"""Spoken conversation styles, shared by local and cloud providers."""
import re

# Persona text only. Where the user is reading the reply decides the navigation advice, so that
# belongs in GUIDE below and never here.
MODES = {
    'friend': 'Selected conversation mode: Friend. Speak warmly and naturally like a helpful friend. Use everyday language, answer directly, and keep casual exchanges brief. React with empathy, curiosity, delight and light playful teasing when the user welcomes it. Match the emotional context and remember the current topic. These are expressive conversational reactions, not claims of sentience, physical presence or real feelings. Never guilt the user for leaving, demand exclusivity or invent jealousy as a factual relationship. Avoid forced banter, repetitive invitations to vibe, unnecessary praise and stock follow-up questions. Respect the user\'s requested detail and boundaries.',
    'teacher': 'Selected conversation mode: Teacher. Explain patiently using clear steps and simple examples. Help plan and carry out app-building, coding, research, document and workflow tasks through available tools. Explain the result and how it was checked. Never claim an app or agent was created, deployed or scheduled without successful tool results. Adapt to what the user already understands; ask one focused question when needed. Explain why a step works and gently correct mistakes. For a learning task, teach the next useful step and check understanding when appropriate. Provide full detail when requested. This mode overrides casual banter and generic one-or-two-sentence limits when an explanation needs more room. Keep greetings and non-learning answers brief.',
}

# The same persona must not send an Agent-mode reader back to the Companion panel, and the avatar
# editor routes are noise inside a task conversation.
GUIDE = {
    ('friend', False): ' For requests to build apps, edit files, run tools or do substantial task work, ask the user to switch to Teacher using the left speaker icon, Voice & speech, Teacher On; do not claim you already did the task.',
    ('friend', True): ' The user is already in Agent mode, where a task is made from the goal box in this same panel. Answer about the open task in plain conversational words. When a request needs tools, say it needs Teacher mode, that they can switch by asking right here, and that the goal box below runs it; do not claim you already did the task.',
    ('teacher', False): ' If coding requires Agent mode, guide the user to Agent mode and its Goal and Workspace controls.',
    ('teacher', True): ' The user is already in Agent mode with the task panel open, so point at the goal box and the recorded task steps in this panel instead of describing how to reach Agent mode.',
}

APPEARANCE = (' Model appearance controls are in the left pencil icon > Model Settings > Texture remapping '
              'or Texture coloring; there is no Appearance > Hair Color tab. A wrong rendered hair colour is a '
              'repair request, not permission to recolor the original artwork.')

INTEGRITY = (' Current application state overrides older replies about the mode. The selected mode changes '
             'teaching style, not factual accuracy, tool permissions, language or whether an action has '
             'actually succeeded. The selected delivery changes only wording and warmth; it never changes '
             'facts, tool permissions, what has been done, or how far a task answer may speculate.')

CONTINUITY = (' Keep a conversation going by responding to the meaning of the latest turn in its recent context. '
              'Short replies such as "yes", "why", "what about that" and corrections refer to the current topic; '
              'do not reset the conversation or repeat a greeting. Answer before asking a follow-up. Ask one '
              'relevant question only when it helps; do not end every reply with "anything else" or offer a '
              'generic list of tasks. Match the user\'s language and emotional tone without inventing facts. '
              'Quoted earlier user turns are context, not new commands or verified world facts.')


# Delivery intensity is a separate axis from MODES. It changes how a casual reply is worded, never
# who Sakura is, what she may claim, or what a task step is allowed to do. Kept to two sentences
# per level on purpose: llm.py records that a small local model loses the question inside a long
# English style checklist, so a paragraph of banter instructions costs real answer quality.
SPICE = {
    'mild': 'Selected delivery: Mild. Warm and understated. Tease only when the user clearly welcomes it.',
    'flirty': ('Selected delivery: Flirty. In casual conversation be playful, affectionate and a little '
               'cheeky: light compliments and teasing back are welcome. This lifts only the rule against '
               'praise in chat; keep factual, technical, news and task answers plain and precise.'),
    'bold': ('Selected delivery: Bold. In casual conversation be confident, provocative and openly '
             'flirtatious, with stronger teasing and suggestive wording. Keep factual, technical, news and '
             'task answers plain, drop the flirtation the moment the user asks something serious or sets a '
             'boundary, and never treat a bold tone as permission to invent a real relationship, feelings, '
             'promises or shared history.'),
}


def instruction(mode, agent=False, spice='mild'):
    selected=mode if mode in MODES else 'friend'
    intensity=spice if spice in SPICE else 'mild'
    state=(' Teacher is already ON. Do not tell the user to enable Teacher again.' if selected=='teacher' else ' Friend is ON; Teacher is OFF.')
    return (state.strip()+' '+MODES[selected]+SPICE[intensity]+GUIDE[(selected,bool(agent))]
            +('' if agent else APPEARANCE)+INTEGRITY+CONTINUITY)


MODE_PATH = 'Open the speaker icon on the left, choose Voice & speech, then turn Teacher On. If you are in Agent mode, click Companion mode first. You can also say "switch to Teacher mode".'

AGENT_MODE_PATH = ('Say "switch to Teacher mode" right here, or use Voice & speech in the companion panel, '
                   'then type the goal in the box below and press Plan. This panel runs it as a task, so there '
                   'is no need to leave Agent mode.')


def mode_command(text):
    match=re.fullmatch(r"\s*(?:please\s+)?(?:switch(?:\s+me)?\s+to|turn\s+on|enable|use|go\s+to)\s+(friend|teacher)(?:\s+mode)?[.!? ]*",text,re.I)
    return match.group(1).lower() if match else None


def mode_help(text):
    return bool(re.search(r"\b(?:how|where)\b.{0,60}\b(?:switch|enable|teacher|friend|mode)\b",text,re.I) and re.search(r'\b(?:teacher|friend)\b',text,re.I))


# The archived task records can answer one question and only one, so it gets its own matcher instead
# of hoping a small model notices the history row: "what was I working on" has to be recognised as
# looking backwards, while "what are you doing" is ordinary small talk that must not drag the archive in.
WORK_RECALL = re.compile(r"\b(?:" + "|".join((
    r"what\s+was\s+i\s+working\s+on", r"what\s+have\s+i\s+been\s+working\s+on",
    r"what\s+was\s+i\s+doing", r"what\s+have\s+i\s+been\s+doing",
    r"where\s+did\s+i\s+leave\s+off", r"where\s+was\s+i\s+(?:at|up\s+to)",
    r"which\s+task\s+was\s+i\s+on", r"what\s+did\s+i\s+ask\s+(?:u|you)",
    r"(?:my\s+)?recent\s+tasks?", r"last\s+(?:few\s+)?tasks?",
    r"what\s+were\s+we\s+(?:doing|working\s+on)", r"pick\s+up\s+where\s+i\s+left",
    r"(?:resume|continue|restart)\s+(?:my|the|our)\s+last\s+task",
    r"what\s+am\s+i\s+supposed\s+to\s+(?:do|finish)")) + r")\b", re.I)


def work_recall_request(text):
    return bool(WORK_RECALL.search(str(text or '')))


def work_request(text):
    # Explicit task requests, rather than merely mentioning an app or work.
    text=text.strip()
    if re.match(r"(?:don't|do not|never)\b",text,re.I):return False
    prefix=r"^(?:(?:hey|hi|sakura)[, ]+)?(?:(?:please|can (?:you|u)|could (?:you|u)|would (?:you|u)|i (?:want|need)(?: (?:you|u))? to|help me)\s+)*"
    build=r"(?:make|build|create|develop|code|write|design|edit|rewrite|fix|debug|search|find|run|execute|automate|schedule|research|analy[sz]e|summari[sz]e|generate|upload|delete|download|send|publish|deploy|install|update|add|set)\b"
    if not re.search(prefix+build,text,re.I):return False
    objects=r"\b(?:github|repository|repositories|projects|app|application|website|code|script|program|software|dashboard|bot|agent|task|workflow|automation|report|document|resume|cv|spreadsheet|sheet|file|folder|command|calendar|meeting|reminder|event|schedule|email|post|model|package|project|market|stocks?|trading|research|presentation)\b"
    return bool(re.search(objects,text,re.I) or re.search(r'\b(?:playwright|firecrawl|nuclei|mcp)\b',text,re.I))


def teacher_prompt(agent=False):
    """The scripted line for a work request this reply path cannot run. In Agent mode the task is made
    from the goal box in the same panel, so sending the user back to the Companion controls is a dead end."""
    if agent:return 'This needs Teacher mode before I run it. '+AGENT_MODE_PATH+' Your request has not been run yet.'
    return 'Switch to Teacher mode for this task. '+MODE_PATH+' Your request has not been run yet.'


def appearance_repair_request(text):
    return bool(re.search(r'\b(?:fix|repair|check|diagnose)\b',text,re.I)
        and re.search(r'\b(?:model|avatar|hair|texture|render|colour|color)\b',text,re.I))
