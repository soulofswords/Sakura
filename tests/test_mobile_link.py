import time
import unittest
import tempfile
from pathlib import Path
import httpx
from mobile_link import MobileLink

class MobileLinkTests(unittest.IsolatedAsyncioTestCase):
    async def test_pairing_does_not_start_tracking_and_camera_is_separate(self):
        import base64
        await self.pair();self.assertEqual(self.link.poll({'edition':'companion'})['commands'],[])
        response=await self.client.post('/command',json={'type':'camera-start'})
        self.assertEqual(response.status_code,200)
        image=base64.b64encode(b'\xff\xd8\xfftest').decode()
        response=await self.client.post('/camera',json={'image':image});self.assertEqual(response.status_code,200)
        data=self.link.poll({'edition':'companion'})
        self.assertEqual(data['commands'],[{'type':'camera-start'}]);self.assertIsNone(data['frame'])
        self.assertEqual(data['camera']['image'],image)
        self.assertIsNone(self.link.poll({})['camera'])
        self.assertEqual((await self.client.post('/camera',json={'image':'bad'})).status_code,400)
        self.link.state={'edition':'vtuber'}
        self.assertEqual((await self.client.post('/camera',json={'image':image})).status_code,409)
    async def asyncSetUp(self):
        self.directory=tempfile.TemporaryDirectory();self.store=Path(self.directory.name)/'devices.json'
        self.link=MobileLink(self.store);self.link.enabled=True;self.link.code='123456';self.link.code_expires=time.time()+300
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=self.link.api,client=('192.168.1.22',1000)),base_url='http://pc')
    async def asyncTearDown(self):await self.client.aclose();self.directory.cleanup()
    async def pair(self):
        response=await self.client.post('/pair',json={'code':'123456'});self.assertEqual(response.status_code,200)
        self.client.headers['Authorization']='Bearer '+response.json()['token']
    async def test_requires_pairing_and_revokes_on_stop(self):
        self.assertEqual((await self.client.get('/state')).status_code,401)
        await self.pair();self.assertEqual((await self.client.get('/state')).status_code,200)
        self.link.stop();self.assertEqual((await self.client.get('/state')).status_code,403)
    async def test_commands_are_limited_to_current_expressions(self):
        await self.pair();self.link.poll({'expressions':['Smile'],'edition':'vtuber'})
        self.assertEqual((await self.client.post('/command',json={'type':'expression','name':'Smile'})).status_code,200)
        self.assertEqual((await self.client.post('/command',json={'type':'expression','name':'Missing'})).status_code,400)
        self.assertEqual((await self.client.post('/command',json={'type':'run-shell'})).status_code,400)
        self.assertEqual(self.link.poll({})['commands'],[{'type':'expression','name':'Smile'}])
    async def test_latest_frame_transfer_and_validation(self):
        await self.pair()
        for i in range(3):
            response=await self.client.post('/frame',json={'face':{'matrix':[1.0]*16,'landmarks':[{'x':i,'y':0,'z':0}],'blendshapes':[]},'headPoseFiltered':True})
            self.assertEqual(response.status_code,200)
        latest=self.link.poll({});self.assertEqual(latest['frame']['face']['landmarks'][0]['x'],2)
        self.assertTrue(latest['frame']['headPoseFiltered'],'Already conditioned phone head samples bypass duplicate PC filtering')
        self.assertIsNone(self.link.poll({})['frame'])
        self.assertEqual((await self.client.post('/frame',json={'face':{'matrix':[1]*15}})).status_code,400)
    async def test_pairing_rate_limit_and_expiry(self):
        for _ in range(5):self.assertEqual((await self.client.post('/pair',json={'code':'wrong'})).status_code,401)
        self.assertEqual((await self.client.post('/pair',json={'code':'123456'})).status_code,429)
    async def test_standalone_vtuber_cannot_chat_or_set_key(self):
        await self.pair();self.link.state={'edition':'vtuber'}
        self.assertEqual((await self.client.post('/chat',json={'text':'hello'})).status_code,409)
        self.assertEqual((await self.client.post('/gemini',json={'key':'test'})).status_code,409)
    async def test_public_network_cannot_connect(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.link.api,client=('8.8.8.8',1000)),base_url='http://pc') as public:
            self.assertEqual((await public.post('/pair',json={'code':'123456'})).status_code,403)

    async def test_device_remembered_after_restart_and_forget_revokes(self):
        response=await self.client.post('/pair',json={'code':'123456','device_id':'test-phone','device_name':'Pixel test'})
        token=response.json()['token'];self.assertNotIn(token,self.store.read_text())
        restarted=MobileLink(self.store);restarted.enabled=True
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=restarted.api,client=('192.168.1.22',1000)),base_url='http://pc',headers={'Authorization':'Bearer '+token}) as client:
            self.assertEqual((await client.get('/state')).status_code,200)
            self.assertEqual(restarted.info()['devices'][0]['name'],'Pixel test')
            restarted.stop();self.assertEqual((await client.get('/state')).status_code,403)
            restarted.enabled=True;self.assertEqual((await client.get('/state')).status_code,200)
            restarted.forget_device('test-phone');self.assertEqual((await client.get('/state')).status_code,401)
            self.assertEqual(MobileLink(self.store).devices,{})

    async def test_new_code_retains_known_devices(self):
        await self.pair();before=self.client.headers['Authorization']
        self.link.new_pairing_code();self.assertEqual((await self.client.get('/state')).status_code,200)
        self.assertEqual(len(self.link.devices),1);self.assertEqual(self.client.headers['Authorization'],before)

