import io
import hashlib
import json
from pathlib import Path
from unittest.mock import Mock,patch
import zipfile
import pytest
import agent_integrations as integrations
from agent_connections import Connections
from agent_runtime import AgentRuntime


def test_installer_requires_official_checksum_before_writing(tmp_path,monkeypatch):
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w') as archive:archive.writestr('nuclei.exe',b'MZ verified fixture')
    package=output.getvalue();digest=hashlib.sha256(package).hexdigest();name='nuclei_3.0.0_windows_amd64.zip'
    release={'tag_name':'v3.0.0','assets':[{'name':name,'browser_download_url':'https://github.com/package'},{'name':'checksums.txt','browser_download_url':'https://github.com/checksums'}]}
    monkeypatch.setattr(integrations,'ROOT',tmp_path)
    responses=[json.dumps(release).encode(),(digest+'  '+name).encode(),package]
    with patch.object(integrations,'download',side_effect=responses):result=integrations.setup('nuclei',Mock())
    assert result['installed'] and integrations.nuclei_path().read_bytes()==b'MZ verified fixture'
    integrations.nuclei_path().unlink()
    responses=[json.dumps(release).encode(),('0'*64+'  '+name).encode(),package]
    with patch.object(integrations,'download',side_effect=responses),pytest.raises(ValueError,match='checksum'):integrations.setup('nuclei',Mock())
    assert not integrations.nuclei_path().exists()


def test_no_unauthorized_scan_or_freeform_cli(tmp_path,monkeypatch):
    monkeypatch.setattr(integrations,'ROOT',tmp_path)
    monkeypatch.setattr(integrations,'secret_get',lambda slot:{'scan_origins':['https://owned.example']})
    exe=integrations.nuclei_path();exe.parent.mkdir();exe.write_bytes(b'fixture')
    with patch('agent_runtime.run_process',return_value={'ok':True,'output':''}) as process:
        with pytest.raises(ValueError,match='Authorize'):integrations.execute('nuclei.scan',{'url':'https://other.example'},None)
        process.assert_not_called()
        result=integrations.execute('nuclei.scan',{'url':'https://owned.example/path'},None)
        assert result['ok']
        args=process.call_args.args[0]
        assert '-dut' in args and '-ni' in args and '-pt' in args
        assert process.call_args.kwargs['timeout']==120


def test_mcp_prompt_add_uses_review_and_real_discovery(tmp_path,monkeypatch):
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'))
    monkeypatch.setattr('agent_connections.secret_get',lambda slot:{})
    monkeypatch.setattr('agent_connections.secret_set',lambda *args:None)
    run=runtime.new_run('Connect my MCP',str(tmp_path))
    action=runtime.propose(run['id'],'mcp.add',{'name':'Test server','transport':'http','url':'http://127.0.0.1:8100/gateway'})['steps'][-1]
    assert runtime.connections.public()==[]
    with patch('agent_connections.mcp_request',return_value=[{'name':'fixture','description':'Test','inputSchema':{}}]):result=runtime.decide(action['id'],True)
    assert result['action']['result']['discovered_tools']==['fixture']
    assert len(runtime.connections.public())==1


def test_firecrawl_missing_secret_does_not_send_anything(monkeypatch):
    monkeypatch.setattr(integrations,'secret_get',lambda slot:{})
    with patch.object(integrations.requests,'post') as request:
        with pytest.raises(ValueError,match='API key'):integrations.firecrawl('firecrawl.scrape',{'url':'https://example.com'})
        request.assert_not_called()


def test_chat_can_prepare_curated_setup_without_guessing_a_workspace(tmp_path):
    from teacher_agent_chat import TeacherAgentChat
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'));bridge=TeacherAgentChat(runtime)
    result=bridge.handle('Please add Firecrawl',{'conversation_mode':'teacher'},Mock(),{})
    pending=bridge.status(result['agent_task']['id'])['pending']
    assert pending['tool']=='integrations.setup' and pending['arguments']=={'provider':'firecrawl'}
    assert pending['status']=='pending'
