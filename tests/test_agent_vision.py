import base64
import copy
import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

import agent_vision
from agent_connections import Connections
from agent_runtime import AgentRuntime, planner_identity


class AssistantStub:
    """Shaped like the companion model: images ride in a message-level 'images' list."""
    provider = 'ollama'
    model = 'llama3.2'
    base_url = 'http://127.0.0.1:11434'
    vision_model = 'qwen3-vl:8b'

    def __init__(self, reply='A terminal window. It reads "61 GB free".'):
        self.reply = reply
        self.calls = []

    def _request_raw(self, messages, summarizing=False, model=None, structured=False, planning=False):
        self.calls.append({'messages': messages, 'summarizing': summarizing, 'model': model})
        return self.reply


class NativeStub:
    """Shaped like Sakura's own worker: one image per message, OpenAI-style content parts."""
    loaded = 'qwen3-vl-4b.gguf'
    loaded_engine = 'llama.cpp'
    root = 'X:/native'
    vision = True

    def __init__(self, reply='A photo of a desk.'):
        self.reply = reply
        self.calls = []

    def _request_raw(self, messages, structured=False, planning=False):
        self.calls.append({'messages': messages, 'structured': structured})
        return self.reply


class CloudStub(AssistantStub):
    provider = 'gemini'
    gemini_model = 'gemini-flash-latest'
    gemini_api_key = 'secret'


class VisionModuleTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)

    def png(self, name='shot.png'):
        path = self.root / name
        Image.new('RGB', (40, 24), '#123456').save(path)
        return path

    def test_local_image_is_sent_to_the_vision_model_as_bounded_text(self):
        model = AssistantStub()
        result = agent_vision.analyze(self.png(), model, '')
        self.assertTrue(result['ok'])
        self.assertIn('61 GB free', result['reading'])
        self.assertFalse(result['truncated'])
        self.assertEqual(result['filename'], 'shot.png')
        call = model.calls[0]
        self.assertEqual(call['model'], 'qwen3-vl:8b')
        self.assertTrue(call['summarizing'])
        images = call['messages'][-1]['images']
        self.assertEqual(len(images), 1)
        with Image.open(BytesIO(base64.b64decode(images[0]))) as decoded:
            self.assertEqual(decoded.format, 'JPEG')
        joined = json.dumps(call['messages'])
        self.assertIn('untrusted', joined.casefold())
        self.assertIn('Transcribe', call['messages'][-1]['content'])

    def test_a_question_replaces_the_default_reading_prompt(self):
        model = AssistantStub()
        agent_vision.analyze(self.png(), model, '  How   many\ncolumns\nare in this chart?  ')
        self.assertEqual(model.calls[0]['messages'][-1]['content'], 'How many columns are in this chart?')

    def test_native_worker_gets_one_attached_image_not_a_remote_url(self):
        model = NativeStub()
        result = agent_vision.analyze(self.png(), model, 'What is on this desk?')
        self.assertEqual(result['reading'], 'A photo of a desk.')
        parts = model.calls[0]['messages'][-1]['content']
        self.assertEqual(parts[0], {'type': 'text', 'text': 'What is on this desk?'})
        self.assertTrue(parts[1]['image_url']['url'].startswith('data:image/jpeg;base64,'))
        self.assertNotIn('http', json.dumps(parts[1]))

    def test_a_cloud_planner_is_rejected_only_for_the_shape_it_cannot_use(self):
        """Gemini rides the assistant shape, so a cloud planner still works."""
        model = CloudStub()
        self.assertIn('61 GB free', agent_vision.analyze(self.png(), model)['reading'])

    def test_long_readings_are_cut_down_to_the_evidence_budget(self):
        result = agent_vision.analyze(self.png(), AssistantStub(reply='x' * (agent_vision.MAX_READING + 500)), '')
        self.assertEqual(len(result['reading']), agent_vision.MAX_READING)
        self.assertTrue(result['truncated'])

    def test_an_unreadable_reply_is_reported_instead_of_empty_evidence(self):
        for reply in ('', '   ', None, 5):
            with self.assertRaisesRegex(ValueError, 'no usable reading'):
                agent_vision.analyze(self.png(), AssistantStub(reply=reply), '')

    def test_other_file_kinds_and_missing_models_are_refused_before_inference(self):
        note = self.root / 'notes.txt'
        note.write_text('plain text', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'PNG, JPEG or WebP'):
            agent_vision.analyze(note, AssistantStub(), '')
        with self.assertRaisesRegex(ValueError, 'vision-capable'):
            agent_vision.analyze(self.png(), None, '')
        damaged = self.root / 'broken.png'
        damaged.write_bytes(b'\x89PNG not really an image')
        with self.assertRaisesRegex(ValueError, 'could not be'):
            agent_vision.analyze(damaged, AssistantStub(), '')

    def test_pixels_are_only_read_never_written(self):
        path = self.png('keep.png')
        before = path.read_bytes()
        agent_vision.analyze(path, AssistantStub(), '')
        self.assertEqual(path.read_bytes(), before)


class LocalRuntimeBudgetTests(unittest.TestCase):
    """The real local runtime decides how much of the image the model may transcribe."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        path = Path(self.folder.name) / 'shot.png'
        Image.new('RGB', (40, 24), '#123456').save(path)
        self.image = path
        from llm import LLM
        self.llm = LLM(Path(self.folder.name) / 'memory.json')
        self.llm.configure_local('qwen3:4b', fallback=False, context=4096, timeout=8)

    def test_an_evidence_reading_keeps_room_to_transcribe_the_image(self):
        ok = Mock(status_code=200)
        ok.json.return_value = {'message': {'content': 'The chart shows three columns.'}}
        with patch('llm.requests.post', return_value=ok) as post:
            result = agent_vision.analyze(self.image, self.llm, 'How many columns are in this chart?')
        payload = post.call_args.kwargs['json']
        self.assertEqual(result['reading'], 'The chart shows three columns.')
        self.assertEqual(payload['model'], self.llm.vision_model)
        self.assertEqual(payload['options']['num_predict'], 512)
        self.assertTrue(payload['messages'][-1]['images'])

    def test_a_spoken_reply_about_a_picture_still_stays_short(self):
        ok = Mock(status_code=200)
        ok.json.return_value = {'message': {'content': 'Looks like a chart with three columns.'}}
        with patch('llm.requests.post', return_value=ok) as post:
            self.llm._request_raw([{'role': 'user', 'content': 'What is this?', 'images': ['abcd']}])
        self.assertEqual(post.call_args.kwargs['json']['options']['num_predict'], 160)


class AgentVisionToolTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.other = tempfile.TemporaryDirectory()
        self.addCleanup(self.other.cleanup)
        self.runtime = AgentRuntime(Connections(self.root / 'connections.json'))
        self.run = self.runtime.new_run('Explain the screenshot in my workspace', str(self.root))
        path = self.root / 'shot.png'
        Image.new('RGB', (40, 24), '#123456').save(path)
        self.image = path

    def plan(self, model):
        with self.runtime.lock:
            self.runtime.planners[self.run['id']] = copy.copy(model)

    def action(self, tool, args):
        return self.runtime.propose(self.run['id'], tool, args)['steps'][-1]

    def test_image_read_waits_for_approval_and_names_the_model_that_will_see_it(self):
        model = AssistantStub()
        self.plan(model)
        action = self.action('files.analyze', {'path': 'shot.png', 'question': 'What does this show?'})
        self.assertEqual(action['status'], 'pending')
        self.assertEqual(action['preview']['reader'], 'ollama llama3.2')
        self.assertIn('image stays on this PC', action['preview']['warning'])
        self.assertEqual(action['preview']['question'], 'What does this show?')
        self.assertNotIn('reading', json.dumps(action))
        with self.assertRaisesRegex(ValueError, 'Only observing steps'):
            self.runtime._decide(action['id'], True, auto=True)
        self.assertFalse(model.calls)
        result = self.runtime.decide(action['id'], True)
        self.assertEqual(result['action']['status'], 'completed')
        self.assertIn('61 GB free', result['action']['result']['reading'])

    def test_a_cloud_planner_discloses_that_the_image_bytes_leave_the_pc(self):
        self.plan(CloudStub())
        action = self.action('files.analyze', {'path': 'shot.png'})
        self.assertIn('generativelanguage.googleapis.com', action['preview']['warning'])

    def test_a_native_planner_is_named_in_the_review(self):
        self.plan(NativeStub())
        action = self.action('files.analyze', {'path': 'shot.png'})
        self.assertEqual(action['preview']['reader'], 'local qwen3-vl-4b.gguf')

    def test_without_a_selected_model_there_is_no_proposal(self):
        with self.assertRaisesRegex(ValueError, 'Select an AI'):
            self.action('files.analyze', {'path': 'shot.png'})

    def test_text_documents_and_escapes_are_refused_at_proposal_time(self):
        note = self.root / 'notes.txt'
        note.write_text('text', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'PNG, JPEG or WebP'):
            self.action('files.analyze', {'path': 'notes.txt'})
        elsewhere = Path(self.other.name) / 'elsewhere.png'
        Image.new('RGB', (20, 20), '#abcdef').save(elsewhere)
        with self.assertRaisesRegex(ValueError, 'must stay inside'):
            self.action('files.analyze', {'path': str(elsewhere)})
        escaped = Path(self.folder.name).parent / ('sakura-escape-' + self.run['id'] + '.png')
        Image.new('RGB', (20, 20), '#abcdef').save(escaped)
        self.addCleanup(escaped.unlink, missing_ok=True)
        with self.assertRaisesRegex(ValueError, 'must stay inside'):
            self.action('files.analyze', {'path': '../' + escaped.name})

    def test_arguments_beyond_the_schema_never_reach_the_vision_call(self):
        for args in ({'path': 'shot.png', 'command': 'del'}, {'path': 'shot.png', 'question': 'q' * 1300},
                     {'path': 'shot.png', 'images': ['aaa']}):
            with self.assertRaises(Exception):
                self.action('files.analyze', args)

    def test_a_late_image_or_model_swap_forces_a_fresh_approval(self):
        model = AssistantStub()
        self.plan(model)
        action = self.action('files.analyze', {'path': 'shot.png'})
        self.image.write_bytes(b'\x89PNG\r\n\x1a\n' + bytes(range(20)))
        result = self.runtime.decide(action['id'], True)
        self.assertEqual(result['action']['status'], 'failed')
        self.assertIn('File content changed after review', result['action']['result']['error'])
        self.assertFalse(model.calls)
        fresh = self.action('files.analyze', {'path': 'shot.png'})
        other = NativeStub()
        self.plan(other)
        second = self.runtime.decide(fresh['id'], True)
        self.assertEqual(second['action']['status'], 'failed')
        self.assertIn('vision model changed after review', second['action']['result']['error'])
        self.assertFalse(other.calls)

    def test_the_planner_sees_the_image_reading_as_evidence(self):
        self.plan(AssistantStub())
        action = self.action('files.analyze', {'path': 'shot.png'})
        run = self.runtime.decide(action['id'], True)['run']
        self.assertIn('61 GB free', self.runtime._step_history(run)[-1]['result'])

    def test_files_read_now_points_at_the_vision_tool(self):
        action = self.action('files.read', {'path': 'shot.png'})
        result = self.runtime.decide(action['id'], True)
        self.assertEqual(result['action']['status'], 'failed')
        self.assertIn('files.analyze', result['action']['result']['error'])
