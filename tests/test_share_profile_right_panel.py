import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ShareProfileRightPanelTests(unittest.TestCase):
    def test_share_center_uses_real_project_sources_and_safe_deep_link(self):
        source = (ROOT / 'web' / 'share-center.js').read_text(encoding='utf-8')
        self.assertIn("searchParams.set('project',projectId())", source)
        self.assertIn("/history", source)
        self.assertIn("/app-files?project_id=", source)
        self.assertIn("/app-schedules?project_id=", source)
        self.assertIn("/app-integrations/status", source)
        self.assertIn('navigator.share', source)
        self.assertIn('navigator.clipboard.writeText', source)
        self.assertIn("$('#exportChatBtn')?.click()", source)
        self.assertNotIn('password', source.lower())
        self.assertNotIn('token=', source.lower())

    def test_projects_require_validated_share_deep_links(self):
        base = (ROOT / 'web' / 'projects.js').read_text(encoding='utf-8')
        switcher = (ROOT / 'web' / 'project-switcher-live.js').read_text(encoding='utf-8')
        self.assertNotIn('function deepLinkedProject()', base)
        self.assertNotIn("new URLSearchParams(window.location.search).get('project')", base)
        self.assertIn("rawGet.call(localStorage, ACTIVE_PROJECT) || DEFAULT_PROJECT", base)
        self.assertIn("PROJECT_PARAM='project'", switcher)
        self.assertIn("const data=await json('/app-projects')", switcher)
        self.assertIn("list.find(p=>idOf(p)===target)", switcher)
        self.assertIn("if(!match)", switcher)
        self.assertIn("if(e?.status===401)return false", switcher)

    def test_right_panel_unifies_desktop_and_tablet_states(self):
        source = (ROOT / 'web' / 'right-panel-control.js').read_text(encoding='utf-8')
        css = (ROOT / 'web' / 'right-panel-control.css').read_text(encoding='utf-8')
        self.assertIn("classList.add('ref-right-open','dash-right-open','atlas-right-open')", source)
        self.assertIn("aria-expanded", source)
        self.assertIn("aria-controls", source)
        self.assertIn("e.key==='Escape'", source)
        self.assertIn('atlas-right-backdrop', source)
        self.assertIn('env(safe-area-inset-bottom)', css)
        self.assertIn('body.atlas-right-open .atlas-dashboard-right', css)

    def test_profile_card_is_live_workspace_not_fake_identity(self):
        source = (ROOT / 'web' / 'profile-state.js').read_text(encoding='utf-8')
        self.assertIn('/app-budget', source)
        self.assertIn('/app-integrations/status', source)
        self.assertIn('AtlasWorkspaceControl', source)
        self.assertIn('projectName()', source)
        self.assertNotIn('alex@', source.lower())
        self.assertNotIn('алексей', source.lower())

    def test_new_assets_are_loaded_before_legacy_ui_actions(self):
        html = (ROOT / 'web' / 'index.html').read_text(encoding='utf-8')
        for asset in [
            '/app/share-center.css',
            '/app/right-panel-control.css',
            '/app/profile-state.js',
            '/app/share-center.js',
            '/app/right-panel-control.js',
        ]:
            self.assertIn(asset, html)
        self.assertLess(html.index('/app/share-center.js'), html.index('/app/ui-actions.js'))
        self.assertLess(html.index('/app/right-panel-control.js'), html.index('/app/ui-actions.js'))


if __name__ == '__main__':
    unittest.main()
