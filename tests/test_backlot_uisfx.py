"""Tests for the optional, locally served UISFX frontend dependency."""

from pathlib import Path

from backlot import server


def test_uisfx_bundle_mount_is_optional(tmp_path, monkeypatch):
    """A missing npm install must not prevent Backlot from starting."""
    missing_dist = tmp_path / "missing" / "dist"
    monkeypatch.setattr(server, "UISFX_DIST_DIR", missing_dist)

    app_without_uisfx = server.create_app()
    assert not any(getattr(route, "name", None) == "uisfx" for route in app_without_uisfx.routes)

    dist = tmp_path / "node_modules" / "uisfx" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.js").write_text("export function createUISFX() {}", encoding="utf-8")
    monkeypatch.setattr(server, "UISFX_DIST_DIR", dist)

    app_with_uisfx = server.create_app()
    route = next(route for route in app_with_uisfx.routes if getattr(route, "name", None) == "uisfx")
    assert route.path == "/vendor/uisfx"
    assert Path(route.app.directory) == dist
