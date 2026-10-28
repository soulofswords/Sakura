import sys
from unittest.mock import Mock,patch

import pytest

from agent_backends import prepare,execute


IMAGE='sha256:'+'a'*64


def test_docker_is_local_no_pull_bounded_and_readonly(tmp_path):
    args={'backend':'docker','image':IMAGE,'command':'pwd','cwd':str(tmp_path)};run={'workspace':str(tmp_path)}
    with patch('agent_backends.shutil.which',return_value=sys.executable):bindings,warning=prepare(args,run,tmp_path)
    process=Mock(return_value={'ok':True})
    execute(args,run,bindings,process)
    argv=process.call_args_list[0].args[0]
    assert argv[1:3]==['--host',bindings['docker_host']]
    for flag,value in [('--pull','never'),('--network','none'),('--cap-drop','ALL'),('--memory','1g'),('--user','65534:65534')]:assert argv[argv.index(flag)+1]==value
    assert argv[argv.index('--mount')+1].endswith(',readonly')
    assert '--read-only' in argv
    assert process.call_args_list[0].kwargs['input_text']=='pwd\n'
    assert 'no image downloads' in warning
    # Cleanup has to run even when the container exits cleanly, because a run killed
    # outside the timeout window would otherwise leave an owned container behind.
    cleanup=process.call_args_list[1].args[0]
    assert cleanup[-3:-1]==['rm','--force'] and cleanup[-1]==argv[argv.index('--name')+1]


def test_docker_timeout_removes_only_owned_container(tmp_path):
    args={'backend':'docker','image':IMAGE,'command':'loop','cwd':str(tmp_path)}
    process=Mock(side_effect=[{'ok':False,'timed_out':True},{'ok':True}])
    execute(args,{'workspace':str(tmp_path)},{'runner':'docker','docker_host':'local'},process)
    start=process.call_args_list[0].args[0];cleanup=process.call_args_list[1].args[0]
    assert cleanup[-1]==start[start.index('--name')+1]
    assert cleanup[-3:-1]==['rm','--force']


@pytest.mark.parametrize('extra',[{'image':'ubuntu:latest'},{'image':'--privileged'},{'image':IMAGE,'host':'other'}])
def test_docker_invalid_or_cross_backend_options_rejected(tmp_path,extra):
    with patch('agent_backends.shutil.which',return_value=sys.executable),pytest.raises(ValueError):
        prepare({'backend':'docker','command':'pwd',**extra},{'workspace':str(tmp_path)},tmp_path)


def test_ssh_uses_verified_host_noninteractive_auth_and_quoted_path(tmp_path):
    (tmp_path/'.ssh').mkdir();(tmp_path/'.ssh'/'known_hosts').write_text('verified host key')
    args={'backend':'ssh','host':'example.test','user':'dev','remote_cwd':"/work/a'; touched",'command':'pwd','cwd':str(tmp_path)}
    with patch('agent_backends.Path.home',return_value=tmp_path),patch('agent_backends.shutil.which',return_value=sys.executable):
        bindings,warning=prepare(args,{'workspace':str(tmp_path)},tmp_path)
    process=Mock(return_value={'ok':True})
    execute(args,{},bindings,process)
    argv=process.call_args.args[0]
    assert 'BatchMode=yes' in argv and 'StrictHostKeyChecking=yes' in argv
    assert 'ForwardAgent=no' in argv and 'PermitLocalCommand=no' in argv
    assert argv[-2]=='dev@example.test'
    assert process.call_args.kwargs['input_text']=='pwd\n'
    assert 'not a sandbox' in warning


@pytest.mark.parametrize('host',['-oProxyCommand=anything','foo;bar','user@host','host\nother'])
def test_ssh_target_cannot_inject_options(tmp_path,host):
    with patch('agent_backends.shutil.which',return_value=sys.executable),pytest.raises(ValueError):
        prepare({'backend':'ssh','command':'pwd','host':host,'user':'dev','remote_cwd':'/work'},{'workspace':str(tmp_path)},tmp_path)
