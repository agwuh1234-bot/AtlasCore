import os
import unittest
from unittest.mock import patch

from atlas_n8n_policy import classify_tool, decision, preflight


class N8NPolicyTests(unittest.TestCase):
    def test_read_tools_are_classified_read(self):
        for name in ("list_workflows", "workflow_get", "search_executions", "status_health"):
            self.assertEqual(classify_tool(name), "read")

    def test_unknown_tools_fail_closed_as_write(self):
        self.assertEqual(classify_tool("workflow_magic"), "write")

    def test_destructive_tools_are_separate(self):
        self.assertEqual(classify_tool("delete_workflow"), "destructive")

    def test_read_requires_read_intent(self):
        self.assertEqual(decision("list_workflows", "read"), (True, "ok"))
        self.assertEqual(decision("list_workflows", "write"), (False, "intent_mismatch"))

    def test_write_is_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("N8N_WRITES_ENABLED", None)
            self.assertEqual(decision("create_workflow", "write"), (False, "writes_disabled"))

    def test_write_can_be_enabled_without_enabling_delete(self):
        with patch.dict(os.environ, {"N8N_WRITES_ENABLED": "true"}, clear=False):
            os.environ.pop("N8N_DESTRUCTIVE_ENABLED", None)
            self.assertEqual(decision("create_workflow", "write"), (True, "ok"))
            self.assertEqual(decision("delete_workflow", "write"), (False, "destructive_disabled"))

    def test_preflight_requires_exact_discovered_tool(self):
        tools = [{"name": "list_workflows", "description": "List", "inputSchema": {"type": "object"}}]
        missing = preflight(tools, "list_workflow", "read")
        self.assertFalse(missing["found"])
        self.assertFalse(missing["allowed"])
        self.assertEqual(missing["reason"], "unknown_tool")

    def test_preflight_returns_schema_without_executing(self):
        tools = [{"name": "list_workflows", "description": "List", "inputSchema": {"type": "object", "properties": {}}}]
        result = preflight(tools, "list_workflows", "read")
        self.assertTrue(result["found"])
        self.assertTrue(result["allowed"])
        self.assertEqual(result["classification"], "read")
        self.assertEqual(result["input_schema"]["type"], "object")


if __name__ == "__main__":
    unittest.main()
