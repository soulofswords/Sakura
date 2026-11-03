import json
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import Mock,patch
import pytest
from wallclock_schedule import next_run,validate
from knowledge_folders import manifest,FolderKnowledge
from agent_knowledge import Knowledge
from personal_features import PersonalFeatures,export_context,import_context
from memory_archaeology import MemoryArchaeology
from model_choice import ModelChoice


def instant(value):return datetime.fromisoformat(value).timestamp()

def test_wallclock_weekdays_timezone_and_dst():
    schedule={'time':'08:00','timezone':'Asia/Kolkata','weekdays':[0,1,2,3,4,5,6]}
    assert next_run(schedule,instant('2026-11-03T00:00:00+00:00'))==instant('2026-11-03T02:30:00+00:00')
    schedule={'time':'02:30','timezone':'America/New_York','weekdays':[6]}
    assert next_run(schedule,instant('2026-03-08T00:00:00+00:00'))==instant('2026-03-15T06:30:00+00:00')
    schedule={'time':'01:30','timezone':'America/New_York','weekdays':[6]}
    # After the first fall-back occurrence, don't run again at the second fold.
    assert next_run(schedule,instant('2026-11-01T05:31:00+00:00'))==instant('2026-11-08T06:30:00+00:00')
    for value in ({'time':'99:00','timezone':'Asia/Kolkata','weekdays':[0]}, {'time':'08:00','timezone':'invalid','weekdays':[0]}, {'time':'08:00','timezone':'UTC','weekdays':[True]}):
        with pytest.raises(ValueError):validate(value)


def test_wallclock_automation_persists_and_reschedules_after_execution(tmp_path):
    from agent_runtime import AgentRuntime
    from agent_connections import Connections
    from agent_automations import AgentAutomations
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'))
    run=runtime.new_run('List my notes',str(tmp_path),False)
    action=runtime.propose(run['id'],'files.list',{'path':'.'})['steps'][-1]
    runtime.decide(action['id'],True)
    scheduler=AgentAutomations(runtime)
    schedule={'time':'08:00','timezone':'Asia/Kolkata','weekdays':[0]}
    with patch('agent_automations.time.time',return_value=instant('2026-11-03T00:00:00+00:00')):
        item=scheduler.create(run['id'],'Monday brief',1440,True,schedule=schedule)
    assert item['next_run']==instant('2026-11-09T02:30:00+00:00')
    restored=AgentAutomations(runtime);assert restored.list()[0]['schedule']==schedule
    with patch('agent_automations.time.time',return_value=item['next_run']):restored.execute(item['id'])
    assert restored.list()[0]['next_run']==instant('2026-11-16T02:30:00+00:00')


def test_folder_approval_snapshot_stale_sources_and_secret_exclusion(tmp_path):
    root=tmp_path/'documents';root.mkdir();(root/'report.md').write_text('Acme engineering measurements')
    (root/'.env').write_text('SECRET');(root/'settings.json').write_text('SECRET')
    reviewed=manifest(root);assert [row['path'] for row in reviewed['files']]==['report.md']
    knowledge=Knowledge(tmp_path/'kb.sqlite3');folders=FolderKnowledge(tmp_path/'folders.json',knowledge)
    folders.index(reviewed)
    assert folders.search('Acme')['results'][0]['folder']==str(root)
    assert not folders.search('SECRET')['results']
    (root/'report.md').write_text('Changed')
    with pytest.raises(ValueError,match='changed'):folders.index(reviewed)
    (root/'report.md').unlink();folders.index(manifest(root))
    assert not folders.search('Acme')['results']
    folders.remove(str(root));assert folders.folders()==[]


def test_semantic_index_finds_nonliteral_matches_and_clear_removes_vectors(tmp_path):
    class Encoder:
        name='onnx:test'
        def encode(self,texts):return [[1.,0.] for text in texts]
    knowledge=Knowledge(tmp_path/'kb.sqlite3')
    knowledge.index(tmp_path,'pets.md','A feline sleeps quietly.')
    with patch('memory_vectors.embedder',return_value=Encoder()):
        assert knowledge.embed_source(tmp_path,'pets.md')['semantic']
        assert knowledge.search(tmp_path,'cat')['results'][0]['source']=='pets.md'
    knowledge.clear(tmp_path)
    with knowledge.connect() as db:assert db.execute('SELECT count(*) FROM semantic_chunks').fetchone()[0]==0


def test_portable_context_is_explicit_deduplicated_and_lower_trust(tmp_path):
    one=MemoryArchaeology(tmp_path/'one');one.configure(True)
    one.record_save('link','https://example.com','Acme','proposal','excited')
    two=MemoryArchaeology(tmp_path/'two');two.configure(True)
    packet=export_context(one)
    assert import_context(two,packet)['added']==1
    assert import_context(two,packet)['added']==0
    row=two.recall('Acme')['timeline'][0]['saves'][0]
    assert row['source']=='device-import' and row['tag_origin']=='suggested'
    bad={'version':1,'saves':[{'type':'link','url_or_path':'https://example.com/?token=private'}]}
    with pytest.raises(ValueError):import_context(two,bad)
    assert 'links' not in packet['saves'][0]


def test_context_packet_rolls_back_on_index_failure(tmp_path,monkeypatch):
    source=MemoryArchaeology(tmp_path/'source');source.configure(True)
    source.record_save('document','first.md','First')
    source.record_save('document','second.md','Second')
    target=MemoryArchaeology(tmp_path/'target');target.configure(True)
    existing=target.record_save('document','owner.md','Keep owner entry')
    original=target._index;calls=[]
    def fail_second(db,row):
        calls.append(row['id'])
        original(db,row)
        if len(calls)==2:raise RuntimeError('Simulated interrupted index')
    monkeypatch.setattr(target,'_index',fail_second)
    with pytest.raises(RuntimeError):import_context(target,export_context(source))
    with target.db() as db:
        assert [row['id'] for row in db.execute('SELECT id FROM saves')]==[existing['id']]
        assert db.execute('SELECT count(*) FROM save_search').fetchone()[0]==1


def test_guest_chat_never_uses_owner_history_or_command_dispatch(tmp_path):
    feature=PersonalFeatures(tmp_path);feature.configure({'guest':True})
    model=Mock();model._request_raw.return_value='Hello guest'
    assert feature.guest_reply(model,'Hello')['guest']
    messages=model._request_raw.call_args.args[0]
    assert len(messages)==2 and messages[-1]['content']=='Hello'
    model.chat.assert_not_called()
    feature.configure({'guest':False});assert feature.guest_history==[]


def test_expenses_decimal_validation_and_separate_currency_totals(tmp_path):
    feature=PersonalFeatures(tmp_path)
    row=feature.add_expense('2026-11-03','0.10','INR','food')
    feature.add_expense('2026-11-03','0.20','INR');feature.add_expense('2026-11-03','2','USD')
    assert feature.expenses('2026-11')['totals_by_currency']=={'INR':'0.30','USD':'2'}
    for value in ('NaN','Infinity','-1','1.001'):
        with pytest.raises(ValueError):feature.add_expense('2026-11-03',value,'INR')
    feature.delete_expense(row['id']);assert len(feature.expenses()['items'])==2


def test_measured_routing_requires_current_identity_and_cloud_opt_in(tmp_path):
    class Model:
        provider='ollama';model='local';base_url='http://127.0.0.1:11434'
        def _request_raw(self,messages):
            text=messages[-1]['content']
            return 'READY' if 'READY' in text else '323' if '17 *' in text else '10' if 'balls' in text else '{"tool":"files.list","arguments":{}}'
    model=Model();route=ModelChoice(tmp_path/'routing.json')
    route.measure('local',model);route.configure(True,False)
    assert route.select('coding',{'local':model})[0]=='local'
    model.model='changed'
    with pytest.raises(ValueError):route.select('coding',{'local':model})
    route.measure('cloud',model,True)
    with pytest.raises(ValueError):route.select('chat',{'cloud':model})
    route.configure(True,True);assert route.select('chat',{'cloud':model})[0]=='cloud'


def test_mail_triage_is_read_only_and_source_linked():
    from mail_workflows import triage
    result=triage({'messages':[{'id':'one','subject':'Urgent deadline today','from':'Acme'},{'id':'two','subject':'News'}]})
    assert result['messages'][0]['priority_hint']=='review soon'
    with pytest.raises(ValueError):triage({'text':'unstructured'})


def test_speaker_similarity_never_grants_authority(tmp_path,monkeypatch):
    from speaker_profiles import SpeakerProfiles
    profiles=SpeakerProfiles(tmp_path)
    monkeypatch.setattr(profiles,'vector',lambda audio:[1.,0.])
    monkeypatch.setattr(profiles,'_profiles',lambda:{'Owner':[1.,0.]})
    result=profiles.identify(b'clip')
    assert result['label']=='Owner' and result['authority']=='none'
    assert not profiles.status()['ready']


def test_sdk_refuses_remote_endpoints():
    from sakura_sdk import Sakura
    for url in ('https://example.com','http://192.168.1.1','http://user:pass@localhost:8766','http://localhost:8766/path'):
        with pytest.raises(ValueError):Sakura(url,token='test')


def test_optional_speaker_bootstrap_handles_embedded_python(tmp_path,monkeypatch):
    import io,zipfile,hashlib,sys,os
    from speaker_profiles import SpeakerProfiles
    if os.name!='nt':pytest.skip('Windows embedded-runtime bootstrap')
    base=tmp_path/'embedded';base.mkdir()
    for name in ('python.exe','python312.dll','python312.zip','_ssl.pyd'):(base/name).write_bytes(b'runtime')
    (base/'python312._pth').write_text('python312.zip\n.\n')
    (base/'private-key.bin').write_bytes(b'not copied')
    monkeypatch.setattr(sys,'base_prefix',str(base))
    content=io.BytesIO()
    with zipfile.ZipFile(content,'w') as wheel:wheel.writestr('pip/__init__.py','# bootstrap')
    data=content.getvalue();metadata=Mock();metadata.json.return_value={'urls':[{'filename':'pip-25.0.1-py3-none-any.whl','url':'https://files.pythonhosted.org/packages/pip.whl','digests':{'sha256':hashlib.sha256(data).hexdigest()}}]}
    download=Mock();download.iter_content.return_value=[data]
    from unittest.mock import MagicMock
    response=MagicMock();response.__enter__.return_value=download
    session=MagicMock();session.__enter__.return_value=session;session.get.side_effect=[metadata,response]
    with patch('requests.Session',return_value=session):
        profiles=SpeakerProfiles(tmp_path/'voice');profiles._environment()
    assert profiles.python.is_file()
    assert (profiles.python.parent/'Lib/site-packages/pip/__init__.py').is_file()
    assert 'import site' in (profiles.python.parent/'python312._pth').read_text()
    assert not (profiles.python.parent/'private-key.bin').exists()
    assert session.trust_env is False
