import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SettingsCenterTests(unittest.TestCase):
    def test_settings_assets_are_loaded_before_legacy_actions(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('/app/settings-center.css', html)
        self.assertIn('/app/settings-center.js', html)
        self.assertLess(html.index('/app/settings-center.js'), html.index('/app/ui-actions.js'))

    def test_settings_routes_to_real_existing_controls(self):
        source = (ROOT / "web" / "settings-center.js").read_text(encoding="utf-8")
        for selector in (
            "#settingsBtn",
            ".ref-profile",
            "#voiceOutputBtn",
            "#claudeReviewBtn",
            "#writeModeBtn",
            "#notificationBtn",
            "#installBtn",
            "#exportChatBtn",
            "#clearChatBtn",
            "#logoutBtn",
        ):
            self.assertIn(selector, source)
        self.assertIn("AtlasIntegrations", source)

    def test_destructive_session_actions_require_confirmation(self):
        source = (ROOT / "web" / "settings-center.js").read_text(encoding="utf-8")
        self.assertIn("confirm('Очистить историю текущего чата?')", source)
        self.assertIn("confirm('Выйти из Atlas?')", source)

    def test_settings_dialog_moves_and_restores_focus(self):
        source = (ROOT / "web" / "settings-center.js").read_text(encoding="utf-8")
        self.assertIn("previousFocus=document.activeElement", source)
        self.assertIn("target?.focus?.()", source)
        self.assertIn("$('.atlas-settings-close',overlay)?.focus()", source)


if __name__ == "__main__":
    unittest.main()
