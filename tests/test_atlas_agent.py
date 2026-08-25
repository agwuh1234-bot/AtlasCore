import unittest

from atlas_agent import AgentLoopConfig, agent_runtime_prompt, learning_kind, should_stop_after_failure


class AtlasAgentLoopTests(unittest.TestCase):
    def test_runtime_prompt_requires_plan_verification_and_recovery(self):
        prompt = agent_runtime_prompt().lower()
        self.assertIn("план", prompt)
        self.assertIn("проверь", prompt)
        self.assertIn("исправ", prompt)
        self.assertIn("подтвержден", prompt)

    def test_retry_guard_prevents_infinite_recovery(self):
        config = AgentLoopConfig(max_recovery_attempts=3)
        self.assertFalse(should_stop_after_failure(2, config))
        self.assertTrue(should_stop_after_failure(3, config))
        self.assertTrue(should_stop_after_failure(4, config))

    def test_learning_requires_verified_outcome(self):
        self.assertIsNone(learning_kind(True, False))
        self.assertIsNone(learning_kind(False, False))
        self.assertEqual(learning_kind(True, True), "skill")
        self.assertEqual(learning_kind(False, True), "lesson")


if __name__ == "__main__":
    unittest.main()
