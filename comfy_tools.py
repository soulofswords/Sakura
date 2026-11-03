"""Draw one image with the ComfyUI installation already on this computer.

ComfyUI holds the GPU in a different process from Sakura's language model, and a 12 GB card
cannot keep both resident, so a generation asks the local model to step aside first and hands
the card back afterwards. The step is never auto-approved: it costs minutes of the user's GPU,
writes a file, and the exact prompt, size and checkpoint are shown for review before queueing.
Only a loopback ComfyUI address is accepted, because ComfyUI has no authentication of its own.
"""
import json
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

DEFAULT_PORT = 8188
DEFAULT_BASE_URL = 'http://127.0.0.1:%d' % DEFAULT_PORT
LOOPBACK_HOSTS = {'127.0.0.1', 'localhost', '::1'}
MIN_TIMEOUT_SECONDS = 60
MAX_TIMEOUT_SECONDS = 1800
DEFAULT_TIMEOUT_SECONDS = 900
MIN_DIMENSION = 512
MAX_DIMENSION = 1536
DIMENSION_STEP = 8
MIN_STEPS = 4
MAX_STEPS = 60
MAX_BATCH = 4
MAX_PROMPT = 1200
MAX_NEGATIVE = 800
POLL_SECONDS = 0.5
SAMPLERS = ('euler', 'euler_ancestral', 'dpm_2', 'dpm_2_ancestral', 'lcm', 'heun', 'heunpp2', 'dpm_fast',
            'dpm_adaptive', 'dpmpp_2s_ancestral', 'dpmpp_sde', 'dpmpp_sde_gpu', 'dpmpp_2m', 'dpmpp_2m_sde',
            'dpmpp_2m_sde_gpu', 'dpmpp_3m_sde', 'dpmpp_3m_sde_gpu', 'ddim', 'uni_pc', 'uni_pc_bh2')
SCHEDULERS = ('normal', 'karras', 'exponential', 'sgm_uniform', 'simple', 'ddim_uniform', 'beta')


class ComfyError(ValueError):
    pass


def base_url(value=''):
    """A loopable http address for ComfyUI, or a refusal. Remote hosts are never tried."""
    import os
    candidate = str(value or os.environ.get('SAKURA_COMFY_URL') or DEFAULT_BASE_URL).strip()
    parsed = urlparse(candidate if '://' in candidate else 'http://' + candidate)
    if parsed.scheme != 'http':
        raise ComfyError('ComfyUI must be reached over plain http on this computer.')
    if (parsed.hostname or '') not in LOOPBACK_HOSTS:
        raise ComfyError('Only a ComfyUI on 127.0.0.1 or localhost is allowed, because ComfyUI has no login of its own.')
    return '%s://%s' % (parsed.scheme, parsed.netloc)


def _get(url, path, timeout=(3, 15)):
    try:
        answer = requests.get(url + path, timeout=timeout,allow_redirects=False,proxies={'http':'','https':'','all':''})
    except requests.ConnectionError:
        raise ComfyError('Nothing is answering at %s. Start ComfyUI with comfy.start.' % (url + path)) from None
    except requests.Timeout:
        raise ComfyError('ComfyUI at %s did not answer in time.' % url) from None
    if answer.status_code >= 300:
        raise ComfyError('ComfyUI answered %d at %s.' % (answer.status_code, path))
    return answer


def timeout_seconds(value):
    """How long Sakura is willing to wait for one generation."""
    if value is None:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        requested = int(value)
    except (TypeError, ValueError):
        raise ComfyError('Give the waiting time in whole seconds.') from None
    return min(max(requested, MIN_TIMEOUT_SECONDS), MAX_TIMEOUT_SECONDS)


def status(value=''):
    """Whether a ComfyUI server answers, and what it reports about the GPU."""
    url = base_url(value)
    answer = _get(url, '/system_stats', timeout=(2, 6)).json()
    system = answer.get('system', {})
    devices = [{'name': str(item.get('name', '')), 'vram_total': int(item.get('vram_total', 0)),
                'vram_free': int(item.get('vram_free', 0))} for item in answer.get('devices', [])]
    return {'reachable': True, 'url': url, 'comfyui': system.get('comfyui_version', ''),
            'python': system.get('python_version', ''), 'ram_total_gb': round(int(system.get('ram_total', 0)) / 1e9, 1),
            'ram_free_gb': round(int(system.get('ram_free', 0)) / 1e9, 1), 'gpu': devices}


def release(value=''):
    """Request cache unloading while idle; acknowledgement is not measured VRAM recovery."""
    url=base_url(value)
    queued=_get(url,'/queue').json()
    if not isinstance(queued,dict) or 'queue_running' not in queued or 'queue_pending' not in queued:
        raise ComfyError('ComfyUI did not report its queue; GPU release was not requested.')
    if queued['queue_running'] or queued['queue_pending']:
        raise ComfyError('ComfyUI has running or pending jobs. Wait until its queue is empty.')
    try:
        response=requests.post(url+'/free',json={'unload_models':True,'free_memory':True},
                               timeout=(3,15),allow_redirects=False,proxies={'http':'','https':'','all':''})
        if not 200<=response.status_code<300:
            raise ComfyError('ComfyUI rejected the GPU release request (HTTP %s).'%response.status_code)
    except requests.RequestException:
        raise ComfyError('ComfyUI could not acknowledge GPU release. Check its status.') from None
    return {'ok':True,'requested':True,'url':url,
            'message':'ComfyUI accepted a model-unload and memory-release request. Check GPU usage to confirm reclamation.'}

def checkpoints(value=''):
    """Checkpoint names ComfyUI can load, exactly as it lists them."""
    url = base_url(value)
    info = _get(url, '/object_info/CheckpointLoaderSimple').json()
    options = info.get('CheckpointLoaderSimple', {}).get('input', {}).get('required', {}).get('ckpt_name', [[]])[0]
    return [str(item) for item in options]


def release_local_models():
    """Best-effort hand of the GPU to ComfyUI; never fatal, and always reported.

    Ollama is asked what it actually has resident rather than being told to drop the model the
    settings name, because the settings can lag behind what a conversation just loaded.
    """
    moved = []
    try:
        from config import OLLAMA_BASE_URL
        loaded = requests.get(OLLAMA_BASE_URL + '/api/ps', timeout=(3, 10)).json().get('models', [])
        names = [str(item.get('name', '')) for item in loaded if item.get('name')]
        for name in names:
            requests.post(OLLAMA_BASE_URL + '/api/generate', json={'model': name, 'keep_alive': 0, 'stream': False},
                          timeout=(3, 120))
        moved.append('ollama released ' + ', '.join(names) if names else 'ollama held nothing on the GPU')
    except requests.ConnectionError:
        moved.append('ollama is not running')
    except Exception as error:
        moved.append('ollama still holds the GPU (%s)' % _reason(error))
    try:
        from agent_local_ai import local_ai
        resident = local_ai.loaded
        local_ai.unload()
        moved.append('sakura-native %s unloaded' % resident if resident else 'sakura-native held nothing on the GPU')
    except Exception as error:
        moved.append('sakura-native still holds the GPU (%s)' % _reason(error))
    return moved


def _reason(error):
    return ' '.join(str(error).split())[:120] or type(error).__name__


def plan(prompt='', negative='', width=1024, height=1024, steps=28, cfg=6.0, sampler='dpmpp_2m',
         scheduler='karras', seed=None, batch=1, checkpoint=''):
    """The exact generation as it will be queued, or a refusal naming the bad argument."""
    text = str(prompt or '').strip()
    if not text:
        raise ComfyError('Describe the image you want.')
    if len(text) > MAX_PROMPT:
        raise ComfyError('The prompt is %d characters; keep it under %d.' % (len(text), MAX_PROMPT))
    bad = str(negative or '').strip()[:MAX_NEGATIVE]
    for name, value, low, high in (('width', width, MIN_DIMENSION, MAX_DIMENSION), ('height', height, MIN_DIMENSION, MAX_DIMENSION)):
        try:
            side = int(value)
        except (TypeError, ValueError):
            raise ComfyError('%s must be a whole number of pixels.' % name) from None
        if not low <= side <= high or side % DIMENSION_STEP:
            raise ComfyError('%s must be between %d and %d and a multiple of %d.' % (name, low, high, DIMENSION_STEP))
    try:
        count = int(batch)
    except (TypeError, ValueError):
        raise ComfyError('batch must be a whole number.') from None
    if not 1 <= count <= MAX_BATCH:
        raise ComfyError('Ask for between 1 and %d images at a time.' % MAX_BATCH)
    steps = min(max(int(steps), MIN_STEPS), MAX_STEPS)
    cfg = min(max(float(cfg), 1.0), 15.0)
    if str(sampler) not in SAMPLERS:
        raise ComfyError('Sampler %r is not one ComfyUI offers here.' % sampler)
    if str(scheduler) not in SCHEDULERS:
        raise ComfyError('Scheduler %r is not one ComfyUI offers here.' % scheduler)
    chosen = int(seed) % (2 ** 64) if seed is not None else int(time.time() * 1000) % (2 ** 63)
    return {'prompt': text, 'negative': bad, 'width': int(width), 'height': int(height), 'steps': steps,
            'cfg': cfg, 'sampler': str(sampler), 'scheduler': str(scheduler), 'seed': chosen, 'batch': count,
            'checkpoint': str(checkpoint or '')}


def graph(spec, prefix='sakura'):
    """A stock-node SDXL workflow, so no custom node has to be installed for this to run."""
    loader = {'class_type': 'CheckpointLoaderSimple', '_meta': {'title': 'Checkpoint'}, 'inputs': {'ckpt_name': spec['checkpoint']}}
    return {
        '1': loader,
        '2': {'class_type': 'CLIPTextEncode', '_meta': {'title': 'Prompt'}, 'inputs': {'text': spec['prompt'], 'clip': ['1', 1]}},
        '3': {'class_type': 'CLIPTextEncode', '_meta': {'title': 'Negative'}, 'inputs': {'text': spec['negative'], 'clip': ['1', 1]}},
        '4': {'class_type': 'EmptyLatentImage', '_meta': {'title': 'Size'},
              'inputs': {'width': spec['width'], 'height': spec['height'], 'batch_size': spec['batch']}},
        '5': {'class_type': 'KSampler', '_meta': {'title': 'Sample'},
              'inputs': {'model': ['1', 0], 'positive': ['2', 0], 'negative': ['3', 0], 'latent_image': ['4', 0],
                         'seed': spec['seed'], 'steps': spec['steps'], 'cfg': spec['cfg'], 'sampler_name': spec['sampler'],
                         'scheduler': spec['scheduler'], 'denoise': 1.0}},
        '6': {'class_type': 'VAEDecode', '_meta': {'title': 'Decode'}, 'inputs': {'samples': ['5', 0], 'vae': ['1', 2]}},
        '7': {'class_type': 'SaveImage', '_meta': {'title': 'Save'}, 'inputs': {'images': ['6', 0], 'filename_prefix': prefix}},
    }


def queue(value, spec):
    """Send one workflow and return its prompt id; ComfyUI validates before it accepts."""
    url = base_url(value)
    try:
        answer = requests.post(url + '/prompt', json={'prompt': graph(spec)}, timeout=(5, 60),allow_redirects=False,proxies={'http':'','https':'','all':''})
    except requests.ConnectionError:
        raise ComfyError('Nothing is answering at %s. Start ComfyUI with comfy.start.' % url) from None
    except requests.Timeout:
        raise ComfyError('ComfyUI did not accept the workflow in time.') from None
    body = {}
    try:
        body = answer.json()
    except ValueError:
        pass
    if answer.status_code == 400:
        error = body.get('error') or {}
        raise ComfyError('ComfyUI rejected this workflow: %s %s' % (error.get('message', 'invalid prompt'),
                                                                    str(error.get('details', ''))[:300]))
    if answer.status_code >= 300:
        raise ComfyError('ComfyUI answered %d.' % answer.status_code)
    return url, str(body.get('prompt_id', '')), int(body.get('number', 0))


def await_image(url, prompt_id, budget, cancel_event=None):
    """Poll one queued workflow until it writes its images, then fetch the bytes."""
    deadline = time.time() + budget
    while True:
        if cancel_event is not None and cancel_event.is_set():
            raise ComfyError('Cancelled before ComfyUI finished this image.')
        if time.time() > deadline:
            raise ComfyError('ComfyUI was still working after %d seconds, so Sakura stopped waiting. '
                             'The image may still finish in ComfyUI; raise timeout_seconds or ask for fewer pixels.' % budget)
        history = _get(url, '/history/' + prompt_id, timeout=(3, 20)).json()
        entry = history.get(prompt_id) if isinstance(history, dict) else None
        if entry is not None:
            images = entry.get('outputs', {}).get('7', {}).get('images', [])
            if images:
                return [record for record in images if isinstance(record, dict)]
            status = entry.get('status') or {}
            if str(status.get('status_str', '')) == 'error':
                raise ComfyError('ComfyUI reported an error for this image: %s' % str(json.dumps(status)[:600]))
        time.sleep(POLL_SECONDS)


def fetch(url, record, target):
    """Download one finished image into the task workspace; existing files are never replaced."""
    path = Path(target)
    if path.exists():
        raise ComfyError('%s already exists. Name a new file for this image.' % path)
    answer = requests.get(url + '/view', params={'filename': record.get('filename', ''),
                                                 'subfolder': record.get('subfolder', ''),
                                                 'type': record.get('type', 'output')}, timeout=(5, 120),allow_redirects=False,proxies={'http':'','https':'','all':''})
    if answer.status_code >= 300:
        raise ComfyError('ComfyUI could not serve the finished image (HTTP %d).' % answer.status_code)
    if not answer.content:
        raise ComfyError('ComfyUI served an empty file.')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.part')
    temporary.write_bytes(answer.content)
    temporary.replace(path)
    return {'path': str(path), 'bytes': len(answer.content), 'comfy_name': str(record.get('filename', ''))}


def server_port(value=''):
    """The port the reviewed ComfyUI address names, so a start lines up with the read."""
    return urlparse(base_url(value)).port or DEFAULT_PORT


def launch_command(root, value=''):
    """The portable install's own interpreter and entry point, started headless.

    The leading call operator is required because Sakura hands this string to PowerShell,
    which reads a statement that starts with a quoted path as an expression, not a command.
    --windows-standalone-build is left off on purpose: it auto-opens ComfyUI's own web UI in the
    user's browser, while a Sakura task only wants the API on this machine's loopback address. That
    address is named instead of trusted to a default, because ComfyUI has no login of its own.
    """
    root = Path(str(root)).expanduser()
    python = root / 'python_embeded' / 'python.exe'
    main = root / 'ComfyUI' / 'main.py'
    if not python.is_file() or not main.is_file():
        raise ComfyError('%s is not a ComfyUI portable folder: it needs python_embeded/python.exe and ComfyUI/main.py.' % root)
    return {'cwd': str(root), 'command': '& "%s" -s "%s" --listen 127.0.0.1 --port %d' % (python, main, server_port(value)),
            'note': 'ComfyUI holds the GPU while it runs. First generation loads the checkpoint and is the slow one.'}


def installed_roots():
    """Portable ComfyUI folders this machine actually has, without assuming a drive letter."""
    import os
    candidates = [os.environ.get('SAKURA_COMFY_DIR', '')]
    for drive in ('C:\\', 'D:\\', 'E:\\', 'F:\\', 'G:\\'):
        for leaf in (Path('AI') / 'ComfyUI_windows_portable', 'ComfyUI_windows_portable', Path('Programs') / 'ComfyUI'):
            candidates.append(str(Path(drive) / leaf))
    found = []
    for item in candidates:
        if not item:
            continue
        path = Path(item).expanduser()
        if (path / 'python_embeded' / 'python.exe').is_file() and (path / 'ComfyUI' / 'main.py').is_file():
            found.append(str(path.resolve()))
    return found


def available():
    """Whether the image tools can be offered at all on this PC.

    A ComfyUI started from a plain source checkout is invisible here unless SAKURA_COMFY_URL names
    it, because asking that server would mean a network call on every planner pass.
    """
    import os
    return bool(installed_roots()) or bool(str(os.environ.get('SAKURA_COMFY_URL', '')).strip())
