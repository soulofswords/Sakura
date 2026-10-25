import hashlib
import hmac
import json
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from mobile_link import MobileLink

class IdentityTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.temp=tempfile.TemporaryDirectory();self.link=MobileLink(Path(self.temp.name)/'devices.json');self.link.enabled=True
  self.link.lan_addresses=lambda:['192.168.1.3'];self.secret='test-paired-secret';self.link.devices['phone']={'token_hash':hashlib.sha256(self.secret.encode()).hexdigest()}
  self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=self.link.api,client=('192.168.1.8',1234)),base_url='https://192.168.1.3:8771')
 async def asyncTearDown(self):
  await self.client.aclose();self.link.stop();self.temp.cleanup()
 async def test_proves_secret_without_receiving_bearer(self):
  nonce='ab'*32;r=await self.client.post('/identity-proof',json={'endpoint':'https://192.168.1.3:8771','device_id':'phone','nonce':nonce})
  self.assertEqual(r.status_code,200);body=r.json()
  expected=hmac.new(hashlib.sha256(self.secret.encode()).digest(),(self.link.pc_id+'\nhttps://192.168.1.3:8771\n'+nonce).encode(),hashlib.sha256).hexdigest()
  self.assertEqual(body,{'pc_id':self.link.pc_id,'endpoint':'https://192.168.1.3:8771','nonce':nonce,'proof':expected})
  self.assertNotIn(self.secret,r.text);self.assertNotIn(self.link.devices['phone']['token_hash'],r.text)
  other=(await self.client.post('/identity-proof',json={'endpoint':'https://192.168.1.3:8771','device_id':'phone','nonce':'cd'*32})).json()
  self.assertNotEqual(body['proof'],other['proof'])
 async def test_unknown_phone_bad_nonce_disabled_and_rate_limit(self):
  self.assertEqual((await self.client.post('/identity-proof',json={'endpoint':'https://192.168.1.3:8771','device_id':'phone','nonce':'bad'})).status_code,400)
  self.assertEqual((await self.client.post('/identity-proof',json={'endpoint':'https://192.168.1.3:8771','device_id':'other','nonce':'ab'*32})).status_code,401)
  self.link.enabled=False
  self.assertEqual((await self.client.post('/identity-proof',json={'endpoint':'https://192.168.1.3:8771','device_id':'phone','nonce':'ab'*32})).status_code,403)
  self.link.enabled=True;self.link.identity_attempts.clear()
  for _ in range(30):self.assertEqual((await self.client.post('/identity-proof',json={'endpoint':'https://192.168.1.3:8771','device_id':'phone','nonce':'ab'*32})).status_code,200)
  self.assertEqual((await self.client.post('/identity-proof',json={'endpoint':'https://192.168.1.3:8771','device_id':'phone','nonce':'ab'*32})).status_code,429)
 async def test_relay_cannot_get_proof_for_another_endpoint(self):
  payload={'endpoint':'https://192.168.1.99:8771','device_id':'phone','nonce':'ab'*32}
  self.assertEqual((await self.client.post('/identity-proof',json=payload)).status_code,400)
  self.assertEqual((await self.client.post('/identity-proof',json=payload,headers={'host':'192.168.1.99:8771'})).status_code,400)

class BeaconRecoveryTests(unittest.TestCase):
 def test_rebinds_new_address_and_recovers_when_network_returns(self):
  with tempfile.TemporaryDirectory() as temp:
   link=MobileLink(Path(temp)/'devices.json');link.enabled=True
   with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as reserved:
    reserved.bind(('127.0.0.1',0));link.discovery_port=reserved.getsockname()[1]
   addresses=['127.0.0.1']
   def probe(host):
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as client:
     client.settimeout(.8);client.sendto(b'sakura-discover-v1',(host,link.discovery_port));return json.loads(client.recv(2048))
   def wait_bound(host):
    until=time.monotonic()+6
    while time.monotonic()<until:
     try:
      if any(s.getsockname()[0]==host for s in list(link.beacon_sockets)):return
     except OSError:pass
     time.sleep(.05)
    self.fail('Beacon failed to bind '+host)
   with patch.object(link,'lan_addresses',side_effect=lambda:list(addresses)):
    try:
     link.start_beacon();beacon=probe('127.0.0.1');self.assertEqual(beacon['https'],f'https://127.0.0.1:{link.port}')
     self.assertRegex(beacon['fingerprint'],r'^[0-9a-f]{64}$');self.assertNotIn('http',beacon)
     addresses[:]=['127.0.0.2'];wait_bound('127.0.0.2')
     self.assertEqual(probe('127.0.0.2')['id'],link.pc_id)
     addresses.clear();time.sleep(2.3);self.assertTrue(link.beacon_thread.is_alive())
     addresses[:]=['127.0.0.1'];wait_bound('127.0.0.1');self.assertEqual(probe('127.0.0.1')['id'],link.pc_id)
    finally:link.stop()
