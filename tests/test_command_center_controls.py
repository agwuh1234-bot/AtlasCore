import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CommandCenterControlsTests(unittest.TestCase):
    def test_search_and_workspace_assets_are_loaded_before_legacy_actions(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('/app/project-search.css', html)
        self.assertIn('/app/project-search.js', html)
        self.assertIn('/app/workspace-control.css', html)
        self.assertIn('/app/workspace-control.js', html)
        self.assertLess(html.index('/app/project-search.js'), html.index('/app/ui-actions.js'))
        self.assertLess(html.index('/app/workspace-control.js'), html.index('/app/ui-actions.js'))

    def test_project_search_uses_real_workspace_sources(self):
        source = (ROOT / "web" / "project-search.js").read_text(encoding="utf-8")
        self.assertIn("atlas_chat_threads", source)
        self.assertIn("atlas_chat_history", source)
        self.assertIn("/app-files?project_id=", source)
        self.assertIn("atlas_active_project_id", source)
        self.assertIn("requestSubmit", source)
        self.assertIn("metaKey", source)
        self.assertIn("ctrlKey", source)

    def test_pro_panel_uses_live_project_and_budget_data(self):
        source = (ROOT / "web" / "workspace-control.js").read_text(encoding="utf-8")
        self.assertIn("/app-budget", source)
        self.assertIn("/app-projects/", source)
        self.assertIn("/app-integrations/status", source)
        self.assertIn(".ref-pro-card button", source)
        self.assertIn("AtlasIntegrations", source)

    def test_quick_commands_execute_instead_of_being_decorative(self):
        source = (ROOT / "web" / "workspace-control.js").read_text(encoding="utf-8")
        for label in ("Сводка проекта", "Улучшить текст", "Создать план", "Найти решения"):
            self.assertIn(label, source)
        self.assertIn(".dash-check", source)
        self.assertIn(".dash-link", source)
        self.assertIn("смотреть план", source.lower())
        self.assertIn("Покажи актуальный план текущего проекта", source)
        self.assertIn("requestSubmit", source)


if __name__ == "__main__":
    unittest.main()
