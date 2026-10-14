"""Local REA-backed native import comparison. Python standard library only."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys

VERSION = "6.5.0"
LIMIT = "Import declarations only. Does not prove native exports, executed calls, signature/ABI compatibility or runtime loadability."


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def runtime(node_arg, package_arg):
    root = Path(__file__).resolve().parent
    node = node_arg or str(root / ".runtime/node-v24.19.0-win-x64/node.exe")
    if not Path(node).is_file():
        raise ValueError("Local Node is unavailable. Run python setup.py first, or supply --node with an executable path.")
    version = subprocess.check_output([node, "--version"], text=True, timeout=10).strip()
    major, minor, *_ = map(int, version.lstrip("v").split("."))
    if not ((major == 22 and minor >= 19) or (major == 24 and minor >= 11) or major >= 26):
        raise ValueError(f"Unsupported Node {version}.")
    candidates = [Path(package_arg)] if package_arg else [root / "node_modules/rea-agents"]
    for package in candidates:
        if not (package / "package.json").is_file():
            continue
        metadata = json.loads((package / "package.json").read_text(encoding="utf-8"))
        if metadata.get("name") == "rea-agents" and metadata.get("version") == VERSION:
            bin_path = metadata["bin"]
            if isinstance(bin_path, dict):
                bin_path = bin_path["rea"]
            return str(Path(node).resolve()), str((package / bin_path).resolve()), version
    raise ValueError(f"Local rea-agents@{VERSION} unavailable. Run python setup.py first, or supply --rea-package.")


def validate(record, sha):
    if not isinstance(record, dict):
        raise ValueError("REA returned an invalid evidence record.")
    result = record.get("normalized_result", {})
    if not isinstance(result, dict):
        raise ValueError("REA returned an invalid normalized result.")
    for field in ("artifact", "coverage", "metadata"):
        if not isinstance(result.get(field), dict):
            raise ValueError(f"REA returned invalid {field} evidence.")
    if result.get("artifact", {}).get("sha256") != sha:
        raise ValueError("REA artifact digest does not match the input.")
    coverage = result.get("coverage", {})
    if coverage.get("state") != "complete" or coverage.get("issues") != []:
        raise ValueError("REA coverage is incomplete or unknown.")
    metadata = result.get("metadata", {})
    if metadata.get("status") != "complete":
        raise ValueError("Managed metadata is incomplete.")
    rows = result.get("pinvoke_imports")
    tables = metadata.get("table_row_counts")
    if not isinstance(tables, dict):
        raise ValueError("Managed metadata table counts are unavailable.")
    count = tables.get("ImplMap", 0)
    if not isinstance(rows, list) or len(rows) != count:
        raise ValueError("Import declaration count does not match the metadata table.")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Unreadable import declaration.")
        for field in ("import_scope_name", "import_name", "member_name"):
            if not isinstance(row.get(field), str) or not row[field]:
                raise ValueError(f"Unreadable declaration field: {field}.")
        if not isinstance(row.get("row_offset"), int) or not isinstance(row.get("mapping_flags"), int):
            raise ValueError("Missing declaration location or mapping flags.")
    return result


def inspect(path, side, out, node, cli):
    path = path.resolve(strict=True)
    sha = digest(path)
    command = [node, cli, "inspect-managed-native-boundaries", str(path), "--format", "json"]
    dump(out / f"{side}-command.json", command)
    try:
        completed = subprocess.run(command, capture_output=True, timeout=120, cwd=Path(__file__).parent)
    except subprocess.TimeoutExpired as exc:
        (out / f"{side}-rea.json").write_bytes(exc.stdout or b"")
        (out / f"{side}-stderr.txt").write_bytes(exc.stderr or b"")
        dump(out / f"{side}-execution.json", {"status": "timeout", "timeout_seconds": 120, "exit": None})
        raise ValueError(f"{side}: REA exceeded 120 seconds. Partial evidence was retained.") from exc
    (out / f"{side}-rea.json").write_bytes(completed.stdout)
    (out / f"{side}-stderr.txt").write_bytes(completed.stderr)
    (out / f"{side}-exit.txt").write_text(str(completed.returncode), encoding="utf-8")
    if completed.returncode:
        raise ValueError(f"{side}: REA exited {completed.returncode}. See raw evidence.")
    if digest(path) != sha:
        raise ValueError(f"{side}: input changed during inspection.")
    result = validate(json.loads(completed.stdout), sha)
    return {"path": str(path), "sha256": sha, "mvid": result.get("module", {}).get("mvid"),
            "coverage": result["coverage"], "declaration_count": len(result["pinvoke_imports"]),
            "declarations": result["pinvoke_imports"]}


def groups(artifact):
    result = {}
    for row in artifact["declarations"]:
        result.setdefault((row["import_scope_name"], row["import_name"]), []).append(row)
    return result


def compare(old, new):
    left, right = groups(old), groups(new)
    changes = []
    for module, entry in sorted(left.keys() | right.keys()):
        before, after = left.get((module, entry), []), right.get((module, entry), [])
        flags_before = Counter(row["mapping_flags"] for row in before)
        flags_after = Counter(row["mapping_flags"] for row in after)
        kind = "added" if not before else "removed" if not after else "declarations_changed"
        if before and after and flags_before == flags_after:
            continue
        changes.append({"kind": kind, "module": module, "entry_point": entry,
                        "old_count": len(before), "new_count": len(after),
                        "old_flags": dict(sorted(flags_before.items())), "new_flags": dict(sorted(flags_after.items())),
                        "old_offsets": [row["row_offset"] for row in before],
                        "new_offsets": [row["row_offset"] for row in after]})
    return changes


def cell(value):
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("|", "&#124;").replace("\r", " ").replace("\n", " ")


def markdown(report):
    lines = ["# Native import comparison", "", f"Status: {report['status']}", "", LIMIT, ""]
    if report["status"] == "incomplete":
        return "\n".join(lines + ["No comparison verdict is available.", "", cell(report["error"]), ""])
    for side in ("old", "new"):
        item = report[side]
        lines += [f"{side.title()}: {cell(item['path'])}", f"SHA-256: {item['sha256']}",
                  f"Declarations: {item['declaration_count']}. Unique imports: {len(groups(item))}.", ""]
    lines += ["## Native library names", "", "| Library | Old declarations | New declarations |", "| --- | --- | --- |"]
    old_modules = Counter(row["import_scope_name"] for row in report["old"]["declarations"])
    new_modules = Counter(row["import_scope_name"] for row in report["new"]["declarations"])
    for module in sorted(old_modules.keys() | new_modules.keys()):
        lines.append(f"| {cell(module)} | {old_modules[module]} | {new_modules[module]} |")
    if not old_modules and not new_modules:
        lines.append("| None | 0 | 0 |")
    lines += ["", "A native library name change appears as removed and added imports. This does not establish that the underlying functions were removed or added.", ""]
    if not report["changes"]:
        lines += ["No changes in native module/entry-point pairs, declaration counts or mapping-flag distributions.", ""]
    else:
        lines += ["| Change | Native module | Entry point | Old count | New count | Old byte offsets | New byte offsets |", "| --- | --- | --- | --- | --- | --- | --- |"]
        for item in report["changes"]:
            values = [item[k] for k in ("kind", "module", "entry_point", "old_count", "new_count", "old_offsets", "new_offsets")]
            lines.append("| " + " | ".join(map(cell, values)) + " |")
    lines += ["", "Full declarations and mapping flags are retained in report.json and the raw REA records. Matching uses exact native module and entry-point names, not build-local tokens. Managed signatures and method identity are outside this comparison.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old", type=Path)
    parser.add_argument("new", type=Path)
    parser.add_argument("--out", type=Path, required=True, help="New evidence/report directory. Existing directories are refused.")
    parser.add_argument("--node")
    parser.add_argument("--rea-package")
    args = parser.parse_args()
    try:
        args.out.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        print(f"Cannot create output directory: {exc}", file=sys.stderr)
        return 2
    report = {"schema_version": 1, "rea_version": VERSION, "scope": LIMIT, "status": "incomplete"}
    try:
        node, cli, version = runtime(args.node, args.rea_package)
        report["node_version"] = version
        for side in ("old", "new"):
            report[side] = inspect(getattr(args, side), side, args.out, node, cli)
        report["changes"] = compare(report["old"], report["new"])
        report["status"] = "complete"
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        report["error"] = str(exc)
    try:
        # Write the human-readable report first. A successful JSON verdict is
        # published only after both report serializations have succeeded.
        rendered = markdown(report)
        (args.out / "report.md").write_text(rendered, encoding="utf-8")
        dump(args.out / "report.json", report)
    except OSError as exc:
        print(f"Could not finish writing reports: {exc}", file=sys.stderr)
        return 2
    print(f"{report['status']}: {(args.out / 'report.md').resolve()}")
    return 0 if report["status"] == "complete" else 2


if __name__ == "__main__":
    sys.exit(main())
