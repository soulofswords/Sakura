import subprocess
import threading
from pathlib import Path
from unittest.mock import patch
import pytest
import repo_tools
from repo_tools import validate_url,plan,survey,clone


def test_validate_url_accepts_plain_https_projects_and_rejects_every_transport_trick():
    assert validate_url('https://github.com/openai/codex')=='https://github.com/openai/codex'
    assert validate_url(' https://gitlab.example.com/a/b.git ')=='https://gitlab.example.com/a/b.git'
    assert validate_url('https://github.com/openai/codex/')=='https://github.com/openai/codex'
    for hostile in ('http://github.com/a/b','git@github.com:a/b.git','ssh://git@github.com/a/b',
                    'ext::sh -c whoami','--upload-pack=evil','https://github.com',
                    'https://user:token@github.com/a/b','https://github.com/a/b?token=1',
                    'https://github.com/a/b#frag','not a url',None,'https://github.com/a b/c'):
        with pytest.raises(ValueError,match='https'):validate_url(hostile)


def test_plan_names_a_workspace_folder_and_refuses_to_escape_it():
    assert plan('https://github.com/openai/codex','')['folder']=='codex'
    assert plan('https://github.com/openai/codex.git','')['folder']=='codex'
    assert plan('https://github.com/openai/codex','   ')['folder']=='codex'
    assert plan('https://github.com/openai/codex','vendor/codex')['folder']==str(Path('vendor/codex'))
    for folder in ('..','..\\x','a/../..','C:\\Windows','.',str(Path('..')/'sub')):
        with pytest.raises(ValueError):plan('https://github.com/openai/codex',folder)


def test_run_git_uses_argv_and_an_explicit_end_of_options_separator():
    with patch.object(repo_tools,'git_executable',return_value='/usr/bin/git'), \
         patch.object(repo_tools.subprocess,'run',return_value=subprocess.CompletedProcess([],0)) as run:
        repo_tools._run_git(['--','https://github.com/a/b','dest'])
    arguments=run.call_args.args[0]
    assert arguments[:6]==['/usr/bin/git','clone','--depth','1','--single-branch','--']
    assert arguments[-2:]==['https://github.com/a/b','dest']
    assert run.call_args.kwargs['shell'] is False


def test_run_git_turns_a_zero_exit_without_a_folder_into_a_refused_claim(tmp_path):
    with pytest.raises(ValueError,match='clone folder is missing'):survey(tmp_path/'never-created')
    def fake_git(arguments,cancel_event=None):
        Path(arguments[-1]).mkdir()
        return subprocess.CompletedProcess([],0)
    with patch.object(repo_tools,'_run_git',side_effect=fake_git):
        result=clone('https://github.com/a/b',tmp_path/'empty-repo')
    assert result['files']==0 and result['top_level']==[]


def test_an_interrupted_clone_is_the_only_folder_the_tool_will_replace(tmp_path):
    dead=tmp_path/'god-view';(dead/'.git').mkdir(parents=True);(dead/'.git'/'config').write_text('partial',encoding='utf-8')
    assert repo_tools.partial_clone(dead) is True
    living=tmp_path/'project';living.mkdir();(living/'package.json').write_text('{}',encoding='utf-8')
    assert repo_tools.partial_clone(living) is False
    assert repo_tools.partial_clone(tmp_path/'nowhere') is False
    def fake_git(arguments,cancel_event=None):
        path=Path(arguments[-1])
        assert not path.exists(),'A replaced partial clone must be gone before git runs.'
        path.mkdir(parents=True)
        (path/'README.md').write_text('# hi',encoding='utf-8')
        return subprocess.CompletedProcess([],0)
    with patch.object(repo_tools,'_run_git',side_effect=fake_git):
        result=clone('https://github.com/a/b',dead)
    assert result['replaced_partial_clone'] is True and result['files']==1
    assert 'Removed the unfinished clone' in result['message']


def test_a_clone_that_runs_out_of_time_leaves_nothing_to_block_the_retry(tmp_path):
    destination=tmp_path/'big'
    def hang(arguments,**kwargs):
        Path(arguments[-1]).mkdir(parents=True);(Path(arguments[-1])/'.git').mkdir()
        raise subprocess.TimeoutExpired(['git'],repo_tools.MAX_CLONE_SECONDS)
    with patch.object(repo_tools,'git_executable',return_value='/usr/bin/git'), \
         patch.object(repo_tools.subprocess,'run',side_effect=hang):
        with pytest.raises(ValueError,match='removed'):clone('https://github.com/a/b',destination)
    assert not destination.exists()
    with patch.object(repo_tools,'git_executable',return_value='/usr/bin/git'), \
         patch.object(repo_tools.subprocess,'run',side_effect=hang):
        with pytest.raises(ValueError,match='removed'):clone('https://github.com/a/b',destination)


def test_clone_never_touches_a_non_empty_folder_and_reports_what_landed(tmp_path):
    taken=tmp_path/'codex';taken.mkdir();(taken/'old.txt').write_text('keep',encoding='utf-8')
    with pytest.raises(ValueError,match='holds files'):clone('https://github.com/a/b',taken)
    assert (taken/'old.txt').read_text(encoding='utf-8')=='keep'
    destination=tmp_path/'new'
    def fake_git(arguments,cancel_event=None):
        path=Path(arguments[-1])
        (path/'src').mkdir(parents=True);(path/'README.md').write_text('# hi',encoding='utf-8')
        (path/'src'/'main.py').write_text('print(1)',encoding='utf-8')
        (path/'.git').mkdir();(path/'.git'/'config').write_text('x',encoding='utf-8')
        return subprocess.CompletedProcess([],0)
    with patch.object(repo_tools,'_run_git',side_effect=fake_git) as run:
        result=clone('https://github.com/a/b',destination)
    assert run.call_args.args[0][:2]==['--',('https://github.com/a/b')]
    assert result['files']==2 and result['top_level']==['.git/','README.md','src/']
    assert result['ok'] is True and 'Nothing from it has been run' in result['message']
    cancelled=threading.Event();cancelled.set()
    with patch.object(repo_tools,'_run_git') as run:
        with pytest.raises(ValueError,match='Cancelled'):clone('https://github.com/a/b',tmp_path/'other',cancel_event=cancelled)
        assert run.call_args_list==[]


def test_git_failure_is_reported_instead_of_a_claimed_clone(tmp_path):
    failure=subprocess.CompletedProcess([],128)
    failure.stderr='fatal: repository not found'
    with patch.object(repo_tools,'git_executable',return_value='/usr/bin/git'), \
         patch.object(repo_tools.subprocess,'run',return_value=failure):
        with pytest.raises(ValueError,match='repository not found'):clone('https://github.com/a/b',tmp_path/'x')
    assert not (tmp_path/'x').exists()
