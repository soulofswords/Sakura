import json,struct
from pathlib import Path
from model_inspection import inspect_folder,inspect_model
from agent_local_ai import LocalAI


def gguf(path,arch='qwen3vl',split=False):
    def string(s):b=s.encode();return struct.pack('<Q',len(b))+b
    metadata={'general.architecture':arch,'general.name':'My Qwen vision model'}
    parts=[]
    for key,val in metadata.items():parts.append(string(key)+struct.pack('<I',8)+string(val))
    if split:parts.append(string('split.count')+struct.pack('<II',4,2))
    blob=b'GGUF'+struct.pack('<IQQ',3,1,len(parts))+b''.join(parts)
    blob+=string('weight')+struct.pack('<IQIQ',1,8,0,0)
    blob+=b'\0'*((-len(blob))%32)+b'\0'*32
    path.write_bytes(blob)


def test_folder_identifies_gguf_and_projector_and_imports_in_place(tmp_path):
    weights=tmp_path/'weights.gguf';projector=tmp_path/'mmproj.gguf';gguf(weights);gguf(projector,'clip')
    r=LocalAI(tmp_path/'private');result=r.inspect_folder(str(tmp_path))
    assert len(result['models'])==2
    assert all(m['can_add'] for m in result['models'])
    item=next(m for m in result['models'] if m['projector']);assert item['engine']=='llama.cpp'
    r.import_detected(str(projector));entry=next(iter(r.models.values()));assert entry['projector'] and not entry['owned'] and Path(entry['path'])==projector


def test_unknown_arch_split_and_truncated_weights_are_not_offered(tmp_path):
    unknown=tmp_path/'new.gguf';gguf(unknown,'future_unknown');assert inspect_model(unknown)['status']=='unverified'
    split=tmp_path/'split.gguf';gguf(split,split=True);assert not inspect_model(split)['can_add']
    broken=tmp_path/'broken.gguf';broken.write_bytes(b'GGUF');assert inspect_model(broken)['status']=='incomplete'
    gguf(broken);data=broken.read_bytes();broken.write_bytes(data[:-32]);assert inspect_model(broken)['status']=='incomplete'


def test_transformers_and_raw_pytorch_explain_conversion(tmp_path):
    folder=tmp_path/'transformers';folder.mkdir();(folder/'config.json').write_text(json.dumps({'model_type':'llama','_name_or_path':'My Llama'}));(folder/'weights.safetensors').write_bytes(b'raw')
    result=inspect_folder(str(tmp_path));assert result['models'][0]['architecture']=='llama' and not result['models'][0]['can_add']
    raw=tmp_path/'untrusted.pth';raw.write_bytes(b'never unpickle this')
    assert any(m.get('format')=='PyTorch / Safetensors' for m in inspect_folder(str(tmp_path))['models'])
    assert raw.read_bytes()==b'never unpickle this'


def test_import_rechecks_modified_model_before_registration(tmp_path):
    file=tmp_path/'m.gguf';gguf(file);runtime=LocalAI(tmp_path/'private');assert runtime.inspect_folder(str(tmp_path))['models'][0]['can_add']
    file.write_bytes(b'GGUFbad')
    import pytest
    with pytest.raises(ValueError):runtime.import_detected(str(file))
    assert not runtime.models
