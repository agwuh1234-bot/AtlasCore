import unittest
from pathlib import Path

from atlas_automation_executions_api import (
    _collect_executions,
    _execution_arguments,
    _execution_tool,
)


ROOT = Path(__file__).resolve().parents[1]


class AutomationExecutionHistoryTests(unittest.TestCase):
    def test_execution_history_assets_are_loaded_before_legacy_panel(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('/app/automation-executions.css', html)
        self.assertIn('/app/automation-executions.js', html)
        self.assertLess(
            html.index('/app/automation-executions.js'),
            html.index('/app/studio-panels.js'),
        )

    def test_execution_history_api_is_read_only(self):
        source = (ROOT / "atlas_automation_executions_api.py").read_text(encoding="utf-8")
        self.assertIn('@router.get("/executions")', source)
        self.assertNotIn('@router.post(', source)
        self.assertNotIn('@router.put(', source)
        self.assertNotIn('@router.delete(', source)

    def test_execution_tool_prefers_exact_read_list_tool(self):
        tools = [
            {"name": "execute_workflow", "inputSchema": {}},
            {"name": "list_executions", "inputSchema": {"type": "object"}},
            {"name": "get_execution", "inputSchema": {"type": "object"}},
        ]
        self.assertEqual(_execution_tool(tools)["name"], "list_executions")

    def test_execution_arguments_follow_live_schema(self):
        tool = {
            "name": "list_executions",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "workflowId": {"type": "string"},
                    "limit": {"type": "integer", "maximum": 20},
                },
                "required": ["workflowId"],
            },
        }
        self.assertEqual(
            _execution_arguments(tool, "wf-1", 50),
            {"workflowId": "wf-1", "limit": 20},
        )

    def test_unsupported_required_schema_fails_closed(self):
        tool = {
            "name": "list_executions",
            "inputSchema": {
                "type": "object",
                "properties": {"projectId": {"type": "string"}},
                "required": ["projectId"],
            },
        }
        self.assertIsNone(_execution_arguments(tool, "wf-1", 12))

    def test_execution_collection_exposes_only_bounded_receipt_metadata(self):
        payload = {
            "data": [
                {
                    "id": "exec-1",
                    "workflowId": "wf-1",
                    "status": "success",
                    "startedAt": "2026-08-27T06:00:00Z",
                    "data": {"secret": "do-not-expose"},
                },
                {
                    "id": "exec-2",
                    "workflowId": "other",
                    "status": "error",
                    "error": {"message": "private payload"},
                },
            ]
        }
        rows = []
        _collect_executions(payload, rows, set(), "wf-1")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "exec-1")
        self.assertEqual(rows[0]["status"], "success")
        self.assertNotIn("data", rows[0])
        self.assertNotIn("secret", repr(rows))


if __name__ == "__main__":
    unittest.main()
