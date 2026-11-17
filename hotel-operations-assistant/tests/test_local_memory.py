import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("local_memory", Path(__file__).resolve().parents[1] / "scripts" / "local_memory.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class LocalMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name) / "memory"
        self.store = mod.MemoryStore(self.directory)

    def preference(self):
        return dict(kind="preference", title="虚构格式偏好", scope="虚构酒店报表", key="金额格式", value="两位小数", confirmation_quote="测试授权：记住以后两位小数")

    def experience(self):
        return dict(kind="experience", title="虚构房态核对", scope="虚构酒店", tags=["客房"], problem="房态冲突", steps=["对齐导出时间", "现场复核"], result="确认清扫待查", verification="虚构测试核对", limitations="不能代替查房", success_quote="测试反馈：解决了", confirmation_quote="测试授权：保存这次经验")

    def test_read_does_not_create(self):
        self.assertEqual(self.store.summaries(), [])
        self.assertFalse(self.directory.exists())

    def test_put_requires_confirmation(self):
        with self.assertRaises(ValueError): self.store.put(self.preference())
        self.assertFalse(self.directory.exists())

    def test_fresh_instance_reads_saved_record(self):
        row = self.store.put(self.preference(), True)
        self.assertEqual(mod.MemoryStore(self.directory).get(row["id"])["value"], "两位小数")

    def test_experience_requires_success_and_save(self):
        for field in ["success_quote", "confirmation_quote", "verification", "limitations"]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                data = self.experience(); data[field] = ""; self.store.put(data, True)

    def test_summary_and_search(self):
        row = self.store.put(self.experience(), True)
        self.assertEqual(self.store.summaries("experience", "客房")[0]["id"], row["id"])
        self.assertNotIn("steps", self.store.summaries()[0])
        self.assertEqual(self.store.summaries(query="无匹配"), [])

    def test_preference_conflict_and_replacement(self):
        row = self.store.put(self.preference(), True)
        new = self.preference(); new["value"] = "整数"; new["confirmation_quote"] = "测试授权：改为整数"
        with self.assertRaises(ValueError): self.store.put(new, True)
        saved = self.store.put(new, True, row["id"])
        self.assertEqual(saved["id"], row["id"])
        self.assertEqual(len(self.store.summaries()), 1)
        self.assertEqual(self.store.get(row["id"])["value"], "整数")

    def test_delete_requires_confirmation_and_removes(self):
        row = self.store.put(self.experience(), True)
        with self.assertRaises(ValueError): self.store.delete(row["id"])
        self.store.delete(row["id"], True)
        with self.assertRaises(ValueError): self.store.get(row["id"])
        self.assertNotIn(row["id"], self.store.path.read_text(encoding="utf-8"))

    def test_init_preserves_existing(self):
        row = self.store.put(self.preference(), True)
        before = self.store.path.read_bytes(); self.store.init()
        self.assertEqual(before, self.store.path.read_bytes())

    def test_corrupt_store_not_overwritten(self):
        self.directory.mkdir(); self.store.path.write_text("{broken", encoding="utf-8")
        before = self.store.path.read_bytes()
        with self.assertRaises(ValueError): self.store.put(self.preference(), True)
        self.assertEqual(before, self.store.path.read_bytes())

    def test_lock_prevents_mutation(self):
        self.store.init(); before = self.store.path.read_bytes()
        (self.directory / ".write.lock").write_text("busy")
        with self.assertRaises(FileExistsError): self.store.put(self.preference(), True)
        self.assertEqual(before, self.store.path.read_bytes())

    def test_unknown_version_not_reset(self):
        self.directory.mkdir(); self.store.path.write_text(json.dumps({"version": 2, "records": []}))
        with self.assertRaises(ValueError): self.store.init()

    def test_store_is_separate_from_skill(self):
        self.store.put(self.preference(), True)
        self.assertNotIn("scripts", self.store.path.parts)
        self.assertEqual(self.store.path.name, "store.json")

if __name__ == "__main__": unittest.main()
