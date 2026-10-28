import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import vtuber_instances
import gui_server


class VTuberInstanceTests(unittest.TestCase):
    def test_secondary_instances_start_with_unique_empty_profiles(self):
        with tempfile.TemporaryDirectory() as root:
            first=vtuber_instances.instance_profile(root,1)
            self.assertEqual(first,Path(root)/'desktop-profile')
            second=vtuber_instances.instance_profile(root,2)
            (second/'old-scene.json').write_text('old scene')
            reopened=vtuber_instances.instance_profile(root,2)
            self.assertNotEqual(second,reopened)
            self.assertFalse((reopened/'old-scene.json').exists())
    @unittest.skipUnless(sys.platform == 'win32', 'Windows instance lease')
    def test_three_live_slots_limit_and_crash_release(self):
        with tempfile.TemporaryDirectory() as root:
            children=[]
            code="from vtuber_instances import claim_instance;import sys;print(claim_instance(sys.argv[1]),flush=True);sys.stdin.read()"
            try:
                for slot in range(1,4):
                    child=subprocess.Popen([sys.executable,'-u','-c',code,root],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                    children.append(child)
                    self.assertEqual(child.stdout.readline().strip(),str(slot))
                fourth=subprocess.run([sys.executable,'-c','from vtuber_instances import claim_instance;import sys;claim_instance(sys.argv[1])',root],capture_output=True,text=True,timeout=5)
                self.assertNotEqual(fourth.returncode,0)
                self.assertIn('Three Sakura VTuber instances',fourth.stderr)
                children[1].kill();children[1].wait(5)
                replacement=subprocess.Popen([sys.executable,'-u','-c',code,root],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                children.append(replacement)
                self.assertEqual(replacement.stdout.readline().strip(),'2')
            finally:
                for child in children:
                    if child.poll() is None:child.kill()
                    child.communicate(timeout=5)

    def test_each_instance_selects_its_own_backend_range(self):
        ports=[]
        for slot in (1,2,3):
            with patch.dict(os.environ,{'SAKURA_INSTANCE_INDEX':str(slot)}),patch('product.EDITION','vtuber'):
                self.assertFalse(gui_server.select_port())
                ports.append(gui_server.port)
        self.assertEqual(len(set(ports)),3)
        self.assertTrue(all(8780<=port<=8807 for port in ports))

    def test_companion_vtuber_child_has_separate_ports(self):
        with patch.dict(os.environ,{'SAKURA_INSTANCE_INDEX':'2','SAKURA_VTUBER_INSTANCE':'1'}),patch('product.EDITION','companion'):
            self.assertFalse(gui_server.select_port())
            self.assertTrue(8840<=gui_server.port<=8847)

    def test_button_launch_reclaims_slot_in_child_instead_of_inheriting_it(self):
        with patch.dict(os.environ,{'SAKURA_INSTANCE_INDEX':'2'}),patch('vtuber_instances.subprocess.Popen') as spawn:
            vtuber_instances.spawn_instance(Path.cwd())
            self.assertNotIn('SAKURA_INSTANCE_INDEX',spawn.call_args.kwargs['env'])
            self.assertEqual(spawn.call_args.kwargs['env']['SAKURA_START_MODE'],'vtuber')
            self.assertEqual(spawn.call_args.kwargs['env']['SAKURA_VTUBER_INSTANCE'],'1')


if __name__=='__main__':unittest.main()
