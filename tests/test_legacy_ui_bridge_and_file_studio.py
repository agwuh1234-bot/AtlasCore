import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LegacyUiBridgeAndFileStudioTests(unittest.TestCase):
    def test_legacy_alert_bridge_loads_before_shell(self):
        html = (ROOT / 'web' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('/app/legacy-alert-bridge.js', html)
        self.assertLess(html.index('/app/legacy-alert-bridge.js'), html.index('/app/shell.js'))
        source = (ROOT / 'web' / 'legacy-alert-bridge.js').read_text(encoding='utf-8')
        self.assertIn('window.alert=function atlasAlert', source)
        self.assertIn('window.AtlasNotice?.show', source)
        self.assertIn('nativeAlert', source)

    def test_legacy_automation_button_opens_real_studio(self):
        source = (ROOT / 'web' / 'schedules.js').read_text(encoding='utf-8')
        self.assertIn('AtlasAutomationStudio', source)
        self.assertIn("AtlasStudios.open('automation')", source)
        self.assertNotIn('Раздел расписаний готовится', source)

    def test_file_studio_uses_atlas_dialog_and_notices(self):
        source = (ROOT / 'web' / 'file-studio-live.js').read_text(encoding='utf-8')
        self.assertIn('window.AtlasDialog?.confirm', source)
        self.assertIn('window.AtlasNotice?.error', source)
        self.assertIn('window.AtlasNotice?.success', source)
        self.assertNotIn('alert(e.message', source)
        self.assertIn("role','dialog'", source)
        self.assertIn("aria-modal", source)
        self.assertIn("e.key==='Tab'", source)


if __name__ == '__main__':
    unittest.main()
