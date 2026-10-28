import importlib.util
from pathlib import Path
from unittest.mock import Mock
import pytest


def test_all_accounts_checks_second_account_even_if_primary_fails(tmp_path,monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1]/'tools'))
    spec=importlib.util.spec_from_file_location('all_accounts_sync',Path(__file__).parents[1]/'tools/sync-jio-library.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    root=tmp_path/'Sakura';root.mkdir();enabled=tmp_path/'private-model-library-account2/server-enabled.json'
    enabled.parent.mkdir();enabled.write_text('{}')
    monkeypatch.setattr(module,'ROOT',root)
    monkeypatch.setattr('sys.argv',['sync','--all-accounts','--additions-only'])
    run=Mock(side_effect=[Mock(returncode=1),Mock(returncode=0)]);monkeypatch.setattr(module.subprocess,'run',run)
    with pytest.raises(ValueError,match='primary'):module.main()
    assert [call.kwargs['env']['SAKURA_JIO_ACCOUNT'] for call in run.call_args_list]==['primary','account2']
    assert all('--additions-only' in call.args[0] for call in run.call_args_list)
