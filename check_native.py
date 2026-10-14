"""Compare declared P/Invoke names with one explicitly paired native artifact."""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
import compare

LIMIT = 'Static names in explicitly paired files only. Not ABI, platform reachability, runtime loading, or successful execution.'

def classify(row, native):
    name = row['import_name']
    if name.startswith('#'):
        return 'unresolved', 'Ordinal lookup is outside this prototype'
    raw = '_' + name if native['format'] == 'MachO' else name
    entry = native['exports'].get(raw)
    if entry:
        if entry['forwarded']:
            return 'unresolved', 'Export is forwarded or re-exported; destination not verified'
        return 'found', 'Exact exported name present'
    if native['absence_uncertain']:
        return 'unresolved', 'Native library re-exports another library'
    if native['format'] == 'PE' and not row['no_mangle']:
        # Windows suffix probing depends on marshalling and runtime policy.
        if any(name + suffix in native['exports'] for suffix in ('A', 'W')):
            return 'unresolved', 'Only an A/W-suffixed candidate exists; runtime lookup not modeled'
    return 'missing', 'Exact name absent from the supplied native export inventory'

def render(report):
    lines = ['# Native import/export check', '', 'Status: ' + report['status'], '', LIMIT, '']
    if 'error' in report:
        return '\n'.join(lines + [compare.cell(report['error']), ''])
    lines += ['Pairing: `' + compare.cell(report['module']) + '` → `' + compare.cell(report['native']['path']) + '`', '',
              'Managed SHA-256: ' + report['managed']['sha256'], 'Native SHA-256: ' + report['native']['sha256'], '',
              'Declaration totals: ' + ', '.join(f'{k}={v}' for k,v in report['counts'].items()), '',
              'Found means name presence only. Unmapped modules and unsupported lookup rules remain unresolved.', '',
              '| Result | Module | Entry point | Metadata offset | Reason |', '| --- | --- | --- | --- | --- |']
    # Show actionable items first; full results, including duplicates, remain in JSON.
    for r in sorted(report['results'], key=lambda r:(r['result']=='found', r['module'], r['entry'])):
        if r['result'] != 'found':
            lines.append('| ' + ' | '.join(compare.cell(r[k]) for k in ('result','module','entry','row_offset','reason')) + ' |')
    if not any(r['result'] != 'found' for r in report['results']):
        lines += ['', 'All declared names for this mapping were found. This is not a runtime compatibility verdict.']
    return '\n'.join(lines) + '\n'

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('managed', type=Path)
    parser.add_argument('native', type=Path)
    parser.add_argument('--module', required=True, help='Exact declared module name to pair with this native file')
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args(argv)
    out = args.out.resolve()
    try:
        out.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        print(f'Cannot create new output directory: {exc}', file=sys.stderr)
        return 2
    report = {'schema_version':1, 'status':'incomplete', 'scope':LIMIT}
    code = 2
    try:
        managed, native = args.managed.resolve(), args.native.resolve()
        for path in (managed, native):
            if not path.is_file() or not 0 < path.stat().st_size <= 256 * 1024 * 1024:
                raise ValueError('Input missing, empty, or larger than 256 MiB: ' + str(path))
        node, cli, _ = compare.runtime(None, None)
        inventory = compare.inspect(managed, 'managed', out, node, cli)
        before = compare.digest(native)
        command = [sys.executable, str(Path(__file__).with_name('native_exports.py')), str(native)]
        compare.dump(out / 'native-command.json', command)
        run = subprocess.run(command, capture_output=True, timeout=60)
        (out / 'native-stdout.json').write_bytes(run.stdout)
        (out / 'native-stderr.txt').write_bytes(run.stderr)
        (out / 'native-exit.txt').write_text(str(run.returncode))
        if run.returncode or run.stderr.strip():
            raise ValueError('Native parser failed or emitted diagnostics. See native-stderr.txt; no absence verdict issued.')
        if before != compare.digest(native):
            raise ValueError('Native file changed during inspection')
        exports = json.loads(run.stdout)
        results = []
        selected = 0
        for row in inventory['declarations']:
            if row['import_scope_name'] != args.module:
                state, reason = 'unresolved', 'Module not mapped to the supplied native artifact'
            else:
                selected += 1
                state, reason = classify(row, exports)
            results.append({'module':row['import_scope_name'], 'entry':row['import_name'],
                            'row_offset':row['row_offset'], 'mapping_flags':row['mapping_flags'],
                            'result':state, 'reason':reason})
        if not selected:
            raise ValueError('No declarations match --module. Check the exact module name. No compatibility verdict issued.')
        counts = dict(Counter(r['result'] for r in results))
        status = 'incomplete' if counts.get('unresolved') else 'missing_names' if counts.get('missing') else 'names_found'
        code = 2 if status == 'incomplete' else 3 if status == 'missing_names' else 0
        report.update(status=status, module=args.module, rea_version=compare.VERSION,
                      managed=inventory, native={'path':str(native),'sha256':before,
                      'format':exports['format'],'architecture':exports['architecture'],'parser':exports['parser']},
                      counts=counts, results=results)
    except Exception as exc:
        report['error'] = str(exc)
    compare.dump(out / 'report.json', report)
    (out / 'report.md').write_text(render(report), encoding='utf-8')
    print(str(out / 'report.md'))
    return code

if __name__ == '__main__':
    sys.exit(main())
