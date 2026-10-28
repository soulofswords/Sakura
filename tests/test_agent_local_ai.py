import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch

import pytest
from agent_local_ai import LocalAI


def test_imported_original_is_registered_but_never_deleted(tmp_path):
    model=tmp_path/'weights';model.write_bytes(b'GGUFtest')
    runtime=LocalAI(tmp_path/'private');data=runtime.import_file(str(model),'My model')
    identifier=data['models'][0]['id']
    with pytest.raises(ValueError):runtime.remove(identifier,True)
    runtime.remove(identifier,False);assert model.read_bytes()==b'GGUFtest'
    with pytest.raises(ValueError):runtime.import_file(str(Path(__file__)))


def test_only_owned_weights_under_private_store_can_be_deleted(tmp_path):
    runtime=LocalAI(tmp_path/'private');outside=tmp_path/'outside.gguf';outside.write_bytes(b'GGUFtest')
    runtime.models['x']={'id':'x','path':str(outside),'owned':True}
    with pytest.raises(ValueError):runtime.remove('x',True)
    assert outside.exists()


def test_loaded_projector_cannot_be_removed(tmp_path):
    runtime=LocalAI(tmp_path);runtime.loaded='weights';runtime.loaded_projector='projector'
    runtime.models['projector']={'id':'projector','path':str(tmp_path/'vision.gguf'),'owned':True}
    with pytest.raises(ValueError):runtime.remove('projector',False)


def test_native_chat_uses_private_worker_and_rejects_image_url_fetch(tmp_path):
    runtime=LocalAI(tmp_path);runtime.loaded='model';runtime.worker=Mock();runtime.worker.poll.return_value=None;runtime.port=12345;runtime.key='private';runtime.vision=True
    response=Mock(status_code=200);response.json.return_value={'choices':[{'message':{'content':'Hello'}}]}
    with patch('agent_local_ai.requests.post',return_value=response) as post:
        assert runtime._request_raw([{'role':'user','content':'hi'}])=='Hello'
        assert post.call_args.args[0]=='http://127.0.0.1:12345/v1/chat/completions'
        assert post.call_args.kwargs['headers']['Authorization']=='Bearer private'
        assert 'available short-term context' in post.call_args.kwargs['json']['messages'][0]['content']
        with pytest.raises(ValueError):runtime._request_raw([{'role':'user','content':[{'type':'image_url','image_url':{'url':'http://127.0.0.1:8766/api/settings'}}]}])
    runtime.worker=None


def test_model_file_listing_separates_projectors_and_split_sets(tmp_path):
    response=Mock();response.json.return_value={'sha':'a'*40,'siblings':[
        {'rfilename':'model-Q4_K_M.gguf','lfs':{'sha256':'b'*64,'size':100}},
        {'rfilename':'mmproj-f16.gguf','lfs':{'sha256':'c'*64,'size':30}},
        {'rfilename':'model-00001-of-00002.gguf','lfs':{'sha256':'d'*64,'size':50}}]}
    with patch('agent_local_ai.requests.get',return_value=response):files=LocalAI.files('owner/model')
    assert files['files'][1]['projector']
    assert files['files'][2]['split']
    with pytest.raises(ValueError):LocalAI.files('../bad')


def test_download_checks_hash_and_never_registers_corrupt_weights(tmp_path):
    runtime=LocalAI(tmp_path);data=b'GGUFverified download'
    sha=hashlib.sha256(data).hexdigest()
    runtime.files=lambda repo:{'revision':'a'*40,'files':[{'file':'model.gguf','sha256':sha,'bytes':len(data),'projector':False,'split':False}]}
    class Response:
        status_code=200
        headers={}
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def raise_for_status(self):pass
        def iter_content(self,size):yield data
    with patch('agent_local_ai.requests.get',return_value=Response()):
        runtime.download('owner/model','model.gguf');runtime.job_thread.join(10)
    assert len(runtime.models)==1 and not runtime.job.get('error')
    identifier=next(iter(runtime.models));assert runtime.models[identifier]['owned']
    assert Path(runtime.models[identifier]['path']).read_bytes()==data
    runtime.remove(identifier,True);assert not (tmp_path/'models'/ (identifier+'.gguf')).exists()
    runtime.files=lambda repo:{'revision':'a'*40,'files':[{'file':'model.gguf','sha256':'0'*64,'bytes':len(data),'projector':False,'split':False}]}
    with patch('agent_local_ai.requests.get',return_value=Response()):
        runtime.download('owner/model','model.gguf');runtime.job_thread.join(10)
    assert runtime.job.get('error') and not runtime.models


def test_native_followup_includes_verbatim_user_topic_without_mutating_history(tmp_path):
    runtime=LocalAI(tmp_path);runtime.loaded='model';runtime.worker=Mock();runtime.worker.poll.return_value=None;runtime.port=12345;runtime.key='private'
    response=Mock(status_code=200);response.json.return_value={'choices':[{'message':{'content':'You called him moonriverstream.'}}]}
    history=[{'role':'user','content':'Do you know moonriverstream?'},{'role':'assistant','content':'Which creator?'},{'role':'user','content':'That guy, what did I call him?'}]
    with patch('agent_local_ai.requests.post',return_value=response) as post:
        assert 'moonriverstream' in runtime._request_raw(history)
        latest=post.call_args.kwargs['json']['messages'][-1]['content']
        assert 'Do you know moonriverstream?' in latest and 'Latest user message:' in latest
        assert history[-1]['content']=='That guy, what did I call him?'
    runtime.worker=None
