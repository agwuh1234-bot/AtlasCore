import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LegacyDialogBridgeFailSoftTests(unittest.TestCase):
    def test_custom_dialog_confirm_and_prompt_have_native_fallbacks(self):
        source = (ROOT / "web" / "legacy-dialog-bridge.js").read_text(encoding="utf-8")
        self.assertIn("try{return await window.AtlasDialog.confirm(options)}catch(_err){}", source)
        self.assertIn("return window.confirm(fallback)", source)
        self.assertIn("try{return await window.AtlasDialog.prompt(options)}catch(_err){}", source)
        self.assertIn("return window.prompt(fallback,value)", source)

    def test_synthetic_clicks_clear_stale_bypass_flags(self):
        source = (ROOT / "web" / "legacy-dialog-bridge.js").read_text(encoding="utf-8")
        self.assertIn("function clearBypass(button)", source)
        self.assertIn("window.confirm=original;clearBypass(button)", source)
        self.assertIn("window.prompt=original;clearBypass(button)", source)


if __name__ == "__main__":
    unittest.main()
