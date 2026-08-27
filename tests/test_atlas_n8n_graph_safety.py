import unittest

from atlas_n8n_graph_safety import connection_count, connection_shape_issues, duplicate_connections


def body_with_edges(*edges):
    connections = {}
    for source, target in edges:
        connections.setdefault(source, {"main": [[]]})["main"][0].append(
            {"node": target, "type": "main", "index": 0}
        )
    return {"connections": connections}


class N8NGraphSafetyTests(unittest.TestCase):
    def test_counts_duplicate_physical_edges(self):
        body = body_with_edges(("A", "B"), ("A", "B"), ("A", "C"))
        self.assertEqual(connection_count(body, "A", "B"), 2)
        self.assertEqual(connection_count(body, "A", "C"), 1)

    def test_reports_only_watched_duplicate_edges(self):
        body = body_with_edges(("A", "B"), ("A", "B"), ("X", "Y"), ("X", "Y"))
        issues = duplicate_connections(body, (("A", "B"), ("M", "N")))
        self.assertEqual(issues, ["duplicate_connection:A->B"])

    def test_malformed_connections_fail_safe_to_zero_count(self):
        self.assertEqual(connection_count({"connections": []}, "A", "B"), 0)
        self.assertEqual(connection_count({}, "A", "B"), 0)

    def test_shape_validator_accepts_canonical_main_edge(self):
        self.assertEqual(connection_shape_issues(body_with_edges(("A", "B"))), [])

    def test_shape_validator_accepts_finite_two_axis_node_position(self):
        body = body_with_edges(("A", "B"))
        body["nodes"] = [
            {"name": "A", "type": "n8n-nodes-base.manualTrigger", "position": [-100, 20.5]},
            {"name": "B", "type": "n8n-nodes-base.noOp", "position": [0, 0]},
        ]
        self.assertEqual(connection_shape_issues(body), [])

    def test_shape_validator_blocks_malformed_node_positions(self):
        invalid_positions = ([1], [1, 2, 3], [True, 2], [float("inf"), 0], "1,2")
        for position in invalid_positions:
            with self.subTest(position=position):
                body = body_with_edges(("A", "B"))
                body["nodes"] = [
                    {"name": "A", "type": "n8n-nodes-base.manualTrigger", "position": position},
                    {"name": "B", "type": "n8n-nodes-base.noOp"},
                ]
                self.assertEqual(
                    connection_shape_issues(body),
                    ["malformed_workflow_node_position:A"],
                )

    def test_shape_validator_blocks_duplicate_physical_edge_anywhere(self):
        body = body_with_edges(("A", "B"), ("A", "B"), ("X", "Y"), ("X", "Y"))
        self.assertEqual(
            connection_shape_issues(body),
            ["duplicate_physical_connection:A->B", "duplicate_physical_connection:X->Y"],
        )

    def test_shape_validator_blocks_duplicate_workflow_node_names(self):
        body = body_with_edges(("A", "B"))
        body["nodes"] = [
            {"name": "A", "type": "n8n-nodes-base.manualTrigger"},
            {"name": "B", "type": "n8n-nodes-base.noOp"},
            {"name": "B", "type": "n8n-nodes-base.set"},
        ]
        self.assertEqual(connection_shape_issues(body), ["duplicate_workflow_node_name:B"])

    def test_shape_validator_blocks_non_mapping_workflow_node(self):
        body = body_with_edges(("A", "B"))
        body["nodes"] = [
            {"name": "A", "type": "n8n-nodes-base.manualTrigger"},
            "corrupt-node",
            {"name": "B", "type": "n8n-nodes-base.noOp"},
        ]
        self.assertEqual(connection_shape_issues(body), ["malformed_workflow_node:1"])

    def test_shape_validator_blocks_missing_workflow_node_name(self):
        body = body_with_edges(("A", "B"))
        body["nodes"] = [
            {"name": "A", "type": "n8n-nodes-base.manualTrigger"},
            {"type": "n8n-nodes-base.set"},
            {"name": "B", "type": "n8n-nodes-base.noOp"},
        ]
        self.assertEqual(connection_shape_issues(body), ["malformed_workflow_node_name:1"])

    def test_shape_validator_blocks_missing_workflow_node_type(self):
        body = body_with_edges(("A", "B"))
        body["nodes"] = [
            {"name": "A", "type": "n8n-nodes-base.manualTrigger"},
            {"name": "B"},
        ]
        self.assertEqual(connection_shape_issues(body), ["malformed_workflow_node_type:B"])

    def test_shape_validator_blocks_non_boolean_disabled_state(self):
        body = body_with_edges(("A", "B"))
        body["nodes"] = [
            {"name": "A", "type": "n8n-nodes-base.manualTrigger"},
            {"name": "B", "type": "n8n-nodes-base.noOp", "disabled": "false"},
        ]
        self.assertEqual(connection_shape_issues(body), ["malformed_workflow_node_disabled:B"])

    def test_shape_validator_blocks_nonzero_target_input_index(self):
        body = {"connections": {"A": {"main": [[{"node": "B", "type": "main", "index": 1}]]}}}
        self.assertEqual(connection_shape_issues(body), ["unsupported_connection_edge_index:A:1"])

    def test_shape_validator_blocks_nonzero_output_branch(self):
        body = {"connections": {"A": {"main": [[], [{"node": "B", "type": "main", "index": 0}]]}}}
        self.assertEqual(connection_shape_issues(body), ["unsupported_connection_branch_index:A:1"])

    def test_shape_validator_blocks_unreviewed_connection_types(self):
        body = {"connections": {"A": {"ai_tool": [[{"node": "B", "type": "ai_tool", "index": 0}]]}}}
        self.assertEqual(
            connection_shape_issues(body),
            ["unsupported_connection_output_type:A:ai_tool", "unsupported_connection_edge_type:A:ai_tool"],
        )

    def test_shape_validator_blocks_unexpected_edge_metadata(self):
        body = {
            "connections": {
                "A": {
                    "main": [[{
                        "node": "B",
                        "type": "main",
                        "index": 0,
                        "sourceOutput": "legacy",
                    }]]
                }
            }
        }
        self.assertEqual(
            connection_shape_issues(body),
            ["unsupported_connection_edge_metadata:A:sourceOutput"],
        )

    def test_shape_validator_fails_closed_on_missing_connections_map(self):
        self.assertEqual(connection_shape_issues({}), ["malformed_connections"])


if __name__ == "__main__":
    unittest.main()
