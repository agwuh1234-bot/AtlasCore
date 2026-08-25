import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from atlas_router import BudgetController, ModelRouter
from atlas_store import AtlasStore


class FakeCounter:
    def count(self, **kwargs):
        return SimpleNamespace(input_tokens=42)


class FakeClient:
    responses = SimpleNamespace(input_tokens=FakeCounter())


class RouterTests(unittest.TestCase):
    def test_simple_request_uses_fast_lane(self):
        route = ModelRouter().select("Составь короткий список покупок")
        self.assertEqual(route.lane, "fast")
        self.assertFalse(route.use_web)

    def test_code_request_uses_strong_lane(self):
        route = ModelRouter().select("Исправь ошибку в Python API и добавь тест")
        self.assertEqual(route.lane, "strong")

    def test_fresh_request_enables_web(self):
        route = ModelRouter().select("Какие последние новости сегодня?")
        self.assertTrue(route.use_web)

    def test_exact_counter_and_reservation(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AtlasStore(sqlite_path=str(Path(directory) / "router.db"))
            store.initialize()
            budget = BudgetController(store, FakeClient())
            budget.daily_limit_usd = 5.0
            budget.task_limit_usd = 1.0
            reservation = budget.reserve(
                job_id="job-router",
                model="gpt-5.6-luna",
                input_data="hello",
                instructions="test",
                tools=[],
                max_output_tokens=100,
                use_web=False,
            )
            self.assertEqual(reservation.estimated_input_tokens, 42)
            budget.release(reservation)
            store.close()


if __name__ == "__main__":
    unittest.main()
