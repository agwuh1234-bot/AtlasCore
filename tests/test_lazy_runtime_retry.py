from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "web" / "lazy-runtime.js"


class LazyRuntimeRetryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = RUNTIME.read_text(encoding="utf-8")

    def test_failed_lazy_script_is_removed_from_cache(self):
        self.assertIn("loaded.delete(src)", self.source)

    def test_failed_script_element_is_removed_before_retry(self):
        self.assertIn("s?.remove()", self.source)

    def test_lazy_group_pending_entry_is_always_cleared(self):
        self.assertIn("finally{pending.delete(name)}", self.source)


if __name__ == "__main__":
    unittest.main()
