import hashlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import nlmv


class NLMVG2HardeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "docs").mkdir()
        (self.root / "docs" / "a.md").write_text("a", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def manifest(target="docs/a.md"):
        return {
            "schema_version": "0.1",
            "source_universe": [{"id": "A", "label": "Source A"}],
            "dispositions": [
                {"source_ids": ["A"], "status": "SUCCESSOR", "target_paths": [target]}
            ],
        }

    def run_main_json(self, manifest_path):
        out = io.StringIO()
        with redirect_stdout(out):
            code = nlmv.main([
                "verify",
                str(manifest_path),
                "--target-root",
                str(self.root),
                "--json",
            ])
        return code, json.loads(out.getvalue())

    def test_missing_manifest_file_is_invalid_exit_2(self):
        code, report = self.run_main_json(self.root / "does-not-exist.json")
        self.assertEqual(2, code)
        self.assertEqual("INVALID", report["result"])
        self.assertIn("MANIFEST_READ_ERROR", {issue["code"] for issue in report["issues"]})

    def test_malformed_json_is_invalid_exit_2(self):
        path = self.root / "malformed.json"
        path.write_text("{not-json", encoding="utf-8")
        code, report = self.run_main_json(path)
        self.assertEqual(2, code)
        self.assertEqual("INVALID", report["result"])
        self.assertIn("JSON_PARSE_ERROR", {issue["code"] for issue in report["issues"]})

    def test_posix_absolute_target_path_is_invalid(self):
        report = nlmv.verify_manifest(self.manifest("/tmp/outside.md"), self.root)
        self.assertEqual("INVALID", report["result"])
        self.assertIn("UNSAFE_TARGET_PATH", {issue["code"] for issue in report["issues"]})

    def test_windows_absolute_target_path_is_invalid_on_any_host(self):
        report = nlmv.verify_manifest(self.manifest(r"C:\outside\target.md"), self.root)
        self.assertEqual("INVALID", report["result"])
        self.assertIn("UNSAFE_TARGET_PATH", {issue["code"] for issue in report["issues"]})

    def test_forward_slash_relative_target_path_passes(self):
        report = nlmv.verify_manifest(self.manifest("docs/a.md"), self.root)
        self.assertEqual("PASS", report["result"])

    def test_symlink_escape_is_invalid_when_symlinks_are_available(self):
        outside_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(outside_tmp.cleanup)
        outside = Path(outside_tmp.name)
        (outside / "outside.md").write_text("outside", encoding="utf-8")
        link = self.root / "link"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlink unavailable: {exc}")
        report = nlmv.verify_manifest(self.manifest("link/outside.md"), self.root)
        self.assertEqual("INVALID", report["result"])
        self.assertIn("UNSAFE_TARGET_PATH", {issue["code"] for issue in report["issues"]})

    def test_failure_reports_keep_actionable_source_and_target_refs(self):
        data = self.manifest("docs/missing.md")
        report = nlmv.verify_manifest(data, self.root)
        self.assertEqual("FAIL", report["result"])
        issue = next(issue for issue in report["issues"] if issue["code"] == "BROKEN_TARGET")
        self.assertEqual(["A"], issue["source_ids"])
        self.assertEqual(["docs/missing.md"], issue["target_paths"])
        human = nlmv.render_human(report)
        self.assertIn("source_ids=A", human)
        self.assertIn("target_paths=docs/missing.md", human)

    def test_verification_leaves_target_bytes_unchanged(self):
        files = sorted(path for path in self.root.rglob("*") if path.is_file())
        before = {str(path.relative_to(self.root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
        report = nlmv.verify_manifest(self.manifest(), self.root)
        self.assertEqual("PASS", report["result"])
        files_after = sorted(path for path in self.root.rglob("*") if path.is_file())
        after = {str(path.relative_to(self.root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files_after}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
