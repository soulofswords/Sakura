"""Bounded, read-only local model identification. Never imports model code."""
import json
import os
from pathlib import Path
import re
import struct
import time

from inference_engines import colibri_model

# Architecture names from llama.cpp b11899 src/llama-arch.cpp (our pinned engine).
ARCHITECTURES = set('clip llama llama4 deci falcon grok gpt2 gptj gptneox mpt baichuan starcoder refact bert modern-bert nomic-bert nomic-bert-moe neo-bert jina-bert-v2 jina-bert-v3 eurobert bloom stablelm qwen qwen2 qwen2moe qwen2vl sensenova_u1 qwen3 flint qwen3moe qwen3next qwen3vl qwen3vlmoe qwen35 qwen35moe clef vllm-decision2 qwen4exp phi2 phi3 phimoe plamo plamo2 plamo3 codeshell orion internlm2 minicpm minicpm3 gemma gemma2 gemma3 gemma3n gemma4 gemma4-assistant gemma-embedding gemma-embedding2 starcoder2 mamba mamba2 maple jamba falcon-h1 xverse command-r cohere2 cohere2moe dbrx olmo olmo2 olmoe muse-glimmer muse-spark openelm arctic deepseek deepseek2 deepseek2-ocr deepseek32 deepseek4 deepseek41 chatglm glm4 glm4moe glm-dsa bitnet t5 t5encoder jais jais2 nemotron nemotron_h nemotron_h_moe exaone exaone4 exaone-moe rwkv6 rwkv6qwen2 rwkv7 arwkv7 granite granitemoe granitehybrid graniteswitch granite_swa chameleon wavtokenizer-dec plm bailingmoe bailingmoe2 bailingmoe3 dots1 dots3note arcee afmoe laguna ernie4_5 ernie4_5-moe hunyuan-moe hunyuan-dense hunyuan_vl hy_v3 hy_v4 smollm3 gpt-oss lfm2 lfm2moe dream smallthinker llada llada-moe seed_oss grovemoe apertus minimax-01 hrm_text minimax-m2 minimax-m3 cogvlm rnd1 pangu-embedded mistral3 eagle3 dflash mistral4 paddleocr mimo2 step35 spark2_5 llama-embed maincoder maion-coder kimi-linear kimi-k3 glm5-next talkie mellum nanbeige qwen3tts pockettts k2-horizon beam kolibri1'.split())
ENCODERS = {'bert', 'modern-bert', 'nomic-bert', 'nomic-bert-moe', 'neo-bert', 'jina-bert-v2', 'jina-bert-v3', 'eurobert', 't5encoder', 'gemma-embedding', 'gemma-embedding2', 'llama-embed'}
FORMATS = {0:'B', 1:'b', 2:'H', 3:'h', 4:'I', 5:'i', 6:'f', 7:'?', 10:'Q', 11:'q', 12:'d'}


def gguf_metadata(path):
    size = path.stat().st_size
    with path.open('rb') as file:
        limit = min(size, 64 * 1024 * 1024)
        def read(count):
            if count < 0 or file.tell() + count > limit:
                raise ValueError('Incomplete GGUF header or metadata exceeds the 64 MB inspection limit.')
            result = file.read(count)
            if len(result) != count:raise ValueError('Truncated GGUF header.')
            return result
        def number(fmt):return struct.unpack('<' + fmt, read(struct.calcsize('<' + fmt)))[0]
        def string(keep=True):
            count = number('Q')
            if count > 1_048_576:raise ValueError('GGUF metadata string is too large.')
            if keep:return read(count).decode('utf-8', errors='replace')
            if file.tell() + count > limit:raise ValueError('Truncated GGUF metadata.')
            file.seek(count, 1)
        def value(kind, keep, depth=0):
            if kind in FORMATS:
                result = number(FORMATS[kind]);return result if keep else None
            if kind == 8:return string(keep)
            if kind != 9 or depth > 1:raise ValueError('Unsupported GGUF metadata type.')
            subtype, count = number('I'), number('Q')
            if count > 2_000_000:raise ValueError('GGUF metadata array is too large.')
            if subtype in FORMATS:
                length = struct.calcsize('<' + FORMATS[subtype]) * count
                if file.tell() + length > limit:raise ValueError('Truncated GGUF metadata array.')
                file.seek(length, 1)
            elif subtype == 8:
                for _ in range(count):string(False)
            else:raise ValueError('Unsupported GGUF metadata array.')
        if read(4) != b'GGUF':raise ValueError('Not a GGUF file.')
        version = number('I')
        if version not in (2, 3):raise ValueError('Unsupported GGUF version.')
        tensors, count = number('Q'), number('Q')
        if not 0 < tensors <= 1_000_000 or count > 100_000:raise ValueError('Invalid GGUF tensor or metadata count.')
        result = {}
        for _ in range(count):
            key = string();kind = number('I')
            item = value(kind, key.startswith(('general.', 'split.', 'clip.')))
            if item is not None:result[key] = item
        # Ensure tensor directory and each tensor's starting position exist.
        offsets, parameters = [], 0
        for _ in range(tensors):
            string(False);dimensions = number('I')
            if not 1 <= dimensions <= 4:raise ValueError('Invalid GGUF tensor dimensions.')
            elements = 1
            for _ in range(dimensions):
                length = number('Q')
                if length == 0 or length > 2**40:raise ValueError('Invalid GGUF tensor size.')
                elements *= length
            parameters += elements
            number('I');offsets.append(number('Q'))
        alignment = result.get('general.alignment', 32)
        if type(alignment) is not int or not 1 <= alignment <= 4096:raise ValueError('Invalid GGUF alignment.')
        start = (file.tell() + alignment - 1) // alignment * alignment
        if any(start + offset >= size for offset in offsets):raise ValueError('GGUF tensor data is missing or truncated.')
        result['inspected.parameters'] = parameters
        return result


def inspect_model(path):
    source = Path(path).resolve(strict=True)
    row = {'path': str(source), 'name': source.name, 'can_add': False, 'status': 'unsupported', 'engine': '', 'projector': False}
    try:
        if source.is_dir():
            config_path = source / 'config.json'
            if config_path.stat().st_size > 4_000_000:raise ValueError('Model configuration is too large.')
            config = json.loads(config_path.read_text(encoding='utf-8'))
            if not isinstance(config, dict):raise ValueError('Invalid model configuration.')
            text = config.get('text_config') or config
            row.update(format='Safetensors / Transformers', architecture=str(config.get('model_type', 'unknown'))[:120], name=str(config.get('_name_or_path') or source.name)[:180])
            if row['architecture'] in ('qwen4_exp', 'qwen4_exp_text', 'qwen3_5_moe', 'qwen3_5_moe_text') or isinstance(text, dict) and text.get('model_type') in ('qwen4_exp', 'qwen4_exp_text', 'qwen3_5_moe', 'qwen3_5_moe_text'):
                _, size, vision = colibri_model(source)
                row.update(name='Qwen3.6-35B-A3B' if (source/'qwen36_meta.json').is_file() else 'Qwen3.8-Flash-Next', engine='colibri', bytes=size, can_add=True, status='supported', vision=vision, message='Supported Colibri model folder. Use Vulkan on Windows. Loading must verify runtime and available memory.')
            else:row['message']='Identified Transformers weights. Sakura currently requires GGUF for this architecture; convert or obtain a compatible GGUF release.'
            return row
        row.update(bytes=source.stat().st_size, format='GGUF')
        meta = gguf_metadata(source)
        arch = meta.get('general.architecture', '')
        row.update(name=str(meta.get('general.name') or source.name)[:180], architecture=str(arch)[:120], size_label=str(meta.get('general.size_label', ''))[:80], quantization=meta.get('general.file_type'), engine='llama.cpp')
        projector = arch == 'clip' or meta.get('general.type') == 'mmproj'
        row['projector'] = projector
        row['parameter_count'] = meta.get('inspected.parameters')
        if not meta.get('general.name'):
            display = {'qwen3vl':'Qwen3-VL', 'qwen3':'Qwen3', 'qwen2':'Qwen2', 'llama':'Llama', 'clip':'Vision projector'}.get(arch, str(arch) or source.name)
            row['name'] = display + (' · %.2fB tensor parameters' % (row['parameter_count']/1e9) if row['parameter_count'] else '')
        if meta.get('split.count', 1) != 1 or re.search(r'-\d{5}-of-\d{5}', source.name):
            row['message']='Split GGUF sets are not supported by this importer. Choose a single-file quantization.'
        elif arch in ENCODERS or meta.get('general.type') in ('adapter', 'vocab'):
            row['message']='This is an encoder, adapter or vocabulary file, not a standalone chat model.'
        elif arch in ARCHITECTURES:
            row.update(can_add=True, status='supported', message='Supported GGUF architecture. '+('Add as a vision projector and pair it with its matching language model.' if projector else 'Loading must verify this file, runtime and available RAM/VRAM. Vision may require a matching projector.'))
        else:row.update(status='unverified', message='GGUF found, but its architecture is not verified for Sakura’s pinned engine. Choose a supported release or update the engine.')
    except (OSError, ValueError, TypeError, struct.error) as error:
        row.update(status='incomplete', message=str(error)[:300])
    return row


def inspect_folder(path):
    if not isinstance(path, str) or not path.strip():raise ValueError('Enter the full local model folder path.')
    root = Path(path).expanduser().resolve(strict=True)
    if not root.is_dir():raise ValueError('Choose a model folder.')
    rows, warnings, queue = [], [], [(root, 0)]
    visited, started = 0, time.monotonic()
    while queue and len(rows) < 100 and visited < 5000 and time.monotonic() - started < 8:
        folder, depth = queue.pop(0)
        try:
            if (folder / 'config.json').is_file():rows.append(inspect_model(folder))
            with os.scandir(folder) as entries:
                for entry in entries:
                    visited += 1
                    if visited >= 5000 or len(rows) >= 100 or time.monotonic() - started >= 8:break
                    info = entry.stat(follow_symlinks=False)
                    if entry.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:continue
                    candidate = Path(entry.path)
                    if entry.is_dir(follow_symlinks=False):
                        if depth < 3 and entry.name not in ('.git', '__pycache__', '.cache'):queue.append((candidate, depth + 1))
                    elif entry.is_file(follow_symlinks=False) and candidate.suffix.lower() in ('.pth', '.pt', '.safetensors') and not (folder/'config.json').is_file():
                        if not any(row.get('path') == str(folder) for row in rows):rows.append({'path':str(folder),'name':folder.name,'format':'PyTorch / Safetensors','can_add':False,'status':'unsupported','message':'Raw weights found without a supported model configuration. Obtain a complete GGUF release, or the supported Colibri model folder.'})
                    elif entry.is_file(follow_symlinks=False) and (candidate.suffix.lower() in ('.gguf', '.bin', '') or candidate.name.startswith('sha256-')):
                        with candidate.open('rb') as file:magic = file.read(4)
                        if magic == b'GGUF' or candidate.suffix.lower() == '.gguf':rows.append(inspect_model(candidate))
        except OSError:warnings.append('Could not inspect ' + folder.name + '. Check file permissions.')
    if queue or visited >= 5000 or len(rows) >= 100 or time.monotonic() - started >= 8:warnings.append('Scan limit reached. Select a more specific model folder to inspect the remaining files.')
    return {'folder': str(root), 'models': rows, 'warnings': warnings, 'message': 'Metadata compatibility check only. Use Load model to verify execution and hardware capacity.'}
