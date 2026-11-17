import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
spec=importlib.util.spec_from_file_location("toolkit",Path(__file__).resolve().parents[1]/"scripts"/"toolkit.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ToolkitTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.allowed=self.root/"allowed";self.allowed.mkdir()
    def test_read_inside(self):
        f=self.allowed/"a.txt";f.write_text("test");self.assertEqual(m.confined(f,[self.allowed]),f.resolve())
    def test_outside_rejected(self):
        with self.assertRaises(ValueError):m.confined(self.root/"other.txt",[self.allowed])
    def test_prefix_lookalike_rejected(self):
        with self.assertRaises(ValueError):m.confined(self.root/"allowed-other"/"a",[self.allowed])
    def test_traversal_rejected(self):
        with self.assertRaises(ValueError):m.confined(self.allowed/".."/"out",[self.allowed])
    def test_write_existing_rejected(self):
        f=self.allowed/"a.txt";f.write_text("keep")
        with self.assertRaises(ValueError):m.confined(f,[self.allowed],True)
        self.assertEqual(f.read_text(),"keep")
    def test_new_write_allowed(self):self.assertEqual(m.confined(self.allowed/"new.txt",[self.allowed],True),(self.allowed/"new.txt").resolve())
    def test_listing_is_one_level(self):
        (self.allowed/"sub").mkdir();(self.allowed/"sub"/"private.txt").write_text("test")
        result=m.list_files({'read_roots':[str(self.allowed)]},self.allowed);self.assertEqual([x['name'] for x in result],['sub'])
    def test_config_version(self):
        f=self.root/"config.json";f.write_text(json.dumps({'version':2}))
        with self.assertRaises(ValueError):m.load_config(f)
if __name__=='__main__':unittest.main()
