"""Tests for the Flow (Nano Banana) subscription image provider. The driver is always a double."""

from __future__ import annotations

from pathlib import Path

import pytest

from lib.flow_driver import FlowDriver as RealFlowDriver
from tools.base_tool import ToolStatus
from tools.graphics.flow_image import FlowImage
from tools.video.flow_video import FlowVideo


class FakeDriver:
    last_job: dict | None = None
    raises: Exception | None = None

    def __init__(self, cdp_url=None, project_url=None):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def generate_image(self, job):
        FakeDriver.last_job = job
        if FakeDriver.raises:
            raise FakeDriver.raises
        for p in job["output_paths"]:
            Path(p).parent.mkdir(parents=True, exist_ok=True)
            Path(p).write_bytes(b"\xff\xd8jpeg")
        return {"outputs": job["output_paths"], "bytes": [6] * len(job["output_paths"]),
                "model": "🍌 Nano Banana Pro", "credits": 0, "media_id": "Chihuahua"}


@pytest.fixture(autouse=True)
def never_touch_a_real_browser(monkeypatch):
    monkeypatch.setenv("FLOW_CDP_URL", "http://127.0.0.1:9")

    class Forbidden:
        def __init__(self, *a, **k):
            raise AssertionError("a test tried to construct the real FlowDriver")

    monkeypatch.setattr("lib.flow_driver.FlowDriver", Forbidden)


@pytest.fixture
def ready(tmp_path, monkeypatch):
    FakeDriver.last_job = None
    FakeDriver.raises = None
    monkeypatch.setattr(FlowImage, "_lock_path", lambda self: tmp_path / "flow.lock")
    monkeypatch.setattr(FlowVideo, "_cdp_blocker", staticmethod(lambda url: None))
    monkeypatch.setattr("lib.flow_driver.FlowDriver", FakeDriver)
    return tmp_path


def test_status_follows_playwright_install():
    assert FlowImage().get_status() in (ToolStatus.AVAILABLE, ToolStatus.UNAVAILABLE)


def test_blocked_without_cdp_chrome(tmp_path, monkeypatch):
    monkeypatch.setattr(FlowImage, "get_status", lambda self: ToolStatus.AVAILABLE)
    r = FlowImage().execute({"prompt": "x", "output_path": str(tmp_path / "a.jpg")})
    assert not r.success and "No Chrome" in r.error


def test_single_image_maps_model_and_aspect(ready, monkeypatch):
    monkeypatch.setattr(FlowImage, "get_status", lambda self: ToolStatus.AVAILABLE)
    out = ready / "dog.jpg"
    r = FlowImage().execute({"prompt": "a dog", "model_variant": "2", "aspect_ratio": "9:16", "output_path": str(out)})
    assert r.success, r.error
    assert FakeDriver.last_job["model"] == "🍌 Nano Banana 2"
    assert FakeDriver.last_job["aspect_ratio"] == "9:16"
    assert FakeDriver.last_job["count"] == 1
    assert r.artifacts == [str(out)] and out.exists()
    assert r.data["flow_credits"] == 0


def test_batch_numbers_outputs(ready, monkeypatch):
    monkeypatch.setattr(FlowImage, "get_status", lambda self: ToolStatus.AVAILABLE)
    r = FlowImage().execute({"prompt": "frames", "n": 3, "output_path": str(ready / "cat.jpg")})
    assert r.success, r.error
    assert [Path(p).name for p in r.artifacts] == ["cat_1.jpg", "cat_2.jpg", "cat_3.jpg"]


def test_driver_failure_is_reported(ready, monkeypatch):
    from lib.flow_driver import FlowError

    monkeypatch.setattr(FlowImage, "get_status", lambda self: ToolStatus.AVAILABLE)
    FakeDriver.raises = FlowError("settings: Flow does not offer 'x5'")
    r = FlowImage().execute({"prompt": "x", "output_path": str(ready / "a.jpg")})
    assert not r.success and "does not offer" in r.error
    assert not (ready / "flow.lock").exists()


class TestDownloadTier:
    """_pick_row chooses the download row; the plan-gated tier must never be clicked."""

    ROWS = [
        (100.0, "720p Kích thước gốc"),
        (140.0, "1080p Đã tăng độ phân giải"),
        (180.0, "4K Đã tăng độ phân giải Nâng cấp"),
    ]

    def test_native_picks_the_rendered_size(self):
        assert RealFlowDriver._pick_row(self.ROWS, "native")[1].startswith("720p")

    def test_max_picks_the_best_allowed_not_the_paywalled_one(self):
        assert RealFlowDriver._pick_row(self.ROWS, "max")[1].startswith("1080p")

    def test_max_skips_the_animated_gif_row(self):
        rows = [(100.0, "270p Ảnh GIF động"), (140.0, "1K Kích thước gốc")]
        assert RealFlowDriver._pick_row(rows, "max")[1].startswith("1K")

    def test_max_falls_back_to_native_when_nothing_is_allowed(self):
        rows = [(100.0, "1K Kích thước gốc"), (140.0, "4K Đã tăng độ phân giải Nâng cấp")]
        assert RealFlowDriver._pick_row(rows, "max")[1].startswith("1K")
