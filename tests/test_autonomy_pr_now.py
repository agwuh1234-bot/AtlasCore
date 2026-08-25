import unittest
from pathlib import Path


class PRNowTests(unittest.TestCase):
    def test_marker_is_yes(self):
        self.assertEqual(Path("AUTONOMY_PR_NOW").read_text().strip(), "YES")


if __name__ == "__main__":
    unittest.main()
