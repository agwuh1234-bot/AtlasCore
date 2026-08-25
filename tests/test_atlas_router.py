import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from atlas_router import BudgetController, ModelRouter
from atlas_store import AtlasStore, BudgetExceeded


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

    def test_attachment_uses_document_lane(self):
        router = ModelRouter()
        route = router.select("Проанализируй вложение", has_attachments=True)
        self.assertEqual(route.lane, "document")
        self.assertEqual(route.model, router.document_model)
        self.assertEqual(router.public_config()["document"], router.document_model)

    def test_attachment_code_request_still_uses_strong_lane(self):
        route = ModelRouter().select(
            "Исправь Python код из вложения",
            has_attachments=True,
        )
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

    def test_large_attached_document_bypasses_normal_50k_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AtlasStore(sqlite_path=str(Path(directory) / "large-doc.db"))
            store.initialize()
            budget = BudgetController(store, FakeClient())
            budget.count_input_tokens = lambda **kwargs: 796_306
            input_data = [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Проанализируй PDF"},
                        {
                            "type": "input_file",
                            "filename": "large.pdf",
                            "file_data": "data:application/pdf;base64,AAAA",
                        },
                    ],
                }
            ]
            reservation = budget.reserve(
                job_id="job-large-doc",
                model="gpt-5.6-terra",
                input_data=input_data,
                instructions="test",
                tools=[],
                max_output_tokens=1200,
                use_web=False,
            )
            self.assertEqual(reservation.estimated_input_tokens, 796_306)
            self.assertGreater(reservation.estimated_cost_usd, 0)
            budget.release(reservation)
            store.close()

    def test_large_plain_text_remains_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AtlasStore(sqlite_path=str(Path(directory) / "large-text.db"))
            store.initialize()
            budget = BudgetController(store, FakeClient())
            budget.count_input_tokens = lambda **kwargs: 100_000
            with self.assertRaises(BudgetExceeded):
                budget.reserve(
                    job_id="job-large-text",
                    model="gpt-5.6-terra",
                    input_data="not a file",
                    instructions="test",
                    tools=[],
                    max_output_tokens=1200,
                    use_web=False,
                )
            store.close()

    def test_document_over_hard_ceiling_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AtlasStore(sqlite_path=str(Path(directory) / "too-large.db"))
            store.initialize()
            budget = BudgetController(store, FakeClient())
            budget.count_input_tokens = lambda **kwargs: budget.max_large_input_tokens + 1
            input_data = [{"type": "input_file", "filename": "huge.pdf", "file_data": "x"}]
            with self.assertRaises(BudgetExceeded):
                budget.reserve(
                    job_id="job-too-large",
                    model="gpt-5.6-terra",
                    input_data=input_data,
                    instructions="test",
                    tools=[],
                    max_output_tokens=1200,
                    use_web=False,
                )
            store.close()


if __name__ == "__main__":
    unittest.main()
