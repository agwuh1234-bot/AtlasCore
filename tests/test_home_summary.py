import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class HomeSummaryTests(unittest.TestCase):
    def test_home_summary_assets_are_loaded_after_live_dashboard(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('/app/home-summary.css', html)
        self.assertIn('/app/home-summary.js', html)
        self.assertLess(html.index('/app/dashboard-live.js'), html.index('/app/home-summary.js'))

    def test_empty_chat_becomes_live_project_summary(self):
        source = (ROOT / "web" / "home-summary.js").read_text(encoding="utf-8")
        self.assertIn("$('.empty',list)", source)
        self.assertIn('/history', source)
        self.assertIn('/app-files?project_id=', source)
        self.assertIn('/app-schedules?project_id=', source)
        self.assertIn('/app-integrations/status', source)
        self.assertIn('atlas-home-summary', source)

    def test_home_summary_stays_available_with_chat_history(self):
        source = (ROOT / "web" / "home-summary.js").read_text(encoding="utf-8")
        css = (ROOT / "web" / "home-summary.css").read_text(encoding="utf-8")
        self.assertIn('list.prepend(card)', source)
        self.assertIn(".row.user,.row.assistant", source)
        self.assertIn('atlas-home-summary.compact', css)
        self.assertIn('body.atlas-chat-focus .atlas-home-summary', css)

    def test_home_actions_route_to_real_controls(self):
        source = (ROOT / "web" / "home-summary.js").read_text(encoding="utf-8")
        self.assertIn("requestSubmit", source)
        self.assertIn("window.AtlasIntegrations?.open", source)
        self.assertIn("tab('files')", source)
        self.assertIn("tab('auto')", source)
        self.assertIn('Продолжить работу', source)
        self.assertIn('Сводка проекта', source)

    def test_home_summary_is_responsive(self):
        css = (ROOT / "web" / "home-summary.css").read_text(encoding="utf-8")
        self.assertIn('grid-template-columns:repeat(4,minmax(0,1fr))', css)
        self.assertIn('@media(max-width:700px)', css)
        self.assertIn('@media(max-width:430px)', css)


if __name__ == '__main__':
    unittest.main()
