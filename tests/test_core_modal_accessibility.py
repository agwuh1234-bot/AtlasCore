import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CoreModalAccessibilityTests(unittest.TestCase):
    def test_dedicated_login_exposes_label_and_live_error(self):
        html = (ROOT / "web" / "login.html").read_text(encoding="utf-8")
        self.assertIn('<main class="card" id="card">', html)
        self.assertIn('<label for="key">Ключ приложения</label>', html)
        self.assertIn('id="key"', html)
        self.assertIn('type="password"', html)
        self.assertIn('id="error"', html)
        self.assertIn('role="alert"', html)
        self.assertIn('aria-live="polite"', html)

    def test_stable_root_has_no_active_legacy_startup_modals(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        active, marker, legacy = html.partition('<template id="atlas-legacy-regression-assets">')
        self.assertTrue(marker)
        for modal_id in ("loginCard", "installCard", "settingsCard"):
            self.assertNotIn(f'id="{modal_id}"', active)
            self.assertIn(f'id="{modal_id}"', legacy)
        self.assertIn('id="messageInput"', active)
        self.assertIn('id="claudeBtn"', active)


if __name__ == "__main__":
    unittest.main()
