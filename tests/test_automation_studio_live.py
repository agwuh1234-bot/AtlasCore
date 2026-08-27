import unittest
from pathlib import Path

from atlas_automation_api import (
    _blocking_shape_issues,
    _collect_workflows,
    _node_rows,
)


ROOT = Path(__file__).resolve().parents[1]


class AutomationStudioLiveTests(unittest.TestCase):
    def test_assets_load_before_legacy_studio_panel(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('/app/automation-studio-live.css', html)
        self.assertIn('/app/automation-studio-live.js', html)
        self.assertLess(
            html.index('/app/automation-studio-live.js'),
            html.index('/app/studio-panels.js'),
        )

    def test_app_automation_api_is_read_only(self):
        source = (ROOT / "atlas_automation_api.py").read_text(encoding="utf-8")
        self.assertIn('@router.get("/status")', source)
        self.assertIn('@router.get("/workflows")', source)
        self.assertIn('@router.get("/workflow")', source)
        self.assertNotIn('@router.post(', source)
        self.assertNotIn('@router.put(', source)
        self.assertNotIn('@router.delete(', source)

    def test_all_duplicate_action_buttons_are_wired(self):
        source = (ROOT / "web" / "automation-studio-live.js").read_text(encoding="utf-8")
        self.assertIn('$$(`[data-act="${a}"]`,panel).forEach', source)
        self.assertIn("$$('[data-act=\"edit\"]',panel).forEach", source)
        self.assertIn("$$('[data-act=\"run\"]',panel).forEach", source)
        self.assertIn('function workflowReady()', source)
        self.assertIn('function fitGraph()', source)
        self.assertIn("$('.auto-change-input',panel)?.focus()", source)

    def test_node_rows_do_not_expose_credential_values(self):
        body = {
            "nodes": [
                {
                    "name": "Shopify",
                    "type": "n8n-nodes-base.shopify",
                    "typeVersion": 1,
                    "position": [10, 20],
                    "parameters": {"resource": "product", "operation": "get"},
                    "credentials": {
                        "shopifyApi": {"id": "secret-id", "name": "private-name"}
                    },
                }
            ],
            "connections": {},
        }
        rows = _node_rows(body)
        self.assertEqual(rows[0]["credential_types"], ["shopifyApi"])
        self.assertEqual(rows[0]["parameter_keys"], ["operation", "resource"])
        self.assertNotIn("secret-id", repr(rows))
        self.assertNotIn("private-name", repr(rows))

    def test_valid_special_n8n_connection_is_not_ui_blocker(self):
        body = {
            "nodes": [
                {"name": "Model", "type": "@n8n/n8n-nodes-langchain.anthropic"},
                {"name": "Agent", "type": "@n8n/n8n-nodes-langchain.agent"},
            ],
            "connections": {
                "Model": {
                    "ai_languageModel": [
                        [{"node": "Agent", "type": "ai_languageModel", "index": 0}]
                    ]
                }
            },
        }
        self.assertEqual(_blocking_shape_issues(body), [])

    def test_workflow_collection_deduplicates_ids(self):
        payload = {
            "data": [
                {"id": "wf-1", "name": "First", "active": False},
                {"workflowId": "wf-1", "name": "Duplicate", "active": True},
                {"id": "wf-2", "name": "Second", "updatedAt": "now"},
            ]
        }
        rows = []
        _collect_workflows(payload, rows, set())
        self.assertEqual([row["id"] for row in rows], ["wf-1", "wf-2"])


if __name__ == "__main__":
    unittest.main()
