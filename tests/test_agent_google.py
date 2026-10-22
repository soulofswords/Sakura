import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from agent_runtime import AgentRuntime
from agent_connections import Connections
from agent_google import execute
class GoogleToolsTests(unittest.TestCase):
 def test_edit_does_not_execute_until_approved(self):
  with tempfile.TemporaryDirectory() as folder:
   runtime=AgentRuntime(Connections(Path(folder)/'connections.json'));run=runtime.new_run('Update my sheet',folder)
   with patch('agent_calendar.google_calendar.status',return_value={'workspace_connected':True}),patch('agent_google.binding',return_value='account-a'),patch('agent_google.execute',return_value={'updatedCells':1}) as execute_mock:
    proposed=runtime.propose(run['id'],'google.sheets.write',{'file_id':'real-id','range':'Sheet1!A1','values':[['Reviewed text']]})
    action=proposed['steps'][-1];execute_mock.assert_not_called()
    self.assertEqual(action['status'],'pending')
    runtime.decide(action['id'],True);execute_mock.assert_called_once()
 def test_reject_and_account_change_block_edits(self):
  for approve in (False,True):
   with tempfile.TemporaryDirectory() as folder:
    runtime=AgentRuntime(Connections(Path(folder)/'connections.json'));run=runtime.new_run('Rename a file',folder)
    with patch('agent_calendar.google_calendar.status',return_value={'workspace_connected':True}),patch('agent_google.binding',return_value='a'):
     action=runtime.propose(run['id'],'google.drive.rename',{'file_id':'id','name':'New'})['steps'][-1]
    with patch('agent_google.binding',return_value='b'),patch('agent_google.execute') as operation:
     runtime.decide(action['id'],approve);operation.assert_not_called()
 def test_sheet_writes_raw_and_bounded(self):
  with patch('agent_google.request',return_value={}) as request:
   execute('google.sheets.write',{'file_id':'id','range':'Sheet1!A1','values':[['=not a formula']]})
   self.assertEqual(request.call_args.args[3],{'valueInputOption':'RAW'})
 def test_missing_grant_blocks_proposal(self):
  with tempfile.TemporaryDirectory() as folder:
   runtime=AgentRuntime(Connections(Path(folder)/'connections.json'));run=runtime.new_run('Read doc',folder)
   with patch('agent_calendar.google_calendar.status',return_value={'workspace_connected':False}),self.assertRaises(ValueError):runtime.propose(run['id'],'google.docs.read',{'file_id':'id'})
