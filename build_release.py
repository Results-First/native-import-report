"""Build the source ZIP with the evidence files linked by its README."""
from pathlib import Path
import re
import zipfile
import compare

ROOT = Path(__file__).resolve().parent
ARCHIVE = ROOT / "native-import-report-windows-x64-source.zip"


def main():
    files = {"compare.py", "setup.py", "demo.py", "package.json", "package-lock.json", "README.md", "LICENSE", "THIRD-PARTY.md"}
    files.update({'setup_native.py','check_native.py','native_exports.py','demo_native.py',
                  'verify_native.py','test_support.py','NATIVE-PROTOTYPE.md',
                  'test_native.py','verify_native_portable.py','build_release.py'})
    files.update(re.findall(r"\]\((evidence/[^)]+)\)", (ROOT / "README.md").read_text(encoding="utf-8")))
    for name in files:
        target = (ROOT / name).resolve()
        if not target.is_relative_to(ROOT) or not target.is_file():
            raise ValueError(f"Missing or invalid release file: {name}")
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in sorted(files):
            info = zipfile.ZipInfo("native-import-report/" + name, date_time=(2026,10,14,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(info, (ROOT / name).read_bytes())
    with zipfile.ZipFile(ARCHIVE) as bundle:
        if bundle.testzip() is not None:
            raise ValueError("Release archive integrity check failed.")
        for name in files:
            if bundle.read("native-import-report/" + name) != (ROOT / name).read_bytes():
                raise ValueError(f"Release content mismatch: {name}")
    (ROOT / 'evidence').mkdir(exist_ok=True)
    compare.dump(ROOT / "evidence/distribution.json", {"archive": ARCHIVE.name, "sha256": compare.digest(ARCHIVE), "bytes": ARCHIVE.stat().st_size, "files": sorted(files), "archive_verified": True})
    (ROOT / 'SHA256SUMS.txt').write_text(compare.digest(ARCHIVE) + '  ' + ARCHIVE.name + '\n', encoding='utf-8')
    print(f"Verified release: {ARCHIVE}")


if __name__ == "__main__":
    main()
