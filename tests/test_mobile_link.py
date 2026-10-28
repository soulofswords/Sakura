import json
import hashlib
import time
import unittest
import tempfile
from pathlib import Path
import httpx
from mobile_link import MobileLink

class MobileLinkTests(unittest.IsolatedAsyncioTestCase):
    async def test_phone_performance_metrics_are_bounded_and_fresh(self):
        await self.pair()
        payload={'face':{},'hands':[],'trackingMetrics':{'sequence':12,'cameraFps':60,'processedFps':58,'uploadedFps':57,'processingMs':14,'unexpected':'ignored'}}
        self.assertEqual((await self.client.post('/frame',json=payload)).status_code,200)
        metrics=self.link.poll({})['frame']['trackingMetrics']
        self.assertEqual(metrics['sequence'],12);self.assertEqual(metrics['processedFps'],58);self.assertNotIn('unexpected',metrics)
        payload['trackingMetrics']={'cameraFps':9999,'processingMs':-1,'sequence':True}
        self.assertEqual((await self.client.post('/frame',json=payload)).status_code,200)
        metrics=self.link.poll({})['frame']['trackingMetrics']
        self.assertNotIn('cameraFps',metrics);self.assertNotIn('processingMs',metrics);self.assertNotIn('sequence',metrics)
        self.assertIsNone(self.link.poll({})['frame'],'Polling does not manufacture duplicate tracking frames')
    async def test_nvidia_source_is_preserved_between_image_uploads(self):
        from unittest.mock import patch
        await self.pair()
        self.link.state['tracking_face_source']='nvidia_ar'
        payload={'face':{'blendshapes':[{'categoryName':'jawOpen','score':.9}]},'hands':[]}
        with patch('nvidia_ar_tracker.tracker') as tracker:
            tracker.snapshot.return_value={'blendshapes':{'jawOpen':.2}}
            await self.client.post('/frame',json=payload)
            self.assertEqual(self.link.poll({})['frame']['face']['blendshapes'],[{'categoryName':'jawOpen','score':.2}])
            tracker.snapshot.return_value={'blendshapes':{}}
            self.link.state['tracking_face_source']='nvidia_ar'
            await self.client.post('/frame',json=payload)
            self.assertEqual(self.link.poll({})['frame']['face']['blendshapes'],[])
            tracker.submit_frame.assert_not_called()

    async def test_pc_controls_paired_phone_tracking(self):
        await self.pair()
        self.assertTrue(self.link.control_tracking({'action':'start'})['ok'])
        c=(await self.client.get('/state')).json()['tracking_control']
        self.assertEqual(c['action'],'start');self.assertGreater(c['expires'],time.time())
        self.link.control_tracking({'action':'stop'})
        self.assertGreater((await self.client.get('/state')).json()['tracking_control']['id'],c['id'])
        with self.assertRaises(ValueError):self.link.control_tracking({'action':'execute'})

    async def test_phone_hands_and_pose_reach_pc(self):
        await self.pair()
        point={'x':.1,'y':.2,'z':.3,'visibility':.9}
        hand={'side':'Left','confidence':.99,'landmarks':[point]*21,'world':[point]*21}
        pose={'landmarks':[point]*33,'world':[point]*33}
        payload={'face':{'matrix':[1.0]*16},'hands':[hand],'pose':pose}
        self.assertEqual((await self.client.post('/frame',json=payload)).status_code,200)
        frame=self.link.poll({})['frame'];self.assertEqual(frame['hands'],[hand]);self.assertEqual(frame['pose'],pose)
        payload['hands'][0]['landmarks']=[point]*22
        self.assertEqual((await self.client.post('/frame',json=payload)).status_code,400)
        payload['hands']=[];payload['pose']=None
        self.assertEqual((await self.client.post('/frame',json=payload)).status_code,200)
        self.assertEqual(self.link.poll({})['frame']['hands'],[])

    async def test_body_tracking_survives_missing_face(self):
        await self.pair()
        point={'x':.1,'y':.2,'z':.3,'visibility':.9}
        hand={'side':'Left','confidence':.99,'landmarks':[point]*21}
        payload={'face':{'matrix':None,'landmarks':[],'blendshapes':[]},'hands':[hand],'pose':{'landmarks':[point]*33}}
        self.assertEqual((await self.client.post('/frame',json=payload)).status_code,200)
        frame=self.link.poll({})['frame']
        self.assertEqual(frame['hands'],[hand]);self.assertIsNone(frame['face']['matrix'])
        payload['face']['matrix']=[1]*15
        self.assertEqual((await self.client.post('/frame',json=payload)).status_code,400)

    async def test_phone_camera_image_reaches_native_nvidia_without_virtual_webcam(self):
        import base64
        from unittest.mock import patch
        await self.pair()
        self.link.state['tracking_face_source']='nvidia_ar'
        jpeg=b'\xff\xd8\xfftest'
        payload={'face':{'matrix':None},'hands':[], 'cameraFrame':{'image':base64.b64encode(jpeg).decode(),'width':480,'height':360}}
        with patch('nvidia_ar_tracker.tracker') as tracker:
            tracker.snapshot.return_value={'running':True,'blendshapes':{'jawOpen':.3}}
            result=await self.client.post('/frame',json=payload)
            self.assertEqual(result.status_code,200)
            tracker.submit_frame.assert_called_once_with(jpeg,480,360)
            self.assertEqual(self.link.poll({})['frame']['face']['blendshapes'],[{'categoryName':'jawOpen','score':.3}])
        payload['cameraFrame']['width']=99999
        self.assertEqual((await self.client.post('/frame',json=payload)).status_code,400)

    async def test_requested_complete_folder_reaches_authenticated_download(self):
        import zipfile
        import io
        from unittest.mock import patch
        await self.pair()
        request_id=(await self.client.post('/command',json={'type':'request-model'})).json()['request_id']
        folder=Path(self.directory.name)/'selected';(folder/'nested').mkdir(parents=True)
        model=folder/'nested/model.pmx';model.write_bytes(b'pmx')
        (folder/'extra.custom').write_bytes(b'keep this asset too')
        with patch('config.BASE_DIR',Path(self.directory.name)):
            metadata=self.link.stage_selection(model,folder,'pmx',request_id)
        state=(await self.client.get('/state')).json()['transfer_request']
        self.assertEqual(state['status'],'ready');self.assertEqual(state['model'],metadata)
        response=await self.client.get('/model/package/'+metadata['id']);self.assertEqual(response.status_code,200)
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            self.assertEqual(archive.read('nested/model.pmx'),b'pmx')
            self.assertEqual(archive.read('extra.custom'),b'keep this asset too')
        result={'type':'model-result','request_id':request_id,'model_id':metadata['id'],'status':'received'}
        self.assertEqual((await self.client.post('/command',json={**result,'model_id':'wrong'})).status_code,409)
        self.assertEqual((await self.client.post('/command',json=result)).status_code,200)
        self.assertEqual((await self.client.get('/state')).json()['transfer_request']['status'],'received')
    async def test_phone_requests_picker_and_cancel_is_not_tracking(self):
        self.assertEqual((await self.client.post('/command',json={'type':'request-model'})).status_code,401)
        await self.pair()
        response=await self.client.post('/command',json={'type':'request-model'})
        request_id=response.json()['request_id']
        self.assertEqual(self.link.poll({})['commands'],[{'type':'request-model','request_id':request_id}])
        self.assertEqual((await self.client.get('/state')).json()['transfer_request']['status'],'waiting')
        self.assertEqual((await self.client.post('/command',json={'type':'request-model'})).status_code,409)
        self.link.transfer_result(request_id,'preparing')
        self.assertEqual((await self.client.get('/state')).json()['transfer_request']['status'],'preparing')
        await self.client.post('/command',json={'type':'cancel-model','request_id':request_id})
        self.assertEqual((await self.client.get('/state')).json()['transfer_request']['status'],'cancelled')
        self.assertEqual((await self.client.post('/command',json={'type':'request-model'})).status_code,200)
        with self.assertRaises(ValueError):self.link.transfer_result(request_id,'preparing')
    async def test_model_package_requires_pairing_and_exact_active_identifier(self):
        archive=Path(self.directory.name)/'model.zip';archive.write_bytes(b'zip')
        self.link.model_package=archive;self.link.model_transfer={'id':'a'*32,'name':'Test'}
        self.assertEqual((await self.client.get('/model/package/'+'a'*32)).status_code,401)
        await self.pair()
        self.assertEqual((await self.client.get('/state')).json()['model_transfer']['name'],'Test')
        self.link.poll({'edition':'companion'})
        self.assertEqual((await self.client.get('/state')).json()['model_transfer']['name'],'Test')
        self.assertEqual((await self.client.get('/model/package/'+'b'*32)).status_code,404)
        response=await self.client.get('/model/package/'+'a'*32)
        self.assertEqual(response.content,b'zip')
    async def test_pc_tool_route_authentication_and_fixed_forwarding(self):
        self.assertEqual((await self.client.post('/tools',json={'action':'system.status'})).status_code,401)
        await self.pair()
        self.assertEqual((await self.client.post('/tools',json={'action':'shell','code':'anything'})).status_code,400)
        response=httpx.Response(200,json={'ok':True,'reply':'CPU usage is 10 percent.'})
        from unittest.mock import AsyncMock,patch
        with patch('mobile_link.httpx.AsyncClient') as client:
            post=AsyncMock(return_value=response);client.return_value.__aenter__.return_value.post=post
            result=await self.client.post('/tools',json={'action':'system.status','phone':False,'code':'ignored'})
            self.assertEqual(result.status_code,200)
            self.assertEqual(post.call_args.kwargs['json'],{'action':'system.status','phone':True})

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
        self.assertEqual((await self.client.post('/command',json={'type':'companion-tracking-start'})).status_code,200)
        self.assertEqual((await self.client.post('/command',json={'type':'companion-tracking-stop'})).status_code,200)
        self.assertEqual(self.link.poll({'edition':'companion'})['commands'],[
            {'type':'companion-tracking-start'},{'type':'companion-tracking-stop'}])
        self.assertEqual((await self.client.post('/camera',json={'image':'bad'})).status_code,400)
        self.link.state={'edition':'vtuber'}
        self.assertEqual((await self.client.post('/camera',json={'image':image})).status_code,409)
        self.assertEqual((await self.client.post('/command',json={'type':'companion-tracking-start'})).status_code,409)
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
    async def test_a_code_the_phone_will_refuse_is_never_offered_as_live(self):
        self.assertEqual(self.link.info()['code'],'123456')
        self.link.code_expires=time.time()-1
        info=self.link.info();self.assertEqual(info['code'],'');self.assertTrue(info['code_expired'])
        self.assertEqual((await self.client.post('/pair',json={'code':'123456'})).status_code,401)
        self.link.code_expires=time.time()+300
        await self.pair()
        info=self.link.info();self.assertEqual(info['code'],'');self.assertTrue(info['code_expired'])
    async def test_the_panel_can_tell_a_refused_code_from_a_phone_that_never_arrived(self):
        self.assertIsNone(self.link.info()['contact_age'])
        self.assertEqual((await self.client.post('/pair',json={'code':'000000'})).status_code,401)
        refused=self.link.info()
        self.assertEqual((refused['contact_age'],refused['contact_kind'],refused['contact_host']),(None,'',''))
        idle=MobileLink(Path(self.directory.name)/'idle.json');idle.enabled=True
        self.assertIsNone(idle.info()['contact_age'])
        self.assertIsNotNone(idle.discovery_reply(b'sakura-discover-v1','192.168.1.100','192.168.1.103'))
        searching=idle.info()
        self.assertEqual((searching['contact_age'],searching['contact_kind'],searching['contact_host']),(None,'',''))
    async def test_this_pc_answering_its_own_probe_is_not_reported_as_a_phone(self):
        link=MobileLink(self.store);link.enabled=True;link.own_addresses={'192.168.1.100'}
        self.assertIsNotNone(link.discovery_reply(b'sakura-discover-v1','192.168.1.100','192.168.1.100'))
        self.assertIsNone(link.info()['contact_age'])
        self.assertIsNotNone(link.discovery_reply(b'sakura-discover-v1','192.168.1.100','192.168.1.103'))
        arrived=link.info()
        self.assertEqual((arrived['contact_age'],arrived['contact_kind'],arrived['contact_host']),(None,'',''))
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

    async def test_pc_identity_survives_restart_and_ip_change(self):
        identity=self.link.pc_id
        self.assertRegex(identity,r'^[0-9a-f]{32}$')
        self.assertEqual(MobileLink(self.store).pc_id,identity)
        self.assertEqual(self.link.info()['id'],identity)
        self.assertEqual(self.link.info()['name'],self.link.pc_name)
        await self.pair()
        self.assertEqual((await self.client.get('/state')).json()['pc_id'],identity)

    async def test_pairing_returns_the_identity_a_phone_should_remember(self):
        response=await self.client.post('/pair',json={'code':'123456','device_id':'test-phone'})
        self.assertEqual(response.json()['id'],self.link.pc_id)
        self.assertEqual(response.json()['name'],self.link.pc_name)
        self.assertEqual(response.json()['edition'],self.link.edition)
        self.assertEqual(response.json()['fingerprint'],self.link.info()['fingerprint'])

    async def test_pairing_code_is_single_use_and_tokens_expire_after_thirty_days(self):
        response=await self.client.post('/pair',json={'code':'123456','device_id':'test-phone'})
        token=response.json()['token']
        device=self.link.devices['test-phone']
        self.assertAlmostEqual(device['expires_at']-device['last_seen'],30*86400,delta=60)
        self.assertEqual((await self.client.post('/pair',json={'code':'123456'})).status_code,401)
        self.assertTrue(self.link.info()['devices'][0]['pairable'])
        device['expires_at']=time.time()-1;self.link.save_devices()
        self.assertFalse(self.link.info()['devices'][0]['pairable'])
        restarted=MobileLink(self.store);restarted.enabled=True
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=restarted.api,client=('192.168.1.22',1000)),base_url='http://pc',headers={'Authorization':'Bearer '+token}) as client:
            self.assertEqual((await client.get('/state')).status_code,401)

    async def test_a_pairing_saved_without_an_expiry_is_not_offered_as_reusable(self):
        # Phones paired before pair() stamped expires_at sit in real stores today. Their
        # token hash matches, so guard() reaches the expiry check with no value and treats
        # them as spent; the panel has to say so instead of showing a tappable "Remembered".
        token='legacy-phone-token'
        self.store.write_text(json.dumps({'old-phone':{'name':'Xiaomi 24053PY09I',
            'token_hash':hashlib.sha256(token.encode()).hexdigest(),'last_seen':time.time()}}),encoding='utf-8')
        link=MobileLink(self.store);link.enabled=True
        self.assertEqual(link.info()['devices'][0]['pairable'],False)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=link.api,client=('192.168.1.22',1000)),base_url='http://pc',headers={'Authorization':'Bearer '+token}) as client:
            self.assertEqual((await client.get('/state')).status_code,401)

    async def test_discovery_answers_a_probe_with_the_bound_address(self):
        reply=json.loads(self.link.discovery_reply(b'sakura-discover-v1','192.168.1.103'))
        self.assertEqual(reply['service'],'sakura')
        self.assertEqual(reply['id'],self.link.pc_id)
        self.assertEqual(reply['https'],f'https://192.168.1.103:{self.link.port}')
        self.assertEqual(reply['port'],self.link.port)
        self.assertRegex(reply['fingerprint'],r'^[0-9a-f]{64}$')
        self.assertEqual(reply['fingerprint'],self.link.info()['fingerprint'])
        self.assertNotIn('http',reply,'A legacy cleartext endpoint is not advertised')
        self.assertIsNone(self.link.discovery_reply(b'maldroid-discover-v1','192.168.1.103'))
        self.link.enabled=False
        self.assertIsNone(self.link.discovery_reply(b'sakura-discover-v1','192.168.1.103'))

    async def test_discovery_probe_flood_cannot_starve_the_link(self):
        for _ in range(10):self.assertIsNotNone(self.link.discovery_reply(b'sakura-discover-v1','192.168.1.103'))
        self.assertIsNone(self.link.discovery_reply(b'sakura-discover-v1','192.168.1.103'))
        self.link.beacon_replies=[(peer,stamp-1.1) for peer,stamp in self.link.beacon_replies]
        self.assertIsNotNone(self.link.discovery_reply(b'sakura-discover-v1','192.168.1.103'))

    async def test_discovery_only_advertises_private_network_addresses(self):
        import ipaddress
        for address in self.link.lan_addresses():
            self.assertTrue(ipaddress.IPv4Address(address).is_private)
        self.assertEqual(self.link.discovery_port,8770)
        self.link.stop_beacon()

