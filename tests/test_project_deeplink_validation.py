import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProjectDeepLinkValidationTests(unittest.TestCase):
    def test_base_project_scope_does_not_trust_url_project_before_validation(self):
        source = (ROOT / 'web' / 'projects.js').read_text(encoding='utf-8')
        self.assertNotIn('deepLinkedProject', source)
        self.assertNotIn("new URLSearchParams(window.location.search).get('project')", source)
        self.assertIn("rawGet.call(localStorage, ACTIVE_PROJECT) || DEFAULT_PROJECT", source)

    def test_live_switcher_validates_shared_target_against_real_projects(self):
        source = (ROOT / 'web' / 'project-switcher-live.js').read_text(encoding='utf-8')
        self.assertIn("PROJECT_PARAM='project'", source)
        self.assertIn("const data=await json('/app-projects')", source)
        self.assertIn("list.find(p=>idOf(p)===target)", source)
        self.assertIn("if(!match)", source)
        self.assertIn("if(e?.status===401)return false", source)

    def test_manual_project_switch_clears_stale_share_parameter(self):
        source = (ROOT / 'web' / 'projects.js').read_text(encoding='utf-8')
        self.assertIn("url.searchParams.delete('project')", source)
        self.assertIn("window.history.replaceState", source)


if __name__ == '__main__':
    unittest.main()
