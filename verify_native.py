"""Real NuGet artifact tests. No sibling workspace or pre-existing artifacts required."""
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
PACKAGES = {
 'wasmtime/48.0.2':'7672c89e28338de4f838951e5cddfab0eb68cfa86031cb4520390bc71f770951',
 'skiasharp/3.119.0':'1ba4f41385a5f4d5bd9bff475b5469a6ec6ce62729d38bafaa463e26efefbf33',
 'skiasharp.nativeassets.win32/3.119.0':'625b6c05100357b6f7a8bdff62b806d864f026bf0f2f549379a8a641a812003a',
 'skiasharp.nativeassets.win32/2.88.9':'90fe573391a0c0719f3497dee13db23b934866d885ef50dda74a5dd6f1b957fe',
 'sqlitepclraw.provider.e_sqlite3/2.1.11':'2dd7d5df6e409988013b09b03fb30d67130966434ee9bc2b1ef07a0b94b222d0',
 'sqlitepclraw.lib.e_sqlite3/2.1.11':'6667df6c73609cb51db0f6e29229440228715e5d4c79d2014355f3b7ddb6e81c',
 'libgit2sharp/0.31.0':'02fbec03776c0db706363a715973b91758b0f1b86b72d696434303da8252c890',
 'libgit2sharp.nativebinaries/2.0.323':'d2a16ac8d0b4bb4e5417e0c9fcb36f9e0e52babd6bc9c8bec0810685553feeb1',
}
CASES = [
 ('wasmtime-arm64','wasmtime/48.0.2','lib/netstandard2.0/Wasmtime.Dotnet.dll','wasmtime/48.0.2','runtimes/osx-arm64/native/libwasmtime.dylib','wasmtime'),
 ('wasmtime-x64','wasmtime/48.0.2','lib/netstandard2.0/Wasmtime.Dotnet.dll','wasmtime/48.0.2','runtimes/osx-x64/native/libwasmtime.dylib','wasmtime'),
 ('skiasharp','skiasharp/3.119.0','lib/netstandard2.0/SkiaSharp.dll','skiasharp.nativeassets.win32/3.119.0','runtimes/win-x64/native/libSkiaSharp.dll','libSkiaSharp'),
 ('sqlite','sqlitepclraw.provider.e_sqlite3/2.1.11','lib/netstandard2.0/SQLitePCLRaw.provider.e_sqlite3.dll','sqlitepclraw.lib.e_sqlite3/2.1.11','runtimes/win-x64/native/e_sqlite3.dll','e_sqlite3'),
 ('libgit2','libgit2sharp/0.31.0','lib/net472/LibGit2Sharp.dll','libgit2sharp.nativebinaries/2.0.323','runtimes/win-x64/native/git2-3f4182d.dll','git2-3f4182d'),
 ('skiasharp-mixed','skiasharp/3.119.0','lib/netstandard2.0/SkiaSharp.dll','skiasharp.nativeassets.win32/2.88.9','runtimes/win-x64/native/libSkiaSharp.dll','libSkiaSharp'),
]

def artifact(coordinate, member):
    name, version = coordinate.split('/')
    folder = ROOT / 'evidence/native-packages'
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / f'{name}.{version}.nupkg'
    url = f'https://api.nuget.org/v3-flatcontainer/{coordinate}/{name}.{version}.nupkg'
    if not archive.exists():
        with urllib.request.urlopen(url, timeout=60) as response:
            archive.write_bytes(response.read())
    if compare.digest(archive) != PACKAGES[coordinate]:
        raise ValueError('Fixture package hash mismatch: ' + coordinate)
    target = folder / coordinate / member
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        target.write_bytes(bundle.read(member))
    compare.dump(target.with_suffix('.provenance.json'), {'url':url, 'package_sha256':PACKAGES[coordinate], 'member':member, 'sha256':compare.digest(target)})
    return target

def main():
    oracle_dir = ROOT / '.test-tools/native-oracle'
    if not (oracle_dir / 'pefile.py').exists():
        subprocess.run([sys.executable,'-m','pip','install','--target',str(oracle_dir),'--only-binary=:all:',
                        'pefile==2024.8.26','macholib==1.16.3','altgraph==0.17.4'],check=True)
    sys.path.insert(0,str(oracle_dir))
    import pefile
    from macholib.MachO import MachO
    from macholib.SymbolTable import SymbolTable
    pefix = pefix_path()
    run = ROOT / 'evidence' / ('native-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    run.mkdir(parents=True)
    results = []
    for name, mc, mm, nc, nm, module in CASES:
        managed, native = artifact(mc,mm), artifact(nc,nm)
        out = run / name
        command = [sys.executable,str(ROOT/'check_native.py'),str(managed),str(native),'--module',module,'--out',str(out)]
        process = subprocess.run(command,capture_output=True,timeout=180)
        report = json.loads((out/'report.json').read_text())
        compare.dump(out/'invocation.json',{'command':command,'exit':process.returncode})
        assert 'error' not in report, report
        actual_exports = json.loads((out/'native-stdout.json').read_text())['exports']
        if native.suffix == '.dylib':
            expected_exports = {n.decode() for _,n in SymbolTable(MachO(str(native))).extdefsyms}
        else:
            pe = pefile.PE(str(native))
            expected_exports = {s.name.decode() for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name}
        assert expected_exports == set(actual_exports), name
        oracle = subprocess.run([str(pefix),'pinvoke',str(managed),'--json'],capture_output=True,check=True)
        (out/'pefix.json').write_bytes(oracle.stdout)
        expected_imports = Counter((r['module'],r['entry']) for r in json.loads(oracle.stdout)['calls'])
        assert expected_imports == Counter((r['module'],r['entry']) for r in report['results'])
        prefix = '_' if native.suffix == '.dylib' else ''
        expected_missing = {e for (m,e) in expected_imports if m == module and prefix+e not in expected_exports}
        actual_missing = {r['entry'] for r in report['results'] if r['result']=='missing'}
        assert expected_missing == actual_missing, (name,expected_missing ^ actual_missing)
        if name.startswith('wasmtime'):
            assert actual_missing == {'wasmtime_config_macos_use_mach_ports'} and process.returncode == 3
        if name == 'sqlite':
            assert not actual_missing and process.returncode == 0
        if name == 'skiasharp':
            assert not actual_missing and report['counts'] == {'found':877,'unresolved':10} and process.returncode == 2
        if name == 'skiasharp-mixed':
            assert actual_missing and report['counts']['unresolved'] == 10 and process.returncode == 2
        results.append({'case':name,'exit':process.returncode,'status':report['status'],'counts':report['counts'],
                        'missing_unique':len(actual_missing),'independent_imports_and_exports_agree':True})
        print(json.dumps(results[-1]),flush=True)
    compare.dump(run/'verification.json',{'passed':True,'results':results})
    print('Evidence: ' + str(run))

if __name__ == '__main__':
    main()
