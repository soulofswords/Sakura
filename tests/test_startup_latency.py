import asyncio,time,threading
from unittest.mock import Mock,patch
from functools import wraps
def async_test(fn):
    @wraps(fn)
    def run(*args,**kwargs):return asyncio.run(fn(*args,**kwargs))
    return run
import app

@async_test
async def test_desktop_serves_window_before_slow_local_runtime(monkeypatch):
    release=threading.Event();entered=threading.Event()
    model=Mock(provider='ollama',persist_memory=False)
    def configure(*args):entered.set();release.wait(5)
    model.configure_local.side_effect=configure
    cfg=app.get_settings();cfg.update(llm_provider='ollama',phone_link_enabled=False,vtuber_tracking_only=False,selected_voice='kokoro_af_heart')
    monkeypatch.setenv('SAKURA_DESKTOP','1');monkeypatch.delenv('SAKURA_START_MODE',raising=False)
    with patch('llm.LLM',return_value=model),patch.object(app,'get_settings',return_value=cfg),patch.object(app,'configure_saved_ai'),patch('rvc_manager.stop_rvc_service'),patch('mobile_link.link.stop'),patch('screen_audio.listener.stop'),patch('spout_output.output.stop'),patch('virtual_camera.output.stop'),patch('youtube_chat.chat.stop'):
        start=time.perf_counter()
        try:
            async with app.lifespan(app.app):
                elapsed=time.perf_counter()-start
                assert elapsed<1,'The startup window must not wait for inference server setup.'
                await asyncio.to_thread(entered.wait,1)
                assert not app.app.state.local_setup.done()
                assert not app.app.state.renderer_ready
                release.set();await app.app.state.local_setup
        finally:release.set()

@async_test
async def test_tracking_switch_waits_for_inflight_startup_before_unloading():
    completed=[]
    async def setup():await asyncio.sleep(.01);completed.append('configured')
    task=asyncio.create_task(setup())
    with patch.object(app.app.state,'local_setup',task,create=True),patch.object(app.app.state,'ai_unloaded',True,create=True),patch.object(app.app.state,'tracking_only',False,create=True),patch.object(app,'EDITION','companion'):
        await app.set_tracking_mode({'enabled':True})
        assert task.done() and completed==['configured']
