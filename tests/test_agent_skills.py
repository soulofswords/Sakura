import tempfile
import unittest
from pathlib import Path
from agent_skills import AgentSkills

class SkillsTests(unittest.TestCase):
    def test_persist_validate_and_delete(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'skills.json';skills=AgentSkills(path)
            self.assertEqual(skills.list(),[])
            skills.save('report','Read sources and verify the output.')
            self.assertEqual(AgentSkills(path).get('report')['source'],'user-provided')
            with self.assertRaises(ValueError):skills.save('report','Another procedure here')
            with self.assertRaises(ValueError):skills.save('../escape','Read sources and verify output')
            with self.assertRaises(ValueError):skills.save('short','x')
            skills.delete('report')
            with self.assertRaises(ValueError):skills.get('report')
