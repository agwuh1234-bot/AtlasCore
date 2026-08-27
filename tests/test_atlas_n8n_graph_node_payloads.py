import unittest

from atlas_n8n_graph_safety import connection_shape_issues


class N8NNodePayloadShapeTests(unittest.TestCase):
    def _body(self, node):
        return {
            "nodes": [node],
            "connections": {},
        }

    def test_non_mapping_parameters_are_blocked(self):
        body = self._body({
            "name": "Set",
            "type": "n8n-nodes-base.set",
            "parameters": ["unexpected"],
        })
        self.assertEqual(
            connection_shape_issues(body),
            ["malformed_workflow_node_parameters:Set"],
        )

    def test_non_mapping_credentials_are_blocked(self):
        body = self._body({
            "name": "GitHub",
            "type": "n8n-nodes-base.github",
            "credentials": "githubOAuth2Api",
        })
        self.assertEqual(
            connection_shape_issues(body),
            ["malformed_workflow_node_credentials:GitHub"],
        )

    def test_mapping_parameters_and_credentials_are_allowed(self):
        body = self._body({
            "name": "GitHub",
            "type": "n8n-nodes-base.github",
            "parameters": {"operation": "get"},
            "credentials": {"githubOAuth2Api": {"id": "credential-ref"}},
        })
        self.assertEqual(connection_shape_issues(body), [])


if __name__ == "__main__":
    unittest.main()
