from pathlib import Path
from unittest.mock import Mock
import pytest
import gpu_routing
from agent_local_ai import LocalAI

def test_rvc_selection_only_accepts_discovered_devices(tmp_path,monkeypatch):
    monkeypatch.setattr(gpu_routing,'devices',lambda:{'devices':[{'id':'cpu'},{'id':'cuda:1'}]})
    assert gpu_routing.selected(tmp_path)=='auto'
    gpu_routing.configure(tmp_path,'cuda:1');assert gpu_routing.selected(tmp_path)=='cuda:1'
    with pytest.raises(ValueError):gpu_routing.configure(tmp_path,'cuda:99')
    assert gpu_routing.selected(tmp_path)=='cuda:1'

def test_runtime_device_listing_is_parsed_without_a_model_load(tmp_path,monkeypatch):
    binary=tmp_path/'runtime-vulkan/llama-server.exe';binary.parent.mkdir();binary.touch()
    worker=LocalAI(tmp_path)
    result=Mock(stdout='Available devices:\n Vulkan0: RTX test (10000 MiB)\n Vulkan1: Another GPU\n',stderr='')
    run=Mock(return_value=result);monkeypatch.setattr('agent_local_ai.subprocess.run',run)
    assert [d['id'] for d in worker.devices()['devices']]==['Vulkan0','Vulkan1']
    assert run.call_args.args[0]==[str(binary),'--list-devices']

def test_forged_or_cpu_gpu_placement_is_refused(tmp_path):
    worker=LocalAI(tmp_path);binary=tmp_path/'runtime-vulkan/llama-server.exe';binary.parent.mkdir();binary.touch()
    model=tmp_path/'test.gguf';model.touch();worker.models['m']={'id':'m','path':str(model),'projector':False,'name':'test'}
    with pytest.raises(ValueError,match='GPU-offloaded'):worker.load('m',devices=['Vulkan0'],gpu_layers=0)
    with pytest.raises(ValueError,match='distinct'):worker.load('m',devices=['Vulkan0','Vulkan0'],gpu_layers=99)
