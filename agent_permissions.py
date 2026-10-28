import copy
import threading
import uuid
from pathlib import Path


def directory_identity(value):
    original=Path(value).expanduser();resolved=original.resolve(strict=True)
    if not resolved.is_dir() or str(original.absolute()).casefold()!=str(resolved).casefold():
        raise ValueError('Workspace or command folder changed. Review a fresh action.')
    info=resolved.stat()
    return {'path':str(resolved),'device':info.st_dev,'inode':info.st_ino}


class CommandPermissions:
    def __init__(self):
        self.lock=threading.RLock();self.items={}

    @staticmethod
    def signature(action):
        from agent_runtime import digest
        return digest({key:action[key] for key in ('tool','arguments','schema_hash','bindings')})

    def grant(self,action):
        if action['tool']!='shell.run':raise ValueError('Only exact shell commands can be allow-listed.')
        signature=self.signature(action)
        with self.lock:
            if any(item['signature']==signature for item in self.items.values()):return
            if len(self.items)>=50:raise ValueError('Revoke an existing command permission first (limit 50).')
            identifier=uuid.uuid4().hex
            self.items[identifier]={'id':identifier,'signature':signature,'command':action['arguments']['command'],
                                    'cwd':action['arguments']['cwd'],'workspace':action['bindings']['workspace']['path'],
                                    'backend':action['arguments'].get('backend','local'),'session_only':True}

    def allows(self,action):
        if action['tool']!='shell.run':return False
        signature=self.signature(action)
        with self.lock:return any(item['signature']==signature for item in self.items.values())

    def list(self):
        with self.lock:return [copy.deepcopy({k:v for k,v in item.items() if k!='signature'}) for item in self.items.values()]

    def revoke(self,identifier):
        with self.lock:self.items.pop(identifier,None)
        return {'ok':True}

    def clear(self):
        with self.lock:self.items.clear()
