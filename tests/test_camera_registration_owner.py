from unittest.mock import patch
import pytest
import sakura_camera_native as camera


def test_registration_is_specific_to_this_installation(tmp_path):
    foreign=tmp_path/'Other Sakura/sakura-camera64.dll'
    with patch.object(camera,'_registered_dll_path',return_value=foreign),patch.object(camera,'_regsvr32') as register:
        assert not camera.driver_installed()
        with pytest.raises(RuntimeError,match='another Sakura'):camera.uninstall_driver()
        register.assert_not_called()
    with patch.object(camera,'_registered_dll_path',return_value=camera.DRIVER_DLL):
        assert camera.driver_installed()
