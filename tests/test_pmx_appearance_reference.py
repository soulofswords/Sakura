import base64
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image
import pmx_appearance_reference as reference

@pytest.mark.parametrize('value',[None,[],[0,0,0],[True,0,1],[float('nan'),0,1],[float('inf'),0,1],['1',0,1],[1,2,3,4]])
def test_invalid_directions(value):
    with pytest.raises(ValueError):reference._direction(value)

def test_direction_is_normalized():
    assert reference._direction([0,0,5])==[0,0,1]

@pytest.fixture
def setup_reference(tmp_path,monkeypatch):
    editor=tmp_path/'editor/PmxEditor.exe';editor.parent.mkdir();editor.touch()
    for name in ['PEPlugin/PEPlugin.dll','SlimDX/SlimDX.dll']:
        path=editor.parent/'Lib'/name;path.parent.mkdir(parents=True,exist_ok=True);path.touch()
    windir=tmp_path/'Windows';compiler=windir/'Microsoft.NET/Framework64/v4.0.30319/csc.exe';compiler.parent.mkdir(parents=True);compiler.touch()
    model=tmp_path/'model.pmx';model.touch()
    monkeypatch.setenv('WINDIR',str(windir))
    monkeypatch.setattr(reference,'model_file',lambda value:model)
    monkeypatch.setattr(reference,'find_editor',lambda value:editor)
    def compile_plugin(command,**kwargs):
        output=Path(next(arg[5:] for arg in command if arg.startswith('/out:')));output.write_bytes(b'owned-plugin')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(reference.subprocess,'run',compile_plugin)
    image=Image.new('RGB',(64,64));image.putdata([(x%256,(x//64)*3,255-x%256) for x in range(4096)])
    stream=io.BytesIO();image.save(stream,format='PNG');raw=stream.getvalue()
    spawned=[]
    def spawn(command,**kwargs):
        job=Path(kwargs['env']['SAKURA_PMX_REFERENCE_JOB'])
        (job/'reference.png').write_bytes(raw)
        (job/'result.json').write_text(json.dumps({'ok':True,'ambient':[255,255,255],'parts':[{'material':0,'image':'data:image/png;base64,'+base64.b64encode(raw).decode()}]}))
        process=Mock();process.poll.return_value=0;spawned.append(process);return process
    monkeypatch.setattr(reference.subprocess,'Popen',spawn)
    return editor,spawned

def test_capture_returns_real_protocol_and_removes_owned_plugin(setup_reference):
    editor,spawned=setup_reference
    result=reference.capture_reference('pmx/test.pmx',[0,0,1])
    assert result['model']=='pmx/test.pmx'
    assert result['image'].startswith('data:image/png;base64,')
    assert result['parts'][0]['material']==0
    assert not (editor.parent/'_plugin/User/SakuraAppearanceReference.dll').exists()
    assert len(spawned)==1
    spawned[0].terminate.assert_not_called()
    assert reference._LOCK.acquire(blocking=False)
    reference._LOCK.release()

def test_existing_plugin_is_never_overwritten(setup_reference):
    editor,spawned=setup_reference
    target=editor.parent/'_plugin/User/SakuraAppearanceReference.dll';target.parent.mkdir(parents=True);target.write_bytes(b'user-owned')
    with pytest.raises(RuntimeError,match='occupied'):reference.capture_reference('pmx/test.pmx',[0,0,1])
    assert target.read_bytes()==b'user-owned'
    assert not spawned

def test_timeout_terminates_only_owned_process_and_removes_plugin(setup_reference,monkeypatch):
    editor,_=setup_reference
    process=Mock();process.poll.return_value=None
    monkeypatch.setattr(reference.subprocess,'Popen',lambda *a,**kw:process)
    with pytest.raises(RuntimeError,match='timed out'):reference.capture_reference('pmx/test.pmx',[0,0,1],timeout=0)
    process.terminate.assert_called_once()
    process.wait.assert_called_once()
    assert not (editor.parent/'_plugin/User/SakuraAppearanceReference.dll').exists()
    assert reference._LOCK.acquire(blocking=False)
    reference._LOCK.release()

def test_busy_capture_does_not_launch_editor(setup_reference):
    _,spawned=setup_reference
    reference._LOCK.acquire()
    try:
        with pytest.raises(RuntimeError,match='already running'):reference.capture_reference('pmx/test.pmx',[0,0,1])
    finally:reference._LOCK.release()
    assert not spawned


def test_translucent_model_accepts_no_opaque_parts(setup_reference, monkeypatch):
    original_spawn=reference.subprocess.Popen
    def spawn(command, **kwargs):
        process=original_spawn(command, **kwargs)
        report=Path(kwargs['env']['SAKURA_PMX_REFERENCE_JOB'])/'result.json'
        data=json.loads(report.read_text());data['parts']=[]
        report.write_text(json.dumps(data))
        return process
    monkeypatch.setattr(reference.subprocess,'Popen',spawn)
    result=reference.capture_reference('pmx/translucent.pmx',[0,0,1])
    assert result['parts']==[]
    assert result['image'].startswith('data:image/png;base64,')


def _abandoned_slot(editor, payload=b'owned-old-binary'):
    import hashlib
    target=editor.parent/'_plugin/User/SakuraAppearanceReference.dll'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(payload)
    target.with_name(target.name+'.owner.json').write_text(json.dumps({
        'sha256':hashlib.sha256(payload).hexdigest(),
        'source_sha256':hashlib.sha256(reference._PLUGIN_SOURCE.encode('utf-8')).hexdigest(),
    }))
    return target


def test_known_dead_plugin_is_recovered(setup_reference,monkeypatch):
    editor,spawned=setup_reference
    target=_abandoned_slot(editor)
    monkeypatch.setattr(reference,'_editor_process_running',lambda editor:False)
    assert reference.capture_reference('pmx/test.pmx',[0,0,1])['parts']
    assert len(spawned)==1
    assert not target.exists()
    assert not target.with_name(target.name+'.owner.json').exists()


def test_live_editor_blocks_recovery(setup_reference,monkeypatch):
    editor,spawned=setup_reference
    target=_abandoned_slot(editor)
    monkeypatch.setattr(reference,'_editor_process_running',lambda editor:True)
    with pytest.raises(RuntimeError,match='Close PMX Editor'):
        reference.capture_reference('pmx/test.pmx',[0,0,1])
    assert target.read_bytes()==b'owned-old-binary'
    assert not spawned


def test_modified_abandoned_plugin_is_not_reclaimed(setup_reference,monkeypatch):
    editor,spawned=setup_reference
    target=_abandoned_slot(editor);target.write_bytes(b'changed-by-user')
    monkeypatch.setattr(reference,'_editor_process_running',lambda editor:False)
    with pytest.raises(RuntimeError,match='unverified'):
        reference.capture_reference('pmx/test.pmx',[0,0,1])
    assert target.read_bytes()==b'changed-by-user'
    assert not spawned


def test_plugin_slot_lock_excludes_other_jobs(tmp_path):
    target=tmp_path/'plugin.dll'
    first=reference._acquire_slot_lock(target)
    try:
        with pytest.raises(RuntimeError,match='another Sakura instance'):
            reference._acquire_slot_lock(target)
    finally:first.close()
    again=reference._acquire_slot_lock(target)
    again.close()
