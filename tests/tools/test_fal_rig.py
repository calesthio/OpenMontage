"""Contracts for `fal_rig` (Meshy humanoid auto-rigging + preset clips via fal.ai).

All transport is faked: the session-wide socket guard in tests/conftest.py blocks
real network calls, and fal bills per request.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools.base_tool import ToolStatus
from tools.graphics import fal_rig
from tools.graphics.fal_rig import PRESETS, FalRig
from tools.tool_registry import ToolRegistry

MODEL = "fal-ai/meshy/rigging/multi-animation"
QUEUE_URL = f"https://queue.fal.run/{MODEL}"
STATUS_URL = "https://queue.example/status"
RESULT_URL = "https://queue.example/result"


class _Response:
    def __init__(self, payload: Any = None, content: bytes = b""):
        self._payload = payload
        self.content = content

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class _FakeTime:
    """Stand-in for the `time` module so polling never waits and timeouts are deterministic."""

    def __init__(self) -> None:
        self.now = 1_000.0
        self.slept: list[float] = []

    def time(self) -> float:
        return self.now

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def _file(name: str, content_type: str, url: str | None = None) -> dict[str, Any]:
    return {
        "url": url or f"https://cdn.example/rig/{name}",
        "content_type": content_type,
        "file_name": name,
        "file_size": 42,
    }


GLB = "model/gltf-binary"
BIN = "application/octet-stream"


def _completed_payload() -> dict[str, Any]:
    """Mirrors a real multi-animation response (two requested clips)."""
    return {
        "rigged_character_glb": _file("rigged_character.glb", GLB),
        "rigged_character_fbx": _file("rigged_character.fbx", BIN),
        "basic_animations": {
            "walking_glb": _file("walking.glb", GLB),
            "walking_fbx": _file("walking.fbx", BIN),
            "walking_armature_glb": _file("walking_armature.glb", GLB),
            "running_glb": _file("running.glb", GLB),
            "running_fbx": _file("running.fbx", BIN),
            "running_armature_glb": _file("running_armature.glb", GLB),
        },
        "animations": [
            {
                "action_id": 613,
                "animation_glb": _file("animation.glb", GLB, "https://cdn.example/clip0/animation.glb"),
                "animation_fbx": _file("animation.fbx", BIN, "https://cdn.example/clip0/animation.fbx"),
            },
            {
                "action_id": 28,
                "animation_glb": _file("animation.glb", GLB, "https://cdn.example/clip1/animation.glb"),
                # Signed URL without an extension: the suffix must come from file_name.
                "animation_fbx": _file("animation.fbx", BIN, "https://cdn.example/clip1/download?sig=abc"),
            },
        ],
        "rig_task_id": "rig-task-1",
    }


def _install_transport(monkeypatch, *, statuses: list[str], result: dict[str, Any] | None):
    """Fake `requests` for submit -> poll -> fetch result -> download files."""
    calls: dict[str, Any] = {"post": [], "status_polls": 0, "downloads": []}
    status_iter = iter(statuses)

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["post"].append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return _Response({"request_id": "req-1", "status_url": STATUS_URL, "response_url": RESULT_URL})

    def fake_get(url, headers=None, timeout=None, **_kwargs):
        if url == STATUS_URL:
            calls["status_polls"] += 1
            return _Response({"status": next(status_iter, statuses[-1])})
        if url == RESULT_URL:
            return _Response(result)
        calls["downloads"].append(url)
        return _Response(content=url.encode("utf-8"))

    monkeypatch.setattr(fal_rig.requests, "post", fake_post)
    monkeypatch.setattr(fal_rig.requests, "get", fake_get)
    return calls


def _contains_key(value: Any, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_key(v, key) for v in value.values())
    if isinstance(value, list):
        return any(_contains_key(v, key) for v in value)
    return False


@pytest.fixture()
def fake_time(monkeypatch) -> _FakeTime:
    clock = _FakeTime()
    monkeypatch.setattr(fal_rig, "time", clock)
    return clock


@pytest.fixture()
def fal_key(monkeypatch) -> None:
    monkeypatch.setenv("FAL_KEY", "test-key")
    monkeypatch.delenv("FAL_AI_API_KEY", raising=False)


# ---- Discovery and contract ----


def test_registry_discovers_fal_rig_under_character_rigging():
    registry = ToolRegistry()
    registry.discover("tools")
    assert {tool.name for tool in registry.get_by_capability("character_rigging")} >= {"fal_rig"}
    info = registry.get("fal_rig").get_info()
    assert info["provider"] == "fal"
    assert info["runtime"] == "api"
    assert info["agent_skills"] == ["3d-asset-generation"]
    assert set(info["input_schema"]["required"]) == {"animation_action_ids", "output_dir"}


def test_presets_are_within_the_published_library_range():
    assert PRESETS["idle"] == 0
    assert PRESETS["walk_inplace"] == 613
    assert all(0 <= action_id <= 696 for action_id in PRESETS.values())
    assert len(set(PRESETS.values())) == len(PRESETS)


def test_status_follows_fal_key(monkeypatch):
    monkeypatch.delenv("FAL_KEY", raising=False)
    monkeypatch.delenv("FAL_AI_API_KEY", raising=False)
    assert FalRig().get_status() == ToolStatus.UNAVAILABLE
    monkeypatch.setenv("FAL_AI_API_KEY", "alias-key")
    assert FalRig().get_status() == ToolStatus.AVAILABLE


# ---- Cost model: $0.20 per request + $0.12 per distinct clip ----


@pytest.mark.parametrize(
    ("ids", "expected"),
    [
        ([], 0.20),
        ([30], 0.32),
        ([30, 30, 28], 0.44),  # duplicates are de-duplicated server-side, so billed once
        ([0, 28, 613], 0.56),  # fal's own example: "3 clips = $0.56"
        (list(range(10)), 1.40),
    ],
)
def test_estimate_cost_counts_distinct_clip_ids(ids, expected):
    assert FalRig().estimate_cost({"animation_action_ids": ids}) == expected


def test_dry_run_reports_estimated_cost_without_calling_fal(monkeypatch, fal_key):
    monkeypatch.setattr(fal_rig.requests, "post", lambda *a, **k: pytest.fail("dry_run must not submit"))
    report = FalRig().dry_run({"animation_action_ids": [30, 28], "output_dir": "/tmp/x"})
    assert report["estimated_cost_usd"] == 0.44
    assert report["status"] == "available"


# ---- Input validation happens before any paid call ----


def _no_submit(monkeypatch) -> None:
    monkeypatch.setattr(fal_rig.requests, "post", lambda *a, **k: pytest.fail("must not submit to fal"))


def test_missing_key_is_reported_before_submit(monkeypatch, tmp_path):
    monkeypatch.delenv("FAL_KEY", raising=False)
    monkeypatch.delenv("FAL_AI_API_KEY", raising=False)
    _no_submit(monkeypatch)
    result = FalRig().execute({
        "model_url": "https://cdn.example/in/hero.glb", "animation_action_ids": [30], "output_dir": str(tmp_path),
    })
    assert not result.success
    assert "key" in (result.error or "").lower()


@pytest.mark.parametrize(
    ("inputs", "fragment"),
    [
        ({"model_url": "https://cdn.example/in/hero.glb", "animation_action_ids": []}, "at least one"),
        ({"model_url": "https://cdn.example/in/hero.glb", "animation_action_ids": [697]}, "0-696"),
        ({"model_url": "https://cdn.example/in/hero.glb", "animation_action_ids": [-1]}, "0-696"),
        ({"model_url": "https://cdn.example/in/hero.glb", "animation_action_ids": list(range(11))}, "at most 10"),
        ({"animation_action_ids": [30]}, "model_url or model_path"),
    ],
)
def test_invalid_inputs_fail_fast(monkeypatch, fal_key, tmp_path, inputs, fragment):
    _no_submit(monkeypatch)
    result = FalRig().execute({**inputs, "output_dir": str(tmp_path)})
    assert not result.success
    assert fragment in (result.error or "")


def test_ten_distinct_ids_with_repeats_is_still_allowed(monkeypatch, fal_key, fake_time, tmp_path):
    """11 entries but only 10 distinct IDs: fal de-duplicates, so the request is valid."""
    calls = _install_transport(monkeypatch, statuses=["COMPLETED"], result={
        "rigged_character_glb": _file("rigged_character.glb", GLB),
    })
    result = FalRig().execute({
        "model_url": "https://cdn.example/in/hero.glb",
        "animation_action_ids": list(range(10)) + [0],
        "output_dir": str(tmp_path),
    })
    assert result.success, result.error
    assert calls["post"][0]["json"]["animation_action_ids"] == list(range(10))


# ---- Happy path: payload shape, polling, download naming, provenance ----


def test_submit_poll_download_and_provenance(monkeypatch, fal_key, fake_time, tmp_path):
    calls = _install_transport(
        monkeypatch,
        statuses=["IN_QUEUE", "IN_PROGRESS", "COMPLETED"],
        result=_completed_payload(),
    )
    out_dir = tmp_path / "rigged" / "hero"
    result = FalRig().execute({
        "model_url": "https://cdn.example/in/hero.glb",
        "height_meters": 1.2,
        "animation_action_ids": [613, 28, 613],  # repeat collapses to one clip
        "output_dir": str(out_dir),
    })
    assert result.success, result.error

    # Submit payload and headers
    assert len(calls["post"]) == 1
    submit = calls["post"][0]
    assert submit["url"] == QUEUE_URL
    assert submit["headers"] == {"Authorization": "Key test-key", "Content-Type": "application/json"}
    assert submit["json"] == {
        "model_url": "https://cdn.example/in/hero.glb",
        "height_meters": 1.2,
        "animation_action_ids": [613, 28],
        "enable_safety_checker": True,
    }

    # Polled until COMPLETED, sleeping between non-terminal statuses
    assert calls["status_polls"] == 3
    assert fake_time.slept == [5, 5]

    # One file per rigged mesh, basic animation and clip file, named after the input stem
    names = [Path(p).name for p in result.artifacts]
    assert names == [
        "hero_rigged.glb",
        "hero_rigged.fbx",
        "hero_basic_walking_glb.glb",
        "hero_basic_walking_fbx.fbx",
        "hero_basic_walking_armature_glb.glb",
        "hero_basic_running_glb.glb",
        "hero_basic_running_fbx.fbx",
        "hero_basic_running_armature_glb.glb",
        "hero_anim00_id613_animation_glb.glb",
        "hero_anim00_id613_animation_fbx.fbx",
        "hero_anim01_id28_animation_glb.glb",
        "hero_anim01_id28_animation_fbx.fbx",
        "hero_rig.provenance.json",
    ]
    for path in result.artifacts[:-1]:
        assert Path(path).parent == out_dir.resolve()
    # Downloaded bytes land in the matching file (the fake returns the URL as content)
    assert (out_dir / "hero_rigged.glb").read_bytes() == b"https://cdn.example/rig/rigged_character.glb"
    assert (out_dir / "hero_anim01_id28_animation_fbx.fbx").read_bytes() == b"https://cdn.example/clip1/download?sig=abc"
    assert len(calls["downloads"]) == 12

    # ToolResult envelope
    assert result.model == MODEL
    assert result.cost_usd == 0.44
    assert result.duration_seconds >= 0
    assert result.data["provider"] == "fal"
    assert result.data["rig_task_id"] == "rig-task-1"
    assert result.data["outputs"] == result.artifacts[:-1]

    # Provenance: metadata kept, every signed URL stripped
    provenance = json.loads((out_dir / "hero_rig.provenance.json").read_text(encoding="utf-8"))
    assert provenance["provider"] == "fal"
    assert provenance["model"] == MODEL
    assert provenance["request_id"] == "req-1"
    assert provenance["rig_task_id"] == "rig-task-1"
    assert provenance["height_meters"] == 1.2
    assert provenance["animation_action_ids"] == [613, 28]
    assert provenance["outputs"] == result.artifacts[:-1]
    assert provenance["response"]["animations"][1]["action_id"] == 28
    assert provenance["response"]["rigged_character_glb"]["file_name"] == "rigged_character.glb"
    assert not _contains_key(provenance["response"], "url")
    assert "cdn.example" not in json.dumps(provenance["response"])


def test_local_model_is_uploaded_and_dotted_stem_is_preserved(monkeypatch, fal_key, fake_time, tmp_path):
    uploaded: list[str] = []

    def fake_upload(path: str, content_type=None) -> str:
        uploaded.append(path)
        return "https://cdn.example/uploaded/model.glb"

    monkeypatch.setattr("tools.video._shared.upload_file_fal", fake_upload)
    calls = _install_transport(monkeypatch, statuses=["COMPLETED"], result={
        "rigged_character_glb": _file("rigged_character.glb", GLB),
        "rigged_character_fbx": _file("rigged_character.fbx", BIN),
        "rig_task_id": "rig-task-2",
    })
    model = tmp_path / "alfie.tpose.glb"
    model.write_bytes(b"glb")
    out_dir = tmp_path / "out"
    result = FalRig().execute({
        "model_path": str(model), "animation_action_ids": [0], "output_dir": str(out_dir),
    })
    assert result.success, result.error
    assert uploaded == [str(model)]
    assert calls["post"][0]["json"]["model_url"] == "https://cdn.example/uploaded/model.glb"
    assert calls["post"][0]["json"]["height_meters"] == 1.7
    # Stem comes from the local file; its dotted part must survive the extension swap
    assert sorted(p.name for p in out_dir.iterdir()) == [
        "alfie.tpose_rig.provenance.json",
        "alfie.tpose_rigged.fbx",
        "alfie.tpose_rigged.glb",
    ]
    assert result.cost_usd == 0.32


def test_upload_failure_is_reported_not_raised(monkeypatch, fal_key, fake_time, tmp_path):
    def failing_upload(path: str, content_type=None) -> str:
        raise RuntimeError("storage rejected the file")

    monkeypatch.setattr("tools.video._shared.upload_file_fal", failing_upload)
    _no_submit(monkeypatch)
    model = tmp_path / "hero.glb"
    model.write_bytes(b"glb")
    result = FalRig().execute({"model_path": str(model), "animation_action_ids": [0], "output_dir": str(tmp_path)})
    assert not result.success
    assert "storage rejected the file" in (result.error or "")


# ---- Failure paths ----


def test_failed_request_returns_error(monkeypatch, fal_key, fake_time, tmp_path):
    _install_transport(monkeypatch, statuses=["IN_PROGRESS", "FAILED"], result=None)
    result = FalRig().execute({
        "model_url": "https://cdn.example/in/hero.glb", "animation_action_ids": [30], "output_dir": str(tmp_path),
    })
    assert not result.success
    assert "failed" in (result.error or "")
    assert not list(tmp_path.iterdir())


def test_poll_timeout_returns_error(monkeypatch, fal_key, fake_time, tmp_path):
    calls = _install_transport(monkeypatch, statuses=["IN_PROGRESS"], result=None)
    result = FalRig().execute({
        "model_url": "https://cdn.example/in/hero.glb",
        "animation_action_ids": [30],
        "output_dir": str(tmp_path),
        "poll_timeout_seconds": 60,
    })
    assert not result.success
    assert "poll timeout" in (result.error or "")
    assert calls["status_polls"] == 12  # 60s / 5s between polls


def test_completed_without_files_is_an_error(monkeypatch, fal_key, fake_time, tmp_path):
    _install_transport(monkeypatch, statuses=["COMPLETED"], result={"rig_task_id": "rig-task-3", "animations": []})
    result = FalRig().execute({
        "model_url": "https://cdn.example/in/hero.glb", "animation_action_ids": [30], "output_dir": str(tmp_path),
    })
    assert not result.success
    assert "without any downloadable" in (result.error or "")
    assert not (tmp_path / "hero_rig.provenance.json").exists()
