import hashlib
import os
import stat
import tempfile
import unittest
from pathlib import Path

import agent_workspace_files as engine


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class WorkspaceFileEngineTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)

    def write(self, name, text, encoding="utf-8", newline=""):
        path = self.root / name
        with path.open("w", encoding=encoding, newline=newline) as handle:
            handle.write(text)
        return path

    def test_create_writes_exact_reviewed_bytes_and_reports_diff(self):
        path = self.root / "draft.md"
        prepared = engine.prepare_create(path, "# Notes\n\nFirst line.\n")
        result = engine.execute_prepared(path, prepared)
        self.assertEqual(path.read_bytes(), b"# Notes\n\nFirst line.\n")
        self.assertEqual(result["sha256"], sha256(path.read_bytes()))
        self.assertIn("+First line.", prepared["preview"]["diff"])
        self.assertIsNone(prepared["bindings"]["base_sha256"])

    def test_create_refuses_existing_and_directory_paths(self):
        self.write("notes.txt", "hello")
        with self.assertRaisesRegex(ValueError, "existing path"):
            engine.prepare_create(self.root / "notes.txt", "new")
        (self.root / "sub").mkdir()
        with self.assertRaisesRegex(ValueError, "existing path"):
            engine.prepare_create(self.root / "sub", "new")

    def test_create_stale_when_file_appears_after_review(self):
        path = self.root / "late.md"
        prepared = engine.prepare_create(path, "# Late\n")
        path.write_text("someone else", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Stale create"):
            engine.execute_prepared(path, prepared)
        self.assertEqual(path.read_text(encoding="utf-8"), "someone else")

    def test_edit_requires_exact_occurrence_count(self):
        self.write("notes.txt", "alpha beta alpha")
        with self.assertRaisesRegex(ValueError, "expected 1 occurrences, found 2"):
            engine.prepare_edit(self.root / "notes.txt",
                               [{"old": "alpha", "new": "gamma", "count": 1}])
        prepared = engine.prepare_edit(self.root / "notes.txt",
                                      [{"old": "alpha", "new": "gamma", "count": 2}])
        engine.execute_prepared(self.root / "notes.txt", prepared)
        self.assertEqual((self.root / "notes.txt").read_text(encoding="utf-8"),
                         "gamma beta gamma")

    def test_edit_rejects_overlapping_replacements_without_writing(self):
        self.write("notes.txt", "abcabc")
        with self.assertRaisesRegex(ValueError, "[Oo]verlap"):
            engine.prepare_edit(self.root / "notes.txt", [
                {"old": "ab", "new": "X", "count": 2},
                {"old": "bc", "new": "Y", "count": 2},
            ])
        self.assertEqual((self.root / "notes.txt").read_text(encoding="utf-8"), "abcabc")

    def test_edit_is_a_noop_error_when_result_unchanged(self):
        self.write("notes.txt", "same")
        with self.assertRaisesRegex(ValueError, "no-op"):
            engine.prepare_edit(self.root / "notes.txt",
                               [{"old": "same", "new": "same", "count": 1}])

    def test_edit_preserves_crlf_and_reports_only_changed_lines(self):
        path = self.write("notes.txt", "one\r\ntwo\r\nthree\r\n")
        prepared = engine.prepare_edit(path, [{"old": "two", "new": "TWO", "count": 1}])
        engine.execute_prepared(path, prepared)
        self.assertEqual(path.read_bytes(), b"one\r\nTWO\r\nthree\r\n")
        diff = prepared["preview"]["diff"]
        self.assertEqual([line for line in diff.splitlines() if line.startswith(("-", "+"))
                          and not line.startswith(("---", "+++"))], ["-two", "+TWO"])

    def test_mixed_newline_source_is_refused(self):
        path = self.write("notes.txt", "one\r\ntwo\n")
        with self.assertRaisesRegex(ValueError, "mixed newline"):
            engine.prepare_edit(path, [{"old": "two", "new": "TWO", "count": 1}])

    def test_stale_source_blocks_execution_after_review(self):
        path = self.write("notes.txt", "one\ntwo\n")
        prepared = engine.prepare_edit(path, [{"old": "two", "new": "TWO", "count": 1}])
        path.write_text("one\ntwo changed\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "[Ss]tale"):
            engine.execute_prepared(path, prepared)
        self.assertEqual(path.read_text(encoding="utf-8"), "one\ntwo changed\n")

    def test_tampered_preview_content_or_diff_is_rejected(self):
        path = self.write("notes.txt", "one\ntwo\n")
        prepared = engine.prepare_edit(path, [{"old": "two", "new": "TWO", "count": 1}])
        tampered = dict(prepared)
        tampered["content"] = prepared["content"].replace("TWO", "EVIL")
        with self.assertRaisesRegex(ValueError, "tampered"):
            engine.execute_prepared(path, tampered)
        tampered = dict(prepared)
        tampered["preview"] = {**prepared["preview"], "diff": "@@ fake @@\n"}
        with self.assertRaisesRegex(ValueError, "tampered"):
            engine.execute_prepared(path, tampered)
        self.assertEqual(path.read_text(encoding="utf-8"), "one\ntwo\n")

    def test_tampered_arguments_are_rejected(self):
        path = self.write("notes.txt", "one\ntwo\n")
        prepared = engine.prepare_edit(path, [{"old": "two", "new": "TWO", "count": 1}])
        prepared["arguments"]["replacements"][0]["new"] = "EVIL"
        with self.assertRaisesRegex(ValueError, "tampered"):
            engine.execute_prepared(path, prepared)
        self.assertNotIn("EVIL", path.read_text(encoding="utf-8"))

    def test_patch_applies_exact_hunks_and_rejects_mismatch(self):
        path = self.write("notes.txt", "one\ntwo\nthree\n")
        patch = ("--- a/notes.txt\n+++ b/notes.txt\n"
                 "@@ -1,3 +1,3 @@\n one\n-two\n+TWO\n three\n")
        prepared = engine.prepare_patch(path, patch)
        self.assertEqual(prepared["preview"]["hunk_count"], 1)
        engine.execute_prepared(path, prepared)
        self.assertEqual(path.read_bytes(), b"one\nTWO\nthree\n")
        wrong = ("--- a/notes.txt\n+++ b/notes.txt\n"
                 "@@ -1,3 +1,3 @@\n one\n-ZZZ\n+TWO\n three\n")
        with self.assertRaisesRegex(ValueError, "does not exactly match"):
            engine.prepare_patch(path, wrong)

    def test_patch_rejects_renames_and_multiple_files(self):
        path = self.write("notes.txt", "one\n")
        multi = ("--- a/notes.txt\n+++ b/notes.txt\n@@ -1 +1 @@\n-one\n+TWO\n"
                 "--- a/other.txt\n+++ b/other.txt\n@@ -1 +1 @@\n-a\n+b\n")
        with self.assertRaisesRegex(ValueError, "single file|Malformed"):
            engine.prepare_patch(path, multi)
        rename = "--- a/notes.txt\n+++ b/renamed.txt\n@@ -1 +1 @@\n-one\n+TWO\n"
        with self.assertRaisesRegex(ValueError, "single file"):
            engine.prepare_patch(path, rename)

    def test_patch_handles_missing_final_newline(self):
        path = self.write("notes.txt", "one\ntwo")
        patch = ("--- a/notes.txt\n+++ b/notes.txt\n"
                 "@@ -1,2 +1,2 @@\n one\n-two\n\\ No newline at end of file\n+TWO\n")
        prepared = engine.prepare_patch(path, patch)
        engine.execute_prepared(path, prepared)
        self.assertEqual(path.read_bytes(), b"one\nTWO\n")

    def test_execute_preserves_file_mode_and_leaves_no_temp_files(self):
        path = self.write("script.py", "print(1)\n")
        os.chmod(path, 0o755)
        before_mode = stat.S_IMODE(path.stat().st_mode)
        prepared = engine.prepare_edit(path, [{"old": "1", "new": "2", "count": 1}])
        engine.execute_prepared(path, prepared)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), before_mode)
        self.assertEqual([item.name for item in self.root.iterdir()], ["script.py"])

    def test_size_limits_reject_oversized_content_and_non_utf8(self):
        with self.assertRaisesRegex(ValueError, "limit"):
            engine.prepare_create(self.root / "big.md", "x" * (engine.MAX_TEXT_BYTES + 1))
        (self.root / "bin.dat").write_bytes(b"\xff\xfe not utf8")
        with self.assertRaisesRegex(ValueError, "UTF-8"):
            engine.prepare_edit(self.root / "bin.dat", [{"old": "a", "new": "b", "count": 1}])

    def test_delete_is_not_an_available_operation(self):
        path = self.write("notes.txt", "one\n")
        prepared = engine.prepare_edit(path, [{"old": "one", "new": "two", "count": 1}])
        prepared["operation"] = "delete"
        with self.assertRaisesRegex(ValueError, "unknown operation"):
            engine.execute_prepared(path, prepared)
        self.assertEqual(path.read_text(encoding="utf-8"), "one\n")

    def test_prepared_bound_to_a_different_path_is_rejected(self):
        path = self.write("a.txt", "one\n")
        prepared = engine.prepare_edit(path, [{"old": "one", "new": "two", "count": 1}])
        tampered = dict(prepared)
        tampered["bindings"] = {**prepared["bindings"], "path": str(self.root / "b.txt")}
        tampered["preview"] = {**prepared["preview"], "path": str(self.root / "b.txt")}
        with self.assertRaisesRegex(ValueError, "different path"):
            engine.execute_prepared(path, tampered)
        self.assertEqual(path.read_text(encoding="utf-8"), "one\n")


if __name__ == "__main__":
    unittest.main()
