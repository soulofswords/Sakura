import os
import re
import shlex
import shutil
import uuid
from pathlib import Path


PROPERTIES={
    'backend':{'enum':['local','docker','ssh']},
    'image':{'type':'string','maxLength':300},
    'writable':{'type':'boolean'},
    'host':{'type':'string','maxLength':253},
    'user':{'type':'string','maxLength':64},
    'port':{'type':'integer','minimum':1,'maximum':65535},
    'remote_cwd':{'type':'string','maxLength':500}
}


def prepare(args,run,cwd):
    from agent_permissions import directory_identity
    from agent_runtime import powershell,file_hash
    backend=args.get('backend','local')
    fields={'local':set(),'docker':{'image','writable'},'ssh':{'host','user','port','remote_cwd'}}[backend]
    if set(args)-{'command','cwd','backend'}-fields:raise ValueError('Remove options belonging to a different execution backend.')
    runner=powershell() if backend=='local' else shutil.which(backend)
    if not runner:raise ValueError('Install '+backend+' separately and make it available in PATH before choosing this backend.')
    runner=Path(runner).resolve(strict=True)
    bindings={'workspace':directory_identity(run['workspace']),'cwd':directory_identity(cwd),'runner':str(runner),'runner_hash':file_hash(runner)}
    if backend=='docker':
        from sandbox_mount_policy import validate_mount
        validate_mount(run['workspace'])
        if not re.fullmatch(r'(?:[a-zA-Z0-9][a-zA-Z0-9._:/-]*@)?sha256:[a-f0-9]{64}',args.get('image','')):
            raise ValueError('Select an already-installed Docker image by immutable sha256 digest, not a mutable tag.')
        if any(character in run['workspace'] for character in ',\r\n'):raise ValueError('Docker workspace paths cannot contain commas or newlines.')
        bindings['docker_host']='npipe:////./pipe/docker_engine' if os.name=='nt' else 'unix:///var/run/docker.sock'
        warning='Local container: no network, no image downloads, bounded CPU/memory, unprivileged user. Only this workspace is mounted'+(' read/write.' if args.get('writable') else ' read-only.')+' Containers share the host kernel; this is not a VM.'
    elif backend=='ssh':
        host=args.get('host','');user=args.get('user','');remote=args.get('remote_cwd','')
        if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?',host) or '..' in host:raise ValueError('Enter a hostname or IPv4 address, without SSH options.')
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_-]{0,63}',user):raise ValueError('Enter a remote SSH username.')
        if not remote.startswith('/') or any(ord(c)<32 for c in remote):raise ValueError('Choose an absolute POSIX directory on the remote machine.')
        known=Path.home()/'.ssh'/'known_hosts'
        if not known.is_file():raise ValueError('Verify this SSH host manually first; Sakura requires an existing known_hosts file.')
        bindings.update(known_hosts=str(known.resolve()),known_hosts_hash=file_hash(known))
        warning='Runs on the exact remote host as the selected user. No files are uploaded automatically. Requires existing SSH agent/key authentication and a verified host key; password prompts and host-key enrollment are disabled. Remote working directory is not a sandbox. Cloud hosts may incur existing account charges.'
    else:warning='This command can access files and network with your Windows user permissions. The workspace is its working directory, not a sandbox.'
    return bindings,warning


def execute(args,run,bindings,run_process,cancel_event=None):
    backend=args.get('backend','local');cwd=Path(args['cwd']);runner=bindings['runner']
    if backend=='local':return run_process([runner,'-NoProfile','-NonInteractive','-Command',args['command']],cwd,cancel_event=cancel_event)
    if backend=='ssh':
        known=bindings['known_hosts'].replace('\\','/')
        argv=[runner,'-F',os.devnull,'-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UpdateHostKeys=no',
              '-o','ConnectTimeout=10','-o','ForwardAgent=no','-o','ClearAllForwardings=yes','-o','PermitLocalCommand=no',
              '-o','UserKnownHostsFile="'+known+'"','-p',str(args.get('port',22)),args['user']+'@'+args['host'],
              'cd -- '+shlex.quote(args['remote_cwd'])+' && sh -s']
        return run_process(argv,cwd,input_text=args['command']+'\n',cancel_event=cancel_event)
    name='sakura-agent-'+uuid.uuid4().hex
    from sandbox_mount_policy import validate_mount
    validate_mount(run['workspace'])
    mount='type=bind,src='+run['workspace']+',dst=/workspace'+('' if args.get('writable') else ',readonly')
    relative=cwd.relative_to(Path(run['workspace'])).as_posix()
    prefix=[runner,'--host',bindings['docker_host']]
    argv=prefix+['run','--rm','--name',name,'--pull','never','--network','none','--read-only','--cap-drop','ALL',
                 '--security-opt','no-new-privileges','--pids-limit','128','--memory','1g','--cpus','2','--user','65534:65534',
                 '--tmpfs','/tmp:rw,noexec,nosuid,size=64m','--mount',mount,'--workdir','/workspace/'+relative,
                 '--entrypoint','/bin/sh','-i',args['image'],'-s']
    result=None
    try:
        result=run_process(argv,cwd,input_text=args['command']+'\n',cancel_event=cancel_event)
        return result
    finally:
        try:
            cleanup=run_process(prefix+['rm','--force',name],cwd,timeout=15)
            removed=cleanup.get('ok',False) or 'No such container' in cleanup.get('output','')
        except Exception:removed=False
        if result is not None:
            result['container_cleanup_ok']=removed
            if not removed:result.update(ok=False,cleanup_warning='Could not confirm removal of owned container '+name)
