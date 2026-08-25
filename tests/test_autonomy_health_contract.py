import unittest
from unittest.mock import Mock

from atlas_autonomy_runtime import AutonomyRuntime


class HealthContractTests(unittest.TestCase):
    def test_health_reports_runtime_state(self):
        engine = Mock()
        engine.concurrency = 5
        engine.tasks = {"a": Mock(status="running"), "b": Mock(status="done")}
        runtime = AutonomyRuntime(engine=engine, browser_jobs=Mock(), resumed_tasks=2, started=True)
        health = runtime.health()
        self.assertTrue(health["started"])
        self.assertEqual(health["resumed_tasks"], 2)
        self.assertEqual(health["concurrency"], 5)
        self.assertEqual(health["active_tasks"], 1)


if __name__ == "__main__":
    unittest.main()
