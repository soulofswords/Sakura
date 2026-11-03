"""Executed using each extracted release's own Python and dependency payload."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import httpx

edition=sys.argv[1]
os.environ['SAKURA_DESKTOP']='1'
os.environ['SAKURA_START_MODE']='vtuber' if edition=='vtuber' else 'gemini'
import app
from product import EDITION, DISPLAY_NAME, LAUNCHER_NAME
assert EDITION==edition
root=Path(__file__).resolve().parent
assert list(root.glob('sakura_core*.pyd')), 'Compiled application core missing'
assert not (root/'app.py').exists() and not (root/'llm.py').exists(), 'Original application sources shipped'
assert not list((root/'__pycache__').glob('app.*.pyc')), 'Original application bytecode shipped'
for line in (root/'installed-files.tsv').read_text(encoding='utf-8').splitlines():
 digest,name=line.split('\t');assert hashlib.sha256((root.parent/name).read_bytes()).hexdigest()==digest,name
assert subprocess.run([str(root.parent/LAUNCHER_NAME),'--check']).returncode==0

# Verify newly added modules and command behavior in the compiled release,
# rather than accidentally relying on development sources.
from hindi_conversation import common_reply
assert common_reply('appko hindi ati hai','Hindi')=='हाँ, हम हिंदी में बात कर सकते हैं।'
from assistant_reminders import Reminders
import tempfile
with tempfile.TemporaryDirectory() as folder:
    store=Reminders(Path(folder)/'timers.json')
    reply=store.command('start a timer for 2 mins')
    assert '2 min 0 sec' in reply
    assert store.list()[0]['id'] not in reply

async def check():
 async with app.lifespan(app.app):
  if edition=='vtuber':assert app.llm is None and 'llm' not in sys.modules
  else:assert app.llm is not None and not app.app.state.tracking_only
  import gui_server
  origin=f'http://127.0.0.1:{gui_server.port}'
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.app),base_url=origin,headers={'Origin':origin}) as client:
   for path in ['/','/api/models','/api/voices','/api/settings','/api/identity','/api/version']:
    response=await client.get(path);assert response.status_code==200,(path,response.text)
   assert (await client.get('/api/version')).json()['version']=='2.0'
   assert (await client.get('/static/js/pmx-stage.js')).status_code==200
   assert (await client.get('/api/scenery/assets?kind=stage')).status_code==200
   settings=(await client.get('/api/settings')).json();assert settings['product_edition']==edition
   voices=(await client.get('/api/voices')).json()['presets']
   assert sum(p.get('backend')=='kokoro' for p in voices)==10
   assert sum(p.get('backend')=='kokoro' and p.get('language')=='English' for p in voices)==6
   from config import TTS_BACKEND
   assert TTS_BACKEND=='kokoro'
   from kokoro_speech import ASSETS, ASSETS_DIR, _hash
   for name,(size,digest) in ASSETS.items():
    asset=ASSETS_DIR/name;assert asset.stat().st_size==size and _hash(asset)==digest
   assert settings['vtuber_tracking_only']==(edition=='vtuber')
   model_list=(await client.get('/api/models')).json();assert model_list=={'models':[],'live2d_models':[]}
   if edition=='vtuber':
    assert (await client.post('/api/chat',json={'text':'hello'})).status_code==409
    assert (await client.post('/api/tracking/mode',json={'enabled':False})).status_code==409
    assert app.llm is None
   else:
    assert (await client.get('/api/companion/speakers')).status_code==200
    assert (await client.get('/static/js/speaker-enrolment.js')).status_code==200
    assert (await client.post('/api/companion/speakers/install',json={})).status_code==400
    assert (await client.post('/api/companion/speakers/rename',json={'name':'missing','new_name':''})).status_code==400
    from agent_runtime import runtime
    from agent_starter_skills import PACK
    assert set(PACK).issubset({skill['name'] for skill in runtime.skills.list()}),'Starter skills missing from clean installation'
    response=await client.post('/api/tracking/mode',json={'enabled':True});assert response.status_code==200,response.text
    assert app.app.state.tracking_only
    assert (await client.get('/api/companion/speakers')).status_code==409
    response=await client.post('/api/tracking/mode',json={'enabled':False});assert response.status_code==200,response.text
    assert not app.app.state.tracking_only
 print('PASS:',DISPLAY_NAME,'installed payload integrity, imports, launcher and isolated backend; empty model libraries')
asyncio.run(check())
