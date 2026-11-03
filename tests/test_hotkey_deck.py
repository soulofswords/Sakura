from unittest.mock import Mock
import pytest
import hotkey_deck

def test_only_preconfigured_phone_slots_can_execute(tmp_path,monkeypatch):
    monkeypatch.setattr('agent_connections.secret_set',lambda *a:None)
    slots=[{'id':'pose1','label':'Wave','kind':'pose','target':'greeting_wave'}, {'id':'scene1','label':'Gameplay','kind':'scene','target':'Gameplay'}]
    hotkey_deck.configure(tmp_path,{'slots':slots,'port':4455,'password':'not-in-json'})
    assert hotkey_deck.execute(tmp_path,'pose1')['pose']=='greeting_wave'
    call=Mock(return_value={});monkeypatch.setattr(hotkey_deck,'obs_request',call)
    assert hotkey_deck.execute(tmp_path,'scene1')['scene']=='Gameplay'
    call.assert_called_once_with(tmp_path,'SetCurrentProgramScene',{'sceneName':'Gameplay'})
    with pytest.raises(ValueError):hotkey_deck.execute(tmp_path,'unconfigured')
    assert 'not-in-json' not in (tmp_path/'desktop-profile/hotkey-deck.json').read_text()

@pytest.mark.parametrize('slot',[{'id':'x','label':'Bad','kind':'shell','target':'powershell.exe'}, {'id':'x','label':'Bad','kind':'pose','target':'run-code'}, {'id':'x','label':'Bad','kind':'scene','target':'scene\ncommand'}])
def test_deck_is_not_an_arbitrary_command_channel(slot):
    with pytest.raises(ValueError):hotkey_deck.validate({'slots':[slot]})

def test_real_websocket_handshake_and_scene_request(tmp_path,monkeypatch):
    import json,threading
    from websockets.sync.server import serve
    received=[]
    def handler(ws):
        ws.send(json.dumps({'op':0,'d':{'rpcVersion':1}}))
        identify=json.loads(ws.recv(timeout=3));assert identify['op']==1
        ws.send(json.dumps({'op':2,'d':{'negotiatedRpcVersion':1}}))
        request=json.loads(ws.recv(timeout=3));received.append(request['d'])
        ws.send(json.dumps({'op':7,'d':{'requestId':request['d']['requestId'],'requestStatus':{'result':True},'responseData':{'scenes':[{'sceneName':'Gameplay'}]}}}))
    monkeypatch.setattr('agent_connections.secret_get',lambda slot:{})
    with serve(handler,'127.0.0.1',0) as server:
        port=server.socket.getsockname()[1]
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        monkeypatch.setattr(hotkey_deck,'read',lambda root:{'port':port,'slots':[]})
        try:assert hotkey_deck.obs_request(tmp_path,'GetSceneList')['scenes'][0]['sceneName']=='Gameplay'
        finally:server.shutdown();thread.join(timeout=3)
    assert received[0]['requestType']=='GetSceneList'
