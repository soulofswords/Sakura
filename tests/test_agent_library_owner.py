import hashlib
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
import agent_library_owner as module


def owner(tmp_path,monkeypatch):
    monkeypatch.setattr(module,'_crypt',lambda data,decrypt=False:data)
    root=tmp_path/'publisher';root.mkdir()
    for name in module.PINNED_FILES:
        file=root/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text('# fixed publisher code')
    private=root.parent/'private-model-library';private.mkdir()
    (private/'.jio-publish-proof.bin').write_text(json.dumps({'token':'owner-proof-'+'x'*50}))
    (private/'.jio-owner-session.bin').write_text(json.dumps({'session':{'userId':'owner-only-account','twoFAValidated':True}}))
    app=tmp_path/'companion';app.mkdir()
    controller=module.OwnerLibrary(app);controller.register(root)
    return root,controller


def test_owner_registration_is_required_and_public_state_contains_no_credentials(tmp_path,monkeypatch):
    _,controller=owner(tmp_path,monkeypatch)
    data=controller.status();assert data['owner_available']
    text=json.dumps(data);assert 'owner-proof' not in text and 'owner-only-account' not in text
    tester=module.OwnerLibrary(tmp_path/'tester');assert not tester.status()['owner_available']
    with pytest.raises(ValueError):tester.start(True)
    with pytest.raises(ValueError):controller.start(False)


def test_changed_publisher_code_disables_owner_tools_until_local_reregistration(tmp_path,monkeypatch):
    root,controller=owner(tmp_path,monkeypatch)
    (root/module.PINNED_FILES[0]).write_text('changed executable code')
    assert not controller.status()['owner_available']
    with pytest.raises(ValueError):controller.start(True)
    controller.register(root);assert controller.status()['owner_available']


def test_replaced_account_or_capability_cannot_reuse_owner_registration(tmp_path,monkeypatch):
    root,controller=owner(tmp_path,monkeypatch)
    path=root.parent/'private-model-library/.jio-publish-proof.bin'
    path.write_text(json.dumps({'token':'different-proof-'+'z'*50}))
    assert not controller.status()['owner_available']
    with pytest.raises(ValueError):controller.schedule(True,60,True)


def test_schedule_requires_explicit_approval_and_can_be_disabled_without_it(tmp_path,monkeypatch):
    _,controller=owner(tmp_path,monkeypatch)
    with pytest.raises(ValueError):controller.schedule(True,60,False)
    assert controller.schedule(True,60,True)['schedule']['enabled']
    assert not controller.schedule(False,60,False)['schedule']['enabled']
    with pytest.raises(ValueError):controller.schedule(True,1,True)


def test_duplicate_owner_transfer_is_skipped_without_spawning(tmp_path,monkeypatch):
    _,controller=owner(tmp_path,monkeypatch)
    monkeypatch.setattr(controller,'_busy',lambda root:True)
    popen=Mock();monkeypatch.setattr(module.subprocess,'Popen',popen)
    assert controller.start(True)['busy']
    popen.assert_not_called()
    assert controller.status()['result']['state']=='transfer_in_progress'


def test_old_completed_result_is_not_claimed_for_a_new_worker(tmp_path,monkeypatch):
    root,controller=owner(tmp_path,monkeypatch);private=root.parent/'private-model-library-pmx';private.mkdir()
    (private/'agent-library-status.json').write_text(json.dumps({'run_id':'old','state':'complete','sample_install_verified':True}))
    controller.last_run='new';controller.worker=Mock();controller.worker.poll.return_value=None
    assert controller.status()['result']['state']=='starting'
    controller.worker.poll.return_value=1
    assert controller.status()['result']['state']=='interrupted'
