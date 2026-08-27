import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AtlasDialogAdoptionTests(unittest.TestCase):
    def test_projects_use_atlas_prompt_for_create_and_memory(self):
        source = (ROOT / 'web' / 'projects.js').read_text(encoding='utf-8')
        self.assertIn('window.AtlasDialog?.prompt', source)
        self.assertIn("title: 'Новый проект'", source)
        self.assertIn("title: 'Запомнить для проекта'", source)
        self.assertIn("maxLength: 80", source)
        self.assertIn("maxLength: 200", source)

    def test_thread_actions_use_atlas_dialogs(self):
        source = (ROOT / 'web' / 'sidebar.js').read_text(encoding='utf-8')
        self.assertIn('window.AtlasDialog?.prompt', source)
        self.assertIn('window.AtlasDialog?.confirm', source)
        self.assertIn("title:'Переименовать чат'", source)
        self.assertIn("title:'Удалить чат?'", source)
        self.assertIn('danger:true', source)

    def test_dialog_center_is_loaded_before_projects_and_sidebar(self):
        html = (ROOT / 'web' / 'index.html').read_text(encoding='utf-8')
        self.assertLess(html.index('/app/dialog-center.js'), html.index('/app/projects.js'))
        self.assertLess(html.index('/app/dialog-center.js'), html.index('/app/sidebar.js'))


if __name__ == '__main__':
    unittest.main()
