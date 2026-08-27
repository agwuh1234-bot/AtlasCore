import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LegacyDialogBridgeOrderTests(unittest.TestCase):
    def test_legacy_dialog_bridge_loads_before_workspace_modules(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        bridge = '<script src="/app/legacy-dialog-bridge.js" defer></script>'
        self.assertIn(bridge, html)
        bridge_index = html.index(bridge)

        for module in (
            "/app/projects.js",
            "/app/files.js",
            "/app/schedules.js",
            "/app/video-studio-live.js",
            "/app/automation-studio-live.js",
        ):
            marker = f'src="{module}"'
            self.assertIn(marker, html)
            self.assertLess(
                bridge_index,
                html.index(marker),
                f"legacy dialog bridge must appear before {module}",
            )


if __name__ == "__main__":
    unittest.main()
