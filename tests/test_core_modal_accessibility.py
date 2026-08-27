import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CoreModalAccessibilityTests(unittest.TestCase):
    def test_core_modals_expose_dialog_semantics_and_labels(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        expected = {
            "loginCard": "loginTitle",
            "installCard": "installTitle",
            "settingsCard": "settingsTitle",
        }
        for modal_id, title_id in expected.items():
            marker = f'id="{modal_id}"'
            start = html.index(marker)
            end = html.index('</div></div>', start) + len('</div></div>')
            fragment = html[start:end]
            self.assertIn('role="dialog"', fragment)
            self.assertIn('aria-modal="true"', fragment)
            self.assertIn(f'aria-labelledby="{title_id}"', fragment)
            self.assertIn(f'id="{title_id}"', fragment)


if __name__ == "__main__":
    unittest.main()
