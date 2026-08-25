import os
import unittest


for name, value in {
    "BOT_TOKEN": "000000000:test",
    "OPENAI_API_KEY": "sk-test",
    "GITHUB_TOKEN": "github-test",
    "ATLAS_API_KEY": "atlas-api-test",
    "ATLAS_BRIDGE_KEY": "atlas-bridge-test",
    "ATLAS_APP_KEY": "atlas-app-test",
}.items():
    os.environ.setdefault(name, value)

import main


class AppImportTests(unittest.TestCase):
    def test_fastapi_application_imports(self):
        self.assertEqual(main.api.title, "Atlas API")
        self.assertTrue(callable(main.run_atlas))
        self.assertEqual(main.STORE.backend, "sqlite-fallback")


if __name__ == "__main__":
    unittest.main()
