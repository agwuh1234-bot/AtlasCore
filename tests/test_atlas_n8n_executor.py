import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import atlas_n8n_executor


BRIDGE_KEY = "test-bridge-key"
HEADERS = {"X-Atlas-Bridge-Key": BRIDGE_KEY}
READ_TOOL = {
    "name": "list_workflows",
    "description": "List workflows",
    "inputSchema": {"type": "object"},
}
WRITE_TOOL = {
    "name": "update_workflow",
    "description": "Update workflow",
    "inputSchema": {"type": "object"},
}


def make_client():
    app = FastAPI()
    app.include_router(atlas_n8n_executor.build_n8n_executor_router(bridge_key=BRIDGE_KEY))
    return TestClient(app)


class N8NExecutorGatewayTests(unittest.TestCase):
    def test_tools_requires_bridge_key(self):
        client = make_client()
        response = client.get("/executor/n8n/tools")
        self.assertEqual(response.status_code, 401)

    def test_unknown_tool_is_blocked_before_execution(self):
        client = make_client()
        call_tool = AsyncMock()
        with patch.object(atlas_n8n_executor, "configured", return_value=True), \
             patch.object(atlas_n8n_executor, "list_tools", new=AsyncMock(return_value=[READ_TOOL])), \
             patch.object(atlas_n8n_executor, "call_tool", new=call_tool):
            response = client.post(
                "/executor/n8n/call",
                headers=HEADERS,
                json={"name": "missing_tool", "intent": "read", "arguments": {}},
            )
        self.assertEqual(response.status_code, 404)
        call_tool.assert_not_awaited()

    def test_read_tool_executes_after_live_preflight(self):
        client = make_client()
        result = SimpleNamespace(
            isError=False,
            structuredContent={"workflows": []},
            content=[],
        )
        call_tool = AsyncMock(return_value=result)
        with patch.object(atlas_n8n_executor, "configured", return_value=True), \
             patch.object(atlas_n8n_executor, "list_tools", new=AsyncMock(return_value=[READ_TOOL])), \
             patch.object(atlas_n8n_executor, "call_tool", new=call_tool):
            response = client.post(
                "/executor/n8n/call",
                headers=HEADERS,
                json={"name": "list_workflows", "intent": "read", "arguments": {}},
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        call_tool.assert_awaited_once_with("list_workflows", {})

    def test_write_tool_is_fail_closed_by_default(self):
        client = make_client()
        call_tool = AsyncMock()
        with patch.dict(os.environ, {"N8N_WRITES_ENABLED": ""}, clear=False), \
             patch.object(atlas_n8n_executor, "configured", return_value=True), \
             patch.object(atlas_n8n_executor, "list_tools", new=AsyncMock(return_value=[WRITE_TOOL])), \
             patch.object(atlas_n8n_executor, "call_tool", new=call_tool):
            response = client.post(
                "/executor/n8n/call",
                headers=HEADERS,
                json={"name": "update_workflow", "intent": "write", "arguments": {}},
            )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["reason"], "writes_disabled")
        call_tool.assert_not_awaited()

    def test_intent_mismatch_is_blocked(self):
        client = make_client()
        call_tool = AsyncMock()
        with patch.object(atlas_n8n_executor, "configured", return_value=True), \
             patch.object(atlas_n8n_executor, "list_tools", new=AsyncMock(return_value=[WRITE_TOOL])), \
             patch.object(atlas_n8n_executor, "call_tool", new=call_tool):
            response = client.post(
                "/executor/n8n/call",
                headers=HEADERS,
                json={"name": "update_workflow", "intent": "read", "arguments": {}},
            )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["reason"], "intent_mismatch")
        call_tool.assert_not_awaited()

    def test_result_payload_redacts_nested_sensitive_fields(self):
        result = SimpleNamespace(
            isError=False,
            structuredContent={
                "token": "top-secret",
                "nested": {"authorization": "Bearer abc", "safe": "ok"},
                "items": [{"apiKey": "hidden", "name": "kept"}],
            },
            content=[SimpleNamespace(text='{"password":"pw","value":7}')],
        )
        payload = atlas_n8n_executor._result_payload(result)
        structured = payload["structured_content"]
        self.assertEqual(structured["token"], "[REDACTED]")
        self.assertEqual(structured["nested"]["authorization"], "[REDACTED]")
        self.assertEqual(structured["nested"]["safe"], "ok")
        self.assertEqual(structured["items"][0]["apiKey"], "[REDACTED]")
        self.assertEqual(payload["content"][0]["value"]["password"], "[REDACTED]")
        self.assertEqual(payload["content"][0]["value"]["value"], 7)

    def test_result_payload_bounds_unstructured_text(self):
        long_text = "x" * (atlas_n8n_executor._MAX_TEXT_RESULT + 100)
        result = SimpleNamespace(isError=False, structuredContent=None, content=[SimpleNamespace(text=long_text)])
        payload = atlas_n8n_executor._result_payload(result)
        text = payload["content"][0]["text"]
        self.assertTrue(text.endswith("...[TRUNCATED]"))
        self.assertLess(len(text), len(long_text))


if __name__ == "__main__":
    unittest.main()
