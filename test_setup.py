"""Installer failure tests use isolated temporary directories, never the real install."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import setup


class SetupTests(unittest.TestCase):
    def setUp(self):
        machine = patch.object(setup.platform, "machine", return_value="AMD64")
        machine.start()
        self.addCleanup(machine.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = self.root / ".runtime"
        self.runtime.mkdir()
        (self.root / "package-lock.json").write_text("{}")
        self.receipt = self.runtime / "setup-receipt.json"
        self.receipt.write_text('{"old":"success"}')
        self.override = patch.object(setup, "ROOT", self.root)
        self.override.start()
        self.addCleanup(self.override.stop)

    def seed_archive(self):
        archive = self.runtime / setup.ARCHIVE
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr(f"node-v{setup.NODE}-win-x64/node.exe", b"fixture, never executed")
        override = patch.object(setup, "SHA256", hashlib.sha256(archive.read_bytes()).hexdigest())
        override.start()
        self.addCleanup(override.stop)

    def test_checksum_failure_never_executes_download(self):
        with patch.object(setup.urllib.request, "urlopen", return_value=io.BytesIO(b"corrupt")), patch.object(setup.subprocess, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
                setup.main()
            run.assert_not_called()
        self.assertFalse(self.receipt.exists())

    def test_failed_install_removes_old_success_and_retains_logs(self):
        self.seed_archive()
        failure = subprocess.CompletedProcess([], 1, b"output", b"failure")
        with patch.object(setup.subprocess, "run", return_value=failure), self.assertRaisesRegex(RuntimeError, "exited 1"):
            setup.main()
        self.assertFalse(self.receipt.exists())
        self.assertEqual((self.runtime / "npm-install.stderr.txt").read_bytes(), b"failure")

    def test_timeout_retains_logs_and_no_success_receipt(self):
        self.seed_archive()
        failure = subprocess.TimeoutExpired([], 300, output=b"partial", stderr=b"partial error")
        with patch.object(setup.subprocess, "run", side_effect=failure), self.assertRaisesRegex(RuntimeError, "timed out"):
            setup.main()
        self.assertFalse(self.receipt.exists())
        self.assertEqual((self.runtime / "npm-install.stdout.txt").read_bytes(), b"partial")

    def test_wrong_installed_version_is_rejected(self):
        self.seed_archive()
        results = [subprocess.CompletedProcess([], 0, b"ok", b""), subprocess.CompletedProcess([], 0, "16.5.0", "")]
        with patch.object(setup.subprocess, "run", side_effect=results), self.assertRaisesRegex(RuntimeError, "version check"):
            setup.main()
        self.assertFalse(self.receipt.exists())

    def test_success_uses_lockfile_and_disables_scripts(self):
        self.seed_archive()
        results = [subprocess.CompletedProcess([], 0, b"ok", b""), subprocess.CompletedProcess([], 0, "6.5.0\n", "")]
        with patch.object(setup.subprocess, "run", side_effect=results) as run:
            setup.main()
        args = run.call_args_list[0].args[0]
        self.assertIn("ci", args)
        self.assertIn("--ignore-scripts", args)
        self.assertEqual(json.loads(self.receipt.read_text())["rea"], "6.5.0")


if __name__ == "__main__":
    unittest.main(verbosity=2)
