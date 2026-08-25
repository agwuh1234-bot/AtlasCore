import unittest
from pathlib import Path


class PRTriggerTests(unittest.TestCase):
    def test_trigger_marker(self):
        self.assertEqual(Path("AUTONOMY_PR_TRIGGER").read_text().strip(), "PR_SHOULD_BE_OPENED_FROM_THIS_BRANCH")


if __name__ == "__main__":
    unittest.main()
