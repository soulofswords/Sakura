import unittest
from unittest.mock import Mock,patch
import rvc_manager
class RVCOwnershipTests(unittest.TestCase):
 def test_stop_releases_owned_worker_and_children(self):
  worker=Mock();worker.poll.return_value=None;job=Mock()
  with patch.object(rvc_manager,'_worker',worker),patch.object(rvc_manager,'_job',job):
   rvc_manager.stop_rvc_service()
   job.close.assert_called_once();worker.terminate.assert_called_once();worker.wait.assert_called_once_with(timeout=5)
   self.assertIsNone(rvc_manager._worker);self.assertIsNone(rvc_manager._job)
 def test_stop_does_not_touch_external_services(self):
  with patch.object(rvc_manager,'_worker',None),patch.object(rvc_manager,'_job',None),patch('rvc_manager.subprocess.Popen') as launch:
   rvc_manager.stop_rvc_service();launch.assert_not_called()
