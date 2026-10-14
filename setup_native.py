"""Set up the native-check prototype locally on Windows x64 / CPython 3.11."""
import hashlib
from pathlib import Path
import platform
import sys
import urllib.request
import zipfile
import setup

URL = 'https://files.pythonhosted.org/packages/36/30/072f92fd934e328ce00bc5aa86146fe95b199dddf704e7958d40d0b71abb/lief-0.17.3-cp311-cp311-win_amd64.whl'
SHA = '98a970f396b16e6743d9a7fe9cd00a60f25dc767c495ba55f48c8d74d3fd6804'

def main():
    if sys.version_info[:2] != (3, 11) or sys.platform != 'win32' or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise RuntimeError('This prototype setup requires CPython 3.11 on Windows x64.')
    setup.main()
    root = Path(__file__).resolve().parent / '.native-tools'
    root.mkdir(exist_ok=True)
    wheel = root / 'lief.whl'
    if not wheel.exists() or hashlib.sha256(wheel.read_bytes()).hexdigest() != SHA:
        with urllib.request.urlopen(URL, timeout=60) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != SHA:
            raise RuntimeError('LIEF checksum mismatch')
        wheel.write_bytes(data)
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(root)
    print('Native checker ready. Run python check_native.py --help')

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
