"""Fetch the pinned independent verifier used only by development tests."""
from pathlib import Path
import urllib.request
import zipfile
import compare

ROOT = Path(__file__).resolve().parent
PEFIX_SHA256 = "9f8c304e225427863d0d55d2436b623a46e88b240d947eec540b793f416dafd0"


def pefix_path():
    folder = ROOT / ".test-tools"
    folder.mkdir(exist_ok=True)
    archive = folder / "pefix-win-x64.zip"
    if not archive.exists() or compare.digest(archive) != PEFIX_SHA256:
        with urllib.request.urlopen("https://github.com/FeathBow/pefix/releases/download/v1.0.2/pefix-win-x64.zip", timeout=60) as response:
            data = response.read()
        import hashlib
        if hashlib.sha256(data).hexdigest() != PEFIX_SHA256:
            raise ValueError("Independent verifier checksum mismatch.")
        archive.write_bytes(data)
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(folder / "pefix")
    return folder / "pefix/pefix.exe"
