import socket
import ssl
import tempfile
import time
import unittest
import os
import subprocess
from pathlib import Path
import httpx
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import ec
from mobile_link import MobileLink
from mobile_tls import ensure_identity,fingerprint


class IdentityFileTests(unittest.TestCase):
    def test_private_key_permissions_are_repaired_without_changing_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            first=ensure_identity(directory)
            key=Path(first['key']);original=key.read_bytes()
            if os.name=='nt':
                subprocess.run(['icacls',str(key),'/grant','*S-1-5-32-545:R'],check=True,capture_output=True)
            else:os.chmod(key,0o644)
            second=ensure_identity(directory)
            self.assertEqual(first,second)
            self.assertEqual(original,key.read_bytes())
            if os.name=='nt':
                acl=subprocess.run(['icacls',str(key)],check=True,capture_output=True,text=True).stdout
                self.assertNotIn('BUILTIN\\Users:',acl)
                self.assertNotIn('Authenticated Users:',acl)
                self.assertNotIn('(I)',acl)
            else:self.assertEqual(key.stat().st_mode&0o777,0o600)

    def test_identity_is_created_once_and_replaced_when_the_key_is_lost(self):
        with tempfile.TemporaryDirectory() as directory:
            first=ensure_identity(directory)
            self.assertRegex(first['fingerprint'],r'^[0-9a-f]{64}$')
            self.assertEqual(ensure_identity(directory),first)
            certificate=x509.load_pem_x509_certificate(Path(first['cert']).read_bytes())
            self.assertIsInstance(certificate.public_key(),ec.EllipticCurvePublicKey)
            self.assertEqual(certificate.public_key().curve.name,'secp256r1')
            self.assertEqual(fingerprint(certificate),first['fingerprint'])
            Path(first['key']).write_bytes(Path(first['key']).read_bytes()[:-8])
            replacement=ensure_identity(directory)
            self.assertNotEqual(replacement['fingerprint'],first['fingerprint'])

    def test_link_identity_survives_a_restart_of_the_same_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            link=MobileLink(Path(directory)/'devices.json')
            self.assertEqual(MobileLink(Path(directory)/'devices.json').tls,link.tls)


class LiveTlsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.link=MobileLink(Path(self.temp.name)/'devices.json')
        self.link.lan_addresses=lambda:[]
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',0));self.port=probe.getsockname()[1]
        self.link.port=self.port
        self.link.start(8766)
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            try:
                with socket.create_connection(('127.0.0.1',self.port),timeout=.25):break
            except OSError:time.sleep(.05)
        else:self.fail('The TLS phone-link server did not start.')
        context=ssl.create_default_context(cafile=self.link.tls['cert'])
        self.client=httpx.AsyncClient(base_url=f'https://127.0.0.1:{self.port}',verify=context,timeout=10)

    async def asyncTearDown(self):
        await self.client.aclose();self.link.stop()
        if self.link.thread:self.link.thread.join(timeout=3)
        self.temp.cleanup()

    async def test_encrypted_pairing_and_authenticated_state(self):
        response=await self.client.post('/pair',json={'code':self.link.code,'device_id':'tls-phone','device_name':'TLS test'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['fingerprint'],self.link.tls['fingerprint'])
        self.client.headers['Authorization']='Bearer '+response.json()['token']
        state=await self.client.get('/state')
        self.assertEqual(state.status_code,200);self.assertEqual(state.json()['pc_id'],self.link.pc_id)
        plain=httpx.AsyncClient(base_url=f'http://127.0.0.1:{self.port}',timeout=3)
        try:await plain.get('/state')
        except httpx.HTTPError:pass
        else:self.fail('The phone link answered a cleartext request.')
        finally:await plain.aclose()
