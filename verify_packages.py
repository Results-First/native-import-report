"""Download public NuGet fixtures and verify real reports against pefix 1.0.2."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import urllib.request
import zipfile

import compare
from test_support import pefix_path

ROOT = Path(__file__).resolve().parent
CASES = [
    ("skiasharp", ("2.88.9", "3.119.0"), "lib/netstandard2.0/SkiaSharp.dll"),
    ("libgit2sharp", ("0.30.0", "0.31.0"), "lib/net472/LibGit2Sharp.dll"),
    ("newtonsoft.json", ("13.0.1", "13.0.3"), "lib/netstandard2.0/Newtonsoft.Json.dll"),
]


def require(value, message):
    if not value:
        raise RuntimeError(message)


def main():
    run = ROOT / "evidence" / ("packages-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    run.mkdir(parents=True)
    pefix = pefix_path()
    results = []
    for name, versions, member in CASES:
        paths, inventories = [], []
        for version in versions:
            folder = ROOT / "evidence/packages" / name / version
            folder.mkdir(parents=True, exist_ok=True)
            archive = folder / "package.nupkg"
            url = f"https://api.nuget.org/v3-flatcontainer/{name}/{version}/{name}.{version}.nupkg"
            if not archive.exists():
                with urllib.request.urlopen(url, timeout=60) as response:
                    archive.write_bytes(response.read())
            with zipfile.ZipFile(archive) as bundle:
                dll = folder / Path(member).name
                dll.write_bytes(bundle.read(member))
            compare.dump(folder / "provenance.json", {"url": url, "package_sha256": compare.digest(archive), "member": member, "dll_sha256": compare.digest(dll), "authentication": "none"})
            paths.append(dll)
            command = [str(pefix), "pinvoke", str(dll), "--json"]
            check = subprocess.run(command, capture_output=True, timeout=60)
            (run / f"{name}-{version}-pefix.json").write_bytes(check.stdout)
            (run / f"{name}-{version}-pefix.stderr.txt").write_bytes(check.stderr)
            compare.dump(run / f"{name}-{version}-invocation.json", {"command": command, "exit": check.returncode, "pefix_sha256": compare.digest(pefix)})
            require(check.returncode == 0, f"pefix failed: {name} {version}")
            inventories.append(Counter((r["module"], r["method"], r["entry"]) for r in json.loads(check.stdout)["calls"]))
        command = [sys.executable, str(ROOT / "compare.py"), *map(str, paths), "--out", str(run / name)]
        process = subprocess.run(command, capture_output=True, text=True, timeout=300)
        compare.dump(run / f"{name}-invocation.json", {"command": command, "exit": process.returncode, "stdout": process.stdout, "stderr": process.stderr})
        require(process.returncode == 0, f"Comparison failed: {name}. Evidence: {run}")
        report = json.loads((run / name / "report.json").read_text(encoding="utf-8"))
        for side, inventory in zip(("old", "new"), inventories):
            actual = Counter((r["import_scope_name"], r["member_name"], r["import_name"]) for r in report[side]["declarations"])
            require(actual == inventory, f"Inventory disagreement: {name} {side}")
        old, new = ({(module, entry) for module, method, entry in inv} for inv in inventories)
        for kind, expected in (("added", new - old), ("removed", old - new)):
            actual = {(r["module"], r["entry_point"]) for r in report["changes"] if r["kind"] == kind}
            require(actual == expected, f"Delta disagreement: {name} {kind}")
        results.append({"package": name, "versions": versions, "declarations": [report[s]["declaration_count"] for s in ("old", "new")], "changes": dict(Counter(c["kind"] for c in report["changes"])), "independent_inventory_match": True})
        print(json.dumps(results[-1]), flush=True)
    compare.dump(run / "verification.json", {"passed": True, "results": results})
    print(f"Evidence: {run}")


if __name__ == "__main__":
    main()
