"""Check setup and demos in a fresh source folder with no copied runtime/cache."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import os
import zipfile

ROOT = Path(__file__).resolve().parent
def main():
    folder=ROOT/'evidence'/('native-portable-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    folder.mkdir(parents=True)
    with zipfile.ZipFile(ROOT/'native-import-report-windows-x64-source.zip') as archive:
        archive.extractall(folder)
    app = folder/'native-import-report'
    env = os.environ.copy()
    env['PATH'] = str(Path(os.environ['SystemRoot'])/'System32')
    env['NODE_PATH'] = env['NODE_OPTIONS'] = ''
    for key in ('LOCALAPPDATA','APPDATA'):
        env[key] = str(folder/key)
        Path(env[key]).mkdir()
    results=[]
    for command, expected in [([sys.executable,'setup_native.py'],0),
                              ([sys.executable,'demo_native.py','--case','sqlite'],0),
                              ([sys.executable,'demo_native.py'],3)]:
        p=subprocess.run(command,cwd=app,env=env,capture_output=True,timeout=420)
        i=len(results)
        (folder/f'{i}-stdout.txt').write_bytes(p.stdout)
        (folder/f'{i}-stderr.txt').write_bytes(p.stderr)
        results.append({'command':command,'exit':p.returncode,'expected':expected})
        if p.returncode!=expected:
            raise RuntimeError(f'Fresh-source check failed: {results[-1]}. See {folder}')
    reports=[json.loads(p.read_text()) for p in (app/'demo-reports').glob('*/report.json')]
    assert sorted(r['status'] for r in reports)==['missing_names','names_found']
    assert next(r for r in reports if r['status']=='missing_names')['counts']=={'found':197,'missing':1}
    (folder/'verification.json').write_text(json.dumps({'passed':True,'copied_runtime':False,'results':results},indent=2))
    print(str(folder/'verification.json'))

if __name__=='__main__':
    main()
