import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class UiActionDelegationTests(unittest.TestCase):
    def test_legacy_ui_actions_delegate_to_live_centers(self):
        source = (ROOT / "web" / "ui-actions.js").read_text(encoding="utf-8")
        self.assertIn("window.AtlasTemplates?.open", source)
        self.assertIn("window.AtlasIntegrations?.open", source)
        self.assertIn("window.AtlasToolsCenter?.open", source)
        self.assertIn("window.AtlasProjectSwitcher?.open", source)

    def test_old_prompt_only_studio_entries_are_gone(self):
        source = (ROOT / "web" / "ui-actions.js").read_text(encoding="utf-8")
        self.assertNotIn("Создай UGC-рекламу для товара", source)
        self.assertNotIn("Работаем в Video Studio. Нужно создать", source)
        self.assertNotIn("Проверь GitHub проект AtlasCore и покажи доступные действия", source)

    def test_quick_summary_executes_instead_of_only_prefilling(self):
        source = (ROOT / "web" / "ui-actions.js").read_text(encoding="utf-8")
        self.assertIn("function promptText(text,submit=false)", source)
        self.assertIn("form?.requestSubmit", source)
        self.assertIn("function openSummary()", source)
        self.assertIn("следующий шаг.',true)", source)

    def test_new_chat_prefers_thread_aware_control(self):
        source = (ROOT / "web" / "ui-actions.js").read_text(encoding="utf-8")
        self.assertIn("function newChat()", source)
        self.assertIn("const threaded=$('#atlasComposeTop')", source)
        self.assertIn("threaded.click()", source)
        self.assertIn("const legacy=$('#newChatBtn')", source)


if __name__ == '__main__':
    unittest.main()
