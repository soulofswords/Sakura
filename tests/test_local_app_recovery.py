import json
from unittest.mock import Mock,patch
from agent_connections import Connections
from agent_runtime import AgentRuntime
from local_serve_tools import diagnose_startup


def test_diagnostics_bound_to_task_log_and_classifies_missing_package(tmp_path):
    folder=tmp_path/'.sakura-serve';folder.mkdir();log=folder/'server.log'
    log.write_text('npm ERR! ENOENT package.json not found',encoding='utf-8')
    data=diagnose_startup('http://127.0.0.1:4173/',tmp_path,{'log':str(log),'pid':-1})
    assert 'Wrong launch folder' in data['finding']
    outside=tmp_path.parent/'not-the-server.log'
    result=diagnose_startup('http://127.0.0.1:4173/',tmp_path,{'log':str(outside)})
    assert not result['log_tail'] and 'task-owned' in result['finding']


def test_actual_localhost_failure_replans_but_shell_repair_stays_approval_gated(tmp_path):
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'))
    run=runtime.new_run('Launch the project in a local browser',str(tmp_path))
    folder=tmp_path/'.sakura-serve';folder.mkdir();log=folder/'server.log';log.write_text('Port 4173 is already in use',encoding='utf-8')
    runtime.runs[run['id']]['steps'].append({'id':'previous','tool':'shell.serve','status':'completed','arguments':{'command':'npm run dev'},'result':{'ok':True,'log':str(log),'pid':99999999}})
    model=Mock();model._request_raw.side_effect=[
        json.dumps({'tool':'local_app.open','arguments':{'url':'http://127.0.0.1:4173/','wait_seconds':3},'reason':'Verify server'}),
        json.dumps({'tool':'shell.serve','arguments':{'command':'npm run dev -- --host 127.0.0.1 --port 4174 --strictPort'},'reason':'Repair the port conflict reported by the server log'})]
    with patch('local_serve_tools.open_when_ready',return_value={'ok':False,'opened':False,'error':'No HTTP response'}),patch('local_serve_tools._probe',return_value=None),patch('local_serve_tools.start_detached') as start:
        result=runtime.plan(run['id'],model)
    assert result['status']=='awaiting_approval'
    assert result['steps'][-1]['tool']=='shell.serve' and result['steps'][-1]['status']=='pending'
    assert 'Port conflict' in result['steps'][-2]['result']['diagnosis']['finding']
    assert model._request_raw.call_count==2
    start.assert_not_called()


def test_full_access_relaunches_then_verifies_repaired_url(tmp_path):
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'))
    runtime.set_approval_mode('full')
    run=runtime.new_run('Launch the project in a local browser',str(tmp_path))
    folder=tmp_path/'.sakura-serve';folder.mkdir();log=folder/'server.log'
    log.write_text('Port 4173 is already in use',encoding='utf-8')
    runtime.runs[run['id']]['steps'].append({'id':'previous','tool':'shell.serve','status':'completed','arguments':{'command':'npm run dev'},'result':{'ok':True,'log':str(log)}})
    def action(tool,args):return json.dumps({'tool':tool,'arguments':args,'reason':'Repair and verify the local app'})
    model=Mock();model._request_raw.side_effect=[
        action('local_app.open',{'url':'http://127.0.0.1:4173/'}),
        action('shell.serve',{'command':'npm run dev -- --host 127.0.0.1 --port 4174 --strictPort'}),
        action('local_app.open',{'url':'http://127.0.0.1:4174/'}),
        json.dumps({'done':True,'summary':'The repaired app responds on http://127.0.0.1:4174/.'})]
    with patch('local_serve_tools.open_when_ready',side_effect=[{'ok':False,'opened':False},{'ok':True,'opened':True,'status':200,'url':'http://127.0.0.1:4174/'}]),patch('local_serve_tools.start_detached',return_value={'ok':True,'log':str(log),'pid':1234}) as start:
        result=runtime.plan(run['id'],model)
    start.assert_called_once()
    assert result['steps'][-1]['tool']=='local_app.open'
    assert result['steps'][-1]['result']['status']==200
    assert result['steps'][-1]['status']=='completed'
    assert result['status']=='completed'


def test_error_page_is_not_reported_as_working():
    from local_serve_tools import open_when_ready
    with patch('local_serve_tools.wait_for_port',return_value={'answered':True,'status':500,'attempts':1}),patch('local_serve_tools.webbrowser.open') as opened:
        result=open_when_ready('http://127.0.0.1:4173/')
    assert not result['ok'] and 'HTTP 500' in result['error']
    opened.assert_not_called()


def test_recovery_budget_stops_replanning(tmp_path):
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'))
    run=runtime.new_run('Launch this local app',str(tmp_path))
    state=runtime.runs[run['id']];state['local_app_recovery_attempts']=3
    state['steps'].append({'id':'previous','tool':'shell.serve','status':'completed','arguments':{},'result':{'ok':True}})
    model=Mock();model._request_raw.return_value=json.dumps({'tool':'local_app.open','arguments':{'url':'http://127.0.0.1:4173/'},'reason':'Verify startup'})
    with patch('local_serve_tools.open_when_ready',return_value={'ok':False,'opened':False}):
        result=runtime.plan(run['id'],model)
    assert result['status']=='failed'
    assert model._request_raw.call_count==1
