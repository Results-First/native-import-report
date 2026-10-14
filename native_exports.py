"""Native parsing worker. Targets are parsed as bytes, never loaded as code."""
import json
from pathlib import Path
import sys

def extract(path):
    sys.path.insert(0, str(Path(__file__).resolve().parent / '.native-tools'))
    import lief
    if not lief.__version__.startswith('0.17.3-'):
        raise ValueError('Expected LIEF 0.17.3. Run setup_native.py.')
    data = Path(path).read_bytes()
    exports, uncertain = {}, False
    if data[:2] == b'MZ':
        binary = lief.PE.parse(path)
        if binary is None or binary.header.machine != lief.PE.Header.MACHINE_TYPES.AMD64:
            raise ValueError('Only AMD64 PE libraries are supported by this prototype')
        directory = binary.get_export()
        if directory is None:
            raise ValueError('No readable PE export directory; cannot establish absence')
        for entry in directory.entries:
            if entry.name:
                exports[entry.name] = {'forwarded': bool(entry.is_forwarded), 'address': entry.address}
        kind, arch = 'PE', 'x86_64'
    elif data[:4] == b'\xcf\xfa\xed\xfe':
        fat = lief.MachO.parse(path)
        if fat is None or len(fat) != 1:
            raise ValueError('Expected one readable Mach-O slice')
        binary = fat.at(0)
        if binary.header.cpu_type not in (lief.MachO.Header.CPU_TYPE.ARM64, lief.MachO.Header.CPU_TYPE.X86_64):
            raise ValueError('Unsupported Mach-O architecture')
        # Re-exported libraries may supply names not enumerated locally.
        uncertain = any('REEXPORT_DYLIB' in str(c.command) for c in binary.commands)
        for entry in binary.exported_symbols:
            exports[entry.name] = {'forwarded': bool(entry.has_export_info and entry.export_info.flags & 8), 'address': entry.value}
        if not exports:
            raise ValueError('Empty Mach-O export inventory; cannot establish absence')
        kind, arch = 'MachO', str(binary.header.cpu_type).split('.')[-1].lower()
    else:
        raise ValueError('Unsupported native format. Supply AMD64 PE or thin ARM64/x64 Mach-O.')
    return {'format': kind, 'architecture': arch, 'parser': lief.__version__,
            'absence_uncertain': uncertain, 'exports': dict(sorted(exports.items()))}

if __name__ == '__main__':
    try:
        print(json.dumps(extract(sys.argv[1])))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
