import struct
import unittest

from vbridger_receiver import _osc_messages


def osc_string(value):
    raw = value.encode() + b'\0'
    return raw + b'\0' * ((-len(raw)) % 4)


def osc_blend(name, value):
    return osc_string('/VMC/Ext/Blend/Val') + osc_string(',sf') + osc_string(name) + struct.pack('>f', value)


class VBridgerOscTests(unittest.TestCase):
    def test_reads_vmc_blendshape_message(self):
        message = list(_osc_messages(osc_blend('jawOpen', .73)))
        self.assertEqual(message[0][0], '/VMC/Ext/Blend/Val')
        self.assertEqual(message[0][1][0], 'jawOpen')
        self.assertAlmostEqual(message[0][1][1], .73)

    def test_reads_blendshape_inside_vmc_bundle(self):
        message = osc_blend('eyeBlinkLeft', .9)
        packet = b'#bundle\0' + struct.pack('>Q', 1) + struct.pack('>I', len(message)) + message
        self.assertEqual(list(_osc_messages(packet))[0][0], '/VMC/Ext/Blend/Val')

    def test_ignores_malformed_osc(self):
        self.assertEqual(list(_osc_messages(b'/VMC/Ext/Blend/Val')), [])


if __name__ == '__main__':
    unittest.main()
