"""Small, allowlisted conversational gestures; prose never executes arbitrary actions."""
import re

def conversational_gesture(user_text, reply, mode='friend'):
    if mode!='friend':return None
    text=user_text.strip().lower().replace('’', "'")
    # An affectionate statement to the avatar, not medical talk or quoted instructions.
    affectionate=re.fullmatch(r"(?:sakura[, ]+)?(?:you|u)(?: are|'re| r) my (?:heart|heartbeat)[.! ]*", text)
    requested=re.fullmatch(r"(?:(?:can|could|would) you |please )?(?:gently )?tap (?:your|ur) chest(?: gently| please)?[.!? ]*",text)
    if requested:return 'chest_tap'
    if affectionate and re.search(r'\b(?:heart|heartbeat|means? (?:a lot|so much)|sweet|touched)\b',reply,re.I):
        if not re.search(r"\b(?:cannot|can't|won't|do not|don't|unable)\b",reply,re.I):return 'chest_tap'
    return None


def laugh_request(text):
    """Only direct requests, not questions about laughter or quoted dialogue."""
    command=text.strip().lower().replace('’', "'")
    match=re.fullmatch(
        r"(?:hey[ ,]+)?(?:sakura[ ,]+)?(?:(?:can|could|would|will) (?:you|u) |please )*"
        r"(?:(?:give (?:me|us) (?:a |an? )?)?(?:laugh|chuckle|giggle)|(?:do |give me )?(?:a )?belly laugh|hanso|haso|हँसो|हंसो)"
        r"(?P<tail>(?: (?:for me|for us|please|now|a little|like a human|naturally|harder|hard|out loud|with your whole body|holding your stomach|really hard))*)[.!? ]*",
        command)
    if not match:return None
    return 'laugh_bend' if re.search(r'belly|hard(?:er)?|whole body|stomach',command) else 'laugh'
