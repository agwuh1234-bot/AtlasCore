import os
import unittest
from unittest.mock import AsyncMock, patch

import atlas_n8n_bootstrap as bootstrap


class _Logger:
    def __init__(self):
        self.messages = []

    def info(self, message, *args):
        self.messages.append(("info", message % args if args else message))

    def warning(self, message, *args):
        self.messages.append(("warning", message % args if args else message))

    def exception(self, message, *args):
        self.messages.append(("exception", message % args if args else message))


class N8NBootstrapTests(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_bootstrap_does_nothing(self):
        logger = _Logger()
        with patch.dict(os.environ, {"N8N_BOOTSTRAP_TEST_WORKFLOW": ""}, clear=False), patch.object(
            bootstrap, "call_tool", new=AsyncMock()
        ) as call_tool:
            await bootstrap.maybe_bootstrap_test_workflow(logger)
        call_tool.assert_not_awaited()
        self.assertEqual(logger.messages, [])

    async def test_existing_workflow_is_not_recreated(self):
        logger = _Logger()
        existing = type(
            "Result",
            (),
            {
                "structuredContent": {
                    "items": [{"id": "wf-123", "name": bootstrap.WORKFLOW_NAME}]
                },
                "content": [],
            },
        )()
        call_tool = AsyncMock(return_value=existing)
        with patch.dict(os.environ, {"N8N_BOOTSTRAP_TEST_WORKFLOW": "true"}, clear=False), patch.object(
            bootstrap, "configured", return_value=True
        ), patch.object(bootstrap, "decision", return_value=(True, "allowed")), patch.object(
            bootstrap, "call_tool", new=call_tool
        ):
            await bootstrap.maybe_bootstrap_test_workflow(logger)
        call_tool.assert_awaited_once_with("search_workflows", {"query": bootstrap.WORKFLOW_NAME, "limit": 50})
        self.assertTrue(any("action=existing" in message for _, message in logger.messages))

    async def test_policy_block_prevents_any_n8n_write(self):
        logger = _Logger()
        call_tool = AsyncMock()
        with patch.dict(os.environ, {"N8N_BOOTSTRAP_TEST_WORKFLOW": "true"}, clear=False), patch.object(
            bootstrap, "configured", return_value=True
        ), patch.object(bootstrap, "decision", return_value=(False, "write_not_allowed")), patch.object(
            bootstrap, "call_tool", new=call_tool
        ):
            await bootstrap.maybe_bootstrap_test_workflow(logger)
        call_tool.assert_not_awaited()
        self.assertTrue(any("policy_blocked" in message for _, message in logger.messages))

    async def test_validation_failure_blocks_create(self):
        logger = _Logger()
        search = type("Result", (), {"structuredContent": {"items": []}, "content": []})()
        invalid = type("Result", (), {"structuredContent": {"valid": False}, "content": []})()
        call_tool = AsyncMock(side_effect=[search, invalid])
        with patch.dict(os.environ, {"N8N_BOOTSTRAP_TEST_WORKFLOW": "true"}, clear=False), patch.object(
            bootstrap, "configured", return_value=True
        ), patch.object(bootstrap, "decision", return_value=(True, "allowed")), patch.object(
            bootstrap, "call_tool", new=call_tool
        ):
            await bootstrap.maybe_bootstrap_test_workflow(logger)
        self.assertEqual(call_tool.await_count, 2)
        self.assertEqual(call_tool.await_args_list[1].args[0], "validate_workflow")
        self.assertTrue(any("validation_failed" in message for _, message in logger.messages))


if __name__ == "__main__":
    unittest.main()
