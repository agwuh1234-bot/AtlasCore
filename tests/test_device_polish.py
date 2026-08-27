import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DevicePolishTests(unittest.TestCase):
    def test_device_polish_is_loaded_last_in_styles(self):
        html = (ROOT / 'web' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('/app/device-polish.css', html)
        self.assertLess(html.index('/app/right-panel-control.css'), html.index('/app/device-polish.css'))

    def test_mobile_polish_uses_safe_areas_and_real_header_panel_control(self):
        css = (ROOT / 'web' / 'device-polish.css').read_text(encoding='utf-8')
        self.assertIn('env(safe-area-inset-bottom)', css)
        self.assertIn('env(safe-area-inset-top)', css)
        self.assertIn('.ref-right-toggle{display:none!important}', css)
        self.assertIn('@media(min-width:641px) and (max-width:1100px)', css)
        self.assertIn('@media(max-width:640px)', css)
        self.assertIn('font-size:16px!important', css)

    def test_mobile_profile_closes_sidebar_before_workspace(self):
        source = (ROOT / 'web' / 'profile-state.js').read_text(encoding='utf-8')
        self.assertIn('function closeMobileNavigation()', source)
        self.assertIn("classList.remove('atlas-sidebar-open')", source)
        self.assertIn("window.AtlasWorkspaceControl?.open", source)

    def test_quick_menu_uses_svg_and_live_centers(self):
        source = (ROOT / 'web' / 'ui-actions.js').read_text(encoding='utf-8')
        self.assertIn("createElementNS(NS,'svg')", source)
        self.assertIn('window.AtlasShare?.open', source)
        self.assertIn('window.AtlasRightPanel?.open', source)
        self.assertIn("window.AtlasProjectSwitcher?.open", source)
        self.assertIn("window.AtlasToolsCenter?.open", source)
        self.assertIn("window.AtlasTemplates?.open", source)
        self.assertIn("window.AtlasIntegrations?.open", source)


if __name__ == '__main__':
    unittest.main()
