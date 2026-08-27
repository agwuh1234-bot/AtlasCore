import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DashboardLiveBootstrapTests(unittest.TestCase):
    def test_dashboard_starts_with_live_placeholders_not_fake_progress(self):
        source = (ROOT / "web" / "dashboard.js").read_text(encoding="utf-8")
        self.assertNotIn("function calcProgress", source)
        self.assertNotIn("Оформление интерфейса Atlas", source)
        self.assertNotIn("Shopify Actions", source)
        self.assertIn("Загружаю реальные задачи проекта", source)
        self.assertIn("Загружаю файлы проекта", source)
        self.assertIn("ring.style.setProperty('--p','0')", source)

    def test_dashboard_cards_delegate_to_real_live_centers(self):
        source = (ROOT / "web" / "dashboard.js").read_text(encoding="utf-8")
        for name in (
            "AtlasCodeStudio",
            "AtlasVideoStudio",
            "AtlasShopifyStudio",
            "AtlasProjectSwitcher",
            "AtlasToolsCenter",
            "AtlasShare",
            "AtlasRightPanel",
            "AtlasProjectSearch",
            "AtlasUIActions",
        ):
            self.assertIn(name, source)

    def test_header_search_and_more_button_call_live_controllers_directly(self):
        source = (ROOT / "web" / "dashboard.js").read_text(encoding="utf-8")
        self.assertIn("window.AtlasProjectSearch.open", source)
        self.assertIn("window.AtlasUIActions?.openQuickMenu?.()", source)
        self.assertIn("window.AtlasShare?.open?.()", source)
        self.assertIn("window.AtlasRightPanel?.toggle?.()", source)

    def test_quick_commands_distinguish_immediate_and_input_required_actions(self):
        source = (ROOT / "web" / "workspace-control.js").read_text(encoding="utf-8")
        self.assertIn("function runQuickCommand", source)
        self.assertIn("if(t==='Сводка проекта')return send", source)
        self.assertIn("if(t==='Создать план')return send", source)
        self.assertIn("if(t==='Улучшить текст')return prepare", source)
        self.assertIn("if(t==='Найти решения')return prepare", source)
        self.assertIn("requestSubmit", source)


if __name__ == "__main__":
    unittest.main()
