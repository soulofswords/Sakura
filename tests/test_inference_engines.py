import io,json,zipfile
from unittest.mock import Mock,patch
from pathlib import Path
import pytest
import requests
from agent_local_ai import LocalAI
from inference_engines import extract,colibri_model


def test_companion_picker_includes_native_models_without_loading_them(tmp_path):
    runtime=LocalAI(tmp_path/'private');weights=tmp_path/'colibri';weights.mkdir()
    projector=tmp_path/'projector.gguf';projector.write_bytes(b'GGUF')
    runtime.models={'qwen':{'id':'qwen','name':'Qwen3.6-35B-A3B','path':str(weights),'engine':'colibri','bytes':23},
                    'projector':{'id':'projector','path':str(projector),'projector':True},
                    'missing':{'id':'missing','path':str(tmp_path/'missing.gguf')}}
    assert runtime.companion_models()==[{'name':'sakura-native:qwen','label':'Qwen3.6-35B-A3B','engine':'colibri','size':23}]
    assert runtime.worker is None


def test_runtime_extraction_rejects_traversal(tmp_path):
    blob=io.BytesIO()
    with zipfile.ZipFile(blob,'w') as z:z.writestr('../escape.dll',b'bad')
    blob.seek(0)
    with pytest.raises(ValueError,match='Unsafe'):extract(blob,tmp_path)
    assert not (tmp_path.parent/'escape.dll').exists()


def test_cuda_worker_launch_uses_cuda_runtime_and_requested_offload(tmp_path):
    runtime=LocalAI(tmp_path/'private');model=tmp_path/'m.gguf';model.write_bytes(b'GGUFtest')
    result=runtime.import_file(str(model));identifier=result['models'][0]['id']
    folder=runtime.root/'runtime-cuda';folder.mkdir();(folder/'llama-server.exe').write_bytes(b'fake')
    worker=Mock();worker.poll.return_value=None
    response=Mock(status_code=200)
    with patch('agent_local_ai.subprocess.Popen',return_value=worker) as launch,patch('agent_local_ai.ProcessJob'),patch('agent_local_ai.requests.get',return_value=response):
        runtime.load(identifier,gpu_layers=999,backend='auto');runtime.job_thread.join(5)
        assert runtime.loaded==identifier and runtime.loaded_backend=='cuda'
        args=launch.call_args.args[0]
        assert args[0]==str(folder/'llama-server.exe') and args[args.index('-ngl')+1]=='999'
        assert args[args.index('--host')+1]=='127.0.0.1' and '--api-key' in args
        runtime._shutdown()


def make_colibri(tmp_path):
    folder=tmp_path/'qwen';folder.mkdir()
    (folder/'config.json').write_text(json.dumps({'model_type':'qwen4_exp','vision_config':{}}))
    (folder/'model.safetensors.index.json').write_text(json.dumps({'weight_map':{'a':'model-1.safetensors'}}))
    (folder/'model-1.safetensors').write_bytes(b'0'*16)
    (folder/'tokenizer.json').write_text('{}')
    return folder


def test_colibri_folder_validation_and_no_unavailable_cuda(tmp_path):
    folder=make_colibri(tmp_path);runtime=LocalAI(tmp_path/'private')
    result=runtime.import_colibri(str(folder));identifier=result['models'][0]['id']
    assert result['models'][0]['engine']=='colibri'
    with pytest.raises(ValueError,match='Windows CUDA'):runtime.load(identifier,backend='cuda')
    (folder/'model.safetensors.index.json').write_text(json.dumps({'weight_map':{'a':'../escape.safetensors'}}))
    with pytest.raises(ValueError,match='Unsafe'):colibri_model(str(folder))
    runtime.remove(identifier);assert (folder/'model-1.safetensors').exists()


def test_colibri_managed_launch_uses_gpu_without_shell_or_download(tmp_path):
    folder=make_colibri(tmp_path);runtime=LocalAI(tmp_path/'private');identifier=runtime.import_colibri(str(folder))['models'][0]['id']
    engine=runtime.root/'colibri-runtime';engine.mkdir();(engine/'coli').write_text('')
    worker=Mock();worker.poll.return_value=None
    with patch('agent_local_ai.subprocess.Popen',return_value=worker) as launch,patch('agent_local_ai.ProcessJob'),patch('agent_local_ai.requests.get',return_value=Mock(status_code=200)):
        runtime.load(identifier,backend='auto');runtime.job_thread.join(5)
        assert runtime.loaded_engine=='colibri' and runtime.loaded_backend=='vulkan'
        args=launch.call_args.args[0];assert 'serve' in args and 'setup' not in args
        assert args[args.index('--model-id')+1]==identifier
        assert launch.call_args.kwargs['env']['COLI_VULKAN']=='1'
        assert launch.call_args.kwargs['env']['COLI_CUDA']=='0'
        runtime._shutdown()


def test_colibri_unsupported_grammar_is_not_sent(tmp_path):
    runtime=LocalAI(tmp_path);runtime.loaded='q38';runtime.loaded_engine='colibri';runtime.worker=Mock();runtime.worker.poll.return_value=None;runtime.port=1234
    reply=Mock(status_code=200);reply.json.return_value={'choices':[{'message':{'content':'{"done":true}'}}]}
    with patch('agent_local_ai.requests.post',return_value=reply) as request:
        runtime._request_raw([{'role':'user','content':'hi'}],structured=True)
        payload=request.call_args.kwargs['json'];assert 'response_format' not in payload and payload['enable_thinking'] is False
    runtime.worker=None


def test_existing_cuda_toolkit_skips_runtime_bundle_download(tmp_path):
    from inference_engines import install
    import hashlib
    toolkit=tmp_path/'toolkit'/'bin';toolkit.mkdir(parents=True)
    for name in ('cudart64_12.dll','cublas64_12.dll','cublasLt64_12.dll'):(toolkit/name).write_bytes(b'installed toolkit')
    blob=io.BytesIO()
    with zipfile.ZipFile(blob,'w') as z:z.writestr('llama-server.exe',b'engine')
    data=blob.getvalue();response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock();response.headers={'Content-Length':str(len(data))};response.iter_content.return_value=[data]
    assets={('llama.cpp','cuda'):[('engine.zip',hashlib.sha256(data).hexdigest()),('runtime.zip','unused')]}
    with patch.dict('inference_engines.os.environ',{'CUDA_PATH':str(toolkit.parent)}),patch('inference_engines.ASSETS',assets),patch('inference_engines.requests.get',return_value=response) as get:
        dest=install(tmp_path/'private','llama.cpp','cuda',lambda _:None)
    assert get.call_count==1 and get.call_args.args[0].endswith('engine.zip')
    assert (dest/'cublas64_12.dll').read_bytes()==b'installed toolkit'
    assert json.loads((dest/'Sakura-runtime.json').read_text())['reused_cuda_toolkit'] is True


def test_converted_qwen36_import_preserves_source_and_reports_real_vision(tmp_path):
    folder=tmp_path/'Qwen3.6';folder.mkdir()
    (folder/'config.json').write_text(json.dumps({'model_type':'qwen3_5_moe_text','num_hidden_layers':2}))
    (folder/'qwen36_meta.json').write_text(json.dumps({'n_layers':2}))
    for name in ['model-00000.safetensors','model-00001.safetensors','model-globals.safetensors']:(folder/name).write_bytes(b'0'*16)
    (folder/'tokenizer.json').write_text('{}')
    assert colibri_model(folder)==(folder,48,False)
    runtime=LocalAI(tmp_path/'private');entry=runtime.import_colibri(str(folder))['models'][0]
    assert entry['name']=='Qwen3.6-35B-A3B' and not entry['vision']
    from model_inspection import inspect_model
    assert inspect_model(folder)['can_add']
    runtime.remove(entry['id']);assert (folder/'model-globals.safetensors').is_file()
    (folder/'model-00001.safetensors').unlink()
    with pytest.raises((ValueError,OSError)):colibri_model(folder)


def test_qwen36_uses_bounded_cache_and_actual_vulkan_budget(tmp_path):
    folder=tmp_path/'qwen';folder.mkdir()
    (folder/'config.json').write_text(json.dumps({'model_type':'qwen3_5_moe_text','num_hidden_layers':1}))
    (folder/'qwen36_meta.json').write_text(json.dumps({'n_layers':1}))
    (folder/'model-00000.safetensors').write_bytes(b'0'*16)
    (folder/'model-globals.safetensors').write_bytes(b'0'*16)
    (folder/'tokenizer.json').write_text('{}')
    runtime=LocalAI(tmp_path/'private');identifier=runtime.import_colibri(str(folder))['models'][0]['id']
    engine=runtime.root/'colibri-runtime';engine.mkdir();(engine/'coli').write_text('')
    worker=Mock();worker.poll.return_value=None
    with patch('agent_local_ai.subprocess.Popen',return_value=worker) as launch,patch('agent_local_ai.ProcessJob'),patch('agent_local_ai.requests.get',return_value=Mock(status_code=200)):
        runtime.load(identifier,backend='vulkan');runtime.job_thread.join(5)
        assert runtime.loaded_engine=='colibri'
        args=launch.call_args.args[0];assert args[args.index('--cap')+1]=='64'
        environment=launch.call_args.kwargs['env'];assert environment['COLI_VK_TIER_GB']=='5' and environment['COLI_NO_OMP_TUNE']=='1'
        assert environment['COLI_VK_CHAIN_ROWS_MAX']=='512'
        runtime._shutdown()


def test_companion_routes_selected_colibri_without_starting_ollama(tmp_path):
    from llm import LLM
    from agent_local_ai import local_ai
    model=LLM(tmp_path/'memory.json')
    with patch.dict(local_ai.models,{'test-model':{'id':'test-model'}}),patch('ollama_runtime.server_for_folder',return_value='http://127.0.0.1:11435') as ollama,patch.object(local_ai,'request_model',return_value='Hello from Qwen3.6.') as generate:
        model.configure_local('sakura-native:test-model',context=4096)
        local_ai.loaded='test-model'
        assert model._request_raw([{'role':'user','content':'Hello'}])=='Hello from Qwen3.6.'
        assert generate.call_args.args[0]=='test-model'
        ollama.assert_called_once_with('')
        assert model._check_ollama()
        local_ai.loaded=None


def test_companion_screen_keeps_vision_model_and_releases_large_text_worker(tmp_path):
    from llm import LLM
    from agent_local_ai import local_ai
    model=LLM(tmp_path/'memory.json');model.model='sakura-native:test-model';model.vision_model='qwen3-vl:4b-instruct'
    response=Mock(status_code=200);response.json.return_value={'message':{'content':'A window is visible.'}}
    with patch.object(local_ai,'_shutdown') as unload,patch.object(local_ai,'request_model') as native,patch('llm.requests.post',return_value=response) as generate:
        assert model._request_raw([{'role':'user','content':'What do you see?','images':['jpeg']}],model=model.vision_model)=='A window is visible.'
        unload.assert_called_once();native.assert_not_called()
        assert generate.call_args.kwargs['json']['model']=='qwen3-vl:4b-instruct'


def test_switch_from_colibri_does_not_send_its_identifier_to_ollama(tmp_path):
    from llm import LLM
    from agent_local_ai import local_ai
    model=LLM(tmp_path/'memory.json');model.model='sakura-native:existing';model.base_url='http://127.0.0.1:11435'
    listed=Mock(status_code=200);listed.json.return_value={'models':[{'name':'qwen3-vl:4b-instruct'}]}
    with patch('ollama_runtime.server_for_folder',return_value=model.base_url),patch('llm.requests.get',return_value=listed),patch('llm.requests.post') as post,patch.object(local_ai,'_shutdown') as shutdown:
        model.configure_local('qwen3-vl:4b-instruct',validate=True)
        post.assert_not_called();shutdown.assert_called_once()
        assert model.model=='qwen3-vl:4b-instruct' and model.vision_model==model.model


def test_refused_switch_keeps_the_colibri_worker(tmp_path):
    from llm import LLM
    from agent_local_ai import local_ai
    model=LLM(tmp_path/'memory.json');model.model='sakura-native:existing'
    listed=Mock(status_code=200);listed.json.return_value={'models':[]}
    with patch('ollama_runtime.server_for_folder',return_value='http://127.0.0.1:11435'),patch('llm.requests.get',return_value=listed),patch.object(local_ai,'_shutdown') as shutdown:
        with pytest.raises(ValueError,match='not installed'):model.configure_local('missing-model',validate=True)
        shutdown.assert_not_called();assert model.model=='sakura-native:existing'


def test_unknown_current_model_skips_the_unload_and_switches(tmp_path):
    from llm import LLM
    model=LLM(tmp_path/'memory.json');model.model='colibri-2.7b';model.base_url='http://127.0.0.1:11435'
    listed=Mock(status_code=200);listed.json.return_value={'models':[{'name':'qwen3-vl:4b-instruct'}]}
    with patch('ollama_runtime.server_for_folder',return_value=model.base_url),patch('llm.requests.get',return_value=listed),patch('llm.requests.post',side_effect=requests.HTTPError('model not found')) as post:
        model.configure_local('qwen3-vl:4b-instruct',validate=True)
    post.assert_not_called()
    assert model.model=='qwen3-vl:4b-instruct'


def test_unload_refusal_does_not_block_an_installed_model(tmp_path):
    from llm import LLM
    model=LLM(tmp_path/'memory.json');model.model='colibri-2.7b';model.base_url='http://127.0.0.1:11435'
    listed=Mock(status_code=200);listed.json.return_value={'models':[{'name':'colibri-2.7b'},{'name':'qwen3-vl:4b-instruct'}]}
    with patch('ollama_runtime.server_for_folder',return_value=model.base_url),patch('llm.requests.get',return_value=listed),patch('llm.requests.post',side_effect=requests.HTTPError('unload refused')) as post:
        model.configure_local('qwen3-vl:4b-instruct',validate=True)
    assert post.call_args_list[0].kwargs['json']=={'model':'colibri-2.7b','keep_alive':0,'stream':False}
    assert model.model=='qwen3-vl:4b-instruct'
