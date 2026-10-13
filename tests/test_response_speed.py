import asyncio
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
import app
from llm import LLM

class ResponseTests(unittest.TestCase):
    def test_status_reports_provider_without_blocking_event_loop(self):
        with patch.object(app, 'llm') as llm:
            llm.is_available.return_value = True
            llm.provider = 'gemini'
            llm.gemini_model = 'test-model'
            response = TestClient(app.app).get('/api/status')
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()['ok'])
            self.assertEqual(response.json()['model'], 'test-model')
    def test_provider_switch_does_not_wait_for_inflight_reply(self):
        with tempfile.TemporaryDirectory() as folder:
            llm = LLM(Path(folder) / 'memory.json')
            entered = threading.Event()
            release = threading.Event()
            def request(*args, **kwargs):
                entered.set()
                release.wait(3)
                return 'Hello'
            with patch.object(llm, '_request', side_effect=request):
                reply = threading.Thread(target=llm.chat, args=('hello',))
                reply.start()
                self.assertTrue(entered.wait(1))
                switched = threading.Event()
                switch = threading.Thread(target=lambda: (llm.configure_provider('gemini', api_key='synthetic-key'), switched.set()))
                switch.start()
                try:
                    self.assertTrue(switched.wait(0.5), 'Settings must not wait for the reply network call')
                finally:
                    release.set()
                    reply.join(3)
                    switch.join(3)

    def test_deferred_reply_never_waits_for_speech(self):
        with patch.object(app,'llm') as llm, patch.object(app,'tts') as tts:
            llm.chat.return_value='Hello'
            tts.speak_to_file_async=AsyncMock(return_value='sample.mp3')
            r=TestClient(app.app).post('/api/chat',json={'text':'hello','defer_audio':True})
            self.assertEqual(r.json()['reply'],'Hello')
            self.assertIsNone(r.json()['audio'])
            tts.speak_to_file_async.assert_not_awaited()
            speech=TestClient(app.app).post('/api/tts/speak',json={'text':'Hello'})
            self.assertEqual(speech.json()['audio'],'/audio/sample.mp3')
            tts.speak_to_file_async.assert_awaited_once_with('Hello')

    def test_clear_cannot_be_undone_by_background_summary(self):
        with tempfile.TemporaryDirectory() as folder:
            llm=LLM(Path(folder)/'memory.json')
            llm.history=[{'role':'user' if i%2==0 else 'assistant','content':str(i)} for i in range(40)]
            entered=threading.Event();release=threading.Event()
            def request(*args,**kwargs):
                entered.set();release.wait(2);return 'Old facts'
            with patch.object(llm,'_request',side_effect=request):
                thread=threading.Thread(target=llm._refresh_summary);thread.start()
                self.assertTrue(entered.wait(1))
                llm.clear_history();release.set();thread.join(2)
                self.assertFalse(thread.is_alive())
                self.assertEqual(llm.summary,'')
                self.assertEqual(LLM(llm.memory_path).history,[])

    def test_summary_work_runs_outside_reply_thread(self):
        with tempfile.TemporaryDirectory() as folder:
            llm=LLM(Path(folder)/'memory.json')
            llm.history=[{'role':'user' if i%2==0 else 'assistant','content':str(i)} for i in range(40)]
            entered=threading.Event();release=threading.Event()
            def refresh(): entered.set();release.wait(2)
            with patch.object(llm,'_request',return_value='Immediate reply'),patch.object(llm,'_refresh_summary',side_effect=refresh):
                self.assertEqual(llm.chat('hello'),'Immediate reply')
                self.assertTrue(entered.wait(1))
                release.set()

if __name__=='__main__': unittest.main()
