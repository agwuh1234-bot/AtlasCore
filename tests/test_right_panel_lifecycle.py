import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RightPanelLifecycleTests(unittest.TestCase):
    def test_tablet_drawer_is_modal_and_closes_competing_surfaces(self):
        source = (ROOT / "web" / "right-panel-control.js").read_text(encoding="utf-8")
        self.assertIn("p.setAttribute('role','dialog')", source)
        self.assertIn("p.setAttribute('aria-modal','true')", source)
        self.assertIn("classList.remove('atlas-sidebar-open')", source)
        for name in (
            "AtlasShare",
            "AtlasUIActions",
            "AtlasSettingsCenter",
            "AtlasToolsCenter",
            "AtlasTemplates",
            "AtlasIntegrations",
            "AtlasProjectSwitcher",
            "AtlasProjectSearch",
        ):
            self.assertIn(name, source)

    def test_tablet_drawer_traps_focus_and_restores_previous_focus(self):
        source = (ROOT / "web" / "right-panel-control.js").read_text(encoding="utf-8")
        self.assertIn("function trap(e)", source)
        self.assertIn("e.key!=='Tab'", source)
        self.assertIn("e.key==='Escape'", source)
        self.assertIn("previousFocus=document.activeElement", source)
        self.assertIn("f?.focus?.({preventScroll:true})", source)

    def test_tablet_drawer_locks_background_and_respects_safe_areas(self):
        css = (ROOT / "web" / "right-panel-control.css").read_text(encoding="utf-8")
        self.assertIn("body.atlas-right-open{overflow:hidden!important", css)
        self.assertIn("@media(min-width:601px) and (max-width:1100px)", css)
        self.assertIn("env(safe-area-inset-top)", css)
        self.assertIn("env(safe-area-inset-bottom)", css)
        self.assertIn("touch-action:pan-y", css)


if __name__ == "__main__":
    unittest.main()
