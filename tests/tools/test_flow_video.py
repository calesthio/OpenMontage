"""Tests for the Flow (Veo / Omni) subscription video provider.

Nothing here may reach Chrome or Google Flow. The session network guard only
blocks sockets inside the test process; a real browser would escape it, spend
the developer's Flow credits, and take minutes per run. The driver is always a
double.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.base_tool import ToolStatus
from tools.video.flow_video import FlowVideo


class FakeDriver:
    """Stands in for FlowDriver. Records the job it was handed."""

    last_job: dict | None = None
    result: dict = {}
    raises: Exception | None = None

    def __init__(self, cdp_url=None, project_url=None):
        self.cdp_url = cdp_url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def generate(self, job):
        FakeDriver.last_job = job
        if FakeDriver.raises:
            raise FakeDriver.raises
        Path(job["output_path"]).parent.mkdir(parents=True, exist_ok=True)
        Path(job["output_path"]).write_bytes(b"mp4-bytes")
        return {"output": job["output_path"], "bytes": 9, **FakeDriver.result}


@pytest.fixture(autouse=True)
def never_touch_a_real_browser(monkeypatch):
    """Hard floor under every test in this module.

    The module promises it never reaches Chrome, but that promise was one
    conditional away from false: `_cdp_blocker` returns None whenever the
    developer happens to have a debug Chrome open, and the tool then drove the
    real browser during a unit test. Point the tool at a dead port and replace
    the driver by default, so reaching a browser takes a deliberate opt-in
    rather than an ambient condition.
    """
    monkeypatch.setenv("FLOW_CDP_URL", "http://127.0.0.1:9")   # discard port

    class Forbidden:
        def __init__(self, *a, **k):
            raise AssertionError("a test tried to construct the real FlowDriver")

    monkeypatch.setattr("lib.flow_driver.FlowDriver", Forbidden)


@pytest.fixture
def ready(tmp_path, monkeypatch):
    """Playwright installed, Chrome answering on CDP, driver stubbed."""
    FakeDriver.last_job = None
    FakeDriver.result = {"model": "Omni 1.1 Flash", "credits": 7, "media_id": "m-1"}
    FakeDriver.raises = None

    monkeypatch.setattr(FlowVideo, "_lock_path", lambda self: tmp_path / "flow.lock")
    monkeypatch.setattr(FlowVideo, "_cdp_blocker", staticmethod(lambda url: None))
    monkeypatch.setattr("lib.flow_driver.FlowDriver", FakeDriver)
    monkeypatch.setattr("tools.video._shared.probe_output",
                        lambda p: {"duration_seconds": 4.0, "file_size_bytes": 9})
    return tmp_path


class TestStatus:
    def test_available_when_playwright_is_installed(self):
        assert FlowVideo().get_status() is ToolStatus.AVAILABLE

    def test_available_even_though_chrome_is_not_running(self, monkeypatch):
        # The installed-vs-ready split. video_selector drops anything that is
        # not AVAILABLE, so reporting liveness here would hide the provider on
        # every machine where Chrome happens to be closed — and the user would
        # never be told to start it.
        monkeypatch.setattr(FlowVideo, "_cdp_blocker", staticmethod(lambda url: "down"))
        assert FlowVideo().get_status() is ToolStatus.AVAILABLE

    def test_unavailable_without_playwright(self, monkeypatch):
        import builtins

        real_import = builtins.__import__

        def no_playwright(name, *args, **kwargs):
            if name == "playwright":
                raise ImportError("no playwright")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", no_playwright)
        assert FlowVideo().get_status() is ToolStatus.UNAVAILABLE

    def test_never_reports_degraded(self, monkeypatch):
        # video_selector._tool_selectable() skips DEGRADED without a word, so a
        # DEGRADED value here would be an invisible provider, not a warning.
        assert FlowVideo().get_status() is not ToolStatus.DEGRADED


class TestCdpBlocker:
    def test_names_the_launcher_and_why_the_profile_matters(self, tmp_path, monkeypatch):
        # FLOW_CDP_URL points at the discard port, so this exercises the real
        # blocker rather than depending on whether a browser happens to be open.
        monkeypatch.setattr(FlowVideo, "_lock_path", lambda self: tmp_path / "flow.lock")
        result = FlowVideo().execute({"prompt": "x", "output_path": str(tmp_path / "a.mp4")})
        assert not result.success
        # The recovery step has to be runnable as written. Telling someone to add
        # a debugging port is not enough on its own: on the default profile Chrome
        # ignores it, so the message must also carry the reason a dedicated
        # profile is involved, or they will "fix" it and hit the same wall.
        assert "scripts/flow_chrome.py" in result.error
        assert "default profile" in result.error


class TestExecute:
    def test_happy_path_reports_what_flow_actually_used(self, ready, monkeypatch):
        out = ready / "clip.mp4"
        result = FlowVideo().execute({
            "prompt": "a kite over a salt flat",
            "model_variant": "Omni", "duration": "4", "aspect_ratio": "16:9",
            "output_path": str(out),
        })

        assert result.success, result.error
        assert result.artifacts == [str(out.resolve())]
        # Read back from the UI, not echoed from the request: reporting an
        # unverified model is how early runs claimed Veo while using Omni.
        assert result.data["flow_model"] == "Omni 1.1 Flash"
        assert result.data["flow_credits"] == 7
        # No money moves, so the cost tracker must not be told otherwise.
        assert result.cost_usd == 0.0
        assert Path(FakeDriver.last_job["output_path"]).is_absolute()

    def test_default_output_path_lands_under_projects_scratch_not_cwd(self, ready, monkeypatch):
        # A caller that omits output_path must never get a bare filename
        # resolved against whatever the shell's cwd happened to be — that is
        # exactly how a stray flow_output_*.mp4 used to end up loose at the
        # repo root, outside every project.
        monkeypatch.setattr("tools.video.flow_video.PROJECTS_DIR", ready)

        result = FlowVideo().execute({"prompt": "x"})

        assert result.success, result.error
        scratch = ready / "_flow_video_scratch"
        assert scratch.is_dir()
        out = Path(result.artifacts[0])
        assert out.parent == scratch
        assert out.name.startswith("flow_output_") and out.suffix == ".mp4"

    def test_driver_error_is_surfaced(self, ready):
        from lib.flow_driver import FlowError

        FakeDriver.raises = FlowError("settings: model dropdown not found")
        result = FlowVideo().execute({"prompt": "x", "output_path": str(ready / "a.mp4")})
        assert not result.success
        assert "model dropdown not found" in result.error

    def test_unexpected_error_is_surfaced_not_swallowed(self, ready):
        FakeDriver.raises = RuntimeError("playwright exploded")
        result = FlowVideo().execute({"prompt": "x", "output_path": str(ready / "a.mp4")})
        assert not result.success
        assert "playwright exploded" in result.error

    def test_image_to_video_requires_a_real_file(self, ready):
        result = FlowVideo().execute({
            "prompt": "x", "operation": "image_to_video",
            "reference_image_path": str(ready / "missing.png"),
            "output_path": str(ready / "a.mp4"),
        })
        assert not result.success
        assert "reference_image_path" in result.error

    def test_concurrent_run_is_refused(self, ready):
        (ready / "flow.lock").write_text("held", encoding="utf-8")
        result = FlowVideo().execute({"prompt": "x", "output_path": str(ready / "a.mp4")})
        assert not result.success
        assert "in progress" in result.error
        assert FakeDriver.last_job is None

    def test_lock_is_released_after_a_failure(self, ready):
        FakeDriver.raises = RuntimeError("boom")
        FlowVideo().execute({"prompt": "x", "output_path": str(ready / "a.mp4")})
        # A stuck lock would wedge every later run with a confusing message.
        assert not (ready / "flow.lock").exists()


class TestReturnedClipMatchesRequest:
    """A valid mp4 is not proof it is the right mp4.

    Two runs during development downloaded an older clip from the same Flow
    project and reported success — ffprobe was happy, the file played, and only
    the duration revealed it was not the clip just generated.
    """

    def test_rejects_a_clip_of_the_wrong_duration(self, ready, monkeypatch):
        monkeypatch.setattr("tools.video._shared.probe_output",
                            lambda p: {"duration_seconds": 8.0})
        result = FlowVideo().execute({
            "prompt": "x", "duration": "4", "output_path": str(ready / "a.mp4")})
        assert not result.success
        assert "8.0s clip but 4s was requested" in result.error

    def test_accepts_a_clip_within_a_second(self, ready, monkeypatch):
        monkeypatch.setattr("tools.video._shared.probe_output",
                            lambda p: {"duration_seconds": 4.01})
        result = FlowVideo().execute({
            "prompt": "x", "duration": "4", "output_path": str(ready / "a.mp4")})
        assert result.success, result.error

    def test_passes_when_ffprobe_is_unavailable(self, ready, monkeypatch):
        # probe_output returns only a file size when ffprobe is missing; that
        # must not turn into a false rejection.
        monkeypatch.setattr("tools.video._shared.probe_output",
                            lambda p: {"file_size_bytes": 9})
        result = FlowVideo().execute({
            "prompt": "x", "duration": "4", "output_path": str(ready / "a.mp4")})
        assert result.success, result.error


class TestOptionalDuration:
    """Veo exposes no duration control in Flow — only the Omni models do.

    A request naming a duration the chosen model cannot honour must fail in the
    browser before any credit is spent. When none is asked for, the tool must
    not invent one, and the length guard must not fire.
    """

    def test_duration_is_not_sent_when_not_requested(self, ready, monkeypatch):
        monkeypatch.setattr("tools.video._shared.probe_output",
                            lambda p: {"duration_seconds": 8.0})
        result = FlowVideo().execute({"prompt": "x", "output_path": str(ready / "a.mp4")})
        assert result.success, result.error
        # No duration asked for, so an 8s clip is not a mismatch.
        assert FakeDriver.last_job["duration"] is None

    def test_resolution_is_not_sent_when_not_requested(self, ready):
        FlowVideo().execute({"prompt": "x", "output_path": str(ready / "a.mp4")})
        assert FakeDriver.last_job["resolution"] is None


def test_cost_is_zero_dollars_for_any_request():
    tool = FlowVideo()
    assert tool.estimate_cost({"duration": "4"}) == 0.0
    assert tool.estimate_cost({"model_variant": "Quality"}) == 0.0


class TestModelLabelCleaning:
    """The reported model must be the label a human sees.

    Flow glues a Material Symbols ligature to it — "volume_up\nVeo 3.1 - Fast"
    for an option, "…arrow_drop_down" for the closed row. A real run reported
    the model as "volume_up Veo 3.1 - Fast", in the very field whose whole
    purpose is saying what Flow actually used.
    """

    @pytest.mark.parametrize("raw,expected", [
        ("volume_up\nVeo 3.1 - Fast", "Veo 3.1 - Fast"),
        ("volume_upOmni 1.1 Flash", "Omni 1.1 Flash"),
        ("Veo 3.1 - Qualityarrow_drop_down", "Veo 3.1 - Quality"),
        ("Omni 1.1 Flash arrow_drop_down", "Omni 1.1 Flash"),
        ("Veo 3.1 - Lite", "Veo 3.1 - Lite"),
        ("", ""),
    ])
    def test_ligatures_are_stripped(self, raw, expected):
        from lib.flow_driver import _clean_model_label

        assert _clean_model_label(raw) == expected
