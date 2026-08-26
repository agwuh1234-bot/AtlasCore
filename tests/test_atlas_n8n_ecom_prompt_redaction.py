import unittest

from atlas_n8n_ecom import _collect_nodes


class EcomPromptRedactionTests(unittest.TestCase):
    def test_anthropic_prompt_content_is_not_exposed_by_inspection_summary(self):
        secret_prompt = "PRIVATE_PROMPT_DO_NOT_LOG token=super-secret-value"
        workflow = {
            "nodes": [
                {
                    "name": "Message a model",
                    "type": "@n8n/n8n-nodes-langchain.anthropic",
                    "typeVersion": 1,
                    "parameters": {
                        "modelId": "claude-sonnet-5",
                        "messages": {"values": [{"content": secret_prompt}]},
                        "options": {"temperature": 0.2},
                    },
                    "credentials": {"anthropicApi": {"id": "cred-id", "name": "Anthropic"}},
                }
            ],
            "connections": {},
        }

        nodes = _collect_nodes(workflow)
        rendered = repr(nodes)

        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["safe_parameters"]["message_count"], 1)
        self.assertEqual(nodes[0]["safe_parameters"]["option_keys"], ["temperature"])
        self.assertEqual(nodes[0]["credential_types"], ["anthropicApi"])
        self.assertNotIn(secret_prompt, rendered)
        self.assertNotIn("super-secret-value", rendered)
        self.assertNotIn("cred-id", rendered)
        self.assertNotIn("Anthropic'", rendered)

    def test_http_request_body_and_headers_are_not_exposed(self):
        workflow = {
            "nodes": [
                {
                    "name": "HTTP Request",
                    "type": "n8n-nodes-base.httpRequest",
                    "parameters": {
                        "method": "POST",
                        "url": "https://example.test/api",
                        "authentication": "genericCredentialType",
                        "sendBody": True,
                        "headers": {"Authorization": "Bearer private-token"},
                        "body": {"api_key": "private-api-key"},
                    },
                }
            ],
            "connections": {},
        }

        rendered = repr(_collect_nodes(workflow))
        self.assertNotIn("private-token", rendered)
        self.assertNotIn("private-api-key", rendered)
        self.assertIn("https://example.test/api", rendered)


if __name__ == "__main__":
    unittest.main()
