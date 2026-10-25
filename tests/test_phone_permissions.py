import unittest
import app


class PhoneCommandPermissionTests(unittest.TestCase):
    def test_a_phone_cannot_drive_the_pc_unless_separately_allowed(self):
        off={'computer_control_enabled':False}
        on={'computer_control_enabled':True}
        self.assertFalse(app.phone_command_allowed(off,{'phone':True}))
        self.assertFalse(app.phone_command_allowed(on,{'phone':True}))
        self.assertTrue(app.phone_command_allowed({**on,'phone_system_access_enabled':True},{'phone':True}))
        self.assertTrue(app.phone_command_allowed(on,{}))

    def test_the_pc_keeps_computer_control_regardless_of_the_phone_setting(self):
        self.assertTrue(app.phone_command_allowed({'computer_control_enabled':True,'phone_system_access_enabled':False},{'phone':False}))
        self.assertFalse(app.phone_command_allowed({'computer_control_enabled':False,'phone_system_access_enabled':True},{'phone':True}))
