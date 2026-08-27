import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ControlIconTests(unittest.TestCase):
    def test_control_icon_assets_are_loaded_after_reference_shell(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('/app/control-icons.css', html)
        self.assertIn('/app/control-icons.js', html)
        self.assertLess(html.index('/app/reference-v2.js'), html.index('/app/control-icons.js'))
        self.assertLess(html.index('/app/control-icons.js'), html.index('/app/nav-state.js'))

    def test_composer_controls_keep_existing_ids_and_gain_svg_icons(self):
        source = (ROOT / "web" / "control-icons.js").read_text(encoding="utf-8")
        for control_id in ('attachBtn', 'voiceBtn', 'writeModeBtn', 'claudeReviewBtn', 'stopBtn', 'sendBtn'):
            self.assertIn(f"getElementById('{control_id}')", source)
        for icon in ('plus', 'mic', 'pen', 'spark', 'stop', 'send'):
            self.assertIn(f"'{icon}'", source)
        self.assertIn('data-atlas-control-icon', source)
        self.assertIn("replaceChildren(svg(name))", source)

    def test_dashboard_header_controls_use_same_icon_language(self):
        source = (ROOT / "web" / "control-icons.js").read_text(encoding="utf-8")
        self.assertIn("'share'", source)
        self.assertIn("'panel'", source)
        self.assertIn("'more'", source)
        self.assertIn(".atlas-dash-head", source)
        self.assertIn("atlasRightToggle", source)

    def test_active_modes_have_visible_icon_state(self):
        css = (ROOT / "web" / "control-icons.css").read_text(encoding="utf-8")
        self.assertIn('#writeModeBtn.active', css)
        self.assertIn('#claudeReviewBtn.active', css)
        self.assertIn('#voiceBtn.active', css)
        self.assertIn('#sendBtn:not(:disabled):active', css)


if __name__ == '__main__':
    unittest.main()
