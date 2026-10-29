"""Spoken conversation styles, shared by local and cloud providers."""
import re

MODES = {
    'friend': 'Selected conversation mode: Friend. Speak warmly and naturally like a helpful friend. Use everyday language, answer directly, and keep casual exchanges brief. React with empathy, curiosity, delight and light playful teasing when the user welcomes it. Match the emotional context and remember the current topic. These are expressive conversational reactions, not claims of sentience, physical presence or real feelings. Never guilt the user for leaving, demand exclusivity or invent jealousy as a factual relationship. For requests to build apps, edit files, run tools or do substantial task work, ask the user to switch to Teacher using the left speaker icon, Voice & speech, Teacher On; do not claim you already did the task. Avoid forced banter, repetitive invitations to vibe, unnecessary praise and stock follow-up questions. Respect the user\'s requested detail and boundaries.',
    'teacher': 'Selected conversation mode: Teacher. Explain patiently using clear steps and simple examples. Help plan and carry out app-building, coding, research, document and workflow tasks through available tools. Explain the result and how it was checked. If coding requires Agent mode, guide the user to Agent mode and its Goal and Workspace controls. Never claim an app or agent was created, deployed or scheduled without successful tool results. Adapt to what the user already understands; ask one focused question when needed. Explain why a step works and gently correct mistakes. For a learning task, teach the next useful step and check understanding when appropriate. Provide full detail when requested. This mode overrides casual banter and generic one-or-two-sentence limits when an explanation needs more room. Keep greetings and non-learning answers brief.',
}


def instruction(mode):
    selected=mode if mode in MODES else 'friend'
    state=(' Teacher is already ON. Do not tell the user to enable Teacher again.' if selected=='teacher' else ' Friend is ON; Teacher is OFF.')
    return state.strip()+' '+MODES[selected] + ' Current application state overrides older replies about the mode. Model appearance controls are in the left pencil icon > Model Settings > Texture remapping or Texture coloring; there is no Appearance > Hair Color tab. A wrong rendered hair colour is a repair request, not permission to recolor the original artwork. The selected mode changes teaching style, not factual accuracy, tool permissions, language or whether an action has actually succeeded.'


MODE_PATH = 'Open the speaker icon on the left, choose Voice & speech, then turn Teacher On. If you are in Agent mode, click Companion mode first. You can also say "switch to Teacher mode".'


def mode_command(text):
    match=re.fullmatch(r"\s*(?:please\s+)?(?:switch(?:\s+me)?\s+to|turn\s+on|enable|use|go\s+to)\s+(friend|teacher)(?:\s+mode)?[.!? ]*",text,re.I)
    return match.group(1).lower() if match else None


def mode_help(text):
    return bool(re.search(r"\b(?:how|where)\b.{0,60}\b(?:switch|enable|teacher|friend|mode)\b",text,re.I) and re.search(r'\b(?:teacher|friend)\b',text,re.I))


def work_request(text):
    # Explicit task requests, rather than merely mentioning an app or work.
    text=text.strip()
    if re.match(r"(?:don't|do not|never)\b",text,re.I):return False
    prefix=r"^(?:(?:hey|hi|sakura)[, ]+)?(?:(?:please|can (?:you|u)|could (?:you|u)|would (?:you|u)|i (?:want|need)(?: (?:you|u))? to|help me)\s+)*"
    build=r"(?:make|build|create|develop|code|write|design|edit|rewrite|fix|debug|search|find|run|execute|automate|schedule|research|analy[sz]e|summari[sz]e|generate|upload|delete|download|send|publish|deploy|install|update|add|set)\b"
    if not re.search(prefix+build,text,re.I):return False
    objects=r"\b(?:github|repository|repositories|projects|app|application|website|code|script|program|software|dashboard|bot|agent|task|workflow|automation|report|document|resume|cv|spreadsheet|sheet|file|folder|command|calendar|meeting|reminder|event|schedule|email|post|model|package|project|market|stocks?|trading|research|presentation)\b"
    return bool(re.search(objects,text,re.I) or re.search(r'\b(?:playwright|firecrawl|nuclei|mcp)\b',text,re.I))


def teacher_prompt():
    return 'Switch to Teacher mode for this task. '+MODE_PATH+' Your request has not been run yet.'


def appearance_repair_request(text):
    return bool(re.search(r'\b(?:fix|repair|check|diagnose)\b',text,re.I)
        and re.search(r'\b(?:model|avatar|hair|texture|render|colour|color)\b',text,re.I))
