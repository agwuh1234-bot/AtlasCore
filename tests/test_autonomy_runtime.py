import os
import unittest
from unittest.mock import Mock, patch

from atlas_autonomy_runtime import build_autonomy_runtime, start_autonomy_runtime


class RuntimeTests(unittest.TestCase):
    @patch.dict(os.environ, {"ATLAS_AUTONOMY_CONCURRENCY": "7"}, clear=False)
    @patch("atlas_autonomy_runtime.AtlasAutonomyStore")
    @patch("atlas_autonomy_runtime.BrowserJobManager")
    @patch("atlas_autonomy_runtime.BrowserExecutor")
    def test_build_registers_runtime_without_session_key(self, executor_cls, manager_cls, store_cls):
        os.environ.pop("ATLAS_BROWSER_SESSION_KEY", None)
        manager = Mock()
        manager_cls.return_value = manager
        runtime = build_autonomy_runtime(Mock())
        self.assertEqual(runtime.engine.concurrency, 7)
        executor_cls.assert_called_once_with(session_store=None)
        self.assertIn("browser", runtime.engine.workers)
        self.assertIn("verify", runtime.engine.workers)
        self.assertIn("approval", runtime.engine.workers)

    def test_start_resumes_and_starts_browser(self):
        runtime = Mock()
        runtime.engine.resume_all.return_value = 3
        count = start_autonomy_runtime(runtime)
        runtime.browser_jobs.start.assert_called_once()
        runtime.engine.resume_all.assert_called_once()
        self.assertEqual(count, 3)
        self.assertEqual(runtime.resumed_tasks, 3)


if __name__ == "__main__":
    unittest.main()
