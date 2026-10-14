"""Verify fresh installation and offline comparison with no inherited Node/cache."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import zipfile
import subprocess
import sys

import compare

ROOT = Path(__file__).resolve().parent


def main():
    run = ROOT / "evidence" / ("portable-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    destination = run / "fresh copy with spaces"
    destination.mkdir(parents=True)
    archive = ROOT / "native-import-report-windows-x64-source.zip"
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(destination)
    app = destination / "native-import-report"
    for name in ("compare.py", "setup.py", "demo.py", "package.json", "package-lock.json"):
        if (app / name).read_bytes() != (ROOT / name).read_bytes():
            raise RuntimeError("Release is stale. Run build_release.py first.")
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(run / "empty-localappdata")
    env["APPDATA"] = str(run / "empty-appdata")
    env["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
    env["NODE_PATH"] = ""
    env["NODE_OPTIONS"] = ""
    env["npm_config_cache"] = str(run / "empty-inherited-cache")
    for key in ("LOCALAPPDATA", "APPDATA", "npm_config_cache"):
        Path(env[key]).mkdir(parents=True)
    commands = []

    def execute(name, arguments, expected):
        result = subprocess.run([sys.executable, *arguments], cwd=app, env=env, capture_output=True, timeout=360)
        (run / f"{name}.stdout.txt").write_bytes(result.stdout)
        (run / f"{name}.stderr.txt").write_bytes(result.stderr)
        commands.append({"name": name, "command": [sys.executable, *arguments], "exit": result.returncode})
        compare.dump(run / "commands.json", commands)
        if result.returncode != expected:
            raise RuntimeError(f"{name}: exit {result.returncode}, expected {expected}. See {run}")

    source = app / "demo-inputs"
    old = str(source / "2.1.11/SQLitePCLRaw.provider.e_sqlite3.dll")
    new = str(source / "3.0.3/SQLitePCLRaw.provider.e_sqlite3.dll")
    execute("before-setup", ["compare.py", old, new, "--out", str(run / "before")], 2)
    execute("setup", ["setup.py"], 0)
    execute("public-demo", ["demo.py", "--out", str(run / "public-demo")], 0)
    # A dead proxy exposes accidental standard HTTP/HTTPS dependency fetching.
    env["HTTP_PROXY"] = env["HTTPS_PROXY"] = "http://127.0.0.1:1"
    env["npm_config_offline"] = "true"
    # Damage only this test's isolated installation, then verify offline repair.
    (app / "node_modules/rea-agents/scripts/rea.mjs").write_text("broken test fixture", encoding="utf-8")
    execute("offline-repair", ["setup.py"], 0)
    execute("offline-demo", ["demo.py", "--out", str(run / "offline-demo")], 0)
    execute("compare", ["compare.py", old, new, "--out", str(run / "report")], 0)
    report = json.loads((run / "report/report.json").read_text(encoding="utf-8"))
    if report["status"] != "complete" or len(report["changes"]) != 5:
        raise RuntimeError("Fresh installation did not reproduce the expected comparison.")
    for side in ("old", "new"):
        command = json.loads((run / f"report/{side}-command.json").read_text(encoding="utf-8"))
        for executable_path in command[:2]:
            if not Path(executable_path).is_relative_to(app):
                raise RuntimeError("Analysis used a runtime outside the fresh installation.")
    compare.dump(run / "verification.json", {"passed": True, "empty_localappdata": env["LOCALAPPDATA"], "path": env["PATH"], "fresh_install": str(app), "rea_commands_use_fresh_install": True, "comparison_changes": len(report["changes"]), "network_note": "Comparison uses local Node and REA directly. npm offline and dead proxies set, not an OS-level network sandbox."})
    print(f"Fresh install and comparison passed. Evidence: {run}")


if __name__ == "__main__":
    main()
