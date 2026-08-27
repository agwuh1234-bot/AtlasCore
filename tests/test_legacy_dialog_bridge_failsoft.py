import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LegacyDialogBridgeFailSoftTests(unittest.TestCase):
    def test_custom_dialog_confirm_and_prompt_have_native_fallbacks(self):
        source = (ROOT / "web" / "legacy-dialog-bridge.js").read_text(encoding="utf-8")
        self.assertIn("try{return await window.AtlasDialog.confirm(options)}catch(_err){}", source)
        self.assertIn("return nativeConfirm(fallback)", source)
        self.assertIn("try{return await window.AtlasDialog.prompt(options)}catch(_err){}", source)
        self.assertIn("return nativePrompt(fallback,value)", source)

    def test_native_dialog_failures_cancel_safely(self):
        source = (ROOT / "web" / "legacy-dialog-bridge.js").read_text(encoding="utf-8")
        self.assertIn("function nativeConfirm(fallback){try{return window.confirm(fallback)}catch(_err){return false}}", source)
        self.assertIn("function nativePrompt(fallback,value=''){try{return window.prompt(fallback,value)}catch(_err){return null}}", source)

    def test_synthetic_clicks_clear_stale_bypass_flags(self):
        source = (ROOT / "web" / "legacy-dialog-bridge.js").read_text(encoding="utf-8")
        self.assertIn("function clearBypass(button)", source)
        self.assertIn("window.confirm=original;clearBypass(button)", source)
        self.assertIn("window.prompt=original;clearBypass(button)", source)

    def test_duplicate_taps_are_guarded_while_dialog_is_pending(self):
        source = (ROOT / "web" / "legacy-dialog-bridge.js").read_text(encoding="utf-8")
        self.assertIn("const PENDING=new WeakSet()", source)
        self.assertIn("if(PENDING.has(button))return false", source)
        self.assertIn("PENDING.add(button)", source)
        self.assertIn("PENDING.delete(button)", source)
        self.assertIn("void guardedHandle(button)", source)

    def test_pending_dialog_state_is_exposed_and_cleared_for_assistive_tech(self):
        source = (ROOT / "web" / "legacy-dialog-bridge.js").read_text(encoding="utf-8")
        self.assertIn("function markPending(button,pending)", source)
        self.assertIn("button.setAttribute('aria-busy','true')", source)
        self.assertIn("button.setAttribute('aria-disabled','true')", source)
        self.assertIn("markPending(button,true)", source)
        self.assertIn("finally{markPending(button,false);PENDING.delete(button)}", source)

    def test_pending_dialog_restores_preexisting_accessibility_attributes(self):
        source = (ROOT / "web" / "legacy-dialog-bridge.js").read_text(encoding="utf-8")
        self.assertIn("const PENDING_A11Y=new WeakMap()", source)
        self.assertIn("busy:button.getAttribute('aria-busy')", source)
        self.assertIn("disabled:button.getAttribute('aria-disabled')", source)
        self.assertIn("function restoreAttr(button,name,value)", source)
        self.assertIn("restoreAttr(button,'aria-busy',previous.busy)", source)
        self.assertIn("restoreAttr(button,'aria-disabled',previous.disabled)", source)
        self.assertIn("PENDING_A11Y.delete(button)", source)


if __name__ == "__main__":
    unittest.main()
