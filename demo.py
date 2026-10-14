"""Download two hash-pinned public DLLs and run the real comparison."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
PACKAGE = "sqlitepclraw.provider.e_sqlite3"
DLL = "SQLitePCLRaw.provider.e_sqlite3.dll"
VERSIONS = [
    ("2.1.11", "2dd7d5df6e409988013b09b03fb30d67130966434ee9bc2b1ef07a0b94b222d0", "25d2fa721d1504a6fbd31b4cd6457d93ce88bdd3b61af81d644f931c21dd18d5"),
    ("3.0.3", "6eb54fbba60405b2ad7caadfe4f57cb03659b269591602f92ac7ba14fd35b85d", "c97285eff57ddfbc6418c4e1278e73f1703e902071ce59af98318b010e0b39ff"),
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="New report directory. Defaults to a timestamped demo report.")
    args = parser.parse_args()
    output = args.out or ROOT / "demo-reports" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    if output.exists():
        raise ValueError("Output already exists. Choose a new directory.")
    paths = []
    for version, package_hash, dll_hash in VERSIONS:
        folder = ROOT / "demo-inputs" / version
        folder.mkdir(parents=True, exist_ok=True)
        archive = folder / "package.nupkg"
        url = f"https://api.nuget.org/v3-flatcontainer/{PACKAGE}/{version}/{PACKAGE}.{version}.nupkg"
        if not archive.exists() or sha(archive.read_bytes()) != package_hash:
            print(f"Downloading public sample {version}...", flush=True)
            with urllib.request.urlopen(url, timeout=60) as response:
                data = response.read()
            if sha(data) != package_hash:
                raise ValueError(f"Package checksum mismatch: {version}")
            archive.write_bytes(data)
        member = f"lib/netstandard2.0/{DLL}"
        with zipfile.ZipFile(archive) as bundle:
            data = bundle.read(member)
        if sha(data) != dll_hash:
            raise ValueError(f"DLL checksum mismatch: {version}")
        path = folder / DLL
        path.write_bytes(data)
        (folder / "source.json").write_text(json.dumps({"url": url, "package_sha256": package_hash, "member": member, "dll_sha256": dll_hash}, indent=2) + "\n", encoding="utf-8")
        paths.append(path)
    result = subprocess.run([sys.executable, str(ROOT / "compare.py"), *map(str, paths), "--out", str(output)], timeout=300)
    if result.returncode:
        return result.returncode
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    observed = {(change["kind"], change["module"], change["entry_point"]) for change in report["changes"]}
    expected = {("added", "e_sqlite3", name) for name in ("sqlite3_key", "sqlite3_key_v2", "sqlite3_rekey", "sqlite3_rekey_v2")}
    expected.add(("removed", "e_sqlite3", "sqlite3_win32_set_directory8"))
    if observed != expected or len(report["changes"]) != 5:
        raise ValueError("Demo differs from the independently verified result. Inspect the report.")
    print(f"Demo verified: four added imports, one removed. Open {output.resolve() / 'report.md'}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, zipfile.BadZipFile) as exc:
        print(f"Demo failed: {exc}", file=sys.stderr)
        sys.exit(2)
