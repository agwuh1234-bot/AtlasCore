import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from atlas_executor_api import build_executor_router


class FakeClaudeBridge:
    configured = True
    model = "claude-test"

    async def ask(self, prompt: str, *, system: str | None = None):
        return {
            "ok": True,
            "model": self.model,
            "answer": f"reviewed:{prompt}",
            "usage": {"input_tokens": 1, "output_tokens": 2},
            "stop_reason": "end_turn",
        }


class ExecutorApiTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(build_executor_router(bridge_key="secret", claude=FakeClaudeBridge()))
        self.client = TestClient(app)

    def test_executor_requires_bridge_key(self):
        response = self.client.get("/executor/capabilities")
        self.assertEqual(response.status_code, 401)

    def test_capabilities_reports_claude(self):
        response = self.client.get(
            "/executor/capabilities",
            headers={"X-Atlas-Bridge-Key": "secret"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["capabilities"]["claude"]["configured"])

    def test_claude_endpoint_returns_answer(self):
        response = self.client.post(
            "/executor/claude",
            headers={"X-Atlas-Bridge-Key": "secret"},
            json={"prompt": "write code"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "reviewed:write code")


if __name__ == "__main__":
    unittest.main()
