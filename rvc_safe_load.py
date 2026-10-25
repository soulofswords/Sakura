"""Restrict user voice checkpoints to PyTorch's data-only loader."""
import functools
import hashlib
import os
from pathlib import Path

TRUSTED = {
    'hubert_base.pt':'f54b40fd2802423a5643779c4861af1e9ee9c1564dc9d32f54f20b5ffba7db96',
    'rmvpe.pt':'6d62215f4306e3ca278246188607209f09af3dc77ed4232efdd069798c4ec193',
}

def install(torch, root):
    original=torch.load
    if getattr(original,'sakura_restricted',False):return
    os.environ.pop('TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD',None)
    @functools.wraps(original)
    def load(source,*args,**kwargs):
        # PyTorch honours this variable even when weights_only=True is passed,
        # so it must not survive into an import of user-supplied weights.
        os.environ.pop('TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD',None)
        trusted=False
        try:
            name=source if isinstance(source,(str,os.PathLike)) else getattr(source,'name',source)
            path=Path(name).resolve()
            if path.name in TRUSTED and path==Path(root).resolve()/'rvc-assets'/path.name:
                with path.open('rb') as stream:
                    trusted=hashlib.file_digest(stream,'sha256').hexdigest()==TRUSTED[path.name]
        except (TypeError,ValueError,OSError):pass
        # Library calls cannot opt an imported voice out of restricted loading.
        kwargs['weights_only']=not trusted
        return original(source,*args,**kwargs)
    load.sakura_restricted=True
    torch.load=load
