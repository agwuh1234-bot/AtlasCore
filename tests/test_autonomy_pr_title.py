import unittest
from pathlib import Path


class PRTitleTests(unittest.TestCase):
    def test_title_is_specific(self):
        title = Path("AUTONOMY_PR_TITLE.txt").read_text().strip()
        self.assertIn("autonomous task engine", title)
        self.assertIn("lifecycle", title)


if __name__ == "__main__":
    unittest.main()
