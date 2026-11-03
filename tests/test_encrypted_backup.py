from pathlib import Path
import pytest
from encrypted_backup import create,restore,allowed

def test_round_trip_excludes_account_credentials_and_never_overwrites(tmp_path):
    root=tmp_path/'source';root.mkdir();(root/'models/pmx/Test').mkdir(parents=True)
    (root/'models/pmx/Test/model.pmx').write_bytes(b'PMX example')
    (root/'memory.json').write_text('{"history": []}')
    (root/'settings.json').write_text('{"api_key":"never-export"}')
    (root/'desktop-profile').mkdir();(root/'desktop-profile/Cookies').write_bytes(b'never-export')
    target=tmp_path/'export.sakurabak';password='long-enough-password'
    result=create(root,target,password);assert result['files']==2
    assert b'PMX example' not in target.read_bytes()
    with pytest.raises(ValueError,match='incorrect|modified'):restore(target,tmp_path,'a-wrong-password')
    assert not list(tmp_path.glob('Sakura-Restore-*'))
    restored=Path(restore(target,tmp_path,password)['path'])
    assert (restored/'models/pmx/Test/model.pmx').read_bytes()==b'PMX example'
    assert not (restored/'settings.json').exists()
    with pytest.raises(ValueError,match='new backup'):create(root,target,password)

@pytest.mark.parametrize('name',['../settings.json','models/../../secret.txt','models/x/C:/file.pmx','/models/x/file.pmx','desktop-profile/Cookies','models/x/code.exe'])
def test_restore_paths_are_allowlisted(name):assert not allowed(name)

def test_modified_ciphertext_never_restores(tmp_path):
    root=tmp_path/'root';root.mkdir();(root/'memory.json').write_text('{}')
    target=tmp_path/'backup.sakurabak';create(root,target,'long-enough-password')
    data=bytearray(target.read_bytes());data[-25]^=1;target.write_bytes(data)
    with pytest.raises(ValueError,match='modified'):restore(target,tmp_path,'long-enough-password')
    assert not list(tmp_path.glob('Sakura-Restore-*'))
