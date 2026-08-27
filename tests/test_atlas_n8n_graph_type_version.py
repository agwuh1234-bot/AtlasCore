import unittest

from atlas_n8n_graph_safety import connection_shape_issues


class N8NNodeTypeVersionTests(unittest.TestCase):
    def _body(self, type_version):
        return {
            "nodes": [
                {"name": "A", "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1},
                {"name": "B", "type": "n8n-nodes-base.noOp", "typeVersion": type_version},
            ],
            "connections": {
                "A": {"main": [[{"node": "B", "type": "main", "index": 0}]]}
            },
        }

    def test_valid_positive_numeric_type_version_is_allowed(self):
        self.assertEqual(connection_shape_issues(self._body(1.1)), [])

    def test_string_type_version_is_blocked(self):
        self.assertEqual(
            connection_shape_issues(self._body("1.1")),
            ["malformed_workflow_node_type_version:B"],
        )

    def test_non_finite_type_version_is_blocked(self):
        self.assertEqual(
            connection_shape_issues(self._body(float("nan"))),
            ["malformed_workflow_node_type_version:B"],
        )

    def test_boolean_type_version_is_blocked(self):
        self.assertEqual(
            connection_shape_issues(self._body(True)),
            ["malformed_workflow_node_type_version:B"],
        )


if __name__ == "__main__":
    unittest.main()
