import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ClaudeReviewRuntimeTests(unittest.TestCase):
    def test_review_switch_is_deterministic_and_visible(self):
        source = (ROOT / 'atlas_entry.py').read_text(encoding='utf-8')
        self.assertIn('_original_run_atlas = atlas.run_atlas', source)
        self.assertIn('claude_review=False', source)
        self.assertIn('raw_review = await atlas.claude_ask(review_prompt)', source)
        self.assertIn('### Проверка Claude', source)
        self.assertIn('atlas.run_atlas = run_atlas', source)

    def test_failed_review_is_visible_instead_of_silent(self):
        source = (ROOT / 'atlas_entry.py').read_text(encoding='utf-8')
        self.assertIn('Claude не подключён к Atlas.', source)
        self.assertIn('Дневной лимит Claude исчерпан.', source)
        self.assertIn('Claude API вернул ошибку', source)
        self.assertIn('CLAUDE_REVIEW ok=false', source)

    def test_startup_probe_checks_key_and_selected_model_without_generation(self):
        source = (ROOT / 'atlas_entry.py').read_text(encoding='utf-8')
        self.assertIn('CLAUDE_STARTUP_PROBE', source)
        self.assertIn('https://api.anthropic.com/v1/models', source)
        self.assertIn('atlas.CLAUDE_MODEL in model_ids', source)
        self.assertNotIn('ATLAS_CLAUDE_OK', source)


if __name__ == '__main__':
    unittest.main()
