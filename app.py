"""
🌸 Sakura — GUI Backend (FastAPI + Uvicorn)
Run:  python app.py
Opens a browser window with the 3D anime assistant.
"""
import os
import asyncio
import sys
import glob
import tempfile
import uuid
import webbrowser
import mimetypes
from pathlib import Path
from contextlib import asynccontextmanager

# Windows registry MIME mappings can identify .mjs as text/plain. ES modules
# and the tracking WASM runtime require their correct browser content types.
mimetypes.add_type('application/javascript', '.mjs')
mimetypes.add_type('application/wasm', '.wasm')

# Configure UTF-8 encoding safely on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
import re
import uvicorn
import gui_server
from product import EDITION, INSTALLATION_ID
from credentials import get_gemini_key, set_gemini_key

from config import BASE_DIR, AUDIO_DIR, MODELS_DIR, VOICES_DIR, OLLAMA_MODEL, VOICE_PRESETS, RVC_SERVER_URL, OLLAMA_VISION_MODEL, canonical_voice_id, DEFAULT_VOICE_ID
from tts import speech_notice

# Directories
STATIC_DIR = BASE_DIR / "static"
SETTINGS_FILE = BASE_DIR / "settings.json"
MODELS_DIR.mkdir(exist_ok=True)
VOICES_DIR.mkdir(exist_ok=True)

def scan_rvc_models():
    """Scan the voices/ directory for subfolders with .pth and optional .index files."""
    models = []
    if not VOICES_DIR.exists():
        return models
    for item in VOICES_DIR.iterdir():
        if item.is_dir():
            pths = list(item.glob("*.pth"))
            if pths:
                pth_file = pths[0]
                indexes = list(item.glob("*.index"))
                index_file = indexes[0] if indexes else None
                models.append({
                    "id": f"rvc_{item.name.lower()}",
                    "name": f"🎤 [RVC] {item.name.capitalize()}",
                    "character": item.name,
                    "pth": str(pth_file.relative_to(BASE_DIR)).replace("\\", "/"),
                    "index": str(index_file.relative_to(BASE_DIR)).replace("\\", "/") if index_file else None,
                    "has_index": index_file is not None,
                })
    return models

def get_settings():
    default = {
        "llm_provider": "ollama",
        "ollama_model": OLLAMA_MODEL,
        "ollama_models_folder": "",
        "ollama_context": 4096,
        "gemini_fallback_enabled": False,
        "local_timeout": 20,
        "gemini_model": "gemini-flash-latest",
        "cloud_model": "", "cloud_endpoint": "", "cloud_vision": False,
        "last_cloud_provider": "gemini",
        "assistant_name": "Sakura",
        "vtuber_name": "Sakura",
        "avatar_presentation": "auto",
        "user_title": "Master",
        "wake_word": "hey sakura",
        "wake_word_enabled": False,
        "computer_control_enabled": False,
        "selected_voice": "kokoro_af_heart",
        "tts_pitch": "+0Hz",
        "tts_rate": "+0%",
        "selected_model": "pmx/evelyn/model.pmx",
        "rvc_model": "",
        "rvc_index": "",
        "rvc_pitch": 0,
        "rvc_index_rate": 0.75,
        "env_color": "#ff6ea7",
        "env_intensity": 1.0,
        "env_rgb_breathing": False,
        "preserve_configuration_on_reinstall": True,
    }
    if SETTINGS_FILE.exists():
        try:
            import json
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            default.update(data)
        except Exception:
            pass
    # The unified app moved into Sakura/. Keep the existing bundled model
    # selection valid after that move without changing custom external stores.
    old_store = BASE_DIR.parent / 'llm-models'
    local_store = BASE_DIR / 'llm-models'
    if default.get('ollama_models_folder') and Path(default['ollama_models_folder']) == old_store and local_store.is_dir():
        default['ollama_models_folder'] = str(local_store)
    if EDITION == 'vtuber':default['vtuber_tracking_only']=True
    default['product_edition']=EDITION
    default['selected_voice']=canonical_voice_id(default.get('selected_voice',DEFAULT_VOICE_ID))
    return default

def save_settings(data: dict):
    import json
    cur = get_settings()
    data = {key: value for key, value in data.items() if key not in ("gemini_api_key", "gemini_key_set", "clear_gemini_key", "api_key", "cloud_api_key", "cloud_key_set", "clear_cloud_key")}
    for secret in ('gemini_api_key','api_key','cloud_api_key'):cur.pop(secret,None)
    cur.update(data)
    if cur.get('llm_provider') not in ('ollama','auto'):cur['last_cloud_provider']=cur['llm_provider']
    cur['selected_voice']=canonical_voice_id(cur.get('selected_voice',DEFAULT_VOICE_ID))
    SETTINGS_FILE.write_text(json.dumps(cur, indent=2), encoding="utf-8")
    return cur

def public_settings(settings):
    result = {key: value for key, value in settings.items() if key not in ('gemini_api_key','api_key','cloud_api_key')}
    try:
        result["gemini_key_set"] = bool(get_gemini_key())
    except OSError:
        result["gemini_key_set"] = False
    from credentials import get_cloud_key
    try:result['cloud_key_set']=bool(get_cloud_key(settings.get('llm_provider',''),settings.get('cloud_endpoint','')))
    except (OSError,ValueError):result['cloud_key_set']=False
    return result


def configure_saved_ai(model,settings):
    provider=settings.get('llm_provider','ollama')
    if provider in ('ollama','gemini'):
        model.configure_provider(provider,settings.get('gemini_model','gemini-flash-latest'),get_gemini_key())
    else:
        from credentials import get_cloud_key
        model.configure_cloud(provider,settings.get('cloud_model',''),get_cloud_key(provider,settings.get('cloud_endpoint','')),settings.get('cloud_endpoint',''),settings.get('cloud_vision',False))


# ── globals ────────────────────────────────────────────────────
llm = None
tts = None
stt = None
stt_task = None
stt_loader = None


async def sync_selected_rvc_service():
    from rvc_manager import ensure_rvc_service, stop_rvc_service
    if tts and tts.rvc_model and not getattr(app.state, 'tracking_only', False):
        await run_in_threadpool(ensure_rvc_service)
    else:
        await run_in_threadpool(stop_rvc_service)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global llm, tts, stt, stt_task, stt_loader
    print("\n⏳ Loading components…")

    from tts import TextToSpeech
    if EDITION=='vtuber':
        llm=None
    else:
        from llm import LLM
        llm=LLM()
    cfg = get_settings()
    startup_mode = os.environ.pop('SAKURA_START_MODE', '')
    if EDITION=='vtuber':startup_mode='vtuber'
    startup_key = os.environ.pop('SAKURA_START_GEMINI_KEY', '')
    if startup_mode in ('local', 'gemini', 'vtuber'):
        changes = {'vtuber_tracking_only': startup_mode == 'vtuber'}
        if startup_mode != 'vtuber':
            changes['llm_provider'] = (cfg.get('llm_provider','gemini') if cfg.get('llm_provider')!='ollama' else cfg.get('last_cloud_provider','gemini')) if startup_mode=='gemini' else 'ollama'
        if startup_mode == 'local':
            # Choosing Local is an explicit local-only session, even if an
            # earlier session enabled the optional cloud fallback.
            changes['gemini_fallback_enabled'] = False
        if startup_mode == 'gemini' and startup_key:
            from cloud_api import detect_provider, PROVIDERS
            from credentials import set_cloud_key
            chosen=os.environ.pop('SAKURA_START_API_PROVIDER','auto')
            provider=detect_provider(startup_key) if chosen=='auto' else chosen
            changes['llm_provider']=provider
            startup_model=os.environ.pop('SAKURA_START_CLOUD_MODEL','').strip()
            if provider=='gemini':
                if startup_model and re.fullmatch(r'[A-Za-z0-9._-]{1,100}',startup_model):changes['gemini_model']=startup_model
                set_gemini_key(startup_key)
            else:
                changes.update(cloud_model=startup_model or (cfg.get('cloud_model','') if cfg.get('llm_provider')==provider else PROVIDERS[provider][1]),cloud_endpoint=PROVIDERS[provider][0],cloud_vision=PROVIDERS[provider][2])
                set_cloud_key(provider,startup_key)
        cfg = save_settings(changes)
    _app.state.startup_mode = startup_mode
    try:
        gemini_key = get_gemini_key() if EDITION!='vtuber' else ''
    except OSError:
        gemini_key = ''
    if llm:configure_saved_ai(llm,cfg)
    _app.state.tracking_only = bool(cfg.get('vtuber_tracking_only', False))
    _app.state.ai_unloaded = _app.state.tracking_only
    if not _app.state.tracking_only and cfg['llm_provider'] == 'ollama':
        try:
            await run_in_threadpool(llm.configure_local, cfg['ollama_model'], cfg['ollama_models_folder'] if cfg['llm_provider'] == 'ollama' else '',
                cfg['gemini_fallback_enabled'], cfg['ollama_context'], cfg['local_timeout'])
        except ValueError as exc:
            print(f'  Local model folder unavailable: {exc}')
            await run_in_threadpool(llm.configure_local, cfg['ollama_model'], '',
                cfg['gemini_fallback_enabled'], cfg['ollama_context'], cfg['local_timeout'])
    if llm:
        llm.tracking_only = _app.state.tracking_only
        llm.set_assistant_name(cfg.get("assistant_name", "Sakura"))
        llm.set_vtuber_name(cfg.get('vtuber_name','Sakura'))
        llm.avatar_presentation=cfg.get('avatar_presentation','auto')
    _app.state.llm_warmup = None if _app.state.tracking_only else asyncio.create_task(asyncio.to_thread(llm.warmup))
    tts = TextToSpeech()

    # Apply saved voice settings
    v_id = cfg.get("selected_voice", "kokoro_af_heart")
    from config import voice_language
    if llm:llm.reply_language = voice_language(v_id)
    tts.set_voice_preset(v_id, cfg.get("tts_pitch"), cfg.get("tts_rate"))
    if v_id.startswith("rvc_") and cfg.get("rvc_model"):
        pth_path = str(BASE_DIR / cfg["rvc_model"])
        idx_path = str(BASE_DIR / cfg["rvc_index"]) if cfg.get("rvc_index") else None
        if Path(pth_path).is_file():
            tts.set_rvc_model(
                pth_path,
                idx_path if not idx_path or Path(idx_path).is_file() else None,
                pitch=cfg.get("rvc_pitch", 0),
                index_rate=cfg.get("rvc_index_rate", 0.75),
            )
        else:
            print(f"  ⚠️ Saved voice model is missing: {pth_path}. Falling back to Sakura voice.")
            tts.set_voice_preset("kokoro_af_heart", cfg.get("tts_pitch"), cfg.get("tts_rate"))

    try:
        await sync_selected_rvc_service()
    except RuntimeError as exc:
        print(f'  RVC startup: {exc}', flush=True)

    # STT is optional for GUI (browser can record → send audio)
    def load_stt():
        global stt
        try:
            from stt import SpeechToText
            stt = SpeechToText()
        except Exception as exc:
            print(f"  ⚠️  STT unavailable (voice input disabled): {exc}")
            stt = None
    stt_loader = load_stt
    # Avoid initializing native Whisper libraries during Qt window startup.
    # In desktop mode, load them only when microphone audio is submitted.
    stt_task = None if os.environ.get('SAKURA_DESKTOP') == '1' or _app.state.tracking_only else asyncio.create_task(asyncio.to_thread(load_stt))

    print("\n✅ All systems go!")
    print(f"🌐 Open  {gui_server.url()}  in your browser\n")

    # Auto-open browser
    if os.environ.get('SAKURA_DESKTOP') != '1':
        webbrowser.open(gui_server.url())

    try:
        yield
    finally:
        from screen_audio import listener as audio_listener
        await run_in_threadpool(audio_listener.stop)
        from mobile_link import link as phone_link
        phone_link.stop()
        from spout_output import output as spout_sender
        await run_in_threadpool(spout_sender.stop)
        from rvc_manager import stop_rvc_service
        await run_in_threadpool(stop_rvc_service)
        from youtube_chat import chat as youtube_inbox
        await run_in_threadpool(youtube_inbox.stop)
        from ollama_runtime import stop
        await run_in_threadpool(stop)


app = FastAPI(title="Sakura", lifespan=lifespan)

@app.get('/api/reminders')
async def list_reminders():
    if EDITION=='vtuber' or getattr(app.state,'tracking_only',False):
        return JSONResponse({'error':'Timers and alarms are available in Companion mode.'},409)
    from assistant_reminders import reminders
    return {'items':await run_in_threadpool(reminders.list)}

@app.post('/api/reminders/dismiss')
async def dismiss_reminder(payload:dict):
    if EDITION=='vtuber' or getattr(app.state,'tracking_only',False):
        return JSONResponse({'error':'Timers and alarms are available in Companion mode.'},409)
    from assistant_reminders import reminders
    return {'ok':await run_in_threadpool(reminders.dismiss,str(payload.get('id','')),payload.get('snooze') is True)}

@app.middleware('http')
async def tracking_only_guard(request, call_next):
    # Loading the local speech engine is shared by Chat Reader and voice
    # changer; it does not enable AI replies in the tracking-only product.
    if request.url.path=='/api/tts/kokoro':return await call_next(request)
    if EDITION=='vtuber' and (request.url.path in ('/api/chat','/api/clear','/api/memory/refresh','/api/vtuber/connect','/api/vtuber/reply') or request.url.path.startswith(('/api/ollama','/api/local','/api/vision','/api/tts/'))):
        return JSONResponse({'error':'This feature is not available in Sakura VTuber.'},409)
    if request.url.path.startswith('/api/screen-audio') and (EDITION=='vtuber' or getattr(app.state, 'tracking_only', False)):
        return JSONResponse({'error': 'Screen audio is only available in AI modes.'}, 409)
    blocked = ('/api/tts/', '/api/vision')
    ai_request = request.url.path in ('/api/chat', '/api/stt', '/api/vtuber/connect', '/api/vtuber/reply') or request.url.path.startswith(blocked)
    if getattr(app.state, 'tracking_only', False) and ai_request:
        return JSONResponse({'error': 'AI and speech are paused in VTuber mode. Stop tracking to use AI VTuber.'}, 409)
    return await call_next(request)

@app.get('/api/screen-audio/sources')
async def screen_audio_sources():
    from screen_audio import sources
    try:
        return {'sources': await run_in_threadpool(sources)}
    except Exception as error:
        return JSONResponse({'error': str(error)}, 503)


@app.post('/api/screen-audio')
async def screen_audio_control(payload: dict):
    global stt_task
    from screen_audio import listener
    if type(payload.get('enabled')) is not bool or type(payload.get('paused', False)) is not bool:
        return JSONResponse({'error': 'enabled and paused must be true or false'}, 400)
    if not payload['enabled']:
        return await run_in_threadpool(lambda: listener.configure(False, [], False, None))
    if stt is None and stt_task is None and stt_loader is not None:
        stt_task = asyncio.create_task(asyncio.to_thread(stt_loader))
    if stt is None and stt_task is not None and not stt_task.done():
        await asyncio.shield(stt_task)
    if stt is None:
        return JSONResponse({'error': 'Speech recognition is unavailable.'}, 503)
    try:
        selected = payload.get('sources', ['default-output'])
        if payload.get('computer_only') is True or getattr(app.state, 'ai_vtuber_audio', False):
            from screen_audio import sources
            outputs = {source['id'] for source in await run_in_threadpool(sources) if source.get('kind') == 'output'}
            if not isinstance(selected, list) or any(source not in outputs for source in selected):
                raise ValueError('AI VTuber accepts computer playback audio only, not microphones.')
        return await run_in_threadpool(listener.configure, True, selected,
                                       payload.get('paused', False), stt.transcribe)
    except ValueError as error:
        return JSONResponse({'error': str(error)}, 400)
    except Exception as error:
        return JSONResponse({'error': str(error)}, 503)


@app.get('/api/spout/status')
async def spout_status():
    from spout_output import output
    return output.status()

@app.get('/api/tracking/nvidia-sdk')
async def nvidia_sdk_status():
    from nvidia_ar_setup import sdk_status
    return await run_in_threadpool(sdk_status,get_settings().get('nvidia_ar_sdk_folder',''))

@app.post('/api/spout/configure')
async def configure_spout(payload: dict):
    from spout_output import output
    if type(payload.get('enabled')) is not bool:
        return JSONResponse({'error':'enabled must be true or false'},400)
    try:
        return await run_in_threadpool(output.configure,payload['enabled'],payload.get('name','Sakura'))
    except ValueError as error:return JSONResponse({'error':str(error)},400)

@app.post('/api/spout/frame')
async def spout_frame(request: Request, width: int, height: int):
    from spout_output import output
    if not 1<=width<=1280 or not 1<=height<=1280:return JSONResponse({'error':'Invalid frame dimensions'},400)
    expected=width*height*4;pixels=bytearray()
    async for chunk in request.stream():
        if len(pixels)+len(chunk)>expected:return JSONResponse({'error':'Frame exceeds expected size'},400)
        pixels.extend(chunk)
    try:
        output.submit(request.headers.get('x-spout-session',''),bytes(pixels),width,height)
        return {'ok':True,'frames':output.sent}
    except ValueError as error:return JSONResponse({'error':str(error)},409)

@app.post('/api/tracking/mode')
async def set_tracking_mode(payload: dict):
    global stt, stt_task
    enabled = payload.get('enabled')
    if type(enabled) is not bool:
        return JSONResponse({'error': 'enabled must be true or false'}, 400)
    if EDITION=='vtuber' and not enabled:
        return JSONResponse({'error':'Sakura VTuber stays in tracking mode.','tracking_only':True},409)
    if not hasattr(app.state, 'tracking_mode_lock'):
        app.state.tracking_mode_lock = asyncio.Lock()
    async with app.state.tracking_mode_lock:
        if enabled:
            if getattr(app.state, 'ai_unloaded', False):
                return {'ok': True, 'tracking_only': True}
            app.state.tracking_only = True
            if llm:
                llm.tracking_only = True
            from rvc_manager import stop_rvc_service
            from youtube_chat import chat as youtube_inbox
            await run_in_threadpool(stop_rvc_service)
            await run_in_threadpool(youtube_inbox.stop)
            # Finish startup work before unloading, so a late warmup cannot
            # put Qwen back into VRAM after the switch.
            warmup = getattr(app.state, 'llm_warmup', None)
            if warmup and not warmup.done():
                await asyncio.shield(warmup)
            if stt_task and not stt_task.done():
                await asyncio.shield(stt_task)
            stt = None
            stt_task = None
            if llm and (llm.provider=='ollama' or getattr(llm,'local_runtime_used',False)):
                def unload():
                    import requests
                    with llm._lock:
                        # A refused connection means there is no resident runtime
                        # to unload (common for Gemini-only installations).
                        try:
                            probe = requests.get(llm.base_url + '/api/tags', timeout=(2, 5))
                            probe.raise_for_status()
                        except requests.ConnectionError as exc:
                            import errno
                            chain, seen = [exc], set()
                            while chain:
                                error = chain.pop()
                                if id(error) in seen:
                                    continue
                                seen.add(id(error))
                                if getattr(error, 'errno', None) in (errno.ECONNREFUSED, 10061):
                                    return
                                chain.extend(value for value in (getattr(error, '__cause__', None),
                                    getattr(error, '__context__', None), getattr(error, 'reason', None),
                                    *getattr(error, 'args', ())) if isinstance(value, BaseException))
                            raise
                        for model in {llm.model, llm.vision_model}:
                            response = requests.post(llm.base_url + '/api/generate',
                                json={'model': model, 'keep_alive': 0, 'stream': False}, timeout=(3, 120))
                            if response.status_code != 404:
                                response.raise_for_status()
                try:
                    await run_in_threadpool(unload)
                except Exception as exc:
                    # Remain paused and report failure rather than pretending
                    # tracking is AI-free while Qwen may still be resident.
                    return JSONResponse({'error': 'AI was paused, but the local model could not be unloaded. Check the local runtime and retry.',
                        'tracking_only': True}, 503)
            save_settings({'vtuber_tracking_only': True})
            app.state.ai_unloaded = True
            return {'ok': True, 'tracking_only': True}
        if llm:
            llm.tracking_only = False
            cfg = get_settings()
            try:
                if cfg['llm_provider']=='ollama':
                    await run_in_threadpool(llm.configure_local, cfg['ollama_model'], cfg['ollama_models_folder'],
                        cfg['gemini_fallback_enabled'], cfg['ollama_context'], cfg['local_timeout'])
            except (ValueError, OSError) as exc:
                llm.tracking_only = True
                return JSONResponse({'error': str(exc), 'tracking_only': True}, 503)
            app.state.llm_warmup = asyncio.create_task(asyncio.to_thread(llm.warmup))
        app.state.tracking_only = False
        app.state.ai_unloaded = False
        await sync_selected_rvc_service()
        save_settings({'vtuber_tracking_only': False})
        return {'ok': True, 'tracking_only': False}

@app.get('/api/tracking/mode')
async def tracking_mode_status():
    return {'tracking_only': getattr(app.state, 'tracking_only', False),
            'startup_mode': getattr(app.state, 'startup_mode', '')}

@app.post('/api/chat-reader/connect')
async def connect_chat_reader(payload: dict):
    if not getattr(app.state, 'tracking_only', False):
        return JSONResponse({'error': 'Chat Reader is available in VTuber mode.'}, 409)
    return await connect_vtuber(payload)

@app.post('/api/chat-reader/speak')
async def speak_chat_reader(payload: dict):
    if not getattr(app.state, 'tracking_only', False):
        return JSONResponse({'error': 'Chat Reader is available in VTuber mode.'}, 409)
    text = payload.get('text', '')
    if not isinstance(text, str) or not text.strip() or len(text) > 600:
        return JSONResponse({'error': 'Invalid chat message.'}, 400)
    # Read verbatim using the selected voice; never invoke an LLM or STT.
    import copy
    from tts import TextToSpeech
    voice = copy.copy(tts) if tts else TextToSpeech()
    if not tts:
        voice.set_voice_preset(get_settings().get('selected_voice','kokoro_af_heart'))
    try:
        path = await voice.speak_to_file_async(text)
        if not path:
            return JSONResponse({'error': 'The selected voice did not produce audio.'}, 503)
        return {'audio': f'/audio/{os.path.basename(path)}'}
    except Exception as exc:
        return JSONResponse({'error': str(exc)}, 503)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── static files ───────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/audio", StaticFiles(directory=str(AUDIO_DIR)), name="audio")

@app.get('/api/mobile/link')
async def mobile_link_info():
    from mobile_link import link
    return link.info()

@app.post('/api/mobile/link')
async def mobile_link_toggle(payload:dict):
    from mobile_link import link
    if payload.get('forget'):return link.forget_device(str(payload['forget']))
    if payload.get('new'):return link.new_pairing_code()
    if payload.get('enabled'):return link.start(gui_server.port)
    link.stop();return link.info()

@app.post('/api/mobile/poll')
async def mobile_link_poll(payload:dict):
    from mobile_link import link
    return link.poll(payload)


# ── smart 3D model & texture route ─────────────────────────────
@app.get("/models/{file_path:path}")
async def serve_model_file(file_path: str, fallback: str = "") :
    """
    Intelligently serve PMX models and textures.
    Handles URL-encoded paths, Windows backslashes, textures.json mapping,
    and automatic fallback across image extensions (.png, .jpg, .bmp, .tga).
    """
    import urllib.parse
    cleaned = urllib.parse.unquote(file_path).strip("/\\")
    norm = cleaned.replace("\\", "/")

    # Older saved model URLs remain valid after organizing the library.
    if norm.split('/')[0].lower() not in {'pmx', 'vrm', 'live2d'}:
        matches = [kind + '/' + norm for kind in ('pmx', 'vrm', 'live2d') if (MODELS_DIR / kind / norm).is_file() or (MODELS_DIR / kind / norm.split('/')[0]).is_dir()]
        if len(matches) == 1:
            norm = matches[0]

    # 1. Direct path check
    candidate = (MODELS_DIR / norm).resolve()
    try:
        candidate.relative_to(MODELS_DIR.resolve())
    except ValueError:
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    if candidate.is_file():
        return FileResponse(str(candidate))

    # 2. Check if textures.json exists in this model's subfolder
    parts = norm.split("/")
    if len(parts) >= 2:
        root_parts = 2 if parts[0].lower() in {'pmx', 'vrm', 'live2d'} and len(parts) >= 3 else 1
        model_folder = candidate.parent
        # Find the nearest model package, never another character's textures.
        boundary = MODELS_DIR.resolve()
        while model_folder != boundary:
            if model_folder.is_dir() and any(p.suffix.lower() in {'.pmx', '.vrm'} for p in model_folder.iterdir() if p.is_file()):
                break
            model_folder = model_folder.parent
        if model_folder == boundary:
            model_folder = candidate.parent
        sub_req = candidate.relative_to(model_folder).as_posix()
        tex_json = model_folder / "textures.json"
        if tex_json.is_file():
            try:
                import json
                meta = json.loads(tex_json.read_text(encoding="utf-8"))
                mapping = meta.get("textures", {})
                for src_key, target_rel in mapping.items():
                    norm_k = src_key.replace("\\", "/")
                    if norm_k == sub_req or src_key == sub_req or norm_k.lower() == sub_req.lower():
                        mapped_target = (model_folder / target_rel.replace("\\", "/")).resolve()
                        if mapped_target.is_relative_to(model_folder.resolve()) and mapped_target.is_file():
                            return FileResponse(str(mapped_target))
            except Exception:
                pass

        # 3. Check for alternative extensions (.png, .jpg, .bmp, .tga) in the same directory
        parent = candidate.parent
        stem = candidate.stem
        if parent.is_dir():
            for ext in [".png", ".jpg", ".jpeg", ".bmp", ".tga", ".webp"]:
                alt = parent / f"{stem}{ext}"
                if alt.is_file():
                    return FileResponse(str(alt))

        req_filename = Path(norm).name

        # 5. Recover only an unambiguous filename within this package.
        if model_folder.is_dir() and req_filename:
            matches = [f for f in model_folder.rglob('*') if f.is_file() and f.name.lower() == req_filename.lower()]
            if len(matches) == 1:
                return FileResponse(str(matches[0]))

        # 6. Fallback: return 1x1 transparent PNG for missing image/texture files
        #    so MMDLoader doesn't abort the entire model load on a 404 texture
        _IMG_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tga", ".webp", ".spa", ".sph", ".dds"}
        if candidate.suffix.lower() in _IMG_EXTS:
            import io
            from PIL import Image
            # Missing diffuse textures must not punch invisible holes through
            # clothes/body. Missing additive/multiply shine maps need neutral
            # black/white respectively, so they cannot bleach the character.
            color = (255, 255, 255, 255) if fallback == 'white' else (0, 0, 0, 255) if fallback == 'black' else (0, 0, 0, 0)
            buffer = io.BytesIO()
            Image.new('RGBA', (1, 1), color).save(buffer, format='PNG')
            return Response(content=buffer.getvalue(), media_type='image/png', headers={'X-Sakura-Asset-Fallback': 'missing'})

    return JSONResponse({"error": f"File not found: {norm}"}, status_code=404)


# ── routes ─────────────────────────────────────────────────────
@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/identity")
async def identity():
    return {"application": "sakura-anime-assistant", 'edition':EDITION,'installation':INSTALLATION_ID}


@app.get("/api/status")
async def status():
    return {
        "ok": await run_in_threadpool(llm.is_available) if llm else False,
        "model": (llm.gemini_model if llm.provider=='gemini' else llm.model if llm.provider=='ollama' else llm.cloud_model) if llm else OLLAMA_MODEL,
        "provider": llm.provider if llm else "ollama",
        "stt": stt is not None,
    }


@app.post('/api/models/texture-check')
async def check_model_textures(payload: dict):
    paths = payload.get('paths', [])
    if not isinstance(paths, list) or len(paths) > 2048 or any(not isinstance(p, str) for p in paths):
        return JSONResponse({'error': 'Provide a list of model texture paths.'}, 400)
    optional_paths = payload.get('optional_paths', [])
    if not isinstance(optional_paths, list) or any(not isinstance(p, str) or p not in paths for p in optional_paths):
        return JSONResponse({'error': 'Optional texture paths must be included in paths.'}, 400)
    missing = []
    for path in dict.fromkeys(paths):
        response = await serve_model_file(path)
        if response.status_code != 200 or response.headers.get('X-Sakura-Asset-Fallback') == 'missing':
            missing.append(path)
    optional = set(optional_paths)
    required_missing = [path for path in missing if path not in optional]
    return {'missing': missing, 'required_missing': required_missing,
            'optional_missing': [path for path in missing if path in optional],
            'checked': len(set(paths)), 'reference': 'Check missing diffuse references in PMX Editor before appearance repairs' if required_missing else ''}


@app.get('/api/models/bone-repairs')
async def get_model_bone_repairs(model: str):
    from model_repairs import read_repairs
    try:return await run_in_threadpool(read_repairs, MODELS_DIR, model)
    except (ValueError, TypeError, OSError) as exc:return JSONResponse({'error':str(exc)},400)


@app.post('/api/models/bone-repairs')
async def save_model_bone_repairs(payload: dict):
    from model_repairs import write_repairs
    try:return await run_in_threadpool(write_repairs, MODELS_DIR, payload.get('model'), payload.get('repairs'))
    except (ValueError, TypeError, OSError) as exc:return JSONResponse({'error':str(exc)},400)

def _pmx_texture_package(model: str):
    package = (MODELS_DIR / model).resolve()
    if not package.is_relative_to(MODELS_DIR.resolve()) or package.suffix.lower() != '.pmx' or not package.is_file():
        raise ValueError('Choose an existing PMX model inside the models folder.')
    return package


@app.post('/api/models/texture-diagnose')
async def diagnose_pmx_textures(payload: dict):
    """Resolve only this package's references; never guess a different image."""
    import json
    from PIL import Image
    try:
        package = _pmx_texture_package(payload.get('model', ''))
        slots = payload.get('slots')
        if not isinstance(slots, list) or len(slots) > 2048:
            raise ValueError('Provide at most 2048 texture slots.')
        results, decoded = [], {}
        mapping_file = package.parent / 'textures.json'
        mapping = json.loads(mapping_file.read_text(encoding='utf-8')).get('textures', {}) if mapping_file.is_file() else {}
        image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tga', '.dds', '.webp', '.sph', '.spa'}
        for item in slots:
            if not isinstance(item, dict):
                raise ValueError('Choose valid texture slots.')
            index, slot, reference = item.get('material'), item.get('slot'), item.get('reference')
            if type(index) is not int or not 0 <= index < 4096 or slot not in {'diffuse', 'sphere', 'toon'} or not isinstance(reference, str) or len(reference) > 1024:
                raise ValueError('Choose valid texture slots.')
            reference = reference.replace('\\', '/')
            candidate = (package.parent / reference).resolve()
            if not reference or not candidate.is_relative_to(package.parent) or candidate.suffix.lower() not in image_extensions:
                raise ValueError('Texture references must stay inside this model package.')
            response = await serve_model_file(candidate.relative_to(MODELS_DIR.resolve()).as_posix())
            result = {'material': index, 'slot': slot, 'reference': reference}
            if not isinstance(response, FileResponse):
                result.update(status='missing', message='Texture is missing or its filename is ambiguous. Select a replacement.')
            else:
                resolved = Path(response.path).resolve()
                if not resolved.is_relative_to(package.parent):
                    raise ValueError('Resolved texture must stay inside this model package.')
                explicit = any(name.replace('\\', '/').lower() == reference.lower() for name in mapping)
                alternatives = [p for p in candidate.parent.glob('*') if p.is_file() and p.stem.lower() == candidate.stem.lower() and p.suffix.lower() in image_extensions] if candidate.parent.is_dir() else []
                if not candidate.is_file() and not explicit and resolved.parent == candidate.parent and len(alternatives) > 1:
                    result.update(status='missing', message='Several image extensions match this reference. Select the intended texture.')
                    results.append(result)
                    continue
                if resolved not in decoded:
                    def inspect_image():
                        try:
                            if resolved.stat().st_size > 64 * 1024 * 1024:
                                return {'status': 'unchecked', 'message': 'Image exceeds the 64 MB diagnostic limit.'}
                            with Image.open(resolved) as image:
                                if image.width * image.height > 16777216:
                                    return {'status': 'unchecked', 'message': 'Image exceeds the 4096 × 4096 diagnostic pixel limit.'}
                                image.load()
                                return {'status': 'ok', 'width': image.width, 'height': image.height}
                        except (OSError, ValueError, Image.DecompressionBombError) as exc:
                            return {'status': 'invalid', 'message': 'Image could not be decoded: ' + str(exc)}
                    decoded[resolved] = await run_in_threadpool(inspect_image)
                result.update(decoded[resolved])
                target = resolved.relative_to(package.parent).as_posix()
                result['resolved'] = target
                if result['status'] == 'ok' and target != reference:
                    result['status'] = 'repairable'
            results.append(result)
        return {'slots': results}
    except (ValueError, TypeError, OSError) as exc:
        return JSONResponse({'error': str(exc)}, 400)


@app.get('/api/models/texture-options')
async def pmx_texture_options(model: str):
    try:
        package = _pmx_texture_package(model)
        extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tga', '.dds', '.webp', '.sph', '.spa'}
        return {'textures': sorted(p.relative_to(package.parent).as_posix() for p in package.parent.rglob('*')
                                  if p.is_file() and p.suffix.lower() in extensions)}
    except ValueError as exc:
        return JSONResponse({'error': str(exc)}, 400)


@app.post('/api/models/texture-material')
async def save_pmx_material_texture(payload: dict):
    import json
    try:
        package = _pmx_texture_package(payload.get('model', ''))
        index, slot, target = payload.get('material'), payload.get('slot'), payload.get('texture')
        if type(index) is not int or not 0 <= index < 4096 or slot not in {'diffuse', 'sphere', 'toon'}:
            raise ValueError('Choose a valid material and texture slot.')
        if target is not None:
            if not isinstance(target, str):
                raise ValueError('Choose a texture file.')
            file = (package.parent / target).resolve()
            if not file.is_relative_to(package.parent) or not file.is_file() or file.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.bmp', '.tga', '.dds', '.webp', '.sph', '.spa'}:
                raise ValueError('Texture must be an image inside this model folder.')
            target = file.relative_to(package.parent).as_posix()
        mapping_file = package.parent / 'textures.json'
        data = json.loads(mapping_file.read_text(encoding='utf-8')) if mapping_file.exists() else {}
        materials = data.setdefault('materials', {}).setdefault(package.name, {})
        material = materials.setdefault(str(index), {})
        if target is None:
            material.pop(slot, None)
        else:
            material[slot] = target
        # Preserve existing reference repairs and other models' overrides.
        temporary = mapping_file.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(mapping_file)
        return {'saved': True}
    except (ValueError, TypeError, OSError) as exc:
        return JSONResponse({'error': str(exc)}, 400)


@app.get("/api/models")
async def list_models():
    """Scan the models/ directory for .pmx files and auto-sync textures if needed (up to 10 models)."""
    pmx_files = []
    for root, _dirs, files in os.walk(str(MODELS_DIR)):
        _dirs[:] = sorted(d for d in _dirs if d != '__MACOSX' and not d.startswith('.'))
        for f in sorted(files):
            if f.startswith('._'):
                continue
            if f.lower().endswith((".pmx", ".vrm")):
                rel = os.path.relpath(os.path.join(root, f), str(MODELS_DIR))
                norm_rel = rel.replace("\\", "/")

                # Extract character name
                parts = norm_rel.split("/")
                while len(parts) > 1 and parts[0].lower() in {'pmx', 'vrm', 'live2d'}:
                    parts = parts[1:]
                folders = parts[:-1]
                char_name = folders[-1].capitalize() if folders else Path(f).stem.capitalize()
                if sum(name.lower().endswith('.pmx') and not name.startswith('._') for name in files) > 1:
                    char_name = Path(f).stem
                problem = None
                try:
                    with open(os.path.join(root, f), 'rb') as model_file:
                        header = model_file.read(9)
                    expected = b'PMX ' if f.lower().endswith('.pmx') else b'glTF'
                    if len(header) < 9 or header[:4] != expected:
                        problem = 'Invalid or incomplete model file. Re-export or replace this file.'
                except OSError:
                    problem = 'Model file is unreadable. Check its permissions or finish copying it.'

                pmx_files.append({
                    "path": norm_rel,
                    "name": char_name,
                    "filename": f,
                    "folders": folders,
                    "error": problem,
                })

                # Check if textures.json exists in the same folder and sync
                dir_path = Path(root)
                tex_json = dir_path / "textures.json"
                if tex_json.is_file():
                    try:
                        import json, shutil
                        meta = json.loads(tex_json.read_text(encoding="utf-8"))
                        mapping = meta.get("textures", {})
                        for src_key, target_rel in mapping.items():
                            src_p = dir_path / target_rel.replace("/", os.sep)
                            dst_p = dir_path / src_key.replace("/", os.sep)
                            if src_p.resolve().is_relative_to(dir_path.resolve()) and dst_p.resolve().is_relative_to(dir_path.resolve()) and src_p.is_file() and not dst_p.exists():
                                dst_p.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(src_p, dst_p)
                                if dst_p.suffix.lower() == ".tga":
                                    shutil.copy2(src_p, dst_p.with_suffix(".png"))
                    except Exception:
                        pass

    # Cap to max 10 models
    live2d_files = [
        {'path': path.relative_to(MODELS_DIR).as_posix(), 'name': path.parent.name,
         'filename': path.name, 'renderable': True}
        for path in sorted((MODELS_DIR / 'live2d').rglob('*.model3.json'))
    ]
    return {"models": pmx_files, "live2d_models": live2d_files}


@app.get("/api/models/live2d-expressions")
async def list_live2d_expressions(model: str):
    """Read declared and VTube Studio sidecar expressions from a Live2D package."""
    import urllib.parse
    from live2d_expressions import discover_live2d_expressions

    relative = urllib.parse.unquote(model).replace("\\", "/").strip("/")
    candidate = (MODELS_DIR / relative).resolve()
    live2d_root = (MODELS_DIR / "live2d").resolve()
    try:
        candidate.relative_to(live2d_root)
    except ValueError:
        return JSONResponse({"error": "Model path is outside the Live2D library."}, status_code=403)
    if not candidate.is_file() or not candidate.name.casefold().endswith(".model3.json"):
        return JSONResponse({"error": "Choose a Live2D model3.json file."}, status_code=400)
    return {"expressions": discover_live2d_expressions(candidate)}


@app.post('/api/models/import')
async def import_models(files: list[UploadFile] = File(...), model_format: str = Form('auto')):
    from model_import import import_package, MAX_BYTES
    contents = []
    total = 0
    try:
        if len(files) > 5000:
            raise ValueError('Choose fewer than 5,000 files.')
        for upload in files:
            content = await upload.read(MAX_BYTES - total + 1)
            total += len(content)
            if total > MAX_BYTES:
                raise ValueError('Model packages must be under 512 MB.')
            contents.append((upload.filename or '', content))
        result = await run_in_threadpool(import_package, MODELS_DIR, contents, model_format)
        return {'ok': True, **result}
    except Exception as exc:
        return JSONResponse({'error': f'Import failed: {exc}'}, 400)


@app.get("/api/voices")
async def list_voices():
    """Return all available voice presets (up to 10) plus custom RVC models."""
    rvc_models = scan_rvc_models()
    cfg = get_settings()
    from system_speech import system_voice_presets
    offline = await run_in_threadpool(system_voice_presets)
    return {
        "presets": [*VOICE_PRESETS, *offline],
        "rvc_models": rvc_models,
        "current": {
            "selected_voice": cfg.get("selected_voice", "kokoro_af_heart"),
            "tts_pitch": cfg.get("tts_pitch", "+0Hz"),
            "tts_rate": cfg.get("tts_rate", "+0%"),
            "rvc_model": cfg.get("rvc_model", ""),
            "rvc_index": cfg.get("rvc_index", ""),
            "rvc_pitch": cfg.get("rvc_pitch", 0),
            "rvc_index_rate": cfg.get("rvc_index_rate", 0.75),
        }
    }


@app.post("/api/voices/upload")
async def upload_voice_model(
    character_name: str = Form(...),
    pth_file: UploadFile = File(...),
    index_file: UploadFile = File(None),
):
    """Upload custom RVC .pth and .index character voice files."""
    name_clean = character_name.strip().lower().replace(" ", "_")
    target_dir = VOICES_DIR / name_clean
    target_dir.mkdir(parents=True, exist_ok=True)

    # Save .pth file
    pth_path = target_dir / pth_file.filename
    pth_content = await pth_file.read()
    pth_path.write_bytes(pth_content)

    # Save .index file if provided
    index_path = None
    if index_file and index_file.filename:
        index_path = target_dir / index_file.filename
        index_content = await index_file.read()
        index_path.write_bytes(index_content)

    rel_pth = str(pth_path.relative_to(BASE_DIR)).replace("\\", "/")
    rel_index = str(index_path.relative_to(BASE_DIR)).replace("\\", "/") if index_path else None

    # Auto-activate this voice model
    save_settings({
        "selected_voice": f"rvc_{name_clean}",
        "rvc_model": rel_pth,
        "rvc_index": rel_index or "",
    })
    if tts:
        tts.set_voice_preset(f'rvc_{name_clean}')
        tts.set_rvc_model(str(pth_path), str(index_path) if index_path else None)
    if llm:
        llm.reply_language = 'English'

    return {
        "ok": True,
        "character": character_name,
        "pth": rel_pth,
        "index": rel_index,
    }


@app.post("/api/tts/test")
async def test_tts_voice(payload: dict):
    """Play a sample speech preview with the selected voice and pitch settings."""
    if not tts:
        return JSONResponse({"error": "TTS unavailable"}, 503)

    sample_text = payload.get("text", "Konnichiwa! I am your companion assistant. How do I sound?")
    preset_id = payload.get("voice", "kokoro_af_heart")
    pitch = payload.get("pitch", "+0Hz")
    rate = payload.get("rate", "+0%")
    rvc_model = payload.get("rvc_model")
    rvc_index = payload.get("rvc_index")
    rvc_pitch = payload.get("rvc_pitch", 0)
    rvc_index_rate = payload.get("rvc_index_rate", 0.75)

    # Preview an isolated copy; never restore stale settings over a new choice.
    import copy
    preview = copy.copy(tts)
    try:
        preview.set_voice_preset(preset_id, pitch, rate)
        preview.set_rvc_model(str(BASE_DIR / rvc_model) if rvc_model else None,
            str(BASE_DIR / rvc_index) if rvc_index else None,
            pitch=rvc_pitch, index_rate=rvc_index_rate)
        audio_file = await preview.speak_to_file_async(sample_text)
        return {"ok": True, "audio": f"/audio/{os.path.basename(audio_file)}", "voice_notice": speech_notice(audio_file)}
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, 500)


@app.get("/api/settings")
async def get_app_settings():
    return public_settings(get_settings())


@app.post("/api/settings")
async def update_app_settings(payload: dict):
    import re
    if 'avatar_presentation' in payload and payload['avatar_presentation'] not in ('auto','feminine','masculine','neutral'):
        return JSONResponse({'error':'Choose a valid avatar presentation.'},400)
    for field, limit in (('assistant_name', 80), ('vtuber_name',80), ('wake_word', 120)):
        if field in payload:
            if not isinstance(payload[field], str) or not payload[field].strip() or len(payload[field]) > limit:
                return JSONResponse({'error': f'Enter a valid {field.replace("_", " ")}.'}, 400)
            payload[field] = payload[field].strip()
    if 'transparency_hotkey' in payload:
        from companion_hotkey import parse_hotkey
        try: payload['transparency_hotkey'] = parse_hotkey(payload['transparency_hotkey'])[0]
        except ValueError as error: return JSONResponse({'error':str(error)},400)
    for field in ('wake_word_enabled', 'computer_control_enabled', 'preserve_configuration_on_reinstall', 'physics_enabled', 'pmx_texture_reference'):
        if field in payload and type(payload[field]) is not bool:
            return JSONResponse({'error': f'{field} must be on or off.'}, 400)
    if 'selected_voice' in payload and (not isinstance(payload['selected_voice'],str) or not payload['selected_voice'] or len(payload['selected_voice'])>200):
        return JSONResponse({'error':'Choose a valid voice.'},400)
    if 'selected_voice' in payload:payload['selected_voice']=canonical_voice_id(payload['selected_voice'])
    if 'selected_voice' in payload and not str(payload['selected_voice']).startswith('rvc_'):
        payload['rvc_model'] = ''
        payload['rvc_index'] = '' 
    if str(payload.get('selected_voice','')).startswith('system_'):
        from system_speech import system_voice_presets
        available=await run_in_threadpool(system_voice_presets)
        if not any(p['id']==payload['selected_voice'] for p in available):
            return JSONResponse({'error':'That Offline voice is no longer installed. Choose another Windows voice.'},400)
    from cloud_api import detect_provider, PROVIDERS, validate as validate_cloud
    from credentials import get_cloud_key, set_cloud_key
    cloud_key=payload.pop('api_key',None)
    if cloud_key is not None and (not isinstance(cloud_key,str) or len(cloud_key)>1024 or any(ord(c)<32 or ord(c)>126 for c in cloud_key)):
        return JSONResponse({'error':'Invalid API key.'},400)
    provider=payload.get('llm_provider',get_settings()['llm_provider'])
    if provider=='auto':
        try:provider=detect_provider((cloud_key or '').strip()) if cloud_key else get_settings()['llm_provider']
        except ValueError as error:return JSONResponse({'error':str(error)},400)
        payload['llm_provider']=provider
    if provider not in ('ollama','gemini',*PROVIDERS):return JSONResponse({'error':'Choose a supported provider or custom OpenAI-compatible endpoint.'},400)
    if cloud_key and cloud_key.strip() and provider=='gemini':payload['gemini_api_key']=cloud_key.strip()
    if provider=='gemini' and payload.get('cloud_model'):payload['gemini_model']=payload['cloud_model']
    if provider in PROVIDERS:
        previous=get_settings()
        try:
            base,cloud_model,cloud_vision=validate_cloud(provider,payload.get('cloud_model','') if provider!=previous['llm_provider'] else payload.get('cloud_model',previous.get('cloud_model','')),payload.get('cloud_endpoint',previous.get('cloud_endpoint','')),payload.get('cloud_vision') if 'cloud_vision' in payload else (previous.get('cloud_vision',False) if provider==previous['llm_provider'] else None))
        except ValueError as error:return JSONResponse({'error':str(error)},400)
        payload.update(cloud_model=cloud_model,cloud_endpoint=base,cloud_vision=cloud_vision)
        if not (cloud_key and cloud_key.strip()) and not get_cloud_key(provider,base) and not payload.get('clear_cloud_key'):
            return JSONResponse({'error':f'Enter a key for {provider}; keys from other providers will not be reused.'},400)
        payload['gemini_fallback_enabled']=False
    if 'gemini_model' in payload and (not isinstance(payload['gemini_model'], str) or
            not re.fullmatch(r'[A-Za-z0-9._-]{1,100}', payload['gemini_model'])):
        return JSONResponse({'error': 'Enter a valid Gemini model name.'}, 400)
    key = payload.get('gemini_api_key')
    if key is not None and (not isinstance(key, str) or len(key) > 512 or any(ord(c) < 32 or ord(c) > 126 for c in key)):
        return JSONResponse({'error': 'Invalid Gemini API key.'}, 400)
    from ollama_runtime import validate_folder
    if 'ollama_model' in payload and (not isinstance(payload['ollama_model'], str) or
            not re.fullmatch(r'[A-Za-z0-9._:/-]{1,150}', payload['ollama_model'])):
        return JSONResponse({'error': 'Enter a valid local model name.'}, 400)
    for field, minimum, maximum in (('ollama_context', 1024, 8192), ('local_timeout', 5, 120)):
        if field in payload and (type(payload[field]) is not int or not minimum <= payload[field] <= maximum):
            return JSONResponse({'error': f'{field} must be between {minimum} and {maximum}.'}, 400)
    if 'gemini_fallback_enabled' in payload and type(payload['gemini_fallback_enabled']) is not bool:
        return JSONResponse({'error': 'Choose whether Gemini fallback is enabled.'}, 400)
    try:
        if 'ollama_models_folder' in payload:
            payload['ollama_models_folder'] = validate_folder(payload['ollama_models_folder'])
        combined = {**get_settings(), **payload}
        if combined['gemini_fallback_enabled'] and (payload.get('clear_gemini_key') or not ((key and key.strip()) or get_gemini_key())):
            return JSONResponse({'error': 'Save a Gemini API key to enable automatic fallback.'}, 400)
        if llm and provider=='ollama' and any(field in payload for field in ('llm_provider', 'ollama_model', 'ollama_models_folder', 'ollama_context', 'gemini_fallback_enabled', 'local_timeout')):
            await run_in_threadpool(llm.configure_local, combined['ollama_model'], combined['ollama_models_folder'] if combined['llm_provider'] == 'ollama' else '',
                combined['gemini_fallback_enabled'], combined['ollama_context'], combined['local_timeout'],
                validate=combined['llm_provider'] == 'ollama')
    except (ValueError, OSError) as exc:
        return JSONResponse({'error': str(exc)}, 400)
    try:
        if payload.get("selected_voice", "").startswith("rvc_"):
            model_rel = payload.get("rvc_model", "")
            model_path = (BASE_DIR / model_rel) if model_rel else None
            if not model_path or not model_path.is_file():
                return JSONResponse({"error": "The selected voice model file was not found. Re-scan voices or upload the .pth model again."}, 400)
        if provider in PROVIDERS:
            if payload.get('clear_cloud_key'):set_cloud_key(provider,'',payload.get('cloud_endpoint',''))
            elif cloud_key and cloud_key.strip():set_cloud_key(provider,cloud_key.strip(),payload.get('cloud_endpoint',''))
        if payload.get('clear_gemini_key'):
            set_gemini_key('')
        elif key and key.strip():
            set_gemini_key(key.strip())
        updated = save_settings(payload)
        if llm and (cloud_key is not None or any(field in payload for field in ('llm_provider','gemini_model','gemini_api_key','clear_gemini_key','cloud_model','cloud_endpoint','cloud_vision','clear_cloud_key'))):
            await run_in_threadpool(configure_saved_ai,llm,updated)
    except OSError:
        return JSONResponse({'error': 'Windows could not save or read your Gemini key.'}, 500)
    if llm and "assistant_name" in payload:
        await run_in_threadpool(llm.set_assistant_name, payload["assistant_name"])
    if llm and 'vtuber_name' in payload:
        await run_in_threadpool(llm.set_vtuber_name,payload['vtuber_name'])
    if llm and 'avatar_presentation' in payload:
        llm.avatar_presentation=payload['avatar_presentation']
    if llm and 'selected_voice' in payload:
        from config import voice_language
        llm.reply_language = voice_language(payload['selected_voice'])
    if tts:
        if "selected_voice" in payload:
            tts.set_voice_preset(
                payload["selected_voice"],
                payload.get("tts_pitch"),
                payload.get("tts_rate"),
            )
        if "rvc_model" in payload:
            m_path = str(BASE_DIR / payload["rvc_model"]) if payload.get("rvc_model") else None
            i_path = str(BASE_DIR / payload["rvc_index"]) if payload.get("rvc_index") else None
            tts.set_rvc_model(
                m_path,
                i_path,
                pitch=payload.get("rvc_pitch", 0),
                index_rate=payload.get("rvc_index_rate", 0.75),
            )
    if tts and any(field in payload for field in ('selected_voice', 'rvc_model')):
        try:
            await sync_selected_rvc_service()
        except RuntimeError as exc:
            return JSONResponse({'error': f'Voice selected, but RVC could not start: {exc}'}, 503)
    return {"ok": True, "settings": public_settings(updated), "voice_notice": None}


@app.post('/api/ollama/models')
async def local_models(payload: dict):
    from ollama_runtime import list_models
    try:
        models = await run_in_threadpool(list_models, payload.get('folder', ''))
        return {'models': models}
    except (ValueError, OSError) as exc:
        return JSONResponse({'error': str(exc)}, 400)

@app.post("/api/llm/test")
async def test_llm_connection():
    if not llm:
        return JSONResponse({'error': 'The assistant is still starting.'}, 503)
    from starlette.concurrency import run_in_threadpool
    try:
        if llm.provider == 'gemini':
            message = await run_in_threadpool(llm.test_gemini_connection)
        elif llm.provider!='ollama':
            message = await run_in_threadpool(llm.test_cloud_connection)
        else:
            local_ready = await run_in_threadpool(llm.is_available)
            if llm.fallback_enabled:
                await run_in_threadpool(llm.test_gemini_connection)
                message = 'Local Ollama and Gemini fallback are ready.' if local_ready else 'Local Ollama is unavailable; Gemini fallback is ready.'
            elif not local_ready:
                return JSONResponse({'error': 'Ollama or the selected local model is unavailable.'}, 503)
            else:
                message = 'Connected to local Ollama.'
        return {'ok': True, 'message': message}
    except ValueError as exc:
        message = str(exc)
        if llm.gemini_api_key:
            message = message.replace(llm.gemini_api_key, '[redacted]')
        return JSONResponse({'error': message}, 400)
    except Exception:
        return JSONResponse({'error': 'Connection failed. Check your network and try again.'}, 400)


def get_vision_status():
    if llm and llm.provider not in ('ollama','gemini'):
        return {'ready':bool(llm.cloud_api_key) and llm.cloud_vision,'model':llm.cloud_model,
                'message':'Cloud image support follows your selected model. Enable images only for vision-capable models in Settings > AI.'}
    if llm and llm.provider == 'gemini':
        return {'ready': bool(llm.gemini_api_key), 'model': llm.gemini_model,
                'message': 'Gemini screen vision is configured.' if llm.gemini_api_key else 'Add your Gemini key in Settings > AI.'}
    import requests
    try:
        response = requests.post(f"{llm.base_url}/api/show", json={"model": llm.vision_model}, timeout=5)
        if response.status_code == 200 and "vision" in response.json().get("capabilities", []):
            return {"ready": True, "model": llm.vision_model, "message": "Screen vision is ready."}
        return {"ready": False, "model": OLLAMA_VISION_MODEL,
                "message": "The local screen vision model is not ready yet. Finish downloading " + OLLAMA_VISION_MODEL + " in Ollama, then try again."}
    except requests.RequestException:
        return {"ready": False, "model": OLLAMA_VISION_MODEL,
                "message": "Ollama is offline. Start Ollama to enable screen vision."}


@app.get("/api/screen/status")
async def screen_status():
    from starlette.concurrency import run_in_threadpool
    return await run_in_threadpool(get_vision_status)


@app.post('/api/vtuber/connect')
async def connect_vtuber(payload: dict):
    from youtube_chat import chat
    link = payload.get('link')
    if not isinstance(link, str) or len(link) > 2048:
        return JSONResponse({'error': 'Enter a YouTube livestream link.'}, 400)
    try:
        identity = await run_in_threadpool(chat.connect, link)
        app.state.ai_vtuber_audio = True
        from screen_audio import listener
        await run_in_threadpool(listener.set_computer_only, True)
        return {'ok': True, 'video_id': identity}
    except ValueError as exc:
        return JSONResponse({'error': str(exc)}, 400)


@app.post('/api/vtuber/disconnect')
async def disconnect_vtuber():
    app.state.ai_vtuber_audio = False
    from screen_audio import listener
    await run_in_threadpool(listener.set_computer_only, False)
    from youtube_chat import chat
    await run_in_threadpool(chat.stop)
    return {'ok': True}


@app.get('/api/vtuber/messages')
async def vtuber_messages():
    from youtube_chat import chat
    return chat.poll()


def validate_screen_frames(frames, screen_image):
    import base64, binascii
    if frames is None: return []
    if not isinstance(frames, list) or len(frames) > 3 or (frames and not screen_image):
        raise ValueError('Live screen frames require an active screen image and at most three frames.')
    if sum(len(frame) if isinstance(frame, str) else 8_000_001 for frame in frames) > 8_000_000:
        raise ValueError('Live screen frames are too large.')
    for frame in frames:
        try:
            if not isinstance(frame, str) or len(frame) > 4_000_000 or not base64.b64decode(frame, validate=True).startswith(b'\xff\xd8\xff'):
                raise ValueError()
        except (ValueError, binascii.Error):
            raise ValueError('Invalid live screen frame.') from None
    return frames


@app.post('/api/vtuber/reply')
async def reply_vtuber(payload: dict):
    if not llm:
        return JSONResponse({'error': 'Sakura is still starting.'}, 503)
    author, text = payload.get('author', ''), payload.get('text', '')
    if not isinstance(author, str) or not isinstance(text, str) or not text.strip() or len(text) > 500 or len(author) > 80:
        return JSONResponse({'error': 'Invalid viewer message.'}, 400)
    try:
        from screen_audio import listener
        image = payload.get('screen_image')
        frames = validate_screen_frames(payload.get('screen_frames'), image)
        if image: validate_screen_frames([image], image)
        extra = {'screen_image': image, 'screen_frames': frames, 'audio_context': listener.context()} if image else {}
        return {'reply': await run_in_threadpool(llm.viewer_reply, author, text, **extra)}
    except ValueError as error:
        return JSONResponse({'error': str(error)}, 400)
    except Exception:
        return JSONResponse({'error': 'Could not generate a viewer reply. Check the AI connection.'}, 502)


@app.post("/api/chat")
async def chat(payload: dict):
    text = payload.get("text", "").strip()
    if not text:
        return JSONResponse({"error": "empty message"}, 400)

    cfg = get_settings()
    if llm and cfg.get('selected_voice'):
        from config import voice_language
        llm.reply_language = voice_language(cfg['selected_voice'])

    screen_image = payload.get("screen_image")
    try:
        screen_frames = validate_screen_frames(payload.get("screen_frames"), screen_image)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, 400)
    avatar_image = payload.get("avatar_image")
    if payload.get('screen_observation'):
        if not llm or not screen_image or not screen_frames:
            return JSONResponse({'error':'Screen observation requires captured frames.'},400)
        # Reuse the bounded JPEG validation for all supplied screen frames.
        try:validate_screen_frames([screen_image],screen_image)
        except ValueError as error:return JSONResponse({'error':str(error)},400)
        vision=await run_in_threadpool(get_vision_status)
        if not vision['ready']:return JSONResponse({'error':vision['message']},503)
        from screen_audio import listener
        recorded=await run_in_threadpool(llm.observe_screen,screen_image,screen_frames,listener.context())
        return {'recorded':recorded}
    camera_image = payload.get('camera_image')
    if camera_image is not None:
        import base64, binascii
        try:
            if not isinstance(camera_image,str) or len(camera_image)>1_000_000:
                raise ValueError()
            if not base64.b64decode(camera_image,validate=True).startswith(b'\xff\xd8\xff'):
                raise ValueError()
        except (ValueError,binascii.Error):
            return JSONResponse({'error':'Camera image must be a bounded JPEG.'},400)
        if getattr(app.state,'tracking_only',False) or payload.get('ai_vtuber'):
            return JSONResponse({'error':'Companion camera access is unavailable in VTuber mode.'},409)
        vision = await run_in_threadpool(get_vision_status)
        if not vision['ready']:
            return JSONResponse({'error':'Camera access needs Gemini or an installed Qwen-VL vision model.'},503)
    if payload.get('camera_reaction'):
        if not camera_image:
            return JSONResponse({'error':'Enable Companion camera access first.'},400)
        reply=await run_in_threadpool(llm.camera_reaction,camera_image)
        emotion=None
        if reply and reply.strip().startswith('{'):
            try:
                import json
                observation=json.loads(reply)
                if not isinstance(observation.get('reply'),str):raise ValueError()
                reply=observation['reply'].strip()[:600]
                if observation.get('emotion') in ('surprised','happy','amused','focused','concerned'):
                    emotion=observation['emotion']
            except (ValueError,TypeError,AttributeError):
                reply='[QUIET]'
        return {'reply':reply,'emotion':emotion,'audio':None,'voice_error':None}
    from dance_commands import dance_action, dance_reply, hand_action, hand_reply
    hand=hand_action(text) if not payload.get('screen_reaction') and not payload.get('ai_vtuber') else None
    if hand and not getattr(app.state,'tracking_only',False):
        from config import voice_language
        supported=payload.get('avatar_can_dance') is True
        reply=hand_reply(hand,voice_language(cfg.get('selected_voice','kokoro_af_heart')),supported)
        app.state.last_avatar_action=None
        if llm:await run_in_threadpool(llm.remember_exchange,text,reply)
        return {'reply':reply,'audio':None,'voice_error':None,'avatar_motion':hand if supported else None}
    motion=dance_action(text) if not payload.get('screen_reaction') and not payload.get('ai_vtuber') else None
    if not motion and getattr(app.state,'last_avatar_action',None)=='dance' and not payload.get('screen_reaction'):
        import re
        if re.search(r'\b(?:just do|show me|want to see|do what (?:you|u) have)\b',text,re.I):motion='groove'
    if motion and not getattr(app.state,'tracking_only',False):
        from config import voice_language
        supported=payload.get('avatar_can_dance') is True
        reply=dance_reply(motion,voice_language(cfg.get('selected_voice','kokoro_af_heart')),supported)
        app.state.last_avatar_action='dance' if supported and motion!='stop' else None
        if llm:await run_in_threadpool(llm.remember_exchange,text,reply)
        return {'reply':reply,'audio':None,'voice_error':None,'avatar_motion':motion if supported else None}
    if not payload.get('screen_reaction'):app.state.last_avatar_action=None
    from assistant_commands import run_command
    command_reply = await run_in_threadpool(run_command, text, cfg.get('computer_control_enabled', False), cfg.get('assistant_name', 'Sakura')) if not payload.get('screen_reaction') else None
    if not command_reply and not payload.get('screen_reaction') and not payload.get('ai_vtuber'):
        from current_information import lookup_with_context
        command_reply, pending_weather = await run_in_threadpool(
            lookup_with_context, text, getattr(app.state, 'pending_weather_date', None))
        app.state.pending_weather_date = pending_weather
    elif command_reply:
        app.state.pending_weather_date = None
    if command_reply:
        screen_image = None
        avatar_image = None
        camera_image = None
    if avatar_image is not None and screen_image is None:
        return JSONResponse({"error": "Enable screen viewing to share the avatar image."}, 400)
    if avatar_image is not None:
        import base64, binascii
        try:
            if not isinstance(avatar_image, str) or len(avatar_image) > 2_000_000:
                raise ValueError()
            if not base64.b64decode(avatar_image, validate=True).startswith(b"\xff\xd8\xff"):
                raise ValueError()
        except (ValueError, binascii.Error):
            return JSONResponse({"error": "Invalid avatar image."}, 400)
    if screen_image is not None:
        import base64
        import binascii
        if not isinstance(screen_image, str) or len(screen_image) > 4_000_000:
            return JSONResponse({"error": "Screen snapshot is too large or invalid."}, 400)
        try:
            image_bytes = base64.b64decode(screen_image, validate=True)
        except (ValueError, binascii.Error):
            return JSONResponse({"error": "Invalid screen snapshot."}, 400)
        if not image_bytes.startswith(b"\xff\xd8\xff"):
            return JSONResponse({"error": "Screen snapshot must be a JPEG image."}, 400)
        vision_status = await run_in_threadpool(get_vision_status)
        if not vision_status["ready"]:
            return JSONResponse({"error": vision_status["message"]}, 503)

    from screen_audio import listener as audio_listener
    audio_context = audio_listener.context() if screen_image and not command_reply else ""

    live_context = {}
    if audio_context: live_context["audio_context"] = audio_context
    if screen_frames: live_context["screen_frames"] = screen_frames
    if camera_image: live_context['camera_image'] = camera_image

    # LLM response
    if command_reply:
        reply = command_reply
        if llm:
            await run_in_threadpool(llm.remember_exchange, text, reply)
    elif payload.get('screen_reaction'):
        if not screen_image:
            return JSONResponse({'error': 'Enable screen viewing first.'}, 400)
        try:
            if payload.get('screen_check'):
                reply = await run_in_threadpool(llm.screen_reaction, screen_image, True, return_details=True, **live_context)
            else:
                reply = await run_in_threadpool(llm.screen_reaction, screen_image, cohost=bool(payload.get('ai_vtuber')), return_details=True, game_watch=payload.get('game_watch') is True, **live_context)
        except Exception as exc:
            message = str(exc)
            if llm.gemini_api_key:
                message = message.replace(llm.gemini_api_key, '[redacted]')
            return JSONResponse({'error': f'Screen vision failed: {message}'}, 502)
    else:
        if payload.get('ai_vtuber'):live_context['cohost']=True
        reply = await run_in_threadpool(llm.chat, text, screen_image, avatar_image, **live_context) if avatar_image or live_context else await run_in_threadpool(llm.chat, text, screen_image)

    if not reply:
        from llm import LLM
        language=getattr(llm,'reply_language','English')
        return JSONResponse({'error':LLM._generation_failure(language)},503)
    game_result=None
    if isinstance(reply,dict):
        game_result=reply.get('game_result')
        reply=reply['reply']
    if payload.get('defer_audio'):
        return {"reply": reply, "audio": None, "voice_error": None, "game_result":game_result}

    # TTS → file (no local playback — browser handles it)
    audio_url = None
    voice_error = None
    try:
        path = await tts.speak_to_file_async(reply)
        if path:
            audio_url = f"/audio/{os.path.basename(path)}"
    except Exception as exc:
        voice_error = str(exc)
        print(f"  ⚠️  TTS error: {exc}")

    return {"reply": reply, "audio": audio_url, "voice_error": voice_error, "game_result":game_result,
            "voice_notice": speech_notice(path) if audio_url else None}


@app.post("/api/tts/speak")
async def generate_reply_speech(payload: dict):
    text = payload.get('text', '')
    if not isinstance(text, str) or not text.strip() or len(text) > 30000:
        return JSONResponse({'error': 'Speech text is empty or too long.'}, 400)
    if not tts:
        return JSONResponse({'error': 'Speech is unavailable.'}, 503)
    try:
        path = await tts.speak_to_file_async(text)
        return {'audio': f'/audio/{os.path.basename(path)}' if path else None, 'voice_notice': speech_notice(path)}
    except Exception as exc:
        return JSONResponse({'error': str(exc)}, 503)


@app.get('/api/tts/kokoro')
async def kokoro_status():
    from kokoro_speech import status
    return status()


@app.post('/api/tts/kokoro')
async def prepare_kokoro():
    from kokoro_speech import prepare
    try:return await run_in_threadpool(prepare)
    except RuntimeError as exc:return JSONResponse({'error':str(exc)},503)


@app.post('/api/voice-changer/convert')
async def convert_vtuber_microphone(audio: UploadFile = File(...)):
    """Convert one spoken microphone segment using the selected local RVC voice."""
    if not getattr(app.state, 'tracking_only', False):
        return JSONResponse({'error': 'The RVC voice changer is available in VTuber mode.'}, 409)
    if not tts or not tts.rvc_model or not tts.selected_preset_id.startswith('rvc_'):
        return JSONResponse({'error': 'Select an installed [RVC] voice from the top voice selector first.'}, 409)
    suffix = Path(audio.filename or 'microphone.wav').suffix.lower()
    if suffix not in {'.wav', '.mp3', '.ogg', '.webm', '.flac', '.m4a'}:
        return JSONResponse({'error': 'Unsupported microphone audio format.'}, 400)
    data = await audio.read(12 * 1024 * 1024 + 1)
    if not data or len(data) > 12 * 1024 * 1024:
        return JSONResponse({'error': 'Audio segment must be between 1 byte and 12 MB.'}, 413)
    source_path = AUDIO_DIR / f'vtuber_voice_input_{uuid.uuid4().hex}{suffix}'
    converted_path = None
    try:
        source_path.write_bytes(data)
        converted_path = await run_in_threadpool(tts._apply_rvc_conversion, str(source_path))
        if not converted_path or not Path(converted_path).is_file():
            return JSONResponse({'error': 'RVC did not produce converted audio.'}, 503)
        return Response(Path(converted_path).read_bytes(), media_type='audio/wav')
    except Exception as exc:
        return JSONResponse({'error': str(exc)}, 503)
    finally:
        source_path.unlink(missing_ok=True)
        if converted_path:
            Path(converted_path).unlink(missing_ok=True)


@app.post('/api/voice-changer/speak')
async def speak_vtuber_microphone(audio: UploadFile = File(...)):
    """Transcribe a mic utterance locally and speak it through the selected built-in voice."""
    global stt, stt_task
    if not getattr(app.state, 'tracking_only', False):
        return JSONResponse({'error': 'Microphone voice playback is available in VTuber mode.'}, 409)
    if not tts or tts.selected_preset_id.startswith('rvc_'):
        return JSONResponse({'error': 'Select a built-in voice for speech playback.'}, 409)
    suffix = Path(audio.filename or 'microphone.wav').suffix.lower()
    if suffix != '.wav':
        return JSONResponse({'error': 'Built-in voice mode expects microphone WAV audio.'}, 400)
    data = await audio.read(12 * 1024 * 1024 + 1)
    if not data or len(data) > 12 * 1024 * 1024:
        return JSONResponse({'error': 'Audio segment must be between 1 byte and 12 MB.'}, 413)

    if stt is None:
        if stt_loader is None:
            return JSONResponse({'error': 'Local speech recognition is unavailable.'}, 503)
        if stt_task is None or stt_task.done():
            stt_task = asyncio.create_task(asyncio.to_thread(stt_loader))
        try:
            await asyncio.shield(stt_task)
        except Exception as exc:
            return JSONResponse({'error': f'Could not load local speech recognition: {exc}'}, 503)
    if stt is None:
        return JSONResponse({'error': 'Local speech recognition is unavailable. Check the app log.'}, 503)

    try:
        import io
        import numpy as np
        import soundfile as sf
        samples, sample_rate = sf.read(io.BytesIO(data), dtype='float32', always_2d=False)
        samples = np.asarray(samples, dtype=np.float32)
        if samples.ndim > 1:
            samples = samples.mean(axis=1)
        if sample_rate != 16000 and samples.size:
            target_count = max(1, round(samples.size * 16000 / sample_rate))
            samples = np.interp(np.linspace(0, samples.size - 1, target_count),
                                np.arange(samples.size), samples).astype(np.float32)
        from config import voice_language
        input_language='hi' if voice_language(get_settings().get('selected_voice','')) in ('Hindi','Hinglish') else None
        text = await run_in_threadpool(stt.transcribe, samples, input_language)
        if not text:
            return JSONResponse({'error': 'No clear speech was recognized. Try speaking a little closer to the microphone.'}, 422)

        import copy
        voice = copy.copy(tts)
        voice.set_voice_preset(tts.selected_preset_id)
        voice.set_rvc_model(None)
        output_path = await voice.speak_to_file_async(text)
        if not output_path or not Path(output_path).is_file():
            return JSONResponse({'error': 'The selected built-in voice did not produce audio.'}, 503)
        media_type = 'audio/mpeg' if Path(output_path).suffix.lower() == '.mp3' else 'audio/wav'
        return Response(Path(output_path).read_bytes(), media_type=media_type)
    except Exception as exc:
        return JSONResponse({'error': str(exc)}, 503)
    finally:
        if 'output_path' in locals() and output_path:
            Path(output_path).unlink(missing_ok=True)


@app.post('/api/voice-changer/prepare')
async def prepare_vtuber_rvc_voice():
    """Start the local RVC worker and preload the currently selected model."""
    if not getattr(app.state, 'tracking_only', False):
        return JSONResponse({'error': 'RVC microphone voice is available in VTuber mode.'}, 409)
    if not tts or not tts.rvc_model or not tts.selected_preset_id.startswith('rvc_'):
        return JSONResponse({'error': 'Select an installed [RVC] voice from the top voice selector first.'}, 409)
    from rvc_manager import ensure_rvc_service
    import requests
    try:
        await run_in_threadpool(ensure_rvc_service)
        response = await run_in_threadpool(requests.post,
            f'{RVC_SERVER_URL.rstrip("/")}/load-model',
            data={'model': os.path.basename(tts.rvc_model)}, timeout=180)
        if response.status_code != 200:
            try: detail = response.json().get('detail') or response.json().get('error')
            except ValueError: detail = response.text[:300]
            return JSONResponse({'error': detail or f'RVC model could not load ({response.status_code}).'}, 503)
        return {'ok': True, 'model': os.path.basename(tts.rvc_model)}
    except Exception as exc:
        return JSONResponse({'error': f'RVC model could not load: {exc}'}, 503)


@app.post('/api/voice-changer/stop')
async def stop_vtuber_voice_changer():
    from rvc_manager import stop_rvc_service
    await run_in_threadpool(stop_rvc_service)
    return {'ok': True}


@app.post("/api/stt")
async def speech_to_text(audio: UploadFile = File(...)):
    """Receive audio blob from browser mic, transcribe with Whisper."""
    global stt_task
    if stt is None and stt_task is None and stt_loader is not None:
        stt_task = asyncio.create_task(asyncio.to_thread(stt_loader))
    if stt is None and stt_task is not None and not stt_task.done():
        await asyncio.shield(stt_task)
    if stt is None:
        return JSONResponse({"error": "STT not available"}, 503)

    # Save uploaded audio to temp file
    suffix = ".webm" if "webm" in (audio.content_type or "") else ".wav"
    tmp = AUDIO_DIR / f"stt_input{suffix}"
    content = await audio.read()
    tmp.write_bytes(content)

    # Convert webm → wav if needed (using ffmpeg or soundfile)
    wav_path = AUDIO_DIR / "stt_input.wav"
    if suffix == ".webm":
        try:
            import subprocess
            import shutil
            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                raise RuntimeError("ffmpeg is required to decode browser microphone audio.")
            converted = subprocess.run(
                [ffmpeg, "-y", "-i", str(tmp), "-af", "highpass=f=80,lowpass=f=7000,afftdn=nf=-25",
                 "-ar", "16000", "-ac", "1", str(wav_path)],
                capture_output=True, timeout=15,
            )
            if converted.returncode != 0 or not wav_path.exists() or wav_path.stat().st_size < 100:
                detail = converted.stderr.decode("utf-8", errors="replace")[-240:]
                raise RuntimeError(f"Could not decode microphone audio. {detail}")
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, 422)
    else:
        wav_path = tmp

    # Transcribe
    import numpy as np
    import soundfile as sf
    try:
        audio_data, sr = sf.read(str(wav_path), dtype="float32")
        if not len(audio_data):
            return {"text": ""}
        if len(audio_data.shape) > 1:
            audio_data = audio_data.mean(axis=1)  # mono
        if sr!=16000:
            count=max(1,round(len(audio_data)*16000/sr))
            audio_data=np.interp(np.linspace(0,len(audio_data)-1,count),np.arange(len(audio_data)),audio_data).astype(np.float32)
        from config import voice_language
        input_language='hi' if voice_language(get_settings().get('selected_voice','')) in ('Hindi','Hinglish') else None
        text = await run_in_threadpool(stt.transcribe,audio_data,input_language)
        return {"text": text}
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, 500)


@app.post("/api/clear")
async def clear_history():
    llm.clear_history()
    return {"ok": True}


@app.post("/api/refresh-memory")
async def refresh_memory():
    from starlette.concurrency import run_in_threadpool
    count = await run_in_threadpool(llm.refresh_memory)
    return {"ok": True, "messages": count, "message": "Memory refreshed."}


# ── entry point ────────────────────────────────────────────────
if __name__ == "__main__":
    print()
    print("  🌸 Sakura — Anime AI Assistant (GUI Mode)")
    print("  ──────────────────────────────────────────")
    print()
    gui_server.launch()
