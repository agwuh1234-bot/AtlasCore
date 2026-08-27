import os
import unittest
from unittest.mock import AsyncMock, Mock, patch

from atlas_autonomy_runtime import build_autonomy_runtime


class RuntimeBuildTests(unittest.TestCase):
    @patch.dict(os.environ, {"ATLAS_AUTONOMY_CONCURRENCY": "7"}, clear=False)
    @patch("atlas_autonomy_runtime.AtlasAutonomyStore")
    @patch("atlas_autonomy_runtime.BrowserJobManager")
    @patch("atlas_autonomy_runtime.BrowserExecutor")
    def test_build_registers_runtime_without_session_key(self, executor_cls, manager_cls, store_cls):
        os.environ.pop("ATLAS_BROWSER_SESSION_KEY", None)
        manager = Mock()
        manager.executor = Mock(session_store=None)
        manager_cls.return_value = manager
        runtime = build_autonomy_runtime(Mock())
        self.assertEqual(runtime.engine.concurrency, 7)
        executor_cls.assert_called_once_with(session_store=None)
        self.assertIn("browser", runtime.engine.workers)
        self.assertIn("verify", runtime.engine.workers)
        self.assertIn("approval", runtime.engine.workers)

    @patch.dict(os.environ, {"ATLAS_AUTONOMY_CONCURRENCY": "not-a-number"}, clear=False)
    @patch("atlas_autonomy_runtime.AtlasAutonomyStore")
    @patch("atlas_autonomy_runtime.BrowserJobManager")
    @patch("atlas_autonomy_runtime.BrowserExecutor")
    def test_invalid_concurrency_falls_back_to_five(self, executor_cls, manager_cls, store_cls):
        manager = Mock()
        manager.executor = Mock(session_store=None)
        manager_cls.return_value = manager
        runtime = build_autonomy_runtime(Mock())
        self.assertEqual(runtime.engine.concurrency, 5)


class RuntimeLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_is_idempotent_and_resumes(self):
        runtime = Mock()
        runtime.started = False
        runtime.resumed_tasks = 0
        runtime.browser_jobs = Mock()
        runtime.engine = Mock()
        runtime.engine.resume_all.return_value = 3
        from atlas_autonomy_runtime import AutonomyRuntime
        real = AutonomyRuntime(runtime.engine, runtime.browser_jobs)
        self.assertEqual(await real.start(), 3)
        self.assertEqual(await real.start(), 3)
        runtime.browser_jobs.start.assert_called_once()
        runtime.engine.resume_all.assert_called_once()
        self.assertTrue(real.started)

    async def test_stop_cancels_tasks_and_browser_worker(self):
        from atlas_autonomy_runtime import AutonomyRuntime
        engine = Mock()
        engine._running = {}
        engine.tasks = {}
        browser = Mock()
        browser.stop = AsyncMock()
        real = AutonomyRuntime(engine, browser, started=True)
        await real.stop()
        browser.stop.assert_awaited_once()
        self.assertFalse(real.started)


if __name__ == "__main__":
    unittest.main()
