import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch


def module(name,file):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).resolve().parents[1]/'tools'/file)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


class SyncJobTests(unittest.TestCase):
    def test_partial_upload_failure_still_publishes_finished_records_then_exits_for_next_scheduled_retry(self):
        job=module('sync_job','sync-library-drive.py')
        with tempfile.TemporaryDirectory() as folder,patch('sys.argv',['sync','--app','owner-app','--output',folder,
                '--source-credentials','private-file','--publish-url','https://example.test/publish']), \
             patch.object(job.subprocess,'run',side_effect=[Mock(returncode=0),Mock(returncode=2),Mock(returncode=0)]) as run:
            self.assertEqual(job.main(),2)
            self.assertEqual(run.call_count,3)
            self.assertIn('--once',run.call_args_list[-1].args[0])

    def test_one_pass_publication_does_not_wait_for_incomplete_uploads(self):
        job=module('catalogue_job','publish-library-catalogue.py')
        entry={'id':'ready','name':'Ready','sha256':'a'*64}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'uploaded-models.json').write_text(json.dumps({'ready':entry}))
            (root/'catalogue.json').write_text(json.dumps({'models':[entry,{'id':'pending','sha256':'b'*64}]}))
            with patch('sys.argv',['publish','--app','unused','--output',folder,'--url','https://example.test/publish','--once']), \
                 patch('agent_connections.secret_get',return_value={'token':'test-owner-proof'}), \
                 patch.object(job.requests,'post',return_value=Mock(status_code=200)) as post,patch.object(job.time,'sleep') as sleep:
                job.main()
            post.assert_called_once();sleep.assert_not_called()
            self.assertEqual(json.loads((root/'published-models.json').read_text()),{'ready':'a'*64})
