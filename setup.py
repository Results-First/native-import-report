"""Install the pinned local runtime on Windows x64. Requires Python 3.10+."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
NODE = "24.19.0"
ARCHIVE = f"node-v{NODE}-win-x64.zip"
SHA256 = "57f71ab3652e797d84acddc79c81cc9ff1c6ddb2a1974cdb83f00fee9bff4c73"


def main():
    if sys.platform != "win32" or platform.machine().lower() not in ("amd64", "x86_64"):
        raise RuntimeError("Automatic setup supports Windows x64 only.")
    runtime = ROOT / ".runtime"
    runtime.mkdir(exist_ok=True)
    receipt_path = runtime / "setup-receipt.json"
    receipt_path.unlink(missing_ok=True)
    archive = runtime / ARCHIVE
    if not archive.exists() or hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        print(f"Downloading Node {NODE} from nodejs.org...", flush=True)
        partial = archive.with_suffix(".download")
        with urllib.request.urlopen(f"https://nodejs.org/dist/v{NODE}/{ARCHIVE}", timeout=60) as response, partial.open("wb") as target:
            shutil.copyfileobj(response, target)
        if hashlib.sha256(partial.read_bytes()).hexdigest() != SHA256:
            raise RuntimeError("Node archive checksum mismatch. Installation stopped.")
        partial.replace(archive)
    # Re-extract the verified archive so a rerun repairs altered runtime files.
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(runtime)
    node_dir = runtime / f"node-v{NODE}-win-x64"
    node = node_dir / "node.exe"
    npm = node_dir / "node_modules/npm/bin/npm-cli.js"
    env = os.environ.copy()
    env["PATH"] = str(node_dir) + os.pathsep + env.get("PATH", "")
    env["npm_config_cache"] = str(runtime / "npm-cache")
    env["npm_config_userconfig"] = str(runtime / "empty.npmrc")
    env["npm_config_globalconfig"] = str(runtime / "empty-global.npmrc")
    for name in ("empty.npmrc", "empty-global.npmrc"):
        (runtime / name).write_text("", encoding="utf-8")
    print("Installing locked REA dependencies locally...", flush=True)
    command = [str(node), str(npm), "ci", "--ignore-scripts", "--no-audit", "--no-fund", "--registry=https://registry.npmjs.org"]
    try:
        completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=300)
    except subprocess.TimeoutExpired as exc:
        (runtime / "npm-install.stdout.txt").write_bytes(exc.stdout or b"")
        (runtime / "npm-install.stderr.txt").write_bytes(exc.stderr or b"")
        raise RuntimeError("npm installation timed out. Partial logs were retained. Rerun setup.py to retry.") from exc
    (runtime / "npm-install.stdout.txt").write_bytes(completed.stdout)
    (runtime / "npm-install.stderr.txt").write_bytes(completed.stderr)
    if completed.returncode:
        raise RuntimeError(f"npm ci exited {completed.returncode}. See .runtime/npm-install.stderr.txt.")
    check = subprocess.run([str(node), str(ROOT / "node_modules/rea-agents/scripts/rea.mjs"), "--version"], capture_output=True, text=True, timeout=30)
    if check.returncode or check.stdout.strip() != "6.5.0":
        raise RuntimeError("Installed REA failed its version check.")
    receipt = {"node": NODE, "node_archive_sha256": SHA256, "rea": "6.5.0", "package_lock_sha256": hashlib.sha256((ROOT / "package-lock.json").read_bytes()).hexdigest(), "npm_exit": completed.returncode, "rea_version_output": check.stdout.strip(), "npm_cache": env["npm_config_cache"]}
    (runtime / "setup-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print("Ready. Run python compare.py OLD.dll NEW.dll --out REPORT_DIRECTORY")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, zipfile.BadZipFile) as exc:
        print(f"Setup failed: {exc}", file=sys.stderr)
        sys.exit(2)
