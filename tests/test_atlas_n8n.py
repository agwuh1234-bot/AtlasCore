import asyncio
import os
import unittest
from unittest.mock import AsyncMock, patch

import atlas_n8n


class N8NBridgeTests(unittest.IsolatedAsyncioTestCase):
    def test_configured_requires_url_and_token(self):
        with patch.object(atlas_n8n, "N8N_MCP_URL", "https://example.test/mcp"), patch.object(atlas_n8n, "N8N_MCP_TOKEN", ""):
            self.assertFalse(atlas_n8n.configured())
        with patch.object(atlas_n8n, "N8N_MCP_URL", "https://example.test/mcp"), patch.object(atlas_n8n, "N8N_MCP_TOKEN", "secret"):
            self.assertTrue(atlas_n8n.configured())

    def test_timeout_is_bounded_and_invalid_values_fall_back(self):
        with patch.dict(os.environ, {"N8N_MCP_TIMEOUT_SECONDS": "0.01"}, clear=False):
            self.assertEqual(atlas_n8n._timeout_seconds(), 1.0)
        with patch.dict(os.environ, {"N8N_MCP_TIMEOUT_SECONDS": "999"}, clear=False):
            self.assertEqual(atlas_n8n._timeout_seconds(), 120.0)
        with patch.dict(os.environ, {"N8N_MCP_TIMEOUT_SECONDS": "bad"}, clear=False):
            self.assertEqual(atlas_n8n._timeout_seconds(), 20.0)

    def test_schema_validation_requires_declared_fields(self):
        schema = {"type": "object", "required": ["workflowId"], "properties": {"workflowId": {"type": "string"}}}
        with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "missing required field"):
            atlas_n8n._validate_arguments_against_schema({}, schema)

    def test_schema_validation_rejects_wrong_top_level_type_and_enum(self):
        schema = {
            "type": "object",
            "properties": {
                "workflowId": {"type": "string"},
                "mode": {"type": "string", "enum": ["safe", "dry-run"]},
            },
        }
        with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "workflowId must be string"):
            atlas_n8n._validate_arguments_against_schema({"workflowId": 123}, schema)
        with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "not an allowed value"):
            atlas_n8n._validate_arguments_against_schema({"mode": "danger"}, schema)

    def test_schema_validation_rejects_undeclared_fields_when_forbidden(self):
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {"workflowId": {"type": "string"}},
        }
        with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "undeclared field"):
            atlas_n8n._validate_arguments_against_schema({"workflowId": "1", "debug": True}, schema)

    def test_schema_validation_enforces_string_length_bounds(self):
        schema = {
            "type": "object",
            "properties": {"workflowId": {"type": "string", "minLength": 2, "maxLength": 5}},
        }
        with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "shorter than minLength"):
            atlas_n8n._validate_arguments_against_schema({"workflowId": "1"}, schema)
        with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "exceeds maxLength"):
            atlas_n8n._validate_arguments_against_schema({"workflowId": "123456"}, schema)
        atlas_n8n._validate_arguments_against_schema({"workflowId": "123"}, schema)

    def test_schema_validation_enforces_array_size_bounds(self):
        schema = {
            "type": "object",
            "properties": {"operations": {"type": "array", "minItems": 1, "maxItems": 2}},
        }
        with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "fewer than minItems"):
            atlas_n8n._validate_arguments_against_schema({"operations": []}, schema)
        with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "exceeds maxItems"):
            atlas_n8n._validate_arguments_against_schema({"operations": [{}, {}, {}]}, schema)
        atlas_n8n._validate_arguments_against_schema({"operations": [{}]}, schema)

    def test_schema_validation_enforces_numeric_bounds(self):
        schema = {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                "ratio": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 1},
            },
        }
        with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "below minimum"):
            atlas_n8n._validate_arguments_against_schema({"limit": 0}, schema)
        with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "exceeds maximum"):
            atlas_n8n._validate_arguments_against_schema({"limit": 101}, schema)
        with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "exclusiveMinimum"):
            atlas_n8n._validate_arguments_against_schema({"ratio": 0}, schema)
        with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "exclusiveMaximum"):
            atlas_n8n._validate_arguments_against_schema({"ratio": 1}, schema)
        atlas_n8n._validate_arguments_against_schema({"limit": 50, "ratio": 0.5}, schema)

    def test_disable_node_operation_is_treated_as_destructive(self):
        self.assertTrue(
            atlas_n8n._contains_destructive_workflow_operation(
                {"operations": [{"type": "setNodeDisabled", "nodeName": "Critical", "disabled": True}]}
            )
        )
        self.assertFalse(
            atlas_n8n._contains_destructive_workflow_operation(
                {"operations": [{"type": "setNodeDisabled", "nodeName": "Critical", "disabled": False}]}
            )
        )

    def test_missing_or_malformed_partial_operations_fail_closed(self):
        self.assertTrue(atlas_n8n._contains_destructive_workflow_operation({"workflowId": "1"}))
        self.assertTrue(
            atlas_n8n._contains_destructive_workflow_operation(
                {"workflowId": "1", "operations": {"type": "addNode"}}
            )
        )

    async def test_await_mcp_fails_closed_on_timeout(self):
        async def slow():
            await asyncio.sleep(0.05)

        with patch.object(atlas_n8n, "_timeout_seconds", return_value=0.001):
            with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "timed out"):
                await atlas_n8n._await_mcp(slow(), "test operation")

    async def test_call_tool_defaults_to_empty_arguments_after_live_discovery(self):
        tool = type("Tool", (), {"name": "workflow_test"})()
        session = AsyncMock()
        session.list_tools.return_value = type("Result", (), {"tools": [tool]})()
        session.call_tool.return_value = object()

        class FakeContext:
            async def __aenter__(self):
                return session
            async def __aexit__(self, exc_type, exc, tb):
                return False

        with patch.dict(os.environ, {"N8N_WRITES_ENABLED": "true"}, clear=False), patch.object(atlas_n8n, "n8n_session", return_value=FakeContext()):
            await atlas_n8n.call_tool("workflow_test")
        session.list_tools.assert_awaited_once()
        session.call_tool.assert_awaited_once_with("workflow_test", {})

    async def test_call_tool_rejects_non_object_arguments_before_connecting(self):
        with patch.object(atlas_n8n, "n8n_session") as mocked_session:
            with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "arguments must be an object"):
                await atlas_n8n.call_tool("workflow_test", ["bad"])
        mocked_session.assert_not_called()

    async def test_call_tool_rejects_name_missing_from_live_discovery(self):
        session = AsyncMock()
        session.list_tools.return_value = type("Result", (), {"tools": []})()

        class FakeContext:
            async def __aenter__(self):
                return session
            async def __aexit__(self, exc_type, exc, tb):
                return False

        with patch.object(atlas_n8n, "n8n_session", return_value=FakeContext()):
            with self.assertRaises(atlas_n8n.N8NBridgeError):
                await atlas_n8n.call_tool("missing_tool")
        session.call_tool.assert_not_awaited()

    async def test_call_tool_blocks_schema_mismatch_before_execution(self):
        tool = type("Tool", (), {
            "name": "workflow_test",
            "inputSchema": {"type": "object", "required": ["workflowId"], "properties": {"workflowId": {"type": "string"}}},
        })()
        session = AsyncMock()
        session.list_tools.return_value = type("Result", (), {"tools": [tool]})()

        class FakeContext:
            async def __aenter__(self):
                return session
            async def __aexit__(self, exc_type, exc, tb):
                return False

        with patch.dict(os.environ, {"N8N_WRITES_ENABLED": "true"}, clear=False), patch.object(atlas_n8n, "n8n_session", return_value=FakeContext()):
            with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "missing required field"):
                await atlas_n8n.call_tool("workflow_test", {})
        session.call_tool.assert_not_awaited()

    async def test_write_call_is_blocked_without_write_opt_in(self):
        tool = type("Tool", (), {"name": "update_workflow"})()
        session = AsyncMock()
        session.list_tools.return_value = type("Result", (), {"tools": [tool]})()

        class FakeContext:
            async def __aenter__(self):
                return session
            async def __aexit__(self, exc_type, exc, tb):
                return False

        with patch.dict(os.environ, {}, clear=False), patch.object(atlas_n8n, "n8n_session", return_value=FakeContext()):
            os.environ.pop("N8N_WRITES_ENABLED", None)
            with self.assertRaises(atlas_n8n.N8NBridgeError):
                await atlas_n8n.call_tool("update_workflow", {"workflowId": "1", "operations": []})
        session.call_tool.assert_not_awaited()

    async def test_destructive_nested_update_requires_separate_opt_in(self):
        tool = type("Tool", (), {"name": "update_workflow"})()
        session = AsyncMock()
        session.list_tools.return_value = type("Result", (), {"tools": [tool]})()

        class FakeContext:
            async def __aenter__(self):
                return session
            async def __aexit__(self, exc_type, exc, tb):
                return False

        arguments = {
            "workflowId": "1",
            "operations": [{"type": "removeConnection", "source": "A", "target": "B"}],
        }
        with patch.dict(os.environ, {"N8N_WRITES_ENABLED": "true"}, clear=False), patch.object(atlas_n8n, "n8n_session", return_value=FakeContext()):
            os.environ.pop("N8N_DESTRUCTIVE_ENABLED", None)
            with self.assertRaises(atlas_n8n.N8NBridgeError):
                await atlas_n8n.call_tool("update_workflow", arguments)
        session.call_tool.assert_not_awaited()

    async def test_disabling_node_requires_separate_destructive_opt_in(self):
        tool = type("Tool", (), {"name": "update_workflow"})()
        session = AsyncMock()
        session.list_tools.return_value = type("Result", (), {"tools": [tool]})()

        class FakeContext:
            async def __aenter__(self):
                return session
            async def __aexit__(self, exc_type, exc, tb):
                return False

        arguments = {
            "workflowId": "1",
            "operations": [{"type": "setNodeDisabled", "nodeName": "Critical", "disabled": True}],
        }
        with patch.dict(os.environ, {"N8N_WRITES_ENABLED": "true"}, clear=False), patch.object(atlas_n8n, "n8n_session", return_value=FakeContext()):
            os.environ.pop("N8N_DESTRUCTIVE_ENABLED", None)
            with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "destructive_disabled"):
                await atlas_n8n.call_tool("update_workflow", arguments)
        session.call_tool.assert_not_awaited()

    async def test_malformed_partial_update_requires_destructive_opt_in(self):
        tool = type("Tool", (), {"name": "n8n_update_partial_workflow"})()
        session = AsyncMock()
        session.list_tools.return_value = type("Result", (), {"tools": [tool]})()

        class FakeContext:
            async def __aenter__(self):
                return session
            async def __aexit__(self, exc_type, exc, tb):
                return False

        with patch.dict(os.environ, {"N8N_WRITES_ENABLED": "true"}, clear=False), patch.object(atlas_n8n, "n8n_session", return_value=FakeContext()):
            os.environ.pop("N8N_DESTRUCTIVE_ENABLED", None)
            with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "destructive_disabled"):
                await atlas_n8n.call_tool("n8n_update_partial_workflow", {"workflowId": "1"})
        session.call_tool.assert_not_awaited()

    async def test_list_tools_exposes_only_public_schema(self):
        tool = type("Tool", (), {"name": "workflow_list", "description": "List workflows", "inputSchema": {"type": "object"}})()
        session = AsyncMock()
        session.list_tools.return_value = type("Result", (), {"tools": [tool]})()

        class FakeContext:
            async def __aenter__(self):
                return session
            async def __aexit__(self, exc_type, exc, tb):
                return False

        with patch.object(atlas_n8n, "n8n_session", return_value=FakeContext()):
            result = await atlas_n8n.list_tools()
        self.assertEqual(result, [{"name": "workflow_list", "description": "List workflows", "inputSchema": {"type": "object"}}])
        self.assertNotIn("token", str(result).lower())


if __name__ == "__main__":
    unittest.main()
