import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SidebarThreadManagementTests(unittest.TestCase):
    def test_thread_state_is_project_scoped(self):
        source = (ROOT / "web" / "projects.js").read_text(encoding="utf-8")
        self.assertIn("'atlas_chat_threads'", source)
        self.assertIn("'atlas_active_thread_id'", source)
        self.assertIn("SCOPED_KEYS", source)

    def test_thread_snapshot_preserves_backend_context_and_custom_title(self):
        source = (ROOT / "web" / "sidebar.js").read_text(encoding="utf-8")
        self.assertIn("response_id:localStorage.getItem(RID)", source)
        self.assertIn("active_job_id:localStorage.getItem(JID)", source)
        self.assertIn("old?.custom_title?old.title:threadTitle(hist)", source)
        self.assertIn("setStored(RID,t.response_id", source)
        self.assertIn("setStored(JID,t.active_job_id", source)

    def test_recent_chat_menu_has_real_actions(self):
        source = (ROOT / "web" / "sidebar.js").read_text(encoding="utf-8")
        self.assertIn("function renameThread", source)
        self.assertIn("function deleteThread", source)
        self.assertIn("function pinThread", source)
        self.assertIn("thread-menu-action", source)
        self.assertIn("Переименовать", source)
        self.assertIn("Удалить", source)

    def test_deleting_active_chat_clears_context_before_restore(self):
        source = (ROOT / "web" / "sidebar.js").read_text(encoding="utf-8")
        self.assertIn("localStorage.setItem(H,'[]')", source)
        self.assertIn("setStored(RID,'')", source)
        self.assertIn("setStored(JID,'')", source)
        self.assertIn("restoreThread(next)", source)

    def test_sidebar_styles_context_menu(self):
        css = (ROOT / "web" / "sidebar.css").read_text(encoding="utf-8")
        self.assertIn(".thread-menu", css)
        self.assertIn(".thread-menu-action", css)
        self.assertIn(".thread-more", css)


if __name__ == "__main__":
    unittest.main()
