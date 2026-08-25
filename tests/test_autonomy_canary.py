import json
import unittest
from pathlib import Path


class CanaryTests(unittest.TestCase):
    def test_canary_is_public_read_only_and_does_not_save_session(self):
        data = json.loads(Path("AUTONOMY_CANARY.json").read_text(encoding="utf-8"))
        browser = data["steps"][0]
        self.assertEqual(browser["worker"], "browser")
        self.assertEqual(browser["payload"]["start_url"], "https://example.com")
        self.assertEqual(browser["payload"]["actions"], [])
        self.assertFalse(browser["payload"]["save_session"])
        self.assertEqual(data["steps"][1]["worker"], "approval")


if __name__ == "__main__":
    unittest.main()
