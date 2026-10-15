"""Repair explicitly selected PMX material flags, retaining a rollback copy.

Requires the pure-Python mmd_tools/core/pmx/__init__.py parser. This does not
rewrite textures, geometry, skin weights, morphs, bones, or physics rigs.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil


def structure(model):
    def encode(value):
        if isinstance(value,bytes):return value.hex()
        if hasattr(value,'__dict__'):return vars(value)
        if hasattr(value,'__slots__'):return {key:getattr(value,key) for key in value.__slots__}
        raise TypeError(type(value).__name__)
    data={key:value for key,value in vars(model).items() if key not in ('materials','textures','filepath','header')}
    return hashlib.sha256(json.dumps(data,default=encode,sort_keys=True).encode()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model',type=Path)
    parser.add_argument('--pmx-module',required=True,type=Path)
    parser.add_argument('--material',action='append',required=True)
    parser.add_argument('--double-sided',action='store_true')
    parser.add_argument('--specular',type=float,default=.625)
    parser.add_argument('--shininess',type=float,default=50)
    args=parser.parse_args()
    if not 0<=args.specular<=1 or not 0<args.shininess<=1000:
        parser.error('Specular must be 0–1 and shininess must be 0–1000')
    spec=importlib.util.spec_from_file_location('pmx_material_repair',args.pmx_module)
    pmx=importlib.util.module_from_spec(spec);spec.loader.exec_module(pmx)
    model=pmx.load(str(args.model.resolve()))
    names=set(args.material)
    if names-{m.name for m in model.materials}:parser.error('Requested material missing')
    before=structure(model)
    backup=args.model.with_name(args.model.name+'.before-material-repair.bak')
    if not backup.exists():shutil.copy2(args.model,backup)
    changes=[]
    for mat in model.materials:
        if mat.name not in names:continue
        changes.append({'name':mat.name,'before':{'double_sided':mat.is_double_sided,'specular':mat.specular,'shininess':mat.shininess}})
        if args.double_sided:mat.is_double_sided=True
        mat.specular=(args.specular,)*3;mat.shininess=args.shininess
    temp=args.model.with_name(args.model.stem+'.material-repair.tmp.pmx')
    try:
        pmx.save(str(temp),model,add_uv_count=max(len(v.additional_uvs) for v in model.vertices))
        checked=pmx.load(str(temp))
        if structure(checked)!=before:raise ValueError('Non-material content changed; refusing replacement')
        for mat in checked.materials:
            if mat.name in names:
                assert abs(mat.shininess-args.shininess)<1e-5
                assert all(abs(s-args.specular)<1e-5 for s in mat.specular)
        temp.replace(args.model)
    finally:
        temp.unlink(missing_ok=True)
    report={'model':str(args.model),'backup':str(backup),'changes':changes,
            'specular':args.specular,'shininess':args.shininess,
            'non_material_content_unchanged':True}
    args.model.with_suffix('.material-repair.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))


if __name__=='__main__':main()
