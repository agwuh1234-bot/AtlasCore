import unittest

from atlas_n8n_graph_safety import connection_shape_issues


class N8NGraphDanglingReferenceTests(unittest.TestCase):
    def _body(self):
        return {
            "nodes": [
                {"name": "Source", "type": "n8n-nodes-base.manualTrigger"},
                {"name": "Target", "type": "n8n-nodes-base.set"},
            ],
            "connections": {
                "Source": {
                    "main": [[{"node": "Target", "type": "main", "index": 0}]]
                }
            },
        }

    def test_canonical_references_to_existing_nodes_are_allowed(self):
        self.assertEqual(connection_shape_issues(self._body()), [])

    def test_dangling_source_is_blocked_when_node_list_is_available(self):
        body = self._body()
        body["connections"] = {
            "Missing": {
                "main": [[{"node": "Target", "type": "main", "index": 0}]]
            }
        }
        self.assertIn("dangling_connection_source:Missing", connection_shape_issues(body))

    def test_dangling_target_is_blocked_when_node_list_is_available(self):
        body = self._body()
        body["connections"]["Source"]["main"][0][0]["node"] = "Missing"
        self.assertIn("dangling_connection_target:Source->Missing", connection_shape_issues(body))


if __name__ == "__main__":
    unittest.main()
