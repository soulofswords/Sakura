"""Sakura draws with the ComfyUI on this PC, and never without showing the exact job first."""
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import comfy_tools as cf
from agent_connections import Connections
from agent_runtime import AUTO_RUN_TOOLS, AgentRuntime


class PlanTests(unittest.TestCase):
    def test_a_generation_keeps_the_words_and_numbers_it_was_given(self):
        spec = cf.plan('a fox spirit under snow', 'lowres, blurry', 832, 1216, 30, 7.5, 'dpmpp_2m_sde', 'karras',
                       42, 2, 'Illustrious-XL-v2.0.safetensors')
        self.assertEqual(spec['prompt'], 'a fox spirit under snow')
        self.assertEqual(spec['negative'], 'lowres, blurry')
        self.assertEqual((spec['width'], spec['height'], spec['batch']), (832, 1216, 2))
        self.assertEqual(spec['seed'], 42)
        self.assertEqual(spec['checkpoint'], 'Illustrious-XL-v2.0.safetensors')

    def test_an_absent_seed_is_chosen_once_and_then_replayed(self):
        first = cf.plan('a lantern on water', seed=None)
        again = cf.plan('a lantern on water', seed=first['seed'])
        self.assertEqual(first['seed'], again['seed'])
        self.assertGreater(first['seed'], 0)

    def test_a_size_that_would_not_run_is_refused_before_it_reaches_the_gpu(self):
        for refused in [{'prompt': ''}, {'prompt': 'x' * (cf.MAX_PROMPT + 1)}, {'prompt': 'a', 'width': 100},
                        {'prompt': 'a', 'width': 1023}, {'prompt': 'a', 'height': 1023}, {'prompt': 'a', 'batch': 0},
                        {'prompt': 'a', 'batch': 9}, {'prompt': 'a', 'sampler': 'not_a_sampler'},
                        {'prompt': 'a', 'scheduler': 'magic'}]:
            with self.subTest(**refused):
                with self.assertRaises(ValueError):
                    cf.plan(**refused)

    def test_the_steps_and_waiting_time_stay_inside_a_sane_band(self):
        spec = cf.plan('a heron', steps=999, cfg=99)
        self.assertEqual((spec['steps'], spec['cfg']), (cf.MAX_STEPS, 15.0))
        self.assertEqual(cf.timeout_seconds(None), cf.DEFAULT_TIMEOUT_SECONDS)
        self.assertEqual(cf.timeout_seconds(1), cf.MIN_TIMEOUT_SECONDS)
        self.assertEqual(cf.timeout_seconds(99999), cf.MAX_TIMEOUT_SECONDS)

    def test_the_workflow_uses_only_nodes_a_plain_comfyui_install_ships(self):
        graph = cf.graph(cf.plan('a paper crane', checkpoint='x.safetensors'))
        self.assertEqual(sorted(graph), ['1', '2', '3', '4', '5', '6', '7'])
        self.assertEqual({node['class_type'] for node in graph.values()},
                         {'CheckpointLoaderSimple', 'CLIPTextEncode', 'EmptyLatentImage', 'KSampler', 'VAEDecode', 'SaveImage'})
        self.assertEqual(graph['2']['inputs']['text'], 'a paper crane')
        self.assertEqual(graph['1']['inputs']['ckpt_name'], 'x.safetensors')


class AddressTests(unittest.TestCase):
    def test_local_service_redirect_is_not_followed_and_ambient_proxies_are_disabled(self):
        reply = Mock(status_code=302, headers={'Location': 'http://192.168.1.1/'})
        with patch.object(cf.requests, 'get', return_value=reply) as get:
            with self.assertRaises(cf.ComfyError):
                cf._get('http://127.0.0.1:8188', '/system_stats')
        self.assertFalse(get.call_args.kwargs['allow_redirects'])
        self.assertEqual(get.call_args.kwargs['proxies'], {'http': '', 'https': '', 'all': ''})
        with patch.object(cf.requests, 'post', return_value=reply) as post:
            with self.assertRaises(cf.ComfyError):
                cf.queue('http://127.0.0.1:8188', cf.plan('test', checkpoint='test.safetensors'))
        self.assertFalse(post.call_args.kwargs['allow_redirects'])

    def test_only_a_comfyui_on_this_computer_is_reachable(self):
        self.assertEqual(cf.base_url('http://localhost:8188'), 'http://localhost:8188')
        self.assertEqual(cf.base_url('127.0.0.1:8190'), 'http://127.0.0.1:8190')
        for refused in ['https://127.0.0.1:8188', 'http://comfy.example.com:8188', 'http://192.168.1.20:8188']:
            with self.subTest(refused):
                with self.assertRaises(ValueError):
                    cf.base_url(refused)

    def test_a_server_that_is_not_running_is_named_as_one_that_can_be_started(self):
        with patch.object(cf.requests, 'get', side_effect=cf.requests.ConnectionError('refused')):
            with self.assertRaisesRegex(ValueError, 'comfy.start'):
                cf.status('http://127.0.0.1:8188')


class GpuHandoffTests(unittest.TestCase):
    """The report has to say what actually moved, because a false claim here becomes an out-of-memory later."""

    def setUp(self):
        native = patch('agent_local_ai.local_ai.unload')
        native.start()
        self.addCleanup(native.stop)

    def test_only_a_model_ollama_reports_resident_is_asked_to_leave(self):
        answers = {'models': [{'name': 'qwen3-vl:4b-instruct', 'size_vram': 4000000000}, {'name': '', 'size_vram': 0}]}
        with patch.object(cf.requests, 'get', return_value=Mock(json=Mock(return_value=answers))) as get, \
             patch.object(cf.requests, 'post') as post:
            moved = cf.release_local_models()
        self.assertEqual([call.args[0].endswith('/api/generate') for call in post.call_args_list], [True])
        self.assertEqual(post.call_args_list[0].kwargs['json']['model'], 'qwen3-vl:4b-instruct')
        self.assertEqual(post.call_args_list[0].kwargs['json']['keep_alive'], 0)
        self.assertIn('ollama released qwen3-vl:4b-instruct', moved)
        self.assertEqual(get.call_args.args[0][-7:], '/api/ps')

    def test_an_ollama_that_is_not_running_is_not_reported_as_one_holding_the_gpu(self):
        with patch.object(cf.requests, 'get', side_effect=cf.requests.ConnectionError('refused')):
            moved = cf.release_local_models()
        self.assertIn('ollama is not running', moved)

    def test_an_empty_gpu_report_says_ollama_held_nothing(self):
        with patch.object(cf.requests, 'get', return_value=Mock(json=Mock(return_value={'models': []}))), \
             patch.object(cf.requests, 'post') as post:
            moved = cf.release_local_models()
        post.assert_not_called()
        self.assertIn('ollama held nothing on the GPU', moved)

    def test_a_native_model_still_generating_is_reported_instead_of_swallowed(self):
        with patch.object(cf.requests, 'get', return_value=Mock(json=Mock(return_value={'models': []}))), \
             patch.object(cf.requests, 'post'), \
             patch('agent_local_ai.local_ai.unload', side_effect=ValueError('Wait for generation to finish before unloading.')):
            moved = cf.release_local_models()
        self.assertTrue(any(item.startswith('sakura-native still holds the GPU') for item in moved), moved)


class RuntimeTests(unittest.TestCase):
    def test_release_refuses_busy_queue_and_posts_only_to_loopback(self):
        with patch.object(cf,'_get',return_value=Mock(json=lambda:{'queue_running':[1],'queue_pending':[]})), patch.object(cf.requests,'post') as post:
            with self.assertRaisesRegex(ValueError,'running or pending'):cf.release()
            post.assert_not_called()
        with patch.object(cf,'_get',return_value=Mock(json=lambda:{'queue_running':[],'queue_pending':[]})), patch.object(cf.requests,'post',return_value=Mock(status_code=200)) as post:
            self.assertTrue(cf.release()['requested'])
            post.assert_called_once_with(cf.DEFAULT_BASE_URL+'/free',json={'unload_models':True,'free_memory':True},timeout=(3,15),allow_redirects=False,proxies={'http':'','https':'','all':''})
        with self.assertRaises(ValueError):cf.release('http://remote.example:8188')

    def test_release_is_reviewed_and_revalidates_its_address(self):
        action=self.runtime._prepare(self.run,'comfy.release',{})
        self.assertNotIn('comfy.release',AUTO_RUN_TOOLS)
        self.assertEqual(action['bindings']['url'],self.url)
        with patch.object(cf,'release',return_value={'ok':True,'requested':True}) as release:
            self.assertTrue(self.runtime._execute(action,self.run)['requested'])
            release.assert_called_once_with(self.url)

    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.runtime = AgentRuntime(Connections(self.root / 'connections.json'))
        self.run = self.runtime.new_run('Draw a fox spirit under snow', str(self.root))
        self.url = 'http://127.0.0.1:8188'
        self.checkpoints = ['Illustrious-XL-v2.0.safetensors', 'anything-v5.safetensors']
        self.status = patch.object(cf, 'status', return_value={'reachable': True, 'url': self.url, 'comfyui': '0.33.1',
                                                               'ram_free_gb': 20.0, 'gpu': [{'name': 'cuda 0', 'vram_free': 120000}]})
        self.listing = patch.object(cf, 'checkpoints', return_value=self.checkpoints)
        self.status.start()
        self.listing.start()
        self.addCleanup(self.status.stop)
        self.addCleanup(self.listing.stop)

    def test_the_reviewer_sees_the_exact_prompt_size_and_checkpoint(self):
        action = self.runtime._prepare(self.run, 'image.generate',
                                      {'prompt': 'a fox spirit under snow', 'checkpoint': self.checkpoints[0],
                                       'width': 832, 'height': 1216, 'steps': 25, 'seed': 7, 'batch': 2})
        self.assertEqual(action['preview']['prompt'], 'a fox spirit under snow')
        self.assertEqual(action['preview']['checkpoint'], self.checkpoints[0])
        self.assertEqual((action['preview']['width'], action['preview']['height'], action['preview']['batch']), (832, 1216, 2))
        self.assertEqual(Path(action['preview']['path']).parent, self.root / 'images')
        self.assertIn('GPU job', action['preview']['warning'])

    def test_a_checkpoint_the_server_does_not_have_is_refused_with_the_real_list(self):
        with self.assertRaisesRegex(ValueError, 'anything-v5'):
            self.runtime._prepare(self.run, 'image.generate', {'prompt': 'a fox', 'checkpoint': 'flux1-dev.safetensors'})
        with self.assertRaisesRegex(ValueError, 'name the checkpoint'):
            self.runtime._prepare(self.run, 'image.generate', {'prompt': 'a fox'})

    def test_the_picture_can_only_land_inside_the_task_workspace(self):
        for refused in ['..', '../outside.png', str(self.root.parent / 'outside.png')]:
            with self.subTest(refused):
                with self.assertRaises(ValueError):
                    self.runtime._prepare(self.run, 'image.generate',
                                         {'prompt': 'a fox', 'checkpoint': self.checkpoints[0], 'path': refused})

    def test_an_existing_file_is_never_painted_over(self):
        taken = self.root / 'poster.png'
        taken.write_bytes(b'already here')
        with self.assertRaisesRegex(ValueError, 'already a file'):
            self.runtime._prepare(self.run, 'image.generate', {'prompt': 'a fox', 'checkpoint': self.checkpoints[0],
                                                              'path': 'poster.png'})

    def test_the_read_only_probe_may_run_alone_but_a_picture_never_does(self):
        self.assertIn('comfy.status', AUTO_RUN_TOOLS)
        self.assertNotIn('image.generate', AUTO_RUN_TOOLS)
        self.assertNotIn('comfy.start', AUTO_RUN_TOOLS)
        drawn = self.runtime._prepare(self.run, 'image.generate', {'prompt': 'a fox', 'checkpoint': self.checkpoints[0]})
        self.assertFalse(self.runtime._auto_allowed(drawn))

    def test_the_queued_job_is_the_one_that_was_shown_and_the_picture_lands_where_it_was_named(self):
        action = self.runtime._prepare(self.run, 'image.generate',
                                       {'prompt': 'a fox spirit under snow', 'checkpoint': self.checkpoints[0],
                                        'width': 832, 'height': 1216, 'seed': 7})
        target = Path(action['preview']['path'])
        records = [{'filename': 'sakura_00007.png', 'subfolder': '', 'type': 'output'}]
        with patch.object(cf, 'queue', return_value=(self.url, 'abc123', 4)) as queue, \
             patch.object(cf, 'await_image', return_value=records) as wait, \
             patch.object(cf, 'release', return_value={'ok':True,'requested':True,'message':'Release requested.'}) as give_back, \
             patch.object(cf, 'release_local_models', return_value=['ollama:qwen3']) as release, \
             patch.object(cf, 'fetch', side_effect=lambda url, record, dest: {'path': str(dest), 'bytes': 1024,
                                                                             'comfy_name': record['filename']}) as fetch:
            result = self.runtime._execute(action, self.run)
        self.assertEqual(queue.call_args.args[1], action['bindings']['spec'])
        self.assertEqual(wait.call_args.args[1], 'abc123')
        self.assertTrue(release.called)
        self.assertEqual(Path(fetch.call_args.args[2]), target)
        self.assertTrue(result['ok'])
        self.assertEqual(result['images'][0]['path'], str(target))
        self.assertIn('ollama:qwen3', result['gpu_handoff'])
        give_back.assert_called_once_with(self.url)
        self.assertTrue(result['gpu_release']['requested'])

    def test_arguments_traded_after_review_are_refused_before_the_gpu_is_touched(self):
        action = self.runtime._prepare(self.run, 'image.generate',
                                      {'prompt': 'a fox spirit under snow', 'checkpoint': self.checkpoints[0]})
        action['arguments']['prompt'] = 'a wolf in a city'
        with patch.object(cf, 'queue') as queue:
            with self.assertRaisesRegex(ValueError, 'changed after review'):
                self.runtime._execute(action, self.run)
            queue.assert_not_called()

    def test_a_file_that_appeared_over_the_named_output_after_review_stops_the_write(self):
        action = self.runtime._prepare(self.run, 'image.generate',
                                      {'prompt': 'a fox', 'checkpoint': self.checkpoints[0]})
        Path(action['preview']['path']).parent.mkdir(parents=True, exist_ok=True)
        Path(action['preview']['path']).write_bytes(b'someone else')
        with patch.object(cf, 'queue') as queue:
            with self.assertRaisesRegex(ValueError, 'already exists'):
                self.runtime._execute(action, self.run)
            queue.assert_not_called()


class StartTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.runtime = AgentRuntime(Connections(self.root / 'connections.json'))
        self.run = self.runtime.new_run('Draw with ComfyUI', str(self.root))
        self.portable = self.root / 'ComfyUI_windows_portable'
        (self.portable / 'python_embeded').mkdir(parents=True)
        (self.portable / 'ComfyUI').mkdir()
        (self.portable / 'python_embeded' / 'python.exe').write_bytes(b'fake interpreter')
        (self.portable / 'ComfyUI' / 'main.py').write_bytes(b'print()')
        self.dead = patch.object(cf, 'status', side_effect=cf.ComfyError('nothing answering'))
        self.dead.start()
        self.addCleanup(self.dead.stop)

    def test_the_start_line_comes_from_the_installs_own_folder_and_ports_match_the_read(self):
        action = self.runtime._prepare(self.run, 'comfy.start', {'folder': str(self.portable)})
        self.assertIn('python_embeded' + os.sep + 'python.exe', action['preview']['command'])
        self.assertIn('--port %d' % cf.DEFAULT_PORT, action['preview']['command'])
        self.assertEqual(action['bindings']['cwd']['path'], str(self.portable.resolve()))

    def test_a_folder_that_is_not_a_comfyui_install_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'not a ComfyUI portable folder'):
            self.runtime._prepare(self.run, 'comfy.start', {'folder': str(self.root)})

    def test_an_already_running_comfyui_is_not_started_twice(self):
        with patch.object(cf, 'status', return_value={'reachable': True, 'url': 'http://127.0.0.1:8188'}):
            with self.assertRaisesRegex(ValueError, 'already answers'):
                self.runtime._prepare(self.run, 'comfy.start', {'folder': str(self.portable)})

    def test_the_server_is_launched_detached_and_the_log_lands_in_the_task_workspace(self):
        action = self.runtime._prepare(self.run, 'comfy.start', {'folder': str(self.portable)})
        self.assertFalse(self.runtime._auto_allowed(action))
        self.assertEqual(Path(action['bindings']['log']).parent, self.root / '.sakura-serve')
        with patch('local_serve_tools.start_detached', return_value={'ok': True, 'pid': 4242}) as launch:
            result = self.runtime._execute(action, self.run)
        self.assertEqual(launch.call_args.args[0], action['bindings']['command'])
        self.assertEqual(launch.call_args.args[1], str(self.portable.resolve()))
        self.assertEqual(result['pid'], 4242)

    def test_a_replaced_interpreter_after_review_forces_a_new_proposal(self):
        action = self.runtime._prepare(self.run, 'comfy.start', {'folder': str(self.portable)})
        (self.portable / 'python_embeded' / 'python.exe').write_bytes(b'tampered')
        with patch('local_serve_tools.start_detached') as launch:
            with self.assertRaisesRegex(ValueError, 'changed after review'):
                self.runtime._execute(action, self.run)
            launch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
