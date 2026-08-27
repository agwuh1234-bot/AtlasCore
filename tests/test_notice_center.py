import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class NoticeCenterTests(unittest.TestCase):
    def test_notice_assets_load_before_project_controls(self):
        html = (ROOT / 'web' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('/app/notice-center.css', html)
        self.assertIn('/app/notice-center.js', html)
        self.assertLess(html.index('/app/notice-center.js'), html.index('/app/projects.js'))
        self.assertLess(html.index('/app/notice-center.css'), html.index('/app/device-polish.css'))

    def test_notice_center_is_non_blocking_and_accessible(self):
        source = (ROOT / 'web' / 'notice-center.js').read_text(encoding='utf-8')
        self.assertIn("aria-live", source)
        self.assertIn("role',type==='error'?'alert':'status'", source)
        self.assertIn('window.AtlasNotice={show,success,error,warn}', source)
        self.assertNotIn('window.alert', source)
        self.assertNotIn('window.confirm', source)

    def test_projects_prefer_atlas_notices(self):
        source = (ROOT / 'web' / 'projects.js').read_text(encoding='utf-8')
        self.assertIn('window.AtlasNotice?.error', source)
        self.assertIn('window.AtlasNotice?.success', source)
        self.assertIn("showSuccess('Сохранено в памяти проекта.')", source)

    def test_notice_styles_are_mobile_safe(self):
        css = (ROOT / 'web' / 'notice-center.css').read_text(encoding='utf-8')
        self.assertIn('env(safe-area-inset-bottom)', css)
        self.assertIn('@media(max-width:600px)', css)
        self.assertIn('.keyboard-open .atlas-notice-host', css)


if __name__ == '__main__':
    unittest.main()
