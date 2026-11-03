"""Opt-in response delivery from observed movements, never emotion recognition."""
import math

KEYS={'mouthSmileLeft','mouthSmileRight','browInnerUp','eyeBlinkLeft','eyeBlinkRight'}


def describe(observed,has_image=False):
    if not isinstance(observed,dict):
        return ('Camera style is enabled. If a face is visibly present in the supplied camera image, you may gently match visible conversational cues. Do not infer feelings, personality, health or identity; do not invent a face when none is visible. Answer the question first.' if has_image else '')
    values={key:round(min(1,max(0,value)),2) for key,value in observed.items() if key in KEYS and type(value) in (int,float) and math.isfinite(value)}
    if not values:return ''
    smiling=(values.get('mouthSmileLeft',0)+values.get('mouthSmileRight',0))/2>=.55
    delivery='Use a slightly warmer, lighter delivery when appropriate to the current topic.' if smiling else 'Keep a calm, clear conversational delivery; do not speculate about the person’s mood.'
    return 'Opt-in camera delivery hint from visible facial movements. '+delivery+' Never announce an inferred emotion or diagnose tiredness from blinks. Preserve factual accuracy, the selected Friend/Teacher mode and action approvals. Do not store these observations as user facts.'
