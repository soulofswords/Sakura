"""Local GPU RVC bridge for Sakura. Run with rvc-runtime/Scripts/python.exe."""
from pathlib import Path
import os
import shutil
import tempfile
import threading
import sys

os.environ.pop('TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD',None)
import torch
from rvc_safe_load import install as install_restricted_checkpoints
install_restricted_checkpoints(torch,Path(__file__).resolve().parent)
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from rvc_python.infer import RVCInference
import rvc_python.infer as rvc_infer

from gpu_info import detect_gpu, pick_torch_device

BASE = Path(__file__).resolve().parent
LOCK = threading.Lock()
asset_dir = Path(rvc_infer.__file__).parent / 'base_model'
asset_dir.mkdir(exist_ok=True)
for name in ('hubert_base.pt', 'rmvpe.pt'):
    source_asset = BASE / 'rvc-assets' / name
    if not source_asset.is_file() or source_asset.stat().st_size < 1000000:
        raise RuntimeError(f'Missing RVC asset: {source_asset}')
    if not (asset_dir / name).is_file():
        shutil.copy2(source_asset, asset_dir / name)
# RMVPE's PyTorch model is used on CUDA; the optional ONNX model isn't needed.
rvc_infer.download_rvc_models = lambda _: None


def _directml_device():
    """A verified torch-directml device for AMD/Intel GPUs, or raise.

    The probe op matters: torch-directml can import fine and still fail to
    run on a driver mismatch, which must fall back to CPU rather than
    break the voice service.
    """
    import torch_directml
    device = torch_directml.device()
    (torch.ones(2, device=device) + 1).cpu()  # forces a real GPU round trip
    return device


def _force_cpu_rmvpe():
    """Pin pitch extraction (RMVPE) to CPU on DirectML machines.

    rvc-python's RMVPE routes any 'privateuseone' device to an
    onnxruntime-DML ONNX model (rmvpe.onnx via $rmvpe_root) that this
    install does not ship — /health would look healthy while the first
    conversion fails. RMVPE is a small fraction of the conversion work,
    so CPU keeps the DirectML path honest. The pipeline imports the
    symbol at call time, so replacing the module attribute is enough.
    """
    import rvc_python.lib.rmvpe as rmvpe_module

    class _CpuRmvpe(rmvpe_module.RMVPE):
        def __init__(self, model_path, is_half=True, device=None, use_jit=False):
            super().__init__(model_path, is_half=False, device='cpu:0', use_jit=use_jit)

    rmvpe_module.RMVPE = _CpuRmvpe


def _build_converter():
    vendor = detect_gpu().get('vendor', 'cpu')
    factory = _directml_device if vendor in ('amd', 'intel') else None
    device, is_directml = pick_torch_device(torch.cuda.is_available(), factory)
    # rvc-python's Config only understands cuda/mps/cpu; a DirectML device
    # string would be clobbered to CPU inside device_config. Construct on
    # CPU and re-point the shared config before any model loads.
    converter = RVCInference(models_dir=str(BASE / 'voices'),
                             device='cpu:0' if is_directml else device)
    if sys.platform == 'darwin':
        # The legacy wrapper auto-selects MPS even when CPU was requested.
        # Keep conversion predictable until full MPS inference is Mac-tested.
        converter.device = converter.config.device = 'cpu:0'
        converter.config.instead = 'cpu'
        converter.config.is_half = False
        converter.config.use_fp32_config()
        _force_cpu_rmvpe()
        device = 'cpu:0'
    if is_directml:
        config = converter.config
        config.device = str(device)  # 'privateuseone:0'
        config.instead = 'cpu'
        config.is_half = False
        config.use_fp32_config()
        # fp32 processing sizes, matching rvc-python's own CPU/DML branch.
        config.x_pad, config.x_query, config.x_center, config.x_max = 1, 6, 38, 41
        _force_cpu_rmvpe()
    return converter, device, is_directml


converter, device, is_directml = _build_converter()
app = FastAPI()
loaded_path = None

def load_voice_model(model_name: str):
    """Load one installed voice once, shared by preload and conversion routes."""
    global loaded_path
    matches = [p for p in (BASE / 'voices').glob('*/*.pth') if p.name == model_name]
    if len(matches) != 1:
        raise HTTPException(400, 'Select an installed, uniquely named voice model.')
    path = matches[0]
    if loaded_path != str(path):
        checkpoint = torch.load(str(path), map_location='cpu', weights_only=True)
        version = checkpoint.get('version', 'v1')
        del checkpoint
        indexes = list(path.parent.glob('*.index'))
        converter.load_model(str(path), version=version,
                             index_path=str(indexes[0]) if indexes else '')
        loaded_path = str(path)
    return path

@app.get('/health')
def health():
    return {'application': 'sakura-rvc', 'device': str(device),
            'directml': is_directml, 'model': loaded_path}

@app.post('/load-model')
def preload_model(model: str = Form(...)):
    """Preload a selected RVC model before microphone capture begins."""
    with LOCK:
        path = load_voice_model(model)
    return {'ok': True, 'model': path.name, 'loaded': True}

@app.post('/voice')
def voice(audio: UploadFile = File(...), model: str = Form(...),
          f0_up_key: int = Form(0), index_rate: float = Form(0.75)):
    with LOCK, tempfile.TemporaryDirectory(prefix='sakura-rvc-') as folder:
        path = load_voice_model(model)
        suffix = Path(audio.filename or 'input.wav').suffix.lower()
        if suffix not in {'.wav', '.mp3', '.ogg', '.webm', '.flac', '.m4a'}:
            suffix = '.wav'
        source = Path(folder) / f'input{suffix}'
        target = Path(folder) / 'output.wav'
        source.write_bytes(audio.file.read())
        converter.set_params(f0method='rmvpe', f0up_key=max(-12, min(12, f0_up_key)),
                             index_rate=max(0, min(1, index_rate)), protect=0.33)
        converter.infer_file(str(source), str(target))
        return Response(target.read_bytes(), media_type='audio/wav')

def main():
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=18888)

if __name__ == '__main__':main()
