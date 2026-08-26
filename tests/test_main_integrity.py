import pathlib
import unittest


class MainIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.path = pathlib.Path(__file__).resolve().parents[1] / "main.py"
        self.text = self.path.read_text(encoding="utf-8")
        self.lines = self.text.splitlines()

    def test_main_is_not_suspiciously_truncated(self):
        # AtlasCore main.py is intentionally large. A prior automation incident
        # replaced it with a tiny file, so fail the deployment early if that
        # ever happens again.
        self.assertGreaterEqual(
            len(self.lines),
            2000,
            f"main.py looks truncated: only {len(self.lines)} lines",
        )

    def test_critical_runtime_entrypoints_still_exist(self):
        required_markers = (
            "from fastapi import FastAPI",
            "async def run_atlas(",
            "def run_api():",
            "def main():",
            'if __name__ == "__main__":',
            "app.run_polling()",
        )
        missing = [marker for marker in required_markers if marker not in self.text]
        self.assertEqual(missing, [], f"main.py missing critical markers: {missing}")

    def test_required_secret_guards_still_exist(self):
        for env_name in (
            "BOT_TOKEN",
            "OPENAI_API_KEY",
            "GITHUB_TOKEN",
            "ATLAS_API_KEY",
            "ATLAS_BRIDGE_KEY",
            "ATLAS_APP_KEY",
        ):
            self.assertIn(env_name, self.text)


if __name__ == "__main__":
    unittest.main()
