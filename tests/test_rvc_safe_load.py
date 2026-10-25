import hashlib
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
import rvc_safe_load


class RestrictedCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.base=Path(self.folder.name)
        self.assets=self.base/'rvc-assets';self.assets.mkdir()
        self.trusted=self.assets/'hubert_base.pt';self.trusted.write_bytes(b'known weights')
        self.patch=patch.dict(rvc_safe_load.TRUSTED,{'hubert_base.pt':hashlib.sha256(b'known weights').hexdigest()})
        self.patch.start()
        self.torch=types.ModuleType('torch');self.calls=[]
        def load(source,*args,**kwargs):
            self.calls.append(kwargs);return kwargs
        self.torch.load=load
        rvc_safe_load.install(self.torch,self.base)

    def tearDown(self):
        self.patch.stop();self.folder.cleanup()

    def test_only_the_exact_shipped_asset_may_skip_the_data_only_loader(self):
        self.assertIs(self.torch.load(str(self.trusted))['weights_only'],False)
        self.assertIs(self.torch.load(self.trusted)['weights_only'],False)
        user_checkpoint=self.base/'voices/mia.pth';user_checkpoint.parent.mkdir();user_checkpoint.write_bytes(b'torch code')
        self.assertIs(self.torch.load(user_checkpoint)['weights_only'],True)
        impostor=self.base/'hubert_base.pt';impostor.write_bytes(b'known weights')
        self.assertIs(self.torch.load(impostor)['weights_only'],True)
        tampered=self.assets/'rmvpe.pt';tampered.write_bytes(b'known weights')
        self.assertIs(self.torch.load(tampered)['weights_only'],True,'A differently named file is not trusted')
        self.trusted.write_bytes(b'tampered weights')
        self.assertIs(self.torch.load(self.trusted)['weights_only'],True,'A modified asset hash is not trusted')

    def test_callers_cannot_request_unsafe_unpickling(self):
        self.assertIs(self.torch.load(self.assets/'..'/'rvc-assets'/'hubert_base.pt',weights_only=False)['weights_only'],False)
        self.assertIs(self.torch.load(self.base/'extra.pt',weights_only=False)['weights_only'],True)

    def test_install_is_idempotent_and_every_load_clears_the_pytorch_override(self):
        wrapped=self.torch.load
        rvc_safe_load.install(self.torch,self.base)
        self.assertIs(self.torch.load,wrapped)
        os.environ['TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD']='1'
        self.assertIs(self.torch.load(self.base/'extra.pt')['weights_only'],True)
        self.assertNotIn('TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD',os.environ)
