"""Download hash-verified public inputs and run one native-check example."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
from verify_native import CASES, artifact

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=[c[0] for c in CASES], default='wasmtime-arm64')
    args = parser.parse_args()
    name, mc, mm, nc, nm, module = next(c for c in CASES if c[0] == args.case)
    managed, native = artifact(mc, mm), artifact(nc, nm)
    root = Path(__file__).resolve().parent
    out = root/'demo-reports'/('native-'+name+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    return subprocess.call([sys.executable,str(root/'check_native.py'),str(managed),str(native),'--module',module,'--out',str(out)])

if __name__ == '__main__':
    sys.exit(main())
