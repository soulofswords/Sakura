"""Who this app speaks as: the shipped assistant plus imported character cards, one active.

The shipped personality file stays the base and an active card adds one row on top of it. That is
deliberate: replacing the file would drop the app's speech, language and grounding rules with it,
and a card written by someone else does not get to decide those. The store keeps the sheet, not the
picture it came with, and nothing here is sent anywhere.
"""
import copy, hashlib, json, re, threading, time
from pathlib import Path

from atomic_state import atomic_text, state_lock
from character_cards import persona_block

BUILTIN_ID='sakura'
VERSION=1
MAX_PERSONAS=24
MAX_NAME=80
DEFAULT={'version':VERSION,'active':BUILTIN_ID,'items':[]}


def card_id(name,card):
    """A stable id: the same sheet imported twice stays one persona, a same-named different sheet does not collide."""
    digest=hashlib.sha256(json.dumps([str(name),card],sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest()[:10]
    base=re.sub(r'[^a-z0-9]+','-',str(name or '').casefold()).strip('-')[:32] or 'card'
    return f'{base}-{digest}'


class Personas:
    def __init__(self,personality_dir,state_path):
        self.dir=Path(personality_dir)
        self.path=Path(state_path)
        self.lock=threading.RLock()

    def _read(self):
        try:
            value=json.loads(self.path.read_text(encoding='utf-8'))
            if isinstance(value,dict) and value.get('version')==VERSION:
                items=[row for row in value.get('items',[]) if isinstance(row,dict) and isinstance(row.get('card'),dict) and row.get('id')]
                active=value.get('active') if isinstance(value.get('active'),str) else BUILTIN_ID
                return {'version':VERSION,'active':active,'items':items[:MAX_PERSONAS]}
        except (OSError,ValueError):
            pass
        return copy.deepcopy(DEFAULT)

    def _save(self,data):
        atomic_text(self.path,json.dumps(data,ensure_ascii=False,sort_keys=True))

    def _items(self):
        return self._read()['items']

    def add(self,card,spec=''):
        """Store one parsed sheet and return its id, or raise ValueError if it cannot be kept."""
        if not isinstance(card,dict) or not str(card.get('name') or '').strip():
            raise ValueError('That card has no character name.')
        name=str(card['name']).strip()[:MAX_NAME]
        row={'id':card_id(name,card),'name':name,'kind':'card','spec':str(spec or '')[:32],
             'imported_at':time.time(),'card':copy.deepcopy(card)}
        with self.lock,state_lock(self.path):
            data=self._read()
            items=[item for item in data['items'] if item.get('id')!=row['id']]
            replaced=len(items)!=len(data['items'])
            if not replaced and len(items)>=MAX_PERSONAS:
                raise ValueError(f'This app keeps at most {MAX_PERSONAS} imported cards. Remove one first.')
            items.append(row)
            data['items']=items
            self._save(data)
        return {'id':row['id'],'name':name,'replaced':replaced}

    def remove(self,persona_id):
        """Forget a stored card. The shipped persona is the file that came with the app."""
        if str(persona_id)==BUILTIN_ID:
            raise ValueError('The shipped persona cannot be removed. Switch back to it to clear the role.')
        with self.lock,state_lock(self.path):
            data=self._read()
            kept=[row for row in data['items'] if row.get('id')!=persona_id]
            if len(kept)==len(data['items']):
                raise ValueError('That persona is not in this app.')
            data['items']=kept
            if data['active']==persona_id:
                data['active']=BUILTIN_ID
            self._save(data)
            return {'active':data['active'],'personas':len(data['items'])}

    def activate(self,persona_id):
        """Choose which persona later replies use. Nothing is changed in files or memory."""
        if persona_id is None:
            persona_id=BUILTIN_ID
        if str(persona_id)!=BUILTIN_ID and not any(row['id']==persona_id for row in self._items()):
            raise ValueError('That persona is not in this app.')
        with self.lock,state_lock(self.path):
            data=self._read()
            data['active']=str(persona_id)
            self._save(data)
        return self.status()

    def active_card(self):
        """The sheet behind the active persona, or None when the shipped one is selected."""
        with self.lock:
            data=self._read()
        if data['active']==BUILTIN_ID:
            return None
        return next((row['card'] for row in data['items'] if row['id']==data['active']),None)

    def prompt(self):
        """The extra system row for the active card, or '' when nothing is layered on."""
        card=self.active_card()
        return persona_block(card) if card else ''

    def status(self,builtin_name='Sakura'):
        with self.lock:
            data=self._read()
        known=[row for row in data['items'] if row.get('id')]
        wanted=data['active']
        active=wanted if wanted==BUILTIN_ID or any(row['id']==wanted for row in known) else BUILTIN_ID
        items=[{'id':BUILTIN_ID,'name':str(builtin_name)[:MAX_NAME],'kind':'shipped',
                'active':active==BUILTIN_ID,'fields':[]}]
        for row in known:
            card=row.get('card') or {}
            items.append({'id':row['id'],'name':row.get('name',''),'kind':'card','spec':row.get('spec',''),
                          'active':row['id']==active,
                          'fields':[name for name in ('description','personality','scenario','greetings','example')
                                    if card.get(name)]})
        return {'ok':True,'active':active,'personality_file_exists':(self.dir/'sakura.txt').is_file(),
                'limit':MAX_PERSONAS,'items':items}

    def export(self,persona_id,directory):
        """Write the active sheet back out as a V2 JSON card and say where it went."""
        row=next((item for item in self._items() if item['id']==persona_id),None)
        if row is None:
            raise ValueError('Only imported cards can be exported; the shipped persona is a plain text file.')
        from character_cards import to_v2
        target=Path(directory)
        safe=re.sub(r'[^a-zA-Z0-9._-]+','-',row['name'])[:60] or 'card'
        path=target/f'{safe}-{row["id"][-10:]}.json'
        path.parent.mkdir(parents=True,exist_ok=True)
        text=json.dumps(to_v2(row['card']),ensure_ascii=False,indent=2)
        atomic_text(path,text)
        return {'path':str(path),'bytes':len(text.encode('utf-8')),'spec':'chara_card_v2'}


def default_paths(base_dir,personality_dir):
    """Where the store lives: beside the other personal state, not inside the shipped files."""
    return (Path(personality_dir),Path(base_dir)/'desktop-profile'/'personas.json')
