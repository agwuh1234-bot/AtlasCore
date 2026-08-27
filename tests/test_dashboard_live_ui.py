from pathlib import Path


def test_live_dashboard_assets_and_endpoints_are_wired():
    root = Path(__file__).resolve().parents[1]
    index = (root / "web" / "index.html").read_text(encoding="utf-8")
    js = (root / "web" / "dashboard-live.js").read_text(encoding="utf-8")
    css = (root / "web" / "dashboard-live.css").read_text(encoding="utf-8")

    assert "/app/dashboard-live.css" in index
    assert "/app/dashboard-live.js" in index
    for endpoint in (
        "/app-projects/",
        "/app-files?project_id=",
        "/app-schedules?project_id=",
        "/memory-health",
        "/integrations/n8n/health",
        "/app-budget",
    ):
        assert endpoint in js
    assert "atlas-dashboard-live" in js
    assert "dash-live-status" in css
    assert "LIVE" in css
