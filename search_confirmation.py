"""One-shot, session-only consent to Google the exact unanswered question."""
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from threading import Lock
from urllib.parse import urlencode


def open_google_in_chrome(question):
    relative='Google/Chrome/Application/chrome.exe'
    candidates=[Path(os.environ.get(key,''))/relative for key in ('PROGRAMFILES','PROGRAMFILES(X86)','LOCALAPPDATA') if os.environ.get(key)]
    executable=next((str(path) for path in candidates if path.is_file()),None)
    executable=executable or shutil.which('chrome') or shutil.which('google-chrome')
    if not executable:return "I couldn't find Google Chrome on this PC. Please install it, then ask me to search again."
    url='https://www.google.com/search?'+urlencode({'q':question})
    try:
        subprocess.Popen([executable,'--new-tab',url],shell=False)
        return 'Opening Google in Chrome to search your question.'
    except OSError:
        return "I couldn't open Chrome. Please try opening it manually."


class SearchConsent:
    def __init__(self,on_approved=None):
        self._lock=Lock()
        self.pending=None
        self.on_approved=on_approved

    def clear(self):
        with self._lock:self.pending=None

    def offer(self,question,reply,language='English'):
        if not isinstance(reply,str) or not re.search(
                r"(?:i (?:do not|don't|don’t) (?:know|have (?:this |that |the |a |any )?(?:verified |reliable |current )*(?:information|info|memory specification|specification|answer))|"
                r"i (?:could not|couldn't|couldn’t|cannot|can't|can’t) verify|i['’]m not sure)",reply,re.I):
            return reply
        if not isinstance(question,str) or not question.strip() or len(question)>2000:return reply
        with self._lock:self.pending=(question.strip(),time.monotonic())
        return {'Hindi':'मेरे पास इसकी जानकारी नहीं है। क्या मैं इसे Google पर खोजूँ?',
                'Hinglish':'Mere paas iski information nahi hai. Kya main ise Google par search karoon?'}.get(
                    language,"I don't have this information. May I Google it?")

    def respond(self,text):
        value=re.sub(r'\bu\b','you',text.casefold())
        value=re.sub(r'\s+',' ',value.replace(',',' ')).strip(' .!?')
        with self._lock:
            pending=self.pending
            self.pending=None
        if not pending or time.monotonic()-pending[1]>120:return None
        if re.fullmatch(r"(?:yes(?: (?:please|you can|go ahead|do it|search(?: (?:it|for it))?))?|yeah(?: go ahead)?|yep|sure|go ahead|you can|please do|haan|han|हाँ|हां|हाँ खोजो)",value):
            reply=open_google_in_chrome(pending[0])
            if self.on_approved and reply.startswith('Opening Google in Chrome'):
                try:reply+=self.on_approved(pending[0]) or ''
                except Exception:reply+=' I could not save a verified answer yet.'
            return reply
        if re.fullmatch(r"(?:no(?: thanks| thank you)?|nope|not now|don't|do not|cancel|nahi|नहीं)",value):
            return "Okay, I won't open Google."
        # A new message cancels the old offer; a later bare yes can't approve it.
        return None


def _learn(question):
    from learned_answers import learn_approved_search
    return learn_approved_search(question)


search_consent=SearchConsent(on_approved=_learn)
