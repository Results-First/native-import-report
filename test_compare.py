"""Unit and real-DLL integration verification. Saves CLI evidence per test run."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import compare
from test_support import pefix_path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "demo-inputs"
RUN = ROOT / "evidence" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


class Verification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        RUN.mkdir(parents=True)
        subprocess.run([sys.executable, str(ROOT / "demo.py"), "--out", str(RUN / "baseline")], check=True, timeout=300)
        cls.old = SOURCE / "2.1.11/SQLitePCLRaw.provider.e_sqlite3.dll"
        cls.new = SOURCE / "3.0.3/SQLitePCLRaw.provider.e_sqlite3.dll"
        cls.record = read(RUN / "baseline/old-rea.json")
        cls.pefix = pefix_path()

    def invoke(self, name, old, new, expected=0):
        command = [sys.executable, str(ROOT / "compare.py"), str(old), str(new), "--out", str(RUN / name)]
        run = subprocess.run(command, capture_output=True, text=True, timeout=300)
        compare.dump(RUN / f"{name}-invocation.json", {"command": command, "exit": run.returncode, "stdout": run.stdout, "stderr": run.stderr})
        self.assertEqual(run.returncode, expected, run.stdout + run.stderr)
        return read(RUN / name / "report.json")

    def test_real_upgrade_matches_independent_inventory(self):
        report = self.invoke("upgrade", self.old, self.new)
        self.assertEqual(report["status"], "complete")
        self.assertEqual({c["entry_point"] for c in report["changes"] if c["kind"] == "added"},
                         {"sqlite3_key", "sqlite3_key_v2", "sqlite3_rekey", "sqlite3_rekey_v2"})
        self.assertEqual([c["entry_point"] for c in report["changes"] if c["kind"] == "removed"], ["sqlite3_win32_set_directory8"])
        self.assertEqual(len(report["changes"]), 5)
        for side, version, count in [("old", "2.1.11", 149), ("new", "3.0.3", 152)]:
            rows = report[side]["declarations"]
            self.assertEqual(report[side]["declaration_count"], count)
            checked = subprocess.run([str(self.pefix), "pinvoke", report[side]["path"], "--json"], capture_output=True, timeout=60)
            (RUN / f"{side}-pefix.json").write_bytes(checked.stdout)
            self.assertEqual(checked.returncode, 0)
            independent = json.loads(checked.stdout)["calls"]
            self.assertEqual(Counter((r["import_scope_name"], r["member_name"], r["import_name"]) for r in rows),
                             Counter((r["module"], r["method"], r["entry"]) for r in independent))

    def test_identical_real_dll(self):
        self.assertEqual(self.invoke("identical", self.old, self.old)["changes"], [])

    def test_malformed_real_cli(self):
        bad = RUN / "malformed.dll"
        bad.write_bytes(b"MZ\x00not a managed assembly")
        report = self.invoke("malformed", self.old, bad, 2)
        self.assertEqual(report["status"], "incomplete")
        self.assertNotIn("changes", report)

    def test_missing_input(self):
        report = self.invoke("missing", RUN / "does-not-exist.dll", self.new, 2)
        self.assertEqual(report["status"], "incomplete")

    def test_native_executable_rejected(self):
        native = ROOT / ".runtime/node-v24.19.0-win-x64/node.exe"
        report = self.invoke("native-executable", self.old, native, 2)
        self.assertEqual(report["status"], "incomplete")

    def test_empty_and_truncated_dll_rejected(self):
        for name, data in (("empty", b""), ("truncated", self.old.read_bytes()[:512])):
            path = RUN / f"{name}.dll"
            path.write_bytes(data)
            with self.subTest(name=name):
                self.assertEqual(self.invoke(name, self.old, path, 2)["status"], "incomplete")

    def test_invalid_evidence_shapes_rejected(self):
        for record in (None, [], {"normalized_result": None}, {"normalized_result": {"artifact": None}}):
            with self.subTest(record=record), self.assertRaises(ValueError):
                compare.validate(record, compare.digest(self.old))

    def test_timeout_retains_partial_output(self):
        out = RUN / "timeout"
        out.mkdir()
        timeout = subprocess.TimeoutExpired(["rea"], 120, output=b"partial", stderr=b"diagnostic")
        with patch.object(compare.subprocess, "run", side_effect=timeout), self.assertRaisesRegex(ValueError, "exceeded"):
            compare.inspect(self.old, "old", out, "node", "rea")
        self.assertEqual((out / "old-rea.json").read_bytes(), b"partial")
        self.assertEqual(read(out / "old-execution.json")["status"], "timeout")

    def test_partial_coverage_rejected(self):
        record = deepcopy(self.record)
        record["normalized_result"]["coverage"]["state"] = "partial"
        with self.assertRaisesRegex(ValueError, "coverage"):
            compare.validate(record, compare.digest(self.old))

    def test_wrong_digest_rejected(self):
        with self.assertRaisesRegex(ValueError, "digest"):
            compare.validate(self.record, "0" * 64)

    def test_missing_rows_rejected(self):
        record = deepcopy(self.record)
        record["normalized_result"]["pinvoke_imports"].pop()
        with self.assertRaisesRegex(ValueError, "count"):
            compare.validate(record, compare.digest(self.old))

    def test_duplicates_and_mapping_flags_are_not_lost(self):
        row = self.record["normalized_result"]["pinvoke_imports"][0]
        before = {"declarations": [row]}
        after = {"declarations": [row, deepcopy(row)]}
        change = compare.compare(before, after)[0]
        self.assertEqual((change["old_count"], change["new_count"]), (1, 2))
        after["declarations"] = [deepcopy(row)]
        after["declarations"][0]["mapping_flags"] += 1
        self.assertEqual(compare.compare(before, after)[0]["kind"], "declarations_changed")

    def test_existing_output_not_overwritten(self):
        out = RUN / "existing"
        out.mkdir()
        sentinel = out / "report.json"
        sentinel.write_text("keep", encoding="utf-8")
        run = subprocess.run([sys.executable, str(ROOT / "compare.py"), str(self.old), str(self.new), "--out", str(out)], capture_output=True)
        self.assertEqual(run.returncode, 2)
        self.assertEqual(sentinel.read_text(), "keep")

    def test_library_rename_is_explained_and_escaped(self):
        row = deepcopy(self.record["normalized_result"]["pinvoke_imports"][0])
        old = {"path": "old.dll", "sha256": "old", "declaration_count": 1, "declarations": [row]}
        new = deepcopy(old)
        new["declarations"][0]["import_scope_name"] = "new|<library>"
        report = {"status": "complete", "old": old, "new": new, "changes": compare.compare(old, new)}
        self.assertEqual({c["kind"] for c in report["changes"]}, {"added", "removed"})
        rendered = compare.markdown(report)
        self.assertIn("new&#124;&lt;library&gt;", rendered)
        self.assertIn("does not establish that the underlying functions", rendered)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Verification)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    compare.dump(RUN / "verification.json", {"python": sys.version, "executable": sys.executable, "tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "passed": result.wasSuccessful(), "evidence": str(RUN)})
    print(f"Evidence: {RUN}")
    sys.exit(0 if result.wasSuccessful() else 1)
