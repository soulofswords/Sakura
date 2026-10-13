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
for line in (root/'installed-files.tsv').read_text().splitlines():
 digest,name=line.split('\t');assert hashlib.sha256((root.parent/name).read_bytes()).hexdigest()==digest,name
assert subprocess.run([str(root.parent/LAUNCHER_NAME),'--check']).returncode==0

async def check():
 async with app.lifespan(app.app):
  if edition=='vtuber':assert app.llm is None and 'llm' not in sys.modules
  else:assert app.llm is not None and not app.app.state.tracking_only
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.app),base_url='http://test') as client:
   for path in ['/','/api/models','/api/voices','/api/settings','/api/identity']:
    response=await client.get(path);assert response.status_code==200,(path,response.text)
   settings=(await client.get('/api/settings')).json();assert settings['product_edition']==edition
   assert settings['vtuber_tracking_only']==(edition=='vtuber')
   model_list=(await client.get('/api/models')).json();assert model_list=={'models':[],'live2d_models':[]}
   if edition=='vtuber':
    assert (await client.post('/api/chat',json={'text':'hello'})).status_code==409
    assert (await client.post('/api/tracking/mode',json={'enabled':False})).status_code==409
    assert app.llm is None
   else:
    response=await client.post('/api/tracking/mode',json={'enabled':True});assert response.status_code==200,response.text
    assert app.app.state.tracking_only
    response=await client.post('/api/tracking/mode',json={'enabled':False});assert response.status_code==200,response.text
    assert not app.app.state.tracking_only
 print('PASS:',DISPLAY_NAME,'installed payload integrity, imports, launcher and isolated backend; empty model libraries')
asyncio.run(check())
