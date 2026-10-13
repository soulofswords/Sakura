"""Read-only, local-only asset server for headless render checks. No AI or mic."""
import argparse
import os
from pathlib import Path
import sys

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app import serve_model_file, check_model_textures, list_live2d_expressions

audit=FastAPI()
audit.mount('/static',StaticFiles(directory=BASE/'static'),name='static')
audit.add_api_route('/models/{file_path:path}',serve_model_file,methods=['GET'])
audit.add_api_route('/api/models/texture-check',check_model_textures,methods=['POST'])
audit.add_api_route('/api/models/live2d-expressions',list_live2d_expressions,methods=['GET'])

def inventory():
    root=BASE/'models';models=[];live=[]
    for directory,folders,files in os.walk(root,followlinks=False):
        folders[:]=sorted(name for name in folders if not name.startswith('.') and name!='__MACOSX' and not (Path(directory)/name).is_symlink())
        for name in sorted(files):
            path=Path(directory)/name
            if name.startswith('._') or not path.resolve().is_relative_to(root.resolve()):continue
            relative=path.relative_to(root).as_posix()
            if path.suffix.lower() in ('.pmx','.vrm'):models.append({'path':relative})
            elif name.lower().endswith('.model3.json'):live.append({'path':relative})
    return {'models':models,'live2d_models':live}

@audit.get('/api/models')
async def models():return inventory()

@audit.get('/audit.html')
async def page():return FileResponse(BASE/'static/library-audit.html')

@audit.get('/health')
async def health():return {'service':'sakura-private-render-check'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,required=True)
    args=parser.parse_args()
    import uvicorn
    uvicorn.run(audit,host='127.0.0.1',port=args.port,log_level='warning',access_log=False)
