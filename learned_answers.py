"""Persistent, source-backed answers learned only after an approved search."""
import json
import re
import time
from pathlib import Path
from threading import RLock

from config import BASE_DIR
from response_evidence import Evidence, retrieve, tool_evidence


def key(question):
    models=re.findall(r'\bRTX\s*(\d{4})(?:\s*(Ti|SUPER))?\b',question,re.I)
    if (len(models)==1 and re.search(r'\b(?:VRAM|memory|GB)\b|\d+\s*GB',question,re.I)
            and not re.search(r'\b(?:laptop|mobile|gaming|compare|faster|why|price|current|news|my)\b',question,re.I)):
        return 'gpu-memory:rtx'+models[0][0]+models[0][1].casefold()+':desktop'
    return re.sub(r'\s+',' ',question.casefold()).strip(' .!?')


class LearnedAnswers:
    def __init__(self,path):
        self.path=Path(path)
        self.lock=RLock()

    def _read(self):
        try:
            data=json.loads(self.path.read_text(encoding='utf-8'))
            return data if isinstance(data,dict) else {}
        except (OSError,ValueError):return {}

    def recall(self,question):
        with self.lock:record=self._read().get(key(question))
        if not isinstance(record,dict):return None
        try:
            if not 0<=time.time()-record['saved_at']<=30*86400:return None
            evidence=Evidence(**record['evidence'])
            return evidence if evidence.answerable(.9) else None
        except (TypeError,ValueError,KeyError):return None

    def learn(self,question):
        # Time-sensitive information must be refreshed, not remembered as current.
        if re.search(r'\b(?:weather|news|time|today|current|latest|price|stock|forecast|status|usage)\b',question,re.I):return None
        try:evidence=retrieve(question,{},allow_actions=False)
        except Exception:return None
        if not isinstance(evidence,Evidence) or not evidence.answerable(.9):
            from factual_grounding import gpu_memory_lookup
            reply=gpu_memory_lookup(question,allow_discovery=True)
            evidence=tool_evidence(reply,'manufacturer specification lookup') if reply else None
        if not isinstance(evidence,Evidence) or not evidence.answerable(.9):return None
        if evidence.method not in ('manufacturer specification lookup','reference retrieval'):return None
        record={'saved_at':time.time(),'evidence':{
            'text':evidence.text,'classification':evidence.classification,'confidence':evidence.confidence,
            'sources':evidence.sources,'method':evidence.method,'observed_at':evidence.observed_at}}
        with self.lock:
            data=self._read();data[key(question)]=record
            data=dict(sorted(data.items(),key=lambda item:item[1].get('saved_at',0))[-200:])
            self.path.parent.mkdir(parents=True,exist_ok=True)
            temporary=self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
            temporary.replace(self.path)
        return evidence


learned_answers=LearnedAnswers(BASE_DIR/'learned-answers.json')


def learn_approved_search(question,credentials=None):
    evidence=learned_answers.learn(question)
    if evidence:return '\n'+evidence.text+'\nI saved this sourced answer for next time.'
    # Approval applies to the exact question, including subjects beyond the
    # small set of dedicated reference extractors. Read a public source rather
    # than treating a launched browser as a completed lookup.
    import agent_web
    try:found=agent_web.lookup(question,credentials,characters=1800)
    except (agent_web.requests.RequestException,ValueError):found=None
    if found:
        excerpt=' '.join(found['text'].split())[:1200]
        return (f"\nFrom {found['title']}:\n{excerpt}\nSource: {found['url']}\n"
                'This is a source excerpt; I have not saved it as a verified fact.')
    return " I couldn't read a usable source for this question yet, so I haven't saved a guess. You can paste a source or result here and I'll check it."
