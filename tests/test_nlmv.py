import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import nlmv


class NLMVAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "docs").mkdir()
        for name in ["a.md", "b.md", "c.md", "merged.md", "split-1.md", "split-2.md"]:
            (self.root / "docs" / name).write_text(name, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def manifest(source_ids=("A", "B", "C"), dispositions=None):
        return {
            "schema_version": "0.1",
            "source_universe": [{"id": sid, "label": f"Source {sid}"} for sid in source_ids],
            "dispositions": dispositions or [],
        }

    def verify(self, data):
        return nlmv.verify_manifest(data, self.root)

    def test_01_complete_one_to_one_preserved_and_na_pass(self):
        data = self.manifest(dispositions=[
            {"source_ids": ["A"], "status": "SUCCESSOR", "target_paths": ["docs/a.md"]},
            {"source_ids": ["B"], "status": "PRESERVED", "target_paths": ["docs/b.md"]},
            {"source_ids": ["C"], "status": "NOT_APPLICABLE", "reason": "out of scope"},
        ])
        report = self.verify(data)
        self.assertEqual("PASS", report["result"])
        self.assertEqual(3, report["summary"]["accounted_total"])

    def test_02_duplicate_source_id_invalid(self):
        data = self.manifest(source_ids=("A", "A"), dispositions=[
            {"source_ids": ["A"], "status": "SUCCESSOR", "target_paths": ["docs/a.md"]}
        ])
        report = self.verify(data)
        self.assertEqual("INVALID", report["result"])
        self.assertIn("DUPLICATE_SOURCE_ID", {x["code"] for x in report["issues"]})

    def test_03_unknown_source_reference_invalid(self):
        data = self.manifest(source_ids=("A",), dispositions=[
            {"source_ids": ["Z"], "status": "SUCCESSOR", "target_paths": ["docs/a.md"]}
        ])
        report = self.verify(data)
        self.assertEqual("INVALID", report["result"])
        self.assertIn("UNKNOWN_SOURCE_ID", {x["code"] for x in report["issues"]})

    def test_04_missing_disposition_fails_closure(self):
        data = self.manifest(source_ids=("A", "B"), dispositions=[
            {"source_ids": ["A"], "status": "SUCCESSOR", "target_paths": ["docs/a.md"]}
        ])
        report = self.verify(data)
        self.assertEqual("FAIL", report["result"])
        self.assertEqual(1, report["summary"]["missing_disposition_total"])

    def test_05_source_in_two_dispositions_fails_closure(self):
        data = self.manifest(source_ids=("A",), dispositions=[
            {"source_ids": ["A"], "status": "SUCCESSOR", "target_paths": ["docs/a.md"]},
            {"source_ids": ["A"], "status": "PRESERVED", "target_paths": ["docs/b.md"]},
        ])
        report = self.verify(data)
        self.assertEqual("FAIL", report["result"])
        self.assertEqual(1, report["summary"]["duplicate_source_total"])

    def test_06_unresolved_fails_closure(self):
        data = self.manifest(source_ids=("A",), dispositions=[
            {"source_ids": ["A"], "status": "UNRESOLVED"}
        ])
        report = self.verify(data)
        self.assertEqual("FAIL", report["result"])
        self.assertEqual(1, report["summary"]["unresolved_total"])

    def test_07_successor_target_missing_fails_closure(self):
        data = self.manifest(source_ids=("A",), dispositions=[
            {"source_ids": ["A"], "status": "SUCCESSOR", "target_paths": ["docs/missing.md"]}
        ])
        report = self.verify(data)
        self.assertEqual("FAIL", report["result"])
        self.assertEqual(1, report["summary"]["broken_target_total"])

    def test_08_preserved_target_missing_fails_closure(self):
        data = self.manifest(source_ids=("A",), dispositions=[
            {"source_ids": ["A"], "status": "PRESERVED", "target_paths": ["docs/missing.md"]}
        ])
        report = self.verify(data)
        self.assertEqual("FAIL", report["result"])
        self.assertEqual(1, report["summary"]["broken_target_total"])

    def test_09_not_applicable_reason_missing_invalid(self):
        data = self.manifest(source_ids=("A",), dispositions=[
            {"source_ids": ["A"], "status": "NOT_APPLICABLE"}
        ])
        report = self.verify(data)
        self.assertEqual("INVALID", report["result"])
        self.assertIn("REASON_REQUIRED", {x["code"] for x in report["issues"]})

    def test_10_one_to_many_without_relation_invalid(self):
        data = self.manifest(source_ids=("A",), dispositions=[
            {"source_ids": ["A"], "status": "SUCCESSOR", "target_paths": ["docs/split-1.md", "docs/split-2.md"]}
        ])
        report = self.verify(data)
        self.assertEqual("INVALID", report["result"])
        self.assertIn("RELATION_REQUIRED", {x["code"] for x in report["issues"]})

    def test_11_explicit_one_to_many_passes(self):
        data = self.manifest(source_ids=("A",), dispositions=[
            {
                "source_ids": ["A"],
                "status": "SUCCESSOR",
                "relation": "ONE_TO_MANY",
                "target_paths": ["docs/split-1.md", "docs/split-2.md"],
            }
        ])
        self.assertEqual("PASS", self.verify(data)["result"])

    def test_12_explicit_many_to_one_passes(self):
        data = self.manifest(source_ids=("A", "B"), dispositions=[
            {
                "source_ids": ["A", "B"],
                "status": "SUCCESSOR",
                "relation": "MANY_TO_ONE",
                "target_paths": ["docs/merged.md"],
            }
        ])
        self.assertEqual("PASS", self.verify(data)["result"])

    def test_12a_preserved_many_to_one_passes(self):
        data = self.manifest(source_ids=("A", "B"), dispositions=[
            {
                "source_ids": ["A", "B"],
                "status": "PRESERVED",
                "relation": "MANY_TO_ONE",
                "target_paths": ["docs/merged.md"],
            }
        ])
        report = self.verify(data)
        self.assertEqual("PASS", report["result"])
        self.assertEqual(2, report["summary"]["preserved_total"])

    def test_13_implicit_cross_record_duplicate_target_fails(self):
        data = self.manifest(source_ids=("A", "B"), dispositions=[
            {"source_ids": ["A"], "status": "SUCCESSOR", "target_paths": ["docs/merged.md"]},
            {"source_ids": ["B"], "status": "SUCCESSOR", "target_paths": ["docs/merged.md"]},
        ])
        report = self.verify(data)
        self.assertEqual("FAIL", report["result"])
        self.assertEqual(1, report["summary"]["duplicate_target_total"])

    def test_14_relation_cardinality_mismatch_invalid(self):
        data = self.manifest(source_ids=("A",), dispositions=[
            {
                "source_ids": ["A"],
                "status": "SUCCESSOR",
                "relation": "MANY_TO_ONE",
                "target_paths": ["docs/split-1.md", "docs/split-2.md"],
            }
        ])
        report = self.verify(data)
        self.assertEqual("INVALID", report["result"])
        self.assertIn("RELATION_CARDINALITY_MISMATCH", {x["code"] for x in report["issues"]})

    def test_15_json_report_totals_and_exit_codes(self):
        pass_data = self.manifest(dispositions=[
            {"source_ids": ["A"], "status": "SUCCESSOR", "target_paths": ["docs/a.md"]},
            {"source_ids": ["B"], "status": "PRESERVED", "target_paths": ["docs/b.md"]},
            {"source_ids": ["C"], "status": "INTENTIONAL_REMOVAL", "reason": "retired"},
        ])
        manifest_path = self.root / "pass.json"
        manifest_path.write_text(json.dumps(pass_data), encoding="utf-8")
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = nlmv.main(["verify", str(manifest_path), "--target-root", str(self.root), "--json"])
        report = json.loads(buf.getvalue())
        self.assertEqual(0, code)
        self.assertEqual("PASS", report["result"])
        self.assertEqual(3, report["summary"]["source_total"])
        self.assertEqual(3, report["summary"]["accounted_total"])
        self.assertEqual(1, report["summary"]["successor_total"])
        self.assertEqual(1, report["summary"]["preserved_total"])
        self.assertEqual(1, report["summary"]["intentional_removal_total"])
        self.assertEqual(0, report["summary"]["unresolved_total"])
        self.assertEqual([], report["issues"])

        fail_data = self.manifest(source_ids=("A",), dispositions=[{"source_ids": ["A"], "status": "UNRESOLVED"}])
        fail_path = self.root / "fail.json"
        fail_path.write_text(json.dumps(fail_data), encoding="utf-8")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(1, nlmv.main(["verify", str(fail_path), "--target-root", str(self.root), "--json"]))

        invalid_data = self.manifest(source_ids=("A",), dispositions=[{"source_ids": ["A"], "status": "NOT_APPLICABLE"}])
        invalid_path = self.root / "invalid.json"
        invalid_path.write_text(json.dumps(invalid_data), encoding="utf-8")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(2, nlmv.main(["verify", str(invalid_path), "--target-root", str(self.root), "--json"]))

    def test_16_target_path_escape_is_invalid(self):
        data = self.manifest(source_ids=("A",), dispositions=[
            {"source_ids": ["A"], "status": "SUCCESSOR", "target_paths": ["../outside.md"]}
        ])
        report = self.verify(data)
        self.assertEqual("INVALID", report["result"])
        self.assertIn("UNSAFE_TARGET_PATH", {x["code"] for x in report["issues"]})


if __name__ == "__main__":
    unittest.main()
