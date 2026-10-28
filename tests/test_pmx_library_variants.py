import importlib.util
from pathlib import Path
import sys
import zipfile

SPEC=importlib.util.spec_from_file_location('prepare_pmx',Path(__file__).parents[1]/'tools/prepare-jio-pmx-library.py')
builder=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def test_nested_variants_are_individually_discovered_and_props_excluded(tmp_path,monkeypatch):
    monkeypatch.setattr(builder,'CATEGORIES',('game',))
    monkeypatch.setattr(builder,'pmx_bone_names',lambda data:data)
    def validate(data,name):
        if data==b'prop':raise ValueError('Not humanoid')
    monkeypatch.setattr(builder,'validate_humanoid_names',validate)
    for name,data in [('game/Kafka/outfit1/glasses.pmx',b'avatar'),('game/Kafka/outfit1/normal.pmx',b'avatar'),
                      ('game/Kafka/outfit2/dress.pmx',b'avatar'),('game/Kafka/outfit2/gun.pmx',b'prop')]:
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    rows=list(builder.variants(tmp_path))
    assert len(rows)==3
    assert all(row[2].name!='gun.pmx' for row in rows)


def test_selected_variant_package_retains_textures_and_only_selected_model(tmp_path,monkeypatch):
    monkeypatch.setattr(builder,'pmx_bone_names',lambda data:[])
    monkeypatch.setattr(builder,'validate_humanoid_names',lambda *args:None)
    monkeypatch.setattr(builder,'import_package',lambda *args:None)
    root=tmp_path/'models';folder=root/'game/Kafka';selected=folder/'dress/normal.pmx'
    selected.parent.mkdir(parents=True);selected.write_bytes(b'avatar1')
    (selected.parent/'glasses.pmx').write_bytes(b'avatar2')
    texture=selected.parent/'tex/body.tga';texture.parent.mkdir();texture.write_bytes(b'original texture bytes')
    out=tmp_path/'out';out.mkdir()
    key,entry=builder.prepare(root,'game',folder,out,{},selected)
    assert entry['models']==1
    assert entry['name']=='game / Kafka / dress / normal'
    assert entry['preview_model']=='pmx/game/Kafka/dress/normal.pmx'
    with zipfile.ZipFile(out/(key+'.zip')) as package:
        assert package.read('dress/tex/body.tga')==b'original texture bytes'
        assert 'dress/normal.pmx' in package.namelist()
        assert 'dress/glasses.pmx' not in package.namelist()


def test_any_new_category_is_discovered_but_generated_packages_are_not(tmp_path,monkeypatch):
    monkeypatch.setattr(builder,'pmx_bone_names',lambda data:[])
    monkeypatch.setattr(builder,'validate_humanoid_names',lambda *args:None)
    for name in ['New game/Character/hero.pmx','Another game/hero.pmx','Sakura library packages/ignore/model.pmx']:
        file=tmp_path/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(b'avatar')
    rows=list(builder.variants(tmp_path))
    assert {row[0] for row in rows}=={'New game','Another game'}
