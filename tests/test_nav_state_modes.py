import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class NavStateModeTests(unittest.TestCase):
    def test_home_and_chat_are_distinct_actions(self):
        source = (ROOT / "web" / "nav-state.js").read_text(encoding="utf-8")
        self.assertIn("function home()", source)
        self.assertIn("function chat()", source)
        self.assertIn("atlas_dashboard_view", source)
        self.assertIn("atlas-chat-focus", source)
        self.assertIn("'Главная':home", source)
        self.assertIn("'Чат':chat", source)

    def test_navigation_routes_to_live_centers(self):
        source = (ROOT / "web" / "nav-state.js").read_text(encoding="utf-8")
        self.assertIn("AtlasToolsCenter", source)
        self.assertIn("AtlasTemplates", source)
        self.assertIn("AtlasIntegrations", source)
        self.assertIn("AtlasSettingsCenter", source)
        self.assertIn("tapTab('projects')", source)
        self.assertIn("tapTab('files')", source)

    def test_centers_are_mutually_exclusive(self):
        source = (ROOT / "web" / "nav-state.js").read_text(encoding="utf-8")
        self.assertIn("AtlasSettingsCenter?.close", source)
        self.assertIn("AtlasToolsCenter?.close", source)
        self.assertIn("AtlasTemplates?.close", source)
        self.assertIn("AtlasIntegrations?.close", source)
        self.assertIn(".atlas-settings-overlay", source)

    def test_mobile_navigation_collapses_sidebar(self):
        source = (ROOT / "web" / "nav-state.js").read_text(encoding="utf-8")
        self.assertIn("function collapseSidebar()", source)
        self.assertIn("innerWidth>=980", source)
        self.assertIn("atlas-sidebar-open", source)
        self.assertIn("atlas_sidebar_open", source)
        for action in ("home", "chat", "projects", "files", "tools", "templates", "integrations", "settings"):
            self.assertIn(f"function {action}(){{collapseSidebar();", source)

    def test_escape_closes_open_mobile_sidebar(self):
        source = (ROOT / "web" / "nav-state.js").read_text(encoding="utf-8")
        self.assertIn("document.addEventListener('keydown'", source)
        self.assertIn("e.key==='Escape'", source)
        self.assertIn("innerWidth<980", source)
        self.assertIn("classList.contains('atlas-sidebar-open')", source)
        self.assertIn("collapseSidebar()", source)

    def test_escape_restores_focus_to_sidebar_toggle(self):
        source = (ROOT / "web" / "nav-state.js").read_text(encoding="utf-8")
        self.assertIn("collapseSidebar();$('#atlasSidebarToggle')?.focus()", source)

    def test_open_mobile_sidebar_moves_focus_into_navigation(self):
        source = (ROOT / "web" / "nav-state.js").read_text(encoding="utf-8")
        self.assertIn("sidebarOpenState!==open", source)
        self.assertIn("document.activeElement===t", source)
        self.assertIn("$('#atlasRefNav .ref-nav-item')?.focus()", source)

    def test_open_mobile_sidebar_traps_tab_focus(self):
        source = (ROOT / "web" / "nav-state.js").read_text(encoding="utf-8")
        self.assertIn("function trapSidebarTab(e)", source)
        self.assertIn("e.key!=='Tab'", source)
        self.assertIn("const side=$('#atlasSidebar')", source)
        self.assertIn("side.contains(active)", source)
        self.assertIn("e.shiftKey", source)
        self.assertIn("first.focus()", source)
        self.assertIn("last.focus()", source)

    def test_sidebar_toggle_accessibility_state_tracks_open_class(self):
        source = (ROOT / "web" / "nav-state.js").read_text(encoding="utf-8")
        self.assertIn("function syncSidebarToggle()", source)
        self.assertIn("setAttribute('aria-expanded',String(open))", source)
        self.assertIn("open?'Скрыть меню':'Открыть меню'", source)
        self.assertIn("function bindSidebarObserver()", source)
        self.assertIn("attributeFilter:['class']", source)

    def test_focus_chat_css_removes_dashboard_noise(self):
        css = (ROOT / "web" / "nav-state.css").read_text(encoding="utf-8")
        self.assertIn("body.atlas-chat-focus .atlas-dashboard-right", css)
        self.assertIn("body.atlas-chat-focus .atlas-tool-strip", css)
        self.assertIn("grid-template-columns:minmax(0,1fr)", css)

    def test_focus_styles_are_loaded(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('/app/nav-state.css', html)
        self.assertIn('/app/nav-state.js', html)


if __name__ == "__main__":
    unittest.main()
