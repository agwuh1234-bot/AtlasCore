import unittest
from unittest.mock import Mock

from atlas_autonomy_runtime import AutonomyRuntime


class HealthContractTests(unittest.TestCase):
    def test_health_reports_runtime_state(self):
        engine = Mock()
        engine.concurrency = 5
        engine.tasks = {"a": Mock(status="running"), "b": Mock(status="done")}
        engine.workers = {"browser": Mock(), "verify": Mock(), "approval": Mock()}
        engine.snapshot.side_effect = lambda task_id: {
            "a": {"status": "running"},
            "b": {"status": "done"},
        }[task_id]
        browser_jobs = Mock()
        browser_jobs.executor.session_store = None
        runtime = AutonomyRuntime(engine=engine, browser_jobs=browser_jobs, resumed_tasks=2, started=True)
        health = runtime.health()
        self.assertTrue(health["started"])
        self.assertEqual(health["resumed_tasks"], 2)
        self.assertEqual(health["concurrency"], 5)
        self.assertEqual(health["active_tasks"], 1)
        self.assertEqual(health["workers"], ["approval", "browser", "verify"])
        self.assertFalse(health["encrypted_sessions"])


if __name__ == "__main__":
    unittest.main()
