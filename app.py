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
import copy
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
        "game_ollama_model": "", "game_cloud_auto_enabled": True,
        "ollama_models_folder": "",
        "ollama_context": 4096,
        "gemini_fallback_enabled": False,
        "local_timeout": 20,
        "gemini_model": "gemini-flash-latest",
        "cloud_model": "", "cloud_endpoint": "", "cloud_vision": False,
        "last_cloud_provider": "gemini",
        "assistant_name": "Sakura",
        "user_address": "sir",
        "news_area": "",
        "evidence_confidence_threshold": 0.9,
        "response_restriction_level": "off",
        "web_search_enabled": True,
        "phone_link_enabled":False,
        "phone_system_access_enabled":False,
        "phone_clipboard_enabled":False,
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
    # Write beside the real file, then swap: a crash mid-write cannot leave a
    # truncated settings file that get_settings() silently falls back to defaults.
    handle = tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=str(SETTINGS_FILE.parent),
                                         prefix='.settings-', suffix='.tmp', delete=False)
    try:
        with handle:
            json.dump(cur, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(handle.name, SETTINGS_FILE)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise
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
    try:result['brave_key_set']=bool(get_cloud_key('brave'))
    except (OSError,ValueError):result['brave_key_set']=False
    return result


def configure_saved_ai(model,settings):
    provider=settings.get('llm_provider','ollama')
    model.web_search_enabled=bool(settings.get('web_search_enabled',True))
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
        llm=LLM(persist_memory=False)
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
    _app.state.tracking_only = False if startup_mode == 'agent' else bool(cfg.get('vtuber_tracking_only', False))
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
        llm.user_address=cfg.get('user_address','sir')
    _app.state.renderer_ready=False
    # Desktop GPU uploads must finish before local inference reserves VRAM.
    _app.state.llm_warmup = None if _app.state.tracking_only or os.environ.get('SAKURA_DESKTOP')=='1' else asyncio.create_task(asyncio.to_thread(llm.warmup))
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
    if cfg.get('phone_link_enabled'):
        from mobile_link import link as phone_link
        phone_link.start(gui_server.port)
    print(f"🌐 Open  {gui_server.url()}  in your browser\n")

    # Auto-open browser
    if os.environ.get('SAKURA_DESKTOP') != '1':
        webbrowser.open(gui_server.url())

    try:
        yield
    finally:
        if llm and not getattr(llm,'persist_memory',False):
            await run_in_threadpool(llm.clear_history)
        from screen_audio import listener as audio_listener
        await run_in_threadpool(audio_listener.stop)
        from mobile_link import link as phone_link
        phone_link.stop()
        from spout_output import output as spout_sender
        await run_in_threadpool(spout_sender.stop)
        from virtual_camera import output as virtual_camera_sender
        await run_in_threadpool(virtual_camera_sender.stop)
        from rvc_manager import stop_rvc_service
        await run_in_threadpool(stop_rvc_service)
        from youtube_chat import chat as youtube_inbox
        await run_in_threadpool(youtube_inbox.stop)
        from nvidia_ar_tracker import tracker as nvidia_face_tracker
        await run_in_threadpool(nvidia_face_tracker.stop)
        from nvidia_expressionapp_tracker import tracker as nvidia_dlc_tracker
        await run_in_threadpool(nvidia_dlc_tracker.stop)
        from ollama_runtime import stop
        await run_in_threadpool(stop)


app = FastAPI(title="Sakura", lifespan=lifespan)

@app.middleware('http')
async def revalidate_app_code(request, call_next):
    response=await call_next(request)
    path=request.url.path
    if path=='/' or (path.startswith('/static/') and path.endswith(('.js','.mjs','.css','.html'))):
        # Keep cached code, but check its ETag/mtime on each load. Models and
        # large textures retain their normal cache behavior.
        response.headers['Cache-Control']='no-cache'
    return response

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
    blocked = ('/api/tts/', '/api/vision', '/api/chat/attachments')
    if EDITION=='vtuber' and request.url.path.startswith('/api/chat/attachments'):
        return JSONResponse({'error':'Chat attachments are available in Sakura Companion AI modes.'},409)
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

@app.post('/api/virtual-camera/configure')
async def configure_virtual_camera(payload: dict):
    from virtual_camera import output
    if type(payload.get('enabled')) is not bool:
        return JSONResponse({'error':'enabled must be true or false'},400)
    try:
        return await run_in_threadpool(output.configure,payload['enabled'],'Sakura')
    except ValueError as error:
        return JSONResponse({'error':str(error)},400)

@app.post('/api/virtual-camera/frame')
async def virtual_camera_frame(request: Request, width: int, height: int):
    from virtual_camera import output
    if not 1 <= width <= 1280 or not 1 <= height <= 1280:
        return JSONResponse({'error':'Invalid frame dimensions'},400)
    expected=width*height*4
    pixels=bytearray()
    async for chunk in request.stream():
        if len(pixels)+len(chunk)>expected:
            return JSONResponse({'error':'Frame exceeds expected size'},400)
        pixels.extend(chunk)
    try:
        output.submit(request.headers.get('x-camera-session',''),bytes(pixels),width,height)
        return {'ok':True,'device':output.status()['device']}
    except ValueError:
        return JSONResponse({'error':output.error or 'Virtual camera session stopped. Enable it again.'},409)

@app.get('/api/tracking/nvidia-sdk')
async def nvidia_sdk_status():
    from nvidia_ar_setup import sdk_status
    return await run_in_threadpool(sdk_status,get_settings().get('nvidia_ar_sdk_folder',''))

@app.post('/api/tracking/nvidia-sdk/download')
async def download_nvidia_sdk():
    from nvidia_ar_setup import CORE_DOWNLOAD_URL
    if sys.platform!='win32':
        return JSONResponse({'error':'This package is for Windows x64 RTX PCs.'},400)
    opened=await run_in_threadpool(webbrowser.open,CORE_DOWNLOAD_URL)
    return {'ok':bool(opened),'url':CORE_DOWNLOAD_URL,'message':'Download opened in your browser. Sign in to your own NVIDIA account if requested. After it finishes, choose Import downloaded SDK ZIP. Download progress is shown in your browser.'}

@app.post('/api/tracking/nvidia-sdk/import')
async def import_nvidia_sdk(file: UploadFile = File(...)):
    from nvidia_ar_setup import import_sdk_archive
    try:
        result=await run_in_threadpool(import_sdk_archive,file.file,BASE_DIR/'optional'/'nvidia-ar')
        save_settings({'nvidia_ar_sdk_folder':result['folder']})
        return result
    except Exception as error:
        return JSONResponse({'error':str(error)},400)
    finally:
        await file.close()

def _started_locally(request: Request):
    """Allow same-origin and native-webview calls; refuse POSTs driven by another website.

    A cross-origin page cannot read these responses, but a multipart or JSON POST still
    executes, so the endpoints that launch installers have to check who is asking.
    """
    origin = str(request.headers.get('origin') or '').strip()
    if not origin:
        # No Origin means a non-browser caller (the desktop window or a local script),
        # unless the browser itself reports the request as cross-site.
        return str(request.headers.get('sec-fetch-site') or '').lower() != 'cross-site'
    from urllib.parse import urlsplit
    try:
        host = (urlsplit(origin).hostname or '').strip('[]')
    except ValueError:
        return False
    return host in ('localhost', '127.0.0.1', '::1', '::ffff:127.0.0.1')


@app.post('/api/tracking/nvidia-sdk/install-features')
async def install_nvidia_sdk_features(request: Request):
    from nvidia_ar_feature_installer import installer
    from nvidia_ar_setup import sdk_status
    if not _started_locally(request):
        return JSONResponse({'error':'NVIDIA feature installation can only be started from this computer.'},403)
    try:
        payload=await request.json()
        api_key=str(payload.get('api_key','')).strip()
        folder=str(payload.get('folder') or get_settings().get('nvidia_ar_sdk_folder','')).strip()
        detected=await run_in_threadpool(sdk_status,folder)
        if not detected.get('installed'):
            return JSONResponse({'error':'Install NVIDIA AR SDK Core first, then install the face-tracking features.'},409)
        save_settings({'nvidia_ar_sdk_folder':detected['folder']})
        result=await run_in_threadpool(installer.start,detected['folder'],api_key)
        # Never echo or persist the submitted NGC key.
        return result
    except (ValueError,FileNotFoundError,RuntimeError) as error:
        return JSONResponse({'error':str(error)},400)
    except Exception as error:
        return JSONResponse({'error':f'Could not start NVIDIA feature setup: {error}'},400)

@app.get('/api/tracking/nvidia-sdk/install-features')
async def nvidia_sdk_features_install_status():
    from nvidia_ar_feature_installer import installer
    return installer.status()

@app.get('/api/tracking/nvidia-ar')
async def nvidia_ar_tracking_status():
    from nvidia_ar_tracker import tracker
    return tracker.snapshot()

@app.post('/api/tracking/nvidia-ar/start')
async def start_nvidia_ar_tracking():
    from nvidia_ar_setup import sdk_status
    from nvidia_ar_tracker import tracker
    detected=await run_in_threadpool(sdk_status,get_settings().get('nvidia_ar_sdk_folder',''))
    if not detected.get('tracking_ready'):
        return JSONResponse({'error':detected.get('message','NVIDIA AR SDK is not ready.'),'sdk':detected},409)
    try:
        return await run_in_threadpool(tracker.start,detected['folder'])
    except Exception as error:
        return JSONResponse({'error':str(error)},500)

@app.post('/api/tracking/nvidia-ar/frame')
async def submit_nvidia_ar_frame(request: Request, width: int, height: int):
    from nvidia_ar_tracker import tracker
    try:
        payload=await request.body()
        await run_in_threadpool(tracker.submit_frame,payload,width,height)
        return {'ok':True}
    except (ValueError,RuntimeError) as error:
        return JSONResponse({'error':str(error)},409)

@app.post('/api/tracking/nvidia-ar/stop')
async def stop_nvidia_ar_tracking():
    from nvidia_ar_tracker import tracker
    await run_in_threadpool(tracker.stop)
    return {'ok':True,'running':False}

@app.get('/api/tracking/nvidia-expressionapp')
async def nvidia_expressionapp_status():
    from nvidia_expressionapp_tracker import tracker, detect_installed_folder
    result=tracker.snapshot()
    result['folder']=get_settings().get('nvidia_expressionapp_folder') or detect_installed_folder()
    result['camera']=get_settings().get('nvidia_expressionapp_camera',0)
    return result

@app.post('/api/tracking/nvidia-expressionapp/install')
async def install_nvidia_expressionapp():
    if sys.platform!='win32':return JSONResponse({'error':'The Steam NVIDIA Broadcast Tracker DLC runs on Windows only.'},400)
    from nvidia_expressionapp_tracker import detect_installed_folder
    detected=detect_installed_folder()
    if detected:
        save_settings({'nvidia_expressionapp_folder':detected})
        return {'ok':True,'installed':True,'folder':detected,'message':'NVIDIA tracker DLC is already installed and ready in Sakura.'}
    # Steam performs the authenticated download and keeps the DLC associated
    # with the user's VTube Studio base-app account; Sakura must not mirror it.
    uri='steam://install/2178540'
    opened=await run_in_threadpool(webbrowser.open,uri)
    if not opened:
        opened=await run_in_threadpool(webbrowser.open,'https://store.steampowered.com/app/2178540/VTube_Studio__NVIDIA_Broadcast_Tracker/')
    return {'ok':bool(opened),'installed':False,'message':'Steam was opened for the NVIDIA Broadcast Tracker DLC. Confirm Install in Steam; Sakura will detect it when the download finishes.' if opened else 'Could not open Steam. Start Steam and try again.'}

@app.post('/api/tracking/nvidia-expressionapp/settings')
async def save_nvidia_expressionapp_settings(request: Request):
    payload=await request.json()
    folder=str(payload.get('folder','')).strip()
    camera=max(0,min(5,int(payload.get('camera',0))))
    if folder:
        from nvidia_expressionapp_tracker import ExpressionAppTracker
        try:folder=str(ExpressionAppTracker.validate_folder(folder))
        except (ValueError,OSError) as error:return JSONResponse({'error':str(error)},400)
    save_settings({'nvidia_expressionapp_folder':folder,'nvidia_expressionapp_camera':camera})
    return {'ok':True,'folder':folder,'camera':camera}

@app.post('/api/tracking/nvidia-expressionapp/start')
async def start_nvidia_expressionapp_tracking():
    from nvidia_expressionapp_tracker import tracker, detect_installed_folder
    config=get_settings()
    folder=str(config.get('nvidia_expressionapp_folder','')).strip() or detect_installed_folder()
    if not folder:return JSONResponse({'error':'Choose the installed VTube Studio NVIDIA tracker folder first. This is the Steam DLC MXTracker/v2 folder.'},409)
    try:
        save_settings({'nvidia_expressionapp_folder':folder})
        return await run_in_threadpool(tracker.start,folder,config.get('nvidia_expressionapp_camera',0))
    except Exception as error:return JSONResponse({'error':str(error)},409)

@app.post('/api/tracking/nvidia-expressionapp/stop')
async def stop_nvidia_expressionapp_tracking():
    from nvidia_expressionapp_tracker import tracker
    await run_in_threadpool(tracker.stop)
    return {'ok':True,'running':False}

@app.get('/api/tracking/vbridger')
async def vbridger_tracking_status():
    """Receive VBridger VMC blendshape packets on localhost UDP."""
    from vbridger_receiver import receiver
    try:
        await run_in_threadpool(receiver.start)
    except OSError as error:
        return JSONResponse({'connected':False,'blendshapes':{},'error':f'Could not listen on 127.0.0.1:39539 ({error}). Close any other VMC receiver or change its port.'},409)
    return receiver.snapshot()

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

@app.get('/api/assistant-tools/capabilities')
async def assistant_capabilities():
    from assistant_tools import capabilities
    return {'capabilities':capabilities()}

@app.get('/api/assistant-tools/status')
async def assistant_system_status():
    if not get_settings().get('computer_control_enabled',False):return JSONResponse({'error':'Enable computer access first.'},403)
    from system_tools import system_status
    try:return await run_in_threadpool(system_status)
    except (OSError,RuntimeError) as error:return JSONResponse({'error':str(error)},503)


@app.post('/api/game-mode/cloud-fallback')
async def game_mode_cloud_fallback(payload: dict):
    """Temporarily route Game Mode replies to the saved cloud provider under VRAM pressure."""
    if type(payload.get('active')) is not bool:
        return JSONResponse({'error': 'active must be true or false.'}, 400)
    if not llm or getattr(app.state, 'tracking_only', False):
        return JSONResponse({'error': 'AI replies are unavailable in this mode.'}, 409)
    cfg = get_settings()
    active = payload['active']
    try:
        if active:
            if cfg.get('game_cloud_auto_enabled') is False:
                return {'ok':True,'active':False,'reason':'Automatic game cloud fallback is disabled.'}
            if cfg.get('llm_provider') != 'ollama':
                return {'ok': True, 'active': False, 'reason': 'Local LLM is not selected.'}
            provider = cfg.get('last_cloud_provider', 'gemini')
            if provider == 'gemini':
                key = get_gemini_key()
                if not key:
                    return {'ok': True, 'active': False, 'reason': 'No saved Gemini key is available.'}
                # Switching replies alone would leave Ollama resident in VRAM.
                # Unload its active models first so the fallback frees GPU memory.
                await run_in_threadpool(_unload_game_local_models)
                await run_in_threadpool(llm.configure_provider, 'gemini', cfg.get('gemini_model', 'gemini-flash-latest'), key)
            else:
                from cloud_api import PROVIDERS
                from credentials import get_cloud_key
                if provider not in PROVIDERS:
                    return {'ok': True, 'active': False, 'reason': 'No saved cloud provider is configured.'}
                endpoint = cfg.get('cloud_endpoint', '')
                key = get_cloud_key(provider, endpoint)
                if not key:
                    return {'ok': True, 'active': False, 'reason': f'No saved {provider} key is available.'}
                await run_in_threadpool(_unload_game_local_models)
                await run_in_threadpool(llm.configure_cloud, provider, cfg.get('cloud_model', ''), key, endpoint, cfg.get('cloud_vision', False))
            app.state.game_cloud_fallback_active = True
            app.state.game_cloud_fallback_provider = provider
            return {'ok': True, 'active': True, 'provider': provider}

        if getattr(app.state, 'game_cloud_fallback_active', False):
            fallback_provider = getattr(app.state, 'game_cloud_fallback_provider', '')
            # If the user changed providers in Settings while Game Mode was
            # active, preserve that newer choice instead of forcing local.
            if cfg.get('llm_provider') == 'ollama' and getattr(llm, 'provider', '') == fallback_provider:
                await run_in_threadpool(llm.configure_local, (cfg.get('game_ollama_model') if getattr(app.state,'game_model_active',False) else '') or cfg.get('ollama_model', OLLAMA_MODEL),
                    cfg.get('ollama_models_folder', ''), cfg.get('gemini_fallback_enabled', False),
                    cfg.get('ollama_context', 4096), cfg.get('local_timeout', 20))
            app.state.game_cloud_fallback_active = False
            app.state.game_cloud_fallback_provider = ''
            return {'ok': True, 'active': False, 'provider': getattr(llm, 'provider', cfg.get('llm_provider'))}
        return {'ok': True, 'active': False, 'provider': getattr(llm, 'provider', cfg.get('llm_provider'))}
    except (ValueError, OSError, RuntimeError) as error:
        return JSONResponse({'error': str(error)}, 503)


def _unload_game_local_models():
    if not llm or not getattr(llm, 'base_url', ''):
        return
    import requests
    with llm._lock:
        try:
            probe = requests.get(llm.base_url + '/api/tags', timeout=(2, 5))
            probe.raise_for_status()
        except requests.RequestException as error:
            # A stopped/unavailable Ollama server has no resident model to free.
            chain, seen = [error], set()
            import errno
            while chain:
                item = chain.pop()
                if id(item) in seen: continue
                seen.add(id(item))
                if isinstance(error, requests.ConnectionError) and getattr(item, 'errno', None) in (errno.ECONNREFUSED, 10061): return
                chain.extend(value for value in (getattr(item, '__cause__', None),
                    getattr(item, '__context__', None), getattr(item, 'reason', None),
                    *getattr(item, 'args', ())) if isinstance(value, BaseException))
            raise RuntimeError('Could not contact the local model runtime to free VRAM.') from None
        for model_name in {getattr(llm, 'model', ''), getattr(llm, 'vision_model', '')} - {''}:
            try:
                response = requests.post(llm.base_url + '/api/generate',
                    json={'model': model_name, 'keep_alive': 0, 'stream': False}, timeout=(3, 120))
                if response.status_code != 404:
                    response.raise_for_status()
            except requests.RequestException:
                raise RuntimeError('Could not unload the local model to free VRAM. Staying on local AI.') from None

@app.get('/api/assistant-tools/runs')
async def assistant_runs():
    from assistant_tools import runs
    return {'runs':runs()}

@app.post('/api/assistant-tools/cancel')
async def assistant_cancel_run(payload:dict):
    from assistant_tools import cancel_run
    return {'cancelled':cancel_run(payload.get('id'))}

@app.post('/api/assistant-tools/device')
async def assistant_device_action(payload:dict):
    cfg=get_settings();kind=payload.get('action');remote=payload.get('phone') is True
    if kind in ('clipboard.read','clipboard.write'):
        if not cfg.get('phone_clipboard_enabled',False):return JSONResponse({'error':'Enable phone clipboard sharing on the PC first.'},403)
        from native_clipboard import read_text,copy_text
        try:
            if kind=='clipboard.read':return {'ok':True,'text':await run_in_threadpool(read_text)}
            return {'ok':True,**await run_in_threadpool(copy_text,payload.get('text'))}
        except (ValueError,RuntimeError,OSError) as error:return JSONResponse({'error':str(error)},400)
    if not cfg.get('computer_control_enabled',False) or (remote and not cfg.get('phone_system_access_enabled',False)):
        return JSONResponse({'error':'Enable computer access and the requested phone PC-tools permission first.'},403)
    if kind not in ('system.status','audio.volume'):return JSONResponse({'error':'Unsupported device action.'},400)
    from assistant_tools import execute
    args={}
    if kind=='audio.volume':
        operation=payload.get('operation','get')
        if operation not in ('get','set','up','down','mute','unmute'):return JSONResponse({'error':'Unsupported volume action.'},400)
        value=payload.get('value')
        if operation=='set' and (type(value) not in (int,float) or not 0<=value<=100):return JSONResponse({'error':'Choose volume from 0 to 100.'},400)
        args={'action':operation,'value':value}
    try:return await run_in_threadpool(execute,kind,args)
    except (OSError,ValueError,RuntimeError) as error:return JSONResponse({'error':str(error)},503)

@app.post('/api/mobile/tracking-control')
async def mobile_tracking_control(payload:dict):
    from mobile_link import link
    try:return link.control_tracking(payload)
    except ValueError as error:return JSONResponse({'error':str(error)},409)

@app.get('/api/mobile/link')
async def mobile_link_info():
    from mobile_link import link
    return link.info()

@app.post('/api/mobile/link')
async def mobile_link_toggle(payload:dict):
    from mobile_link import link
    if payload.get('forget'):return link.forget_device(str(payload['forget']))
    if payload.get('new'):return link.new_pairing_code()
    save_settings({'phone_link_enabled':bool(payload.get('enabled'))})
    if payload.get('enabled'):return link.start(gui_server.port)
    link.stop();return link.info()

@app.post('/api/mobile/model')
async def mobile_model_transfer(payload:dict):
    from mobile_link import link
    try:return {'ok':True,'model':await run_in_threadpool(link.stage_model,payload.get('model',''))}
    except (ValueError,OSError) as error:return JSONResponse({'error':str(error)},400)

@app.post('/api/mobile/poll')
async def mobile_link_poll(payload:dict):
    from mobile_link import link
    return link.poll(payload)

@app.post('/api/mobile/transfer-status')
async def mobile_transfer_status(payload:dict):
    from mobile_link import link
    try:return link.transfer_result(str(payload.get('request_id','')),str(payload.get('status','')),str(payload.get('error','')))
    except ValueError as error:return JSONResponse({'error':str(error)},400)

@app.get('/api/mobile/transfer-status')
async def mobile_transfer_request_info():
    from mobile_link import link
    return {'enabled':link.enabled,'request':link.transfer_request}


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


# ── opt-in VTuber Collab model packages ──────────────────────────
_COLLAB_MODEL_ROOT = Path(tempfile.gettempdir()) / 'sakura-collab-models'
_COLLAB_MODEL_ROOT.mkdir(parents=True, exist_ok=True)
_COLLAB_PACKAGE_MAX_BYTES = 300 * 1024 * 1024
_COLLAB_PACKAGE_MAX_FILES = 150


@app.post('/api/collab/package')
async def collab_model_package(payload: dict):
    """Create a bounded archive of the currently selected model's folder."""
    import io, zipfile, urllib.parse
    try:
        relative = urllib.parse.unquote(str(payload.get('path') or '')).replace('\\', '/').strip('/')
        if not relative or any(part in {'', '.', '..'} for part in relative.split('/')):
            return JSONResponse({'error': 'Choose a valid model path.'}, 400)
        source = (MODELS_DIR / relative).resolve()
        source.relative_to(MODELS_DIR.resolve())
        if not source.is_file() or source.suffix.lower() not in {'.pmx', '.vrm', '.json'}:
            return JSONResponse({'error': 'The selected file is not a supported avatar model.'}, 400)
        folder = source.parent
        files = sorted(p for p in folder.rglob('*') if p.is_file() and not p.is_symlink() and '__MACOSX' not in p.parts and not p.name.startswith('._'))
        if len(files) > _COLLAB_PACKAGE_MAX_FILES:
            return JSONResponse({'error': f'Model package has more than {_COLLAB_PACKAGE_MAX_FILES} files.'}, 413)
        total = sum(p.stat().st_size for p in files)
        if total > _COLLAB_PACKAGE_MAX_BYTES:
            return JSONResponse({'error': 'Model package exceeds the 300 MB collab limit.'}, 413)
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
            for path in files:
                archive.write(path, path.relative_to(folder).as_posix())
        if output.tell() > _COLLAB_PACKAGE_MAX_BYTES:
            return JSONResponse({'error': 'Compressed model package exceeds the 300 MB collab limit.'}, 413)
        entry = source.relative_to(folder).as_posix()
        return Response(output.getvalue(), media_type='application/zip', headers={
            'X-Sakura-Collab-Entry': urllib.parse.quote(entry, safe='/'),
            'X-Sakura-Collab-Name': urllib.parse.quote(source.name, safe=''),
            'Content-Disposition': 'attachment; filename="sakura-avatar.zip"',
        })
    except (ValueError, OSError) as exc:
        return JSONResponse({'error': f'Could not package the selected model: {exc}'}, 400)


@app.post('/api/collab/import')
async def collab_import_model(request: Request):
    """Receive an invited peer's explicitly shared avatar into a temp folder."""
    import io, secrets, zipfile, urllib.parse
    try:
        body = await request.body()
        if not body or len(body) > _COLLAB_PACKAGE_MAX_BYTES:
            return JSONResponse({'error': 'The transferred model package is empty or exceeds 300 MB.'}, 413)
        entry = urllib.parse.unquote(str(request.headers.get('x-sakura-collab-entry', ''))).replace('\\', '/').strip('/')
        if not entry or any(part in {'', '.', '..'} for part in entry.split('/')):
            return JSONResponse({'error': 'The model package entry is invalid.'}, 400)
        try:
            archive = zipfile.ZipFile(io.BytesIO(body))
        except zipfile.BadZipFile:
            return JSONResponse({'error': 'The transferred model package is not a valid ZIP.'}, 400)
        infos = [item for item in archive.infolist() if not item.is_dir()]
        if len(infos) > _COLLAB_PACKAGE_MAX_FILES:
            return JSONResponse({'error': 'The model package contains too many files.'}, 413)
        if sum(item.file_size for item in infos) > 600 * 1024 * 1024:
            return JSONResponse({'error': 'The uncompressed model package exceeds the 600 MB limit.'}, 413)
        if entry not in {item.filename for item in infos}:
            return JSONResponse({'error': 'The model entry file is missing from the package.'}, 400)
        safe_infos=[];seen=set()
        for item in infos:
            name=item.filename.replace('\\', '/')
            if name.startswith('/') or any(part in {'', '.', '..'} for part in name.split('/')):
                return JSONResponse({'error': 'Unsafe path in transferred model package.'}, 400)
            if name in seen:
                return JSONResponse({'error': 'Duplicate path in transferred model package.'}, 400)
            seen.add(name);safe_infos.append((item,name))
        token = secrets.token_urlsafe(18)
        destination = (_COLLAB_MODEL_ROOT / token).resolve()
        destination.mkdir(parents=True, exist_ok=False)
        for item,name in safe_infos:
            target = (destination / name).resolve()
            target.relative_to(destination)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(item) as source, target.open('wb') as output:
                import shutil
                shutil.copyfileobj(source, output, 1024 * 1024)
        return {'ok': True, 'model_url': f'/collab-models/{token}/' + '/'.join(urllib.parse.quote(part) for part in entry.split('/'))}
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        return JSONResponse({'error': f'Could not import the shared model: {exc}'}, 400)


@app.get('/collab-models/{token}/{file_path:path}')
async def collab_model_file(token: str, file_path: str):
    import re, urllib.parse
    if not re.fullmatch(r'[A-Za-z0-9_-]{16,40}', token):
        return JSONResponse({'error': 'Invalid temporary model session.'}, 404)
    relative = urllib.parse.unquote(file_path).replace('\\', '/').strip('/')
    if not relative or any(part in {'', '.', '..'} for part in relative.split('/')):
        return JSONResponse({'error': 'Invalid model asset path.'}, 400)
    root = (_COLLAB_MODEL_ROOT / token).resolve()
    target = (root / relative).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return JSONResponse({'error': 'Forbidden'}, 403)
    if not target.is_file():
        return JSONResponse({'error': 'Shared model asset not found.'}, 404)
    return FileResponse(str(target))


@app.delete('/api/collab/import/{token}')
async def collab_remove_import(token: str):
    import re, shutil
    if not re.fullmatch(r'[A-Za-z0-9_-]{16,40}', token):
        return JSONResponse({'error': 'Invalid temporary model session.'}, 404)
    root = _COLLAB_MODEL_ROOT.resolve()
    target = (_COLLAB_MODEL_ROOT / token).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return JSONResponse({'error': 'Forbidden'}, 403)
    if target.is_dir():
        shutil.rmtree(target, ignore_errors=True)
    return {'ok': True}


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


@app.post('/api/renderer/ready')
async def renderer_ready():
    if getattr(app.state,'renderer_ready',False):return {'ok':True}
    app.state.renderer_ready=True
    if llm and not getattr(app.state,'tracking_only',False) and getattr(llm,'provider',None)=='ollama':
        async def settled_warmup():
            await asyncio.sleep(1)
            if llm and not getattr(app.state,'tracking_only',False):await asyncio.to_thread(llm.warmup)
        if getattr(app.state,'llm_warmup',None) is None:
            app.state.llm_warmup=asyncio.create_task(settled_warmup())
    return {'ok':True}


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


VOICE_FOLDER_NAME = re.compile(r'^[a-z0-9_]{1,48}$')
MAX_RVC_BYTES = 512 * 1024 * 1024


def _rvc_target(folder, filename, suffix):
    """Only one plain, correctly-typed file name may land in this character's own folder."""
    given = Path(str(filename or '')).name
    if not given or given != Path(given).name or Path(given).is_absolute():
        raise ValueError(f'Upload one {suffix} file, not a folder or a renamed archive.')
    target = (folder / given).resolve()
    if target.parent != folder.resolve() or target.suffix.lower() != suffix:
        raise ValueError(f'That {suffix} file name is not allowed.')
    return target


async def _drain_upload(upload, target, limit):
    written = 0
    try:
        with target.open('wb') as handle:
            while chunk := await upload.read(1024 * 1024):
                written += len(chunk)
                if written > limit:
                    raise ValueError('Voice files must be under 512 MB.')
                handle.write(chunk)
    except BaseException:
        target.unlink(missing_ok=True)
        raise


@app.post("/api/voices/upload")
async def upload_voice_model(
    character_name: str = Form(...),
    pth_file: UploadFile = File(...),
    index_file: UploadFile = File(None),
):
    """Upload custom RVC .pth and .index character voice files."""
    name_clean = character_name.strip().lower().replace(" ", "_")
    if not VOICE_FOLDER_NAME.match(name_clean):
        return JSONResponse({'error': 'Use up to 48 letters, numbers, underscores or spaces for the character name.'}, 400)
    target_dir = VOICES_DIR / name_clean
    pth_path = index_path = None
    try:
        pth_path = _rvc_target(target_dir, pth_file.filename, '.pth')
        if index_file and index_file.filename:
            index_path = _rvc_target(target_dir, index_file.filename, '.index')
        target_dir.mkdir(parents=True, exist_ok=True)
        # Save the index first: a failed .pth then leaves the previous voice pair untouched.
        if index_path:
            await _drain_upload(index_file, index_path, MAX_RVC_BYTES)
        await _drain_upload(pth_file, pth_path, MAX_RVC_BYTES)
    except ValueError as error:
        return JSONResponse({'error': str(error)}, 400)
    except OSError as error:
        return JSONResponse({'error': f'Could not write the voice files: {error}'}, 400)

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
    if 'response_restriction_level' in payload and payload['response_restriction_level'] not in ('off','medium','strict'):
        return JSONResponse({'error':'Choose off, medium or strict response restrictions.'},400)
    if 'evidence_confidence_threshold' in payload:
        import math
        value=payload['evidence_confidence_threshold']
        if type(value) not in (int,float) or not math.isfinite(value) or not 0 <= value <= 1:
            return JSONResponse({'error':'Evidence threshold must be a finite number from 0 to 1.'},400)
    if 'news_area' in payload:
        if not isinstance(payload['news_area'], str) or len(payload['news_area']) > 100:
            return JSONResponse({'error':'News area must be a city or state of up to 100 characters.'},400)
        payload['news_area'] = payload['news_area'].strip()
    if 'user_address' in payload and payload['user_address'] not in ('sir','maam','none'):
        return JSONResponse({'error':'Choose Sir, Ma’am or No title.'},400)
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
    for field in ('phone_system_access_enabled','phone_clipboard_enabled','wake_word_enabled', 'computer_control_enabled', 'preserve_configuration_on_reinstall', 'physics_enabled', 'pmx_texture_reference'):
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
    if 'game_ollama_model' in payload and (not isinstance(payload['game_ollama_model'],str) or
            (payload['game_ollama_model'] and not re.fullmatch(r'[A-Za-z0-9._:/-]{1,150}',payload['game_ollama_model']))):
        return JSONResponse({'error':'Choose a valid game model name.'},400)
    if 'game_cloud_auto_enabled' in payload and type(payload['game_cloud_auto_enabled']) is not bool:
        return JSONResponse({'error':'Choose whether automatic game cloud fallback is enabled.'},400)
    for field, minimum, maximum in (('ollama_context', 1024, 8192), ('local_timeout', 5, 120)):
        if field in payload and (type(payload[field]) is not int or not minimum <= payload[field] <= maximum):
            return JSONResponse({'error': f'{field} must be between {minimum} and {maximum}.'}, 400)
    if 'gemini_fallback_enabled' in payload and type(payload['gemini_fallback_enabled']) is not bool:
        return JSONResponse({'error': 'Choose whether Gemini fallback is enabled.'}, 400)
    if 'web_search_enabled' in payload and type(payload['web_search_enabled']) is not bool:
        return JSONResponse({'error': 'Choose whether Sakura may look answers up online.'}, 400)
    brave_key = payload.pop('brave_key', None)
    if brave_key is not None and (not isinstance(brave_key, str) or len(brave_key) > 200
            or any(ord(c) < 32 or ord(c) > 126 for c in brave_key)):
        return JSONResponse({'error': 'Invalid Brave Search API key.'}, 400)
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
        if payload.get('clear_brave_key'):
            set_cloud_key('brave','')
        elif brave_key and brave_key.strip():
            set_cloud_key('brave',brave_key.strip())
        if payload.get('clear_gemini_key'):
            set_gemini_key('')
        elif key and key.strip():
            set_gemini_key(key.strip())
        updated = save_settings(payload)
        if llm and 'web_search_enabled' in payload:
            llm.web_search_enabled = payload['web_search_enabled']
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
    if llm and 'user_address' in payload:
        llm.user_address=payload['user_address']
    if llm and 'evidence_confidence_threshold' in payload:
        llm.evidence_confidence_threshold=payload['evidence_confidence_threshold']
    if llm and 'response_restriction_level' in payload:
        llm.response_restriction_level=payload['response_restriction_level']
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

@app.get('/api/ollama/manager')
async def model_manager_status():
    from local_model_manager import manager
    return {'catalog':manager.catalog(),'job':manager.status()}

@app.post('/api/ollama/manager/{operation}')
async def manage_local_model(operation: str, payload: dict):
    from local_model_manager import manager
    if EDITION=='vtuber' or getattr(app.state,'tracking_only',False):
        return JSONResponse({'error':'Manage language models in Companion AI mode.'},409)
    try:
        cfg=get_settings()
        folder=payload.get('folder',cfg.get('ollama_models_folder',''))
        model=str(payload.get('model','')).strip()
        if operation=='search':
            from local_model_manager import registry_search
            return await run_in_threadpool(registry_search,payload.get('query',''),payload.get('family',''))
        if operation=='details':
            from local_model_manager import model_details
            return await run_in_threadpool(model_details,model,folder)
        if operation=='import':
            from local_model_manager import import_gguf
            return await run_in_threadpool(import_gguf,manager,model,payload.get('paths'),folder)
        if operation=='download':return await run_in_threadpool(manager.download,model,folder)
        if operation=='delete':
            if payload.get('confirm')!=model:raise ValueError('Confirm the exact model to uninstall.')
            protected=[cfg.get('game_ollama_model'),cfg.get('ollama_model'),getattr(llm,'model',''),getattr(llm,'vision_model',cfg.get('ollama_vision_model',''))]
            return await run_in_threadpool(manager.remove,model,folder,protected)
        raise ValueError('Unknown model operation.')
    except Exception as error:
        return JSONResponse({'error':str(error)},400)

@app.post('/api/llm/models')
async def discover_cloud_models(payload:dict):
    if EDITION=='vtuber' or getattr(app.state,'tracking_only',False):return JSONResponse({'error':'Cloud model discovery is available in AI modes only.'},409)
    from cloud_api import detect_provider,PROVIDERS
    from cloud_diagnostics import discover
    from credentials import get_cloud_key,get_gemini_key
    try:
        settings=get_settings();provider=str(payload.get('provider') or settings['llm_provider']);key=str(payload.get('api_key') or '').strip()
        if provider=='auto':provider=detect_provider(key) if key else settings['llm_provider']
        if provider!='gemini' and provider not in PROVIDERS:raise ValueError('Choose a cloud provider first.')
        endpoint=str(payload.get('endpoint') or '')
        if not key:key=get_gemini_key() if provider=='gemini' else get_cloud_key(provider,endpoint)
        models=await run_in_threadpool(discover,provider,key,str(payload.get('model') or ''),endpoint)
        return {'ok':True,'provider':provider,'models':models,'message':'Model listing does not verify generation quota or image support. Select a model and use Test API.'}
    except ValueError as error:return JSONResponse({'error':str(error)},400)

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


async def short_singing_reply(text,cfg):
    from singing import make_vocalise,named_song
    if not tts:return JSONResponse({'error':'Select an available voice first.'},503)
    import uuid
    from config import AUDIO_DIR,voice_language
    try:
        source=await tts.speak_to_file_async('La.')
        target=AUDIO_DIR/('sing-'+uuid.uuid4().hex+'.wav')
        await run_in_threadpool(make_vocalise,source,target)
        language=voice_language(cfg.get('selected_voice','kokoro_af_heart'))
        reply={'Hindi':'यह रही एक छोटी सी नई ला-ला धुन।','Hinglish':'Yeh rahi ek chhoti si original la-la dhun.'}.get(language,'Here is a short original la-la tune.')
        if named_song(text):
            reply={'Hindi':'मैं अभी उस गाने को नहीं गा सकती। इसकी जगह एक छोटी सी अपनी धुन सुनाती हूँ।',
                   'Hinglish':'Main abhi woh gaana perform nahi kar sakti. Uski jagah ek chhoti original dhun sunati hoon.'}.get(language,"I can’t perform that named song yet. Here’s a short original tune instead.")
        return {'reply':reply,'audio':None,'performance_audio':'/audio/'+target.name,'voice_error':None}
    except Exception:
        return JSONResponse({'error':'The short tune could not be generated with this voice. Try a local Kokoro voice.'},503)


@app.post('/api/vtuber/reply')
async def reply_vtuber(payload: dict):
    if not llm:
        return JSONResponse({'error': 'Sakura is still starting.'}, 503)
    author, text = payload.get('author', ''), payload.get('text', '')
    if not isinstance(author, str) or not isinstance(text, str) or not text.strip() or len(text) > 500 or len(author) > 80:
        return JSONResponse({'error': 'Invalid viewer message.'}, 400)
    # Explicit avatar actions are deterministic and should run before the
    # factual-response gate. Viewer performance remains isolated from private
    # companion memory and only runs when the renderer reports capability.
    cfg=get_settings()
    from dance_commands import dance_action, dance_reply
    motion=dance_action(text)
    if motion:
        if motion=='unsupported':
            return {'reply':'I can do Groove, Side step, Arm wave, Twist, Disco and March. Which would you like?',
                    'speech_reply':'I can do Groove, Side step, Arm wave, Twist, Disco and March. Which would you like?',
                    'audio':None,'avatar_motion':None,'response_kind':'conversation'}
        from config import voice_language
        supported=payload.get('avatar_can_dance') is True
        reply=dance_reply(motion,voice_language(get_settings().get('selected_voice','kokoro_af_heart')),supported)
        from tts import polish_spoken_text
        return {'reply':reply,'speech_reply':polish_spoken_text(reply),'audio':None,
                'avatar_motion':motion if supported else None,'response_kind':'conversation'}
    from singing import requested as singing_requested
    if singing_requested(text):
        return await short_singing_reply(text,cfg)
    from response_evidence import retrieve, response_answer, threshold
    cfg['_cohost']=True
    try:
        image=payload.get('screen_image')
        validate_screen_frames(payload.get('screen_frames'),image)
        if image:validate_screen_frames([image],image)
    except ValueError as error:
        return JSONResponse({'error':str(error)},400)
    if cfg.get('response_restriction_level')=='off':
        from tts import polish_spoken_text
        llm.response_restriction_level='off'
        reply=await run_in_threadpool(llm.viewer_reply,author,text,screen_image=image,screen_frames=payload.get('screen_frames'))
        return {'reply':reply,'speech_reply':polish_spoken_text(reply),'audio':None,'response_kind':'conversation','response_policy':'Normal'}
    try:raw=await run_in_threadpool(retrieve,text,cfg,(),False)
    except Exception:raw=None
    answer=await run_in_threadpool(response_answer,raw,threshold(cfg),text,cfg,llm)
    return await _strict_reply(answer,{'defer_audio':True})



async def _chat_core(payload: dict, resolved_reply=None, skip_retrieval=False, preflight=False, offer_search=False):
    text = payload.get("text", "").strip()
    if not text:
        return JSONResponse({"error": "empty message"}, 400)

    cfg = get_settings()
    from chat_attachments import attachments as attachment_store
    try:attached=attachment_store.get(payload.get('attachments',[]))
    except ValueError as error:return JSONResponse({'error':str(error)},400)
    if attached:
        skip_retrieval=True
        if any(item['kind']=='image' for item in attached):
            vision=await run_in_threadpool(get_vision_status)
            if not vision['ready']:return JSONResponse({'error':'Image attachments need a vision-capable local model or cloud provider.'},503)
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
    if preflight:return None
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
    from dance_commands import dance_action, dance_reply, hand_action, hand_reply, dance_style_followup
    from avatar_gestures import laugh_request
    laughter=laugh_request(text) if not payload.get('screen_reaction') else None
    if laughter and not getattr(app.state,'tracking_only',False):
        supported=payload.get('avatar_can_dance') is True
        reply='😄' if supported else 'Select a rigged PMX or VRM model and turn off face tracking so I can perform the laugh.'
        app.state.last_avatar_action=None
        if llm:await run_in_threadpool(llm.remember_exchange,text,'Shared a laugh.' if supported else reply)
        return {'reply':reply,'audio':None,'voice_error':None,'avatar_motion':laughter if supported else None,
                'performance_audio':('/static/audio/reactions/'+('laugh-belly.wav' if laughter=='laugh_bend' else 'laugh-short.wav')+'?v=natural86') if supported else None}
    from singing import requested as singing_requested
    if not payload.get('screen_reaction') and singing_requested(text):
        result=await short_singing_reply(text,cfg)
        if isinstance(result,dict) and llm:await run_in_threadpool(llm.remember_exchange,text,result['reply'])
        return result
    hand=hand_action(text) if not payload.get('screen_reaction') else None
    if hand and not getattr(app.state,'tracking_only',False):
        from config import voice_language
        supported=payload.get('avatar_can_dance') is True
        reply=hand_reply(hand,voice_language(cfg.get('selected_voice','kokoro_af_heart')),supported)
        app.state.last_avatar_action=None
        if llm:await run_in_threadpool(llm.remember_exchange,text,reply)
        return {'reply':reply,'audio':None,'voice_error':None,'avatar_motion':hand if supported else None}
    motion=dance_action(text) if not payload.get('screen_reaction') else None
    if not payload.get('screen_reaction'):
        current=payload.get('avatar_dance_style') or (getattr(app.state,'last_dance_style',None) if getattr(app.state,'last_avatar_action',None)=='dance' else None)
        motion=dance_style_followup(text,current) or motion
    if not motion and getattr(app.state,'last_avatar_action',None)=='dance' and not payload.get('screen_reaction'):
        import re
        if re.search(r'\b(?:just do|show me|want to see|do what (?:you|u) have)\b',text,re.I):motion='groove'
    if motion and not getattr(app.state,'tracking_only',False):
        from config import voice_language
        supported=payload.get('avatar_can_dance') is True
        from user_address import address_text
        if motion=='unsupported':
            return {'reply':'I have Groove, Side step, Arm wave, Twist, Disco and March. Which would you like?','audio':None,'avatar_motion':None}
        reply=address_text(dance_reply(motion,voice_language(cfg.get('selected_voice','kokoro_af_heart')),supported),'none' if payload.get('ai_vtuber') else cfg.get('user_address','sir'))
        app.state.last_avatar_action='dance' if supported and motion!='stop' else None
        app.state.last_dance_style=motion if supported and motion!='stop' else None
        if llm:await run_in_threadpool(llm.remember_exchange,text,reply)
        return {'reply':reply,'audio':None,'voice_error':None,'avatar_motion':motion if supported else None}
    if not payload.get('screen_reaction'):app.state.last_avatar_action=None
    from assistant_commands import run_command
    command_reply = resolved_reply
    if command_reply is None and not skip_retrieval:
        command_reply = await run_in_threadpool(run_command, text, cfg.get('computer_control_enabled', False), cfg.get('assistant_name', 'Sakura')) if not payload.get('screen_reaction') else None
    if not command_reply and not skip_retrieval and not payload.get('screen_reaction'):
        from factual_grounding import gpu_memory_lookup
        command_reply = await run_in_threadpool(gpu_memory_lookup, text)
    if not command_reply and not skip_retrieval and not payload.get('screen_reaction') and not payload.get('ai_vtuber'):
        from current_information import lookup_with_context
        command_reply, pending_weather = await run_in_threadpool(
            lookup_with_context, text, getattr(app.state, 'pending_weather_date', None), cfg.get('news_area',''))
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
    if attached:live_context['attachments']=attached
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

    from user_address import address_text
    if isinstance(reply,str):reply=address_text(reply,'none' if payload.get('ai_vtuber') else cfg.get('user_address','sir'))
    if not reply:
        from llm import LLM
        language=getattr(llm,'reply_language','English')
        return JSONResponse({'error':LLM._generation_failure(language)},503)
    game_result=None
    if isinstance(reply,dict):
        game_result=reply.get('game_result')
        reply=reply['reply']
    if offer_search and not attached and not payload.get('screen_reaction') and not payload.get('camera_reaction'):
        from search_confirmation import search_consent
        reply=search_consent.offer(text,reply,getattr(llm,'reply_language','English'))
    reply_mood=getattr(llm,'last_reply_mood',None) if not command_reply else None
    if reply_mood not in ('surprised','sparkle'):reply_mood=None
    avatar_motion=None
    from persona_grounding import greeting
    if not command_reply and not payload.get('screen_reaction') and greeting(text) and payload.get('avatar_can_greet') is True and not getattr(app.state,'tracking_only',False):
        avatar_motion='greeting_wave'
    if not avatar_motion and not command_reply and not payload.get('screen_reaction') and payload.get('avatar_can_chest_tap') is True and not getattr(app.state,'tracking_only',False):
        from avatar_gestures import conversational_gesture
        avatar_motion=conversational_gesture(text,reply)
    if payload.get('defer_audio'):
        from tts import polish_spoken_text
        return {"reply": reply, "speech_reply":polish_spoken_text(reply), "audio": None, "voice_error": None, "game_result":game_result,"avatar_motion":avatar_motion,"emotion":reply_mood}

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
            "voice_notice": speech_notice(path) if audio_url else None,"avatar_motion":avatar_motion,"emotion":reply_mood}


async def _strict_reply(evidence,payload):
    from tts import polish_spoken_text
    from persona_grounding import greeting
    result={'reply':evidence.text,'audio':None,'voice_error':None,'avatar_motion':None,'game_result':None,
            **evidence.public(),'response_policy': 'Astra Strict Mode' if get_settings().get('response_restriction_level','medium')=='strict' else 'Medium'}
    if evidence.method in ('built-in conversation','nonfactual conversation'):
        result['response_kind']='conversation'
    # Authored greetings still drive the existing speech-synchronised FBX wave.
    if (evidence.method == 'built-in conversation' and greeting(payload.get('text',''))
            and payload.get('avatar_can_greet') is True
            and not payload.get('screen_reaction') and not payload.get('camera_reaction')
            and not getattr(app.state,'tracking_only',False)):
        result['avatar_motion']='greeting_wave'
    if payload.get('defer_audio'):
        result['speech_reply']=polish_spoken_text(evidence.text)
    elif tts:
        try:
            path=await tts.speak_to_file_async(evidence.text)
            if path:result['audio']='/audio/'+os.path.basename(path)
        except Exception:
            result['voice_error']='Speech is unavailable.'
    return result


@app.post('/api/chat/attachments')
async def upload_chat_attachment(file: UploadFile = File(...)):
    from chat_attachments import MAX_BYTES,extract_attachment,attachments
    data=await file.read(MAX_BYTES+1)
    await file.close()
    try:item=await run_in_threadpool(extract_attachment,file.filename,data)
    except ValueError as error:return JSONResponse({'error':str(error)},400)
    return attachments.put(item)


@app.delete('/api/chat/attachments/{token}')
async def remove_chat_attachment(token:str):
    from chat_attachments import attachments
    attachments.remove(token)
    return {'ok':True}


@app.post("/api/chat")
async def chat(payload: dict):
    from response_evidence import Evidence, UNKNOWN, retrieve, threshold, response_answer, LOCAL_SOURCES
    text=payload.get('text')
    if not isinstance(text,str) or not text.strip():
        return JSONResponse({'error':'empty message'},400)
    if get_settings().get('response_restriction_level')=='off':
        if llm:llm.response_restriction_level='off'
        from search_confirmation import search_consent
        background=any(payload.get(key) for key in ('screen_reaction','camera_reaction','screen_observation'))
        has_files=bool(payload.get('attachments'))
        if has_files:search_consent.clear()
        approval=None if background or has_files else await run_in_threadpool(search_consent.respond,text)
        from learned_answers import learned_answers
        learned=None if background or has_files or approval is not None else await run_in_threadpool(learned_answers.recall,text)
        resolved=approval if approval is not None else learned.text if learned else None
        result=await _chat_core(payload,resolved_reply=resolved,skip_retrieval=resolved is not None,offer_search=not background and approval is None)
        if isinstance(result,dict):
            result.update(response_kind='conversation',response_policy='Normal')
            if learned:result.update(learned.public(),response_kind='factual',learned_answer=True)
        return result
    preflight=await _chat_core(payload,skip_retrieval=True,preflight=True)
    if preflight is not None:return preflight
    cfg=get_settings();cfg['_pending_weather']=getattr(app.state,'pending_weather_date',None)
    cfg['_cohost']=bool(payload.get('ai_vtuber'));minimum=threshold(cfg)
    if llm:llm.evidence_confidence_threshold=minimum
    memory=getattr(llm,'trusted_memory',[]) if llm else []
    if not isinstance(memory,list):memory=[]
    if payload.get('screen_reaction') or payload.get('camera_reaction'):
        result=await _strict_reply(Evidence('[QUIET]',method='unverified visual inference suppressed'),{'defer_audio':True})
        return result
    try:
        raw=await run_in_threadpool(retrieve,text,cfg,memory)
    except Exception:
        raw=None
    if isinstance(raw,Evidence) and raw.method=='weather/news retrieval':
        app.state.pending_weather_date=getattr(raw,'pending_weather',None)
    if isinstance(raw,Evidence) and raw.memory_eligible(minimum) and llm:
        recorder=getattr(llm,'remember_evidence',None)
        if callable(recorder):
            stored=recorder(raw)
            if raw.classification=='User-provided' and stored is True:
                raw=Evidence('Saved your statement as user-provided, not independently verified.','Verified',1,
                             [{'title':'Memory write receipt','url':LOCAL_SOURCES['memory receipt'],'kind':'tool'}],'memory receipt')
    evidence=await run_in_threadpool(response_answer,raw,minimum,text,cfg,llm)
    # No call to _chat_core's action/generation path, llm.chat or _request here.
    return await _strict_reply(evidence,payload)


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


@app.post('/api/assistant/greeting')
async def assistant_greeting():
    if getattr(app.state,'tracking_only',False):return {'reply':'','audio':None}
    from user_address import greeting
    return {'reply':greeting(get_settings().get('user_address','sir')),'audio':None}


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
        input_language='hi' if voice_language(get_settings().get('selected_voice','')) in ('Hindi','Hinglish') else 'en'
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
    tmp = AUDIO_DIR / f"stt_input_{uuid.uuid4().hex}{suffix}"
    content = await audio.read()
    tmp.write_bytes(content)

    # Convert webm → wav if needed (using ffmpeg or soundfile)
    wav_path = tmp.with_suffix(".wav")
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
            tmp.unlink(missing_ok=True)
            wav_path.unlink(missing_ok=True)
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
        input_language='hi' if voice_language(get_settings().get('selected_voice','')) in ('Hindi','Hinglish') else 'en'
        text = await run_in_threadpool(stt.transcribe,audio_data,input_language)
        return {"text": text}
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, 500)
    finally:
        tmp.unlink(missing_ok=True)
        wav_path.unlink(missing_ok=True)


@app.post("/api/clear")
async def clear_history():
    from chat_attachments import attachments
    attachments.clear()
    from search_confirmation import search_consent
    search_consent.clear()
    llm.clear_history()
    return {"ok": True}


@app.post("/api/refresh-memory")
async def refresh_memory():
    from starlette.concurrency import run_in_threadpool
    count = await run_in_threadpool(llm.refresh_memory)
    return {"ok": True, "messages": count, "message": "Chat lasts only for this app session and clears when you exit." if not llm.persist_memory else "Memory refreshed."}


# ── entry point ────────────────────────────────────────────────
from agent_api import agent_router
def _agent_model_for(choice='current'):
    if choice=='current':return llm
    if choice=='ollama' or (isinstance(choice,str) and choice.startswith('ollama:')):
        if not llm or getattr(llm,'tracking_only',False):raise ValueError('Local AI is unavailable while tracking-only mode is active.')
        cfg=get_settings();model_name=cfg.get('ollama_model',llm.model)
        if choice.startswith('ollama:'):
            model_name=choice.partition(':')[2]
            if model_name not in _agent_local_model_names(cfg):raise ValueError('That local model is not installed in Sakura’s selected Ollama folder. Refresh the Agent and choose an installed model.')
        selected=copy.copy(llm)
        selected.configure_local(model_name,cfg.get('ollama_models_folder',''),
            cfg.get('gemini_fallback_enabled',False),cfg.get('ollama_context',4096),cfg.get('local_timeout',20))
        selected.provider='ollama';return selected
    if choice=='gemini':
        if not llm or not llm.gemini_api_key:raise ValueError('Google Gemini is not configured. Add a Gemini API key in Sakura Settings > AI first.')
        selected=copy.copy(llm);selected.provider='gemini';return selected
    raise ValueError('Choose Local AI or Google Gemini.')

def _agent_provider_status():
    if not llm:return []
    cfg=get_settings()
    configured=str(cfg.get('ollama_model',llm.model));names=_agent_local_model_names(cfg)
    providers=[{'id':'ollama','label':'Configured local model · '+configured,'ready':not getattr(llm,'tracking_only',False)}]
    providers.extend({'id':'ollama:'+name,'label':'Local · '+name,'ready':not getattr(llm,'tracking_only',False)} for name in names if name!=configured)
    providers.append({'id':'gemini','label':'Google Gemini · '+str(llm.gemini_model),'ready':bool(llm.gemini_api_key)})
    return providers

def _agent_local_model_names(settings):
    folder=Path(settings.get('ollama_models_folder') or 'llm-models').expanduser()
    if not folder.is_absolute():folder=BASE_DIR/folder
    names=set()
    for root in (folder/'manifests-v2',folder/'manifests'):
        if not root.is_dir():continue
        for manifest in root.rglob('*'):
            if not manifest.is_file():continue
            parts=manifest.relative_to(root).parts
            library=next((index for index,part in enumerate(parts) if part=='library'),None)
            if library is None or len(parts)<library+3:continue
            model='/'.join(parts[library+1:-1]);tag=parts[-1]
            if model and re.fullmatch(r'[A-Za-z0-9._-]{1,100}',tag) and not re.fullmatch(r'[a-f0-9]{64}',tag):names.add(model+':'+tag)
    return sorted(names,key=str.casefold)

app.include_router(agent_router(_agent_model_for,lambda:EDITION!='vtuber' and not getattr(app.state,'tracking_only',False),_agent_provider_status))

if __name__ == "__main__":
    print()
    print("  🌸 Sakura — Anime AI Assistant (GUI Mode)")
    print("  ──────────────────────────────────────────")
    print()
    gui_server.launch()


@app.post('/api/game-mode/model')
async def game_mode_model(payload: dict):
    if type(payload.get('active')) is not bool:return JSONResponse({'error':'active must be true or false'},400)
    if not llm or EDITION=='vtuber' or getattr(app.state,'tracking_only',False):return JSONResponse({'error':'AI model switching requires Companion AI mode.'},409)
    cfg=get_settings();active=payload['active']
    if cfg.get('llm_provider')!='ollama':return {'ok':True,'model':None,'provider':cfg.get('llm_provider')}
    model=(cfg.get('game_ollama_model') if active else '') or cfg['ollama_model']
    try:
        if getattr(app.state,'game_cloud_fallback_active',False):
            app.state.game_model_active=active
            return {'ok':True,'model':model,'provider':getattr(llm,'provider','')}
        from local_model_manager import model_details
        if active and cfg.get('game_ollama_model'):
            details=await run_in_threadpool(model_details,model,cfg.get('ollama_models_folder',''))
            if not details['vision']:raise ValueError('The game model must support vision for screen understanding. Select a vision model in AI settings.')
        await run_in_threadpool(llm.configure_local,model,cfg.get('ollama_models_folder',''),cfg.get('gemini_fallback_enabled',False),cfg.get('ollama_context',4096),cfg.get('local_timeout',20),validate=True)
        app.state.game_model_active=active
        return {'ok':True,'model':model,'provider':'ollama'}
    except Exception as error:return JSONResponse({'error':str(error)},400)
