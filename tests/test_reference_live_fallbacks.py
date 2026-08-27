import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReferenceLiveFallbackTests(unittest.TestCase):
    def test_reference_sidebar_avoids_fake_profile_and_marketing_copy(self):
        source = (ROOT / 'web' / 'reference-v2.js').read_text(encoding='utf-8')
        self.assertIn('Загружаю бюджет и состояние интеграций', source)
        self.assertIn('Текущий проект', source)
        self.assertIn('Atlas Workspace', source)
        self.assertNotIn('Больше возможностей, проекты и премиум', source)
        self.assertNotIn('alex@', source.lower())
        self.assertNotIn('алексей', source.lower())

    def test_reference_fallbacks_delegate_to_live_centers(self):
        source = (ROOT / 'web' / 'reference-v2.js').read_text(encoding='utf-8')
        self.assertIn('AtlasWorkspaceControl', source)
        self.assertIn('AtlasToolsCenter', source)
        self.assertIn('AtlasTemplates', source)
        self.assertIn('AtlasIntegrations', source)
        self.assertIn('AtlasRightPanel', source)
        self.assertIn('AtlasNavState', source)


if __name__ == '__main__':
    unittest.main()
