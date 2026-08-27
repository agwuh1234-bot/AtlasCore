import unittest
from pathlib import Path


class PRChecklistTests(unittest.TestCase):
    def test_checklist_requires_second_ci_after_actual_patch(self):
        text = Path("AUTONOMY_PR_CHECKLIST.md").read_text(encoding="utf-8")
        self.assertIn("Full CI green after actual patch", text)
        self.assertTrue(text.rstrip().endswith("Merge only then"))


if __name__ == "__main__":
    unittest.main()
