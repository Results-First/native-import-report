import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from check_native import classify
from verify_native import artifact

ROOT = Path(__file__).resolve().parent

class LookupRules(unittest.TestCase):
    def native(self, names=(), **kwargs):
        return dict(format='PE',absence_uncertain=False,exports={n:{'forwarded':False} for n in names},**kwargs)
    def test_exact_and_missing(self):
        row={'import_name':'foo','no_mangle':True}
        self.assertEqual(classify(row,self.native(['foo']))[0],'found')
        self.assertEqual(classify(row,self.native(['foobar']))[0],'missing')
    def test_windows_suffix_is_unresolved(self):
        self.assertEqual(classify({'import_name':'foo','no_mangle':False},self.native(['fooW']))[0],'unresolved')
    def test_forwarder_is_not_verified(self):
        n=self.native(['foo']); n['exports']['foo']['forwarded']=True
        self.assertEqual(classify({'import_name':'foo','no_mangle':True},n)[0],'unresolved')
    def test_ordinal_is_unresolved(self):
        self.assertEqual(classify({'import_name':'#12','no_mangle':True},self.native())[0],'unresolved')
    def test_macho_prefix_and_reexports(self):
        n=self.native(['_foo']); n['format']='MachO'
        self.assertEqual(classify({'import_name':'foo','no_mangle':False},n)[0],'found')
        n['absence_uncertain']=True
        self.assertEqual(classify({'import_name':'bar','no_mangle':False},n)[0],'unresolved')

class FailureBehavior(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.managed=artifact('sqlitepclraw.provider.e_sqlite3/2.1.11','lib/netstandard2.0/SQLitePCLRaw.provider.e_sqlite3.dll')
        cls.native=artifact('sqlitepclraw.lib.e_sqlite3/2.1.11','runtimes/win-x64/native/e_sqlite3.dll')
    def run_check(self, managed, native, out, module='e_sqlite3'):
        return subprocess.run([sys.executable,str(ROOT/'check_native.py'),str(managed),str(native),'--module',module,'--out',str(out)],capture_output=True,timeout=120)
    def test_unknown_module_is_incomplete(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'report'
            self.assertEqual(self.run_check(self.managed,self.native,out,'wrong-module').returncode,2)
            r=json.loads((out/'report.json').read_text())
            self.assertEqual(r['status'],'incomplete'); self.assertIn('No declarations',r['error'])
    def test_bad_native_and_managed(self):
        with tempfile.TemporaryDirectory() as d:
            bad=Path(d)/'bad.dll';bad.write_bytes(b'MZtruncated')
            for i,(m,n) in enumerate([(self.managed,bad),(bad,self.native)]):
                out=Path(d)/str(i)
                self.assertEqual(self.run_check(m,n,out).returncode,2)
                self.assertEqual(json.loads((out/'report.json').read_text())['status'],'incomplete')
    def test_existing_report_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d); p=out/'report.json';p.write_text('keep')
            self.assertEqual(self.run_check(self.managed,self.native,out).returncode,2)
            self.assertEqual(p.read_text(),'keep')

if __name__ == '__main__':
    unittest.main()
