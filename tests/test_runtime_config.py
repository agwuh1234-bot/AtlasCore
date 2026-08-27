import os
import unittest
from unittest.mock import patch

from atlas_runtime_config import load_runtime_config


class RuntimeConfigTests(unittest.TestCase):
    @patch.dict(os.environ, {
        "GITHUB_REPO": "owner/repo",
        "GITHUB_BRANCH": "dev",
        "CLAUDE_MODEL": "claude-test",
        "ATLAS_MAX_FILE_LINES": "5000",
        "ATLAS_MAX_FILE_CONTENT_CHARS": "20000",
        "ALLOWED_USER_IDS": "1, 2,2",
    }, clear=True)
    def test_loads_and_bounds_config(self):
        cfg = load_runtime_config()
        self.assertEqual(cfg.github_repo, "owner/repo")
        self.assertEqual(cfg.github_branch, "dev")
        self.assertEqual(cfg.claude_model, "claude-test")
        self.assertEqual(cfg.max_file_lines, 1000)
        self.assertEqual(cfg.max_file_content_chars, 20000)
        self.assertEqual(cfg.allowed_user_ids, frozenset({1, 2}))
        self.assertTrue(cfg.telegram_private)

    @patch.dict(os.environ, {"GITHUB_REPO": "broken", "ALLOWED_USER_IDS": "1"}, clear=True)
    def test_rejects_invalid_repo(self):
        with self.assertRaises(RuntimeError):
            load_runtime_config()

    @patch.dict(os.environ, {"ALLOWED_USER_IDS": "abc"}, clear=True)
    def test_rejects_invalid_user_ids(self):
        with self.assertRaises(RuntimeError):
            load_runtime_config()


if __name__ == "__main__":
    unittest.main()
