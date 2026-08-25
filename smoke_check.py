from __future__ import annotations

from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parent


def read_text(rel_path: str) -> str:
    path = ROOT / rel_path
    assert path.exists(), f"Missing required file: {rel_path}"
    return path.read_text(encoding="utf-8")


def main() -> None:
    main_py = ROOT / "main.py"
    assert main_py.exists(), "main.py must exist"
    main_text = main_py.read_text(encoding="utf-8")
    assert len(main_text) > 30000, f"main.py text too short: {len(main_text)} <= 30000"
    for needle in [
        "async def run_atlas",
        "@api.post(\"/app-jobs\")",
        "@api.get(\"/health\")",
        "claude_used",
        "github_replace_text",
        "app_session_token_valid",
        "APP_JOB_MAX_ACTIVE",
    ]:
        assert needle in main_text, f"main.py missing required text: {needle}"

    index_text = read_text("web/index.html")
    for needle in ["messageInput", "sendBtn", "stopBtn", "/app/recovery.js", "/app/app.js", "/app/ux.js", "/app/status.js", "/app/format.js"]:
        assert needle in index_text, f"web/index.html missing required text: {needle}"

    app_js = read_text("web/app.js")
    assert len(app_js) > 5000, f"web/app.js text too short: {len(app_js)} <= 5000"
    for needle in ["pollJob", "SpeechRecognition", "speechSynthesis", "/app-jobs"]:
        assert needle in app_js, f"web/app.js missing required text: {needle}"

    recovery_js = read_text("web/recovery.js")
    assert len(recovery_js) > 1000, f"web/recovery.js text too short: {len(recovery_js)} <= 1000"
    assert recovery_js != "test", "web/recovery.js must not be exactly 'test'"
    for needle in ["atlas_safe_job_recovery", "allow_writes===false"]:
        assert needle in recovery_js, f"web/recovery.js missing required text: {needle}"

    sw_js = read_text("web/sw.js")
    for needle in ["recovery.js", "app.js", "ux.js", "status.js", "format.js"]:
        assert needle in sw_js, f"web/sw.js missing required asset: {needle}"

    format_js = read_text("web/format.js")
    assert "data-safe-formatted" in format_js, "web/format.js missing required text: data-safe-formatted"
    assert "URL_RE" in format_js, "web/format.js missing required text: URL_RE"
    assert "code-block" in format_js, "web/format.js missing required text: code-block"
    assert "eval(" not in format_js, "web/format.js must not contain eval("

    requirements = read_text("requirements.txt")
    assert requirements.strip(), "requirements.txt must not be empty"

    print("ATLAS_SMOKE_OK")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"AssertionError: {exc}", file=sys.stderr)
        raise
