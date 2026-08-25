from __future__ import annotations

from pathlib import Path
import ast
import json
import os
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent


def read_text(rel_path: str) -> str:
    path = ROOT / rel_path
    assert path.exists(), f"Missing required file: {rel_path}"
    return path.read_text(encoding="utf-8")


def main() -> None:
    main_py = ROOT / "main.py"
    assert main_py.exists(), "main.py must exist"
    main_text = main_py.read_text(encoding="utf-8")
    ast.parse(main_text, filename="main.py")
    for module_name in ("atlas_store.py", "atlas_router.py", "atlas_knowledge.py", "atlas_push.py", "atlas_scheduler.py"):
        module_text = read_text(module_name)
        ast.parse(module_text, filename=module_name)
    assert len(main_text) > 30000, f"main.py text too short: {len(main_text)} <= 30000"
    for needle in [
        "async def run_atlas",
        "@api.post(\"/app-jobs\")",
        "@api.get(\"/health\")",
        "claude_used",
        "github_replace_text",
        "app_session_token_valid",
        "APP_JOB_MAX_ACTIVE",
        "STORE = AtlasStore",
        "async def _app_job_worker",
        '@api.get("/app-projects")',
        '@api.get("/app-budget")',
        '@api.get("/app-plugins")',
        '@api.get("/app-files")',
        '@api.get("/app-push/config")',
        '@api.get("/app-schedules")',
        '@api.post("/app-schedules")',
        '@api.patch("/app-schedules/{schedule_id}")',
        '@api.post("/app-push/subscribe")',
        '@api.post("/app-push/test")',
        '@api.get("/app-files/{file_id}")',
        '@api.delete("/app-files/{file_id}")',
        '@api.get("/app-system-status")',
        '@api.get("/app-permissions")',
        '@api.get("/app-projects/{project_id}/memory-health")',
        '@api.patch("/app-projects/{project_id}/memory/{memory_id}")',
        '@api.delete("/app-projects/{project_id}/memory/{memory_id}")',
        "SHOPIFY_PLAYBOOK",
        "MODEL_ROUTER",
    ]:
        assert needle in main_text, f"main.py missing required text: {needle}"

    index_text = read_text("web/index.html")
    for needle in ["messageInput", "sendBtn", "stopBtn", "/app/projects.js", "/app/files.js", "/app/projects.css", "/app/recovery.js", "/app/app.js", "/app/ux.js", "/app/status.js", "/app/format.js", "/app/shell.js", "/app/shell.css"]:
        assert needle in index_text, f"web/index.html missing required text: {needle}"

    app_js = read_text("web/app.js")
    assert len(app_js) > 5000, f"web/app.js text too short: {len(app_js)} <= 5000"
    for needle in ["pollJob", "SpeechRecognition", "speechSynthesis", "/app-jobs"]:
        assert needle in app_js, f"web/app.js missing required text: {needle}"

    projects_js = read_text("web/projects.js")
    for needle in ["atlas_active_project_id", "project_id", "/app-projects", "/app-budget"]:
        assert needle in projects_js, f"web/projects.js missing required text: {needle}"

    files_js = read_text("web/files.js")
    for needle in ["atlasFileCenter", "selectedIds", "/app-files/", "attachments"]:
        assert needle in files_js, f"web/files.js missing required text: {needle}"

    projects_css = read_text("web/projects.css")
    assert ".project-switcher" in projects_css

    shell_js = read_text("web/shell.js")
    for needle in ["bottomTabs", "visualViewport", "workspacePanels", "/app-plugins", "/app-actions", "/app-files", "/app-schedules", "loadSchedules", "/memory-health", "memory_scope", "/app-system-status", "/app-permissions"]:
        assert needle in shell_js, f"web/shell.js missing required text: {needle}"

    shell_css = read_text("web/shell.css")
    for needle in ["position: fixed", ".bottom-tabs", ".workspace-panel", ".composer-tools"]:
        assert needle in shell_css, f"web/shell.css missing required text: {needle}"

    control_center_js = read_text("web/control_center.js")
    for needle in ["conversationModeBtn", "stopVoiceBtn", "SpeechRecognition", "requestSubmit"]:
        assert needle in control_center_js, f"web/control_center.js missing required text: {needle}"

    push_js = read_text("web/push.js")
    for needle in ["PushManager", "applicationServerKey", "/app-push/subscribe", "/app-push/test"]:
        assert needle in push_js, f"web/push.js missing required text: {needle}"

    recovery_js = read_text("web/recovery.js")
    assert len(recovery_js) > 1000, f"web/recovery.js text too short: {len(recovery_js)} <= 1000"
    assert recovery_js != "test", "web/recovery.js must not be exactly 'test'"
    for needle in ["atlas_safe_job_recovery", "allow_writes===false"]:
        assert needle in recovery_js, f"web/recovery.js missing required text: {needle}"

    sw_js = read_text("web/sw.js")
    for needle in ["projects.js", "files.js", "projects.css", "recovery.js", "control_center.js", "push.js", "app.js", "ux.js", "status.js", "format.js", "shell.js", "shell.css"]:
        assert needle in sw_js, f"web/sw.js missing required asset: {needle}"

    format_js = read_text("web/format.js")
    assert "data-safe-formatted" in format_js, "web/format.js missing required text: data-safe-formatted"
    assert "URL_RE" in format_js, "web/format.js missing required text: URL_RE"
    assert "code-block" in format_js, "web/format.js missing required text: code-block"
    assert "eval(" not in format_js, "web/format.js must not contain eval("

    requirements = read_text("requirements.txt")
    assert "openai>=2.28,<3" in requirements
    assert "psycopg[binary]>=3.2,<4" in requirements
    assert "pywebpush>=2.0,<3" in requirements

    manifest = json.loads(read_text("web/manifest.json"))
    assert manifest.get("display") == "standalone"
    assert manifest.get("start_url") == "/"
    assert isinstance(manifest.get("icons"), list) and manifest.get("icons")

    format_css = read_text("web/format.css")
    assert ".code-block" in format_css
    assert ".prose-link" in format_css

    test_env = os.environ.copy()
    # Pre-deploy tests must never connect to or mutate the production database.
    test_env.pop("DATABASE_URL", None)
    test_env.pop("ATLAS_DATABASE_URL", None)
    with tempfile.TemporaryDirectory(prefix="atlas-smoke-") as temp_dir:
        test_env["ATLAS_DB_PATH"] = str(Path(temp_dir) / "atlas-test.db")
        tests = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=ROOT,
            env=test_env,
            text=True,
            capture_output=True,
            timeout=60,
        )
    if tests.returncode != 0:
        print(tests.stdout, file=sys.stderr)
        print(tests.stderr, file=sys.stderr)
        raise AssertionError("Atlas unit tests failed")
    print(tests.stderr.strip())
    print("ATLAS_SMOKE_OK")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"AssertionError: {exc}", file=sys.stderr)
        raise
