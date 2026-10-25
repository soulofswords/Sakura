import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import numpy as np
from virtual_camera import camera_frame, VirtualCamera
import sakura_camera_native
from sakura_camera_native import CAMERA_NAME, CAMERA_CLSID

class SakuraCameraTests(unittest.TestCase):
    def test_frame_is_rgb_centered_and_contiguous(self):
        frame=camera_frame(bytes([255,0,0,255])*64*64,64,64)
        self.assertEqual(frame.shape,(720,1280,3))
        self.assertTrue(frame.flags.c_contiguous)
        self.assertEqual(frame.dtype,np.uint8)
        self.assertEqual(frame[360,640].tolist(),[255,0,0])
        self.assertEqual(frame[0,0].tolist(),[16,18,28])

    def test_device_has_separate_identity_and_disabled_state(self):
        output=VirtualCamera()
        self.assertEqual(output.status()['device'],CAMERA_NAME)
        self.assertEqual(CAMERA_NAME,'Sakura Virtual Camera')
        self.assertNotEqual(CAMERA_CLSID.lower(),'{a3fce0f5-3493-419f-958a-aba1250ec20b}')
        self.assertFalse(output.configure(False)['enabled'])

@unittest.skipUnless(sys.platform=='win32','The Sakura camera driver registers with Windows.')
class CameraDriverRegistrationTests(unittest.TestCase):
    REGISTERED=Path('C:\\Windows\\System32\\sakura-camera64.dll')

    def test_uninstall_is_a_noop_when_nothing_is_registered(self):
        register=Mock()
        with patch.object(sakura_camera_native,'_registered_dll_path',Mock(return_value=None)),patch.object(sakura_camera_native,'_regsvr32',register):
            self.assertEqual(sakura_camera_native.uninstall_driver(),{'installed':False,'device':CAMERA_NAME})
        register.assert_not_called()

    def test_uninstall_removes_the_registered_driver_not_the_build_output(self):
        register=Mock()
        with patch.object(sakura_camera_native,'_registered_dll_path',Mock(return_value=self.REGISTERED)),patch.object(sakura_camera_native,'driver_installed',Mock(return_value=False)),patch.object(sakura_camera_native,'_regsvr32',register):
            self.assertEqual(sakura_camera_native.uninstall_driver(),{'installed':False,'device':CAMERA_NAME})
        self.assertEqual(register.call_args.args,('camera removal','/s /u "C:\\Windows\\System32\\sakura-camera64.dll"',self.REGISTERED.parent))

    def test_uninstall_reports_a_cancelled_windows_prompt(self):
        shell=Mock(return_value=2)
        with patch.object(sakura_camera_native,'_registered_dll_path',Mock(return_value=self.REGISTERED)),patch.object(sakura_camera_native.ctypes.windll.shell32,'ShellExecuteW',shell):
            with self.assertRaises(RuntimeError) as failure:sakura_camera_native.uninstall_driver()
        self.assertIn('cancelled',str(failure.exception))
        self.assertIn('removal',str(failure.exception))
        self.assertTrue(shell.call_args.args[2].endswith('regsvr32.exe'))
        self.assertEqual(shell.call_args.args[1],'runas')
        self.assertIn('/s /u "C:\\Windows\\System32\\sakura-camera64.dll"',shell.call_args.args[3])

    def test_reinstall_keeps_registering_without_the_uninstall_switch(self):
        register=Mock()
        with tempfile.TemporaryDirectory() as folder:
            dll=Path(folder)/'sakura-camera64.dll'
            dll.write_bytes(b'')
            with patch.object(sakura_camera_native,'DRIVER_DLL',dll),patch.object(sakura_camera_native,'driver_installed',Mock(side_effect=[False,True])),patch.object(sakura_camera_native,'_regsvr32',register):
                self.assertEqual(sakura_camera_native.install_driver(),{'installed':True,'device':CAMERA_NAME})
        action,arguments,workdir=register.call_args.args
        self.assertEqual((action,workdir),('camera installation',dll.parent))
        self.assertEqual(arguments,f'/s "{dll}"')

if __name__=='__main__':unittest.main()
