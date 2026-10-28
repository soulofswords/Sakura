"""Pinned optional inference runtimes; downloads never include model weights."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import zipfile

import requests

LLAMA_RELEASE = 'b11899'
COLIBRI_RELEASE = 'v2.0.0'
ASSETS = {
    ('llama.cpp', 'vulkan'): [('llama-b11899-bin-win-vulkan-x64.zip', 'abce1ade0ef7701aebb9e6ec35def26cd2c8920cfb8e344071f51b3f4867ee0a')],
    ('llama.cpp', 'cuda'): [
        ('llama-b11899-bin-win-cuda-12.4-x64.zip', '2a8489f05eae2443c5dc6e84b134ac50fa0bf6962792a99e0cd00816fa982147'),
        ('cudart-llama-bin-win-cuda-12.4-x64.zip', '8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6')],
    ('colibri', 'vulkan'): [('colibri-v2.0.0-windows-x86_64.zip', 'fdb8ea2fad7dcfe44d9d37bfb3e444f1299207f268ab499719f98bd772397d79')],
}


def extract(package, stage):
    with zipfile.ZipFile(package) as archive:
        if sum(x.file_size for x in archive.infolist()) > 3_000_000_000:
            raise ValueError('Runtime archive is too large.')
        for info in archive.infolist():
            name = PurePosixPath(info.filename.replace('\\', '/'))
            if name.is_absolute() or '..' in name.parts or ':' in str(name) or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Unsafe runtime archive.')
            target = stage / str(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            if info.is_dir():
                target.mkdir(exist_ok=True)
            else:
                with archive.open(info) as source, target.open('wb') as output:
                    shutil.copyfileobj(source, output)


def install(root, engine, backend, progress):
    assets = ASSETS.get((engine, backend))
    if not assets:
        raise ValueError('Choose llama.cpp CUDA/Vulkan, or Colibri Vulkan. Qwen3.8 has no Windows CUDA release yet.')
    # A Toolkit is optional. Reuse its existing CUDA 12 DLLs when present;
    # otherwise the pinned NVIDIA runtime bundle supplies them app-locally.
    cuda_bin = Path(os.environ.get('CUDA_PATH', '')) / 'bin'
    cuda_dlls = ('cudart64_12.dll', 'cublas64_12.dll', 'cublasLt64_12.dll')
    system_cuda = engine == 'llama.cpp' and backend == 'cuda' and all((cuda_bin / name).is_file() for name in cuda_dlls)
    if system_cuda:
        assets = assets[:1]
    destination = root / ('colibri-runtime' if engine == 'colibri' else 'runtime-' + backend)
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root, prefix='inference-') as temporary:
        stage = Path(temporary) / 'stage'
        stage.mkdir()
        repository = 'JustVugg/colibri' if engine == 'colibri' else 'ggml-org/llama.cpp'
        release = COLIBRI_RELEASE if engine == 'colibri' else LLAMA_RELEASE
        for index, (name, expected) in enumerate(assets):
            archive = Path(temporary) / name
            digest = hashlib.sha256()
            total = 0
            url = f'https://github.com/{repository}/releases/download/{release}/{name}'
            with requests.get(url, stream=True, timeout=(15, 120)) as response:
                response.raise_for_status()
                length = int(response.headers.get('Content-Length', 0))
                with archive.open('wb') as output:
                    for chunk in response.iter_content(1024 * 1024):
                        total += len(chunk)
                        if total > 800_000_000:
                            raise ValueError('Runtime download exceeded its size limit.')
                        output.write(chunk)
                        digest.update(chunk)
                        progress(round(100 * (index + total / length) / len(assets), 1) if length else None)
            if digest.hexdigest() != expected:
                raise ValueError('Runtime checksum failed. Nothing was installed.')
            extract(archive, stage)
        binary = next(stage.rglob('coli' if engine == 'colibri' else 'llama-server.exe'), None)
        if binary is None:
            raise ValueError('Runtime archive is missing its launcher.')
        if system_cuda:
            for name in cuda_dlls:
                shutil.copy2(cuda_bin / name, binary.parent / name)
        destination.mkdir(exist_ok=True)
        shutil.copytree(binary.parent, destination, dirs_exist_ok=True)
        (destination / 'Sakura-runtime.json').write_text(json.dumps({'engine': engine, 'backend': backend, 'release': release, 'assets': assets, 'reused_cuda_toolkit': system_cuda}), encoding='utf-8')
    return destination


def colibri_model(path):
    folder = Path(str(path)).expanduser().resolve(strict=True)
    if not folder.is_dir():
        raise ValueError('Choose a supported Colibri model folder containing config.json and safetensors weights.')
    config_path = folder / 'config.json'
    if config_path.stat().st_size > 4_000_000:
        raise ValueError('Model configuration is too large.')
    config = json.loads(config_path.read_text(encoding='utf-8'))
    if not isinstance(config, dict):
        raise ValueError('Model configuration must be an object.')
    kind = config.get('model_type')
    text = config.get('text_config') or config
    if not isinstance(text, dict):
        raise ValueError('Invalid model text configuration.')
    if kind in ('qwen3_5_moe', 'qwen3_5_moe_text') or text.get('model_type') in ('qwen3_5_moe', 'qwen3_5_moe_text'):
        meta_path = folder / 'qwen36_meta.json'
        if not meta_path.is_file() or meta_path.stat().st_size > 4_000_000:
            raise ValueError('Choose a converted Qwen3.6 Colibri container, including qwen36_meta.json; raw Transformers weights are not supported here.')
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        layers = text.get('num_hidden_layers')
        if not isinstance(meta, dict) or type(layers) is not int or not 1 <= layers <= 256 or meta.get('n_layers') != layers:
            raise ValueError('Colibri metadata does not match the model layers.')
        shards = [folder / ('model-%05d.safetensors' % n) for n in range(layers)] + [folder / 'model-globals.safetensors']
        vision = bool(meta.get('vision'))
        if vision:shards.append(folder / 'model-vision.safetensors')
        size = 0
        for shard in shards:
            resolved = shard.resolve(strict=True)
            if resolved.parent != folder or not resolved.is_file() or resolved.stat().st_size < 8:
                raise ValueError('A converted model shard is missing or invalid.')
            size += resolved.stat().st_size
        if not (folder / 'tokenizer.json').is_file():raise ValueError('The model tokenizer is missing.')
        return folder, size, vision
    if kind not in ('qwen4_exp', 'qwen4_exp_text') and text.get('model_type') not in ('qwen4_exp', 'qwen4_exp_text'):
        raise ValueError('This Colibri integration supports Qwen3.6 converted containers and Qwen3.8-Flash-Next safetensors folders. Use GGUF for other models.')
    index = folder / 'model.safetensors.index.json'
    if not index.is_file() or index.stat().st_size > 32_000_000:
        raise ValueError('The model shard index is missing or too large.')
    weights = json.loads(index.read_text(encoding='utf-8')).get('weight_map')
    if not isinstance(weights, dict) or not weights:
        raise ValueError('The model shard index is empty.')
    if not all(isinstance(name, str) for name in weights.values()):
        raise ValueError('Unsafe model shard path.')
    shards = set(weights.values())
    size = 0
    for name in shards:
        if not isinstance(name, str) or not name.endswith('.safetensors') or Path(name).name != name or '/' in name or '\\' in name or ':' in name:
            raise ValueError('Unsafe model shard path.')
        file = (folder / name).resolve(strict=True)
        if file.parent != folder or not file.is_file() or file.stat().st_size < 8:
            raise ValueError('A model shard is missing or invalid.')
        size += file.stat().st_size
    if not (folder / 'tokenizer.json').is_file():
        raise ValueError('The model tokenizer is missing.')
    return folder, size, bool(config.get('vision_config'))
