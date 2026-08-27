import unittest

from atlas_n8n_graph_safety import connection_shape_issues


def body_with_credentials(credentials):
    return {
        "nodes": [
            {
                "name": "A",
                "type": "n8n-nodes-base.manualTrigger",
                "credentials": credentials,
            },
            {"name": "B", "type": "n8n-nodes-base.noOp"},
        ],
        "connections": {
            "A": {"main": [[{"node": "B", "type": "main", "index": 0}]]}
        },
    }


class N8NCredentialReferenceShapeTests(unittest.TestCase):
    def test_canonical_credential_reference_is_allowed(self):
        body = body_with_credentials(
            {"githubOAuth2Api": {"id": "cred-123", "name": "GitHub OAuth"}}
        )
        self.assertEqual(connection_shape_issues(body), [])

    def test_non_mapping_credential_reference_is_blocked(self):
        body = body_with_credentials({"githubOAuth2Api": "cred-123"})
        self.assertEqual(
            connection_shape_issues(body),
            ["malformed_workflow_node_credential_ref:A:githubOAuth2Api"],
        )

    def test_empty_credential_type_is_blocked(self):
        body = body_with_credentials({"": {"id": "cred-123"}})
        self.assertEqual(
            connection_shape_issues(body),
            ["malformed_workflow_node_credential_type:A"],
        )

    def test_non_string_credential_id_is_blocked(self):
        body = body_with_credentials({"githubOAuth2Api": {"id": 123}})
        self.assertEqual(
            connection_shape_issues(body),
            ["malformed_workflow_node_credential_id:A:githubOAuth2Api"],
        )

    def test_blank_credential_name_is_blocked(self):
        body = body_with_credentials({"githubOAuth2Api": {"name": " "}})
        self.assertEqual(
            connection_shape_issues(body),
            ["malformed_workflow_node_credential_name:A:githubOAuth2Api"],
        )


if __name__ == "__main__":
    unittest.main()
