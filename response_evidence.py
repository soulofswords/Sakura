"""Fail-closed factual response routing. Evidence scores are policy scores, not probabilities."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
import re
import requests
from urllib.parse import urlparse

UNKNOWN = "I couldn't verify that."
RULE = 'Prefer uncertainty over fabrication.'
LABELS = ('Verified', 'User-provided', 'Inference', 'Unknown')


@dataclass
class Evidence:
    text: str
    classification: str = 'Unknown'
    confidence: float = 0.0
    sources: list = field(default_factory=list)
    method: str = ''
    observed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def sufficient(self, threshold):
        return (self.classification in ('Verified', 'User-provided')
                and type(self.confidence) in (int,float) and math.isfinite(self.confidence)
                and 0 <= self.confidence <= 1 and self.confidence >= threshold)

    def answerable(self, threshold):
        return self.classification == 'Verified' and self.sufficient(threshold) and verified_sources(self)

    def memory_eligible(self, threshold):
        # Social dialogue is an authored response, not a fact to remember.
        if self.method == 'built-in conversation':return False
        if self.classification == 'Verified':return self.answerable(threshold)
        return (self.classification == 'User-provided' and self.sufficient(threshold)
                and confirmed_user_fact(self.text.removeprefix('Noted: '))
                and any(s.get('kind') == 'user' for s in self.sources))

    def public(self):
        statements = [part.strip() for part in re.split(r'(?<=[.!?।])\s+(?!https?://)|\n(?=Source:)', self.text) if part.strip()]
        return {'statements': [{'text': part, 'classification': self.classification,
                               'confidence': self.confidence, 'sources': self.sources}
                              for part in statements],
                'sources': self.sources, 'verification': {'classification': self.classification,
                'confidence': self.confidence, 'method': self.method, 'observed_at': self.observed_at,
                'confidence_meaning': 'evidence policy score, not a calibrated probability'}}


def threshold(settings):
    value = settings.get('evidence_confidence_threshold', .9)
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        return .9
    return float(value)


LOCAL_SOURCES = {
    'PC command/status/file/time tool': 'sakura://tools/pc-command-status-file-time',
    'application configuration': 'sakura://settings/assistant-identity',
    'confirmed user memory': 'sakura://memory/user-statements',
    'memory receipt': 'sakura://memory/write-receipt',
    'built-in conversation': 'sakura://conversation/authored-replies',
}


def verified_sources(evidence):
    """Accept only citations from the registered retrieval paths, never bare labels."""
    if not isinstance(evidence.sources,list) or not evidence.sources:return False
    for source in evidence.sources:
        if not isinstance(source,dict):return False
        url=source.get('url','')
        if not isinstance(url,str):return False
        if evidence.method in LOCAL_SOURCES:
            if source.get('kind')!='tool' or url!=LOCAL_SOURCES[evidence.method]:return False
            continue
        if source.get('kind')!='external':return False
        try:
            parsed=urlparse(url)
            if parsed.port not in (None,443):return False
        except ValueError:return False
        if parsed.scheme!='https' or parsed.username or parsed.password:return False
        if evidence.method=='manufacturer specification lookup':
            from factual_grounding import trusted_gpu_page
            if not trusted_gpu_page(url):return False
        elif evidence.method=='weather/news retrieval':
            if parsed.hostname not in ('open-meteo.com','news.google.com'):return False
        elif evidence.method=='reference retrieval':
            if parsed.hostname!='en.wikipedia.org' or parsed.path!='/' or not re.fullmatch(r'curid=\d+',parsed.query):return False
        else:return False
        if url not in evidence.text:return False
    return True


def strict_answer(evidence, minimum):
    """No fallback to a model: missing, inferred, user-only or uncited facts refuse."""
    return evidence if isinstance(evidence,Evidence) and evidence.answerable(minimum) else Evidence(UNKNOWN,method='Astra Strict Mode refusal')


def confirmed_user_fact(text):
    """Keep verbatim explicit first-person declarations, never a question/presupposition."""
    if '?' in text or re.search(r'\b(?:maybe|perhaps|i think|not sure|suppose|imagine|if|fiction|guess)\b', text, re.I):
        return False
    return bool(re.fullmatch(r"\s*(?:remember (?:that )?)?(?:my (?:name|city|state|country|PC|GPU|CPU|RAM|birthday|preferred name|pronouns) (?:is|are|has) .{1,220}|I (?:live in|own|have|prefer|use) .{1,220}|मेरा नाम .{1,100}|मैं .{1,100} में रहता हूँ)[.! ]*", text, re.I))


def conversational_request(text):
    from persona_grounding import greeting, identity_question, fiction_requested
    from dance_commands import dance_action, hand_action
    from avatar_gestures import laugh_request, conversational_gesture
    from singing import requested
    if dance_action(text) or hand_action(text) or laugh_request(text) or requested(text):
        return True
    if conversational_gesture(text,'Your heart means a lot.'):
        return True
    if greeting(text) or greeting(re.sub(r'^\s*say\s+','',text,flags=re.I)) or identity_question(text) or fiction_requested(text):
        return True
    if re.match(r'\s*(?:write|generate|create)\b.{0,60}\b(?:code|script|poem|song|story)\b', text, re.I):
        return True
    return bool(re.fullmatch(
        r"\s*(?:how (?:are|r) (?:you|u)|how['’]s it going|are you ready|thanks?(?: you)?|"
        r"good (?:morning|evening|night)|I (?:love|like|miss) (?:you|u)(?: btw)?|"
        r"(?:do|would) (?:you|u) like my .{1,100}|what do you think (?:of|about) my .{1,100}|"
        r"(?:please |can you )?(?:laugh(?: harder)?|dance|stop danc(?:e|ing)|wave|sing(?: .{1,100})?|show (?:your |both |left |right )?hands?)|"
        r"(?:a+p+|tum) (?:kaise|kese) (?:ho|hain)|(?:आप|तुम) कैसे (?:हैं|हो)|"
        r"a+p+ko hindi ati hai|a+p+ ladke ho (?:kya|ya) ladki)[?.! ]*", text, re.I))


def medium_conversation(text):
    """Positive social intents only; mixed factual requests stay on retrieval."""
    topic_text=re.sub(r'\b(?:today|yesterday|tomorrow)\b','',text,flags=re.I)
    if high_risk_topic(topic_text) or re.search(r'\b(?:how (?:much|many|fast)|when|where|who is|what is|what are|verify|prove|search|look up|specification|capital|population)\b',text,re.I):
        return False
    if conversational_request(text):return True
    # User self-reports and preferences can be acknowledged without asserting
    # them as independently verified world facts. Factual/mixed questions above
    # still stay on the evidence path.
    if re.fullmatch(r"\s*(?:i(?:['’]m| am)|i (?:feel|felt|like|love|miss|enjoy|hate|want|need)|my day (?:was|is))\s+[^?\n]{1,350}[.! ]*",text,re.I):
        return True
    return bool(re.fullmatch(
        r"\s*(?:(?:i(?:['’]m| am)|i feel|i am feeling)\s+(?:also |very |really |a bit |so |not )*(?:great|good|fine|okay|ok|happy|sad|tired|bored|lonely|excited|upset|angry|stressed|better|well)(?: today| now| too)?|"
        r"(?:my day (?:was|is)|i had a) (?:great|good|bad|long|rough|busy|nice)(?: day)?|"
        r"(?:that(?:['’]s| is)|sounds) (?:great|good|nice|fun|cool|bad|sad)|"
        r"(?:yes|yeah|yep|no|nope|okay|ok|sure|nice|great|cool|same here|me too|and you|what about you)|"
        r"(?:let['’]?s (?:chat|talk)|talk to me|keep me company|tell me a joke|what should we talk about)|"
        r"(?:can|could|will) you (?:chat|talk|keep me company|cheer me up)|"
        r"(?:how (?:was|is) your day|what do you (?:like|enjoy)|do (?:you|u) like (?:me|talking to me)|can we (?:chat|talk)|"
        r"tell me more|what do you mean|why|really|are you sure)|"
        r"(?:मैं|main) (?:भी |bhi )?(?:ठीक|अच्छा|खुश|उदास|थका|theek|thik|khush|udaas|badiya)(?: हूँ| हूं| hoon| hu)?)[?.! ]*",text,re.I))


def response_answer(evidence, minimum, text, settings, model=None):
    """Medium permits social language, never an unsupported factual fallback."""
    if settings.get('response_restriction_level') == 'off':
        # Prefer a real tool result when present; missing evidence no longer
        # forces a refusal or limits which conversational intents can generate.
        return evidence if isinstance(evidence,Evidence) and evidence.answerable(minimum) else None
    if (settings.get('response_restriction_level','medium') != 'strict'
            and medium_conversation(text)
            and (evidence is None or (isinstance(evidence,Evidence) and evidence.classification=='Unknown' and evidence.method=='no sufficient evidence'))):
        reply=None
        if model is not None:
            try:reply=model.conversation_reply(text,cohost=bool(settings.get('_cohost')))
            except Exception:pass
        if not isinstance(reply,str) or not reply.strip() or not generated_reply_allowed(reply,text):
            reply="Tell me a little more."
        return Evidence(reply,'Inference',0,method='nonfactual conversation')
    return strict_answer(evidence,minimum)


def high_risk_topic(text):
    return bool(re.search(r'\b(?:RTX|GTX|Radeon|Ryzen|Intel|hardware|software|version|release|price|cost|specs|specifications|VRAM|GHz|DDR\d|current|latest|today|yesterday|tomorrow|president|prime minister|weather|news|forecast|headlines|stock|medical|medicine|legal)\b|\d+\s*GB\b', text, re.I))


def _tool_failed(text):
    return bool(re.search(r"could(?:n['’]t| not)|cannot|can['’]t|unable|unavailable|not available|not found|not have a verified|should not guess|enable .{0,70}first|which city|which .{0,50}would you|please (?:ask|share)|outside this live|no recent|no matching|failed|error", text, re.I))


def _sources(text, method):
    urls = list(dict.fromkeys(url.rstrip('.,)') for url in re.findall(r'https://[^\s<>]+', text)))
    return [{'title': 'Retrieved source', 'url': url, 'kind': 'external'} for url in urls] or ([{'title': method, 'url': LOCAL_SOURCES[method], 'kind': 'tool'}] if method in LOCAL_SOURCES else [])


def tool_evidence(text, method):
    if _tool_failed(text):
        return Evidence(UNKNOWN, method=method)
    return Evidence(text, 'Verified', 1.0, _sources(text, method), method)


PRIVATE_MARKERS = re.compile(
    r'\b(?:my|me|your|password|secret|token|API key|email|clipboard|file|folder|address|bank)\b'
    r'|[\w.+-]+@[\w.-]+|\bsk-[\w-]+', re.I)
SENSITIVE_TOPICS = re.compile(
    r'\b(?:medical|medicine|diagnosis|symptom|dosage|prescription|legal advice|lawsuit|immigration'
    r'|tax filing|investment advice|suicide|self-harm)\b', re.I)
CREATIVE_TASKS = re.compile(
    r'\b(?:translate|write a|compose|imagine|story|joke|poem|song|roleplay|fiction|pretend|opinion'
    r'|should i|what should)\b', re.I)
FACT_SEEKING = re.compile(
    r'[?？]|\b(?:what|who|when|where|which|why|how (?:much|many|long|old|is|are|does)|is|are|does|do'
    r'|price|cost|specs?|specifications|vram|memory|release|latest|current|today|news|weather|version|walkthrough|guide|boss|quest|mission)\b'
    r'|\b(?:क्या|कितना|कितने|कब|कौन|कहाँ|कैसा)\b', re.I)


def _search_query(text, name=''):
    query = re.sub(r'^(?:hey|hi|hello|okay|ok|so|now|please)[,!]?\s+', '', text.strip(), flags=re.I)
    if name:
        query = re.sub(r'^(?:hey |ok )*' + re.escape(name) + r'[,!]?\s*', '', query, flags=re.I)
    query = re.sub(r'^(?:can you|could you|do you know|tell me|i want to know)\s+(?:please\s+)?'
                   r'(?:me|that|this)?\s*', '', query, flags=re.I)
    return re.sub(r'\s+', ' ', query).strip(' .!?')[:160]


def web_context(text, credentials=None, name=''):
    """Web evidence for the generation path, or an unverified-answer warning.

    Returns '' when the question must never leave the device; social, personal,
    creative and high-stakes questions are refused before any network call.
    """
    if not isinstance(text, str) or not text.strip():
        return ''
    if PRIVATE_MARKERS.search(text) or SENSITIVE_TOPICS.search(text) or CREATIVE_TASKS.search(text):
        return ''
    if conversational_request(text) or medium_conversation(text) or not FACT_SEEKING.search(text):
        return ''
    query = _search_query(text, name)
    if len(query) < 8:
        return ''
    import agent_web
    try:
        found = agent_web.lookup(query, credentials)
    except (agent_web.requests.RequestException, ValueError):
        found = None
    if not found:
        return ('No usable web result was found for this question. Answer from what you know, but '
                'state clearly in one short line that you could not verify it. Never invent an exact '
                'specification, price, version or date.')
    excerpt = found['text'][:2500]
    return (f"Web lookup just now ({found['provider']}). From {found['title']} - {found['url']}:\n"
            f"{excerpt}\nAnswer using only these facts and name the source briefly. Do not add any "
            'number or detail that is missing above; if it does not answer the question, say what is '
            'missing instead of guessing.')


def web_retrieve(text):
    """General reference retrieval only. Current/product/high-stakes claims need dedicated sources."""
    if high_risk_topic(text):
        return None
    # Only explicit public-reference questions may leave the device. Do not
    # turn private PC/file/memory questions or arbitrary dialogue into searches.
    if not re.match(r'^\s*(?:what (?:is|are)|who (?:is|was)|tell me about|explain|define)\s+',text,re.I):
        return None
    if re.search(r'\b(?:my|me|your|password|secret|token|API key|email|clipboard|file|folder|address|bank)\b|[\w.+-]+@[\w.-]+|\bsk-[\w-]+',text,re.I):
        return None
    query = re.sub(r'^(?:what (?:is|are)|who (?:is|was)|tell me about|explain|define)\s+', '', text.strip(), flags=re.I).strip(' ?.')
    if not query or len(query) > 160:
        return None
    terms = set(re.findall(r'[a-z]{3,}', query.casefold())) - {'the', 'and', 'for', 'about', 'does', 'with', 'that', 'this', 'you', 'your', 'what', 'how', 'why'}
    if not terms:
        return None
    try:
        response = requests.get('https://en.wikipedia.org/w/api.php', params={
            'action': 'query', 'generator': 'search', 'gsrsearch': query, 'gsrlimit': 1,
            'prop': 'extracts', 'exintro': 1, 'explaintext': 1, 'exsentences': 3, 'format': 'json'},
            headers={'User-Agent': 'Sakura/1.0 (user-requested reference retrieval)'}, timeout=(2, 4), allow_redirects=False)
        response.raise_for_status()
        if len(response.content) > 300_000:
            return None
        pages = response.json().get('query', {}).get('pages', {})
        if len(pages) != 1:
            return None
        page = next(iter(pages.values()))
        title, extract, page_id = page.get('title', ''), page.get('extract', ''), page.get('pageid')
        if not isinstance(title, str) or not isinstance(extract, str) or type(page_id) is not int or page_id <= 0:
            return None
        title_terms = set(re.findall(r'[a-z]{3,}', title.casefold()))
        if not terms.issubset(title_terms) or not extract or len(extract) > 4000 or 'may refer to' in extract.lower():
            return None
        url = f'https://en.wikipedia.org/?curid={page_id}'
        # Return the extract verbatim. A model cannot add plausible extra details.
        return Evidence(extract + '\nSource: ' + url, 'Verified', .9,
                        [{'title': 'Wikipedia: ' + title, 'url': url, 'kind': 'external'}], 'reference retrieval')
    except (requests.RequestException, ValueError, TypeError, AttributeError, KeyError):
        return None


def retrieve(text, settings, memory=(), allow_actions=True):
    from assistant_commands import run_command
    from factual_grounding import gpu_memory_lookup
    from current_information import lookup_with_context
    if allow_actions:
        # Only the review flow may run a PC action. An action that needs approval must
        # never be executed here as a side effect of gathering evidence, so the evidence
        # stage drops it and leaves the decision to the caller's review prompt.
        try:
            from command_approval import required
            allow_actions = not required(text, settings)
        except ImportError:
            pass
    reply = run_command(text, settings.get('computer_control_enabled', False), settings.get('assistant_name', 'Sakura')) if allow_actions else None
    if isinstance(reply, str) and reply:
        return tool_evidence(reply, 'PC command/status/file/time tool')
    from persona_grounding import identity_question, safe_smalltalk
    from config import voice_language
    name=settings.get('vtuber_name','Sakura') if settings.get('_cohost') else settings.get('assistant_name','Sakura')
    language=settings.get('reply_language') or voice_language(settings.get('selected_voice','kokoro_af_heart'))
    social=safe_smalltalk(text,name,language,bool(settings.get('_cohost')))
    if social:
        method='application configuration' if identity_question(text) else 'built-in conversation'
        return Evidence(social,'Verified',1,
                        [{'title':'Saved assistant identity' if identity_question(text) else 'Authored conversational reply (not a retrieved world fact)',
                          'url':LOCAL_SOURCES[method],'kind':'tool'}],method)
    reply = gpu_memory_lookup(text)
    if reply:
        return tool_evidence(reply, 'manufacturer specification lookup')
    reply, pending = lookup_with_context(text, settings.get('_pending_weather'), settings.get('news_area', ''))
    if reply:
        result=tool_evidence(reply, 'weather/news retrieval')
        result.pending_weather=pending
        return result
    if confirmed_user_fact(text):
        return Evidence('Noted: ' + text, 'User-provided', 1.0, [{'title': 'Your statement', 'kind': 'user'}], 'explicit user statement')
    if re.search(r'\b(?:my|I told you|did I (?:say|tell)|what do you know about me)\b', text, re.I):
        records = [r for r in memory if r.get('classification') == 'User-provided']
        keys = set(re.findall(r'\b(?:name|city|state|country|PC|GPU|CPU|RAM|birthday|pronouns)\b', text, re.I))
        records = [r for r in records if any(re.search(r'\b'+re.escape(key)+r'\b', r['text'], re.I) for key in keys)]
        if records:
            return Evidence('You told me: ' + records[-1]['text'].removeprefix('Noted: '), 'Verified', 1.0,
                            [{'title':'Your recorded statement (not independently verified)', 'url':LOCAL_SOURCES['confirmed user memory'], 'kind':'tool'}], 'confirmed user memory')
    if conversational_request(text) or medium_conversation(text):
        return None
    return web_retrieve(text) or Evidence(UNKNOWN, method='no sufficient evidence')


def generated_reply_allowed(reply, question):
    """Unverified generated statements may express tone/fiction, never supply factual answers."""
    from persona_grounding import fiction_requested
    from factual_grounding import unsupported_tool_claim
    if unsupported_tool_claim(reply, question):
        return False
    if fiction_requested(question):
        return True
    if not (conversational_request(question) or medium_conversation(question)):
        return False
    if re.search(r"\bI (?:won|earned|graduated|worked|met|visited|bought|own|have a (?:friend|pet|family)|remember (?:when|that we))\b",reply,re.I):
        return False
    # Concrete external assertions in an otherwise social reply still require evidence.
    if re.search(r'https?://|\b\d+(?:\.\d+)?\s*(?:GB|MB|TB|GHz|MHz|percent|%|dollars|rupees)|\b(?:RTX|GTX|Radeon|Ryzen|Intel|according to|research shows|studies show|capital of|was born|released in|costs? \d)\b', reply, re.I):
        return False
    # Keep ordinary AI dialogue warm; avoid third-person factual claims/lore.
    if re.search(r'\b(?:he|she|they|it|the [\w -]{1,40}) (?:is|are|was|were|has|have)\b', reply, re.I):
        return False
    return True
