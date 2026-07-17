"""Contract tests for Kling official avatar and lip-sync providers."""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.avatar.kling_avatar import KlingAvatar
from tools.avatar.kling_lip_sync import KlingLipSync
from tools.avatar.lip_sync import LipSync
from tools.avatar.talking_head import TalkingHead


def test_registry_discovers_kling_avatar(monkeypatch, isolated_tool_registry):
    monkeypatch.delenv("KLING_API_KEY", raising=False)
    isolated_tool_registry.discover("tools")
    tool = isolated_tool_registry.get("kling_avatar")
    assert tool is not None
    assert tool.capability == "avatar"
    assert tool.provider == "kling_official"


def test_avatar_schema_and_local_tool_are_distinct():
    tool = KlingAvatar()
    assert "anyOf" in tool.input_schema
    assert "allOf" in tool.input_schema
    assert "kling-official" in tool.agent_skills
    assert "avatar-video" in tool.agent_skills
    assert tool.runtime.value == "api"
    assert TalkingHead().provider == "sadtalker"
    assert TalkingHead().runtime.value == "local_gpu"


def test_avatar_payload_uses_image_and_audio_paths(tmp_path):
    image_path = tmp_path / "avatar.png"
    audio_path = tmp_path / "voice.mp3"
    image_path.write_bytes(b"image")
    audio_path.write_bytes(b"audio")

    request = KlingAvatar()._build_request(
        {
            "image_path": str(image_path),
            "audio_path": str(audio_path),
            "prompt": "warm presenter, subtle head motion",
            "mode": "pro",
            "callback_url": "https://example.com/kling/callback",
        }
    )

    assert request["path"] == "/v1/videos/avatar/image2video"
    assert request["payload"]["image"] == base64.b64encode(b"image").decode("ascii")
    assert request["payload"]["sound_file"] == base64.b64encode(b"audio").decode("ascii")
    assert request["payload"]["mode"] == "pro"
    assert request["payload"]["callback_url"] == "https://example.com/kling/callback"
    assert request["audio_source"]["type"] == "sound_file"


def test_avatar_requires_image_and_audio():
    tool = KlingAvatar()
    try:
        tool._build_request({"audio_id": "audio-a"})
    except ValueError as exc:
        assert "image_url or image_path" in str(exc)
    else:
        raise AssertionError("Kling avatar must require an image")

    try:
        tool._build_request({"image_url": "https://example.com/avatar.png"})
    except ValueError as exc:
        assert "requires audio_id" in str(exc)
    else:
        raise AssertionError("Kling avatar must require audio input")


def test_execute_downloads_avatar_video(monkeypatch, tmp_path, budget_gate_isolated):
    class FakeClient:
        def create_classic_task(self, path, payload):
            self.path = path
            self.payload = payload
            return "avatar-task-1"

        def poll_classic(self, path, task_id, result_key, timeout_seconds, poll_interval):
            assert result_key == "videos"
            return [{"url": "https://example.com/avatar.mp4"}]

        def download(self, url, output_path):
            output_path.write_bytes(b"video")
            return output_path

    monkeypatch.setenv("KLING_API_KEY", "test-key")
    # Stub accepts the max_retries kwarg execute() now passes; behavior unchanged.
    monkeypatch.setattr("tools.avatar.kling_avatar.KlingClient", lambda *args, **kwargs: FakeClient())
    monkeypatch.setattr("tools.avatar.kling_avatar.probe_output", lambda path: {"duration_seconds": 5.0})

    # Gate active; approve this paid tool via the gate's real API.
    budget_gate_isolated.approve_tool("kling_avatar")

    result = KlingAvatar().execute(
        {
            "image_url": "https://example.com/avatar.png",
            "audio_id": "audio-a",
            "output_path": str(tmp_path / "avatar.mp4"),
        }
    )

    assert result.success
    assert result.data["provider"] == "kling_official"
    assert result.data["task_id"] == "avatar-task-1"
    assert result.data["duration_seconds"] == 5.0
    assert Path(result.artifacts[0]).read_bytes() == b"video"
    assert result.cost_usd > 0


def test_avatar_cost_estimate_is_not_zero():
    tool = KlingAvatar()
    base = tool.estimate_cost({"image_url": "x", "audio_id": "a"})
    pro = tool.estimate_cost({"image_url": "x", "audio_id": "a", "mode": "pro"})
    assert base > 0
    assert pro > base
    assert tool.dry_run({"image_url": "x", "audio_id": "a"})["cost_estimate_confidence"] == "low"


def test_registry_discovers_kling_lip_sync(monkeypatch, isolated_tool_registry):
    monkeypatch.delenv("KLING_API_KEY", raising=False)
    isolated_tool_registry.discover("tools")
    tool = isolated_tool_registry.get("kling_lip_sync")
    assert tool is not None
    assert tool.capability == "avatar"
    assert tool.provider == "kling_official"


def test_lip_sync_schema_and_local_tool_are_distinct():
    tool = KlingLipSync()
    props = tool.input_schema["properties"]
    assert "kling-official" in tool.agent_skills
    assert "avatar-video" in tool.agent_skills
    assert "sound_start_time" in props
    assert "sound_end_time" in props
    assert "sound_insert_time" in props
    assert tool.runtime.value == "api"
    assert LipSync().provider == "wav2lip"
    assert LipSync().runtime.value == "local_gpu"


def test_identify_face_payload_and_local_video_rejection():
    tool = KlingLipSync()
    request = tool._build_identify_request({"video_url": "https://example.com/source.mp4"})
    assert request["path"] == "/v1/videos/identify-face"
    assert request["payload"] == {"video_url": "https://example.com/source.mp4"}

    try:
        tool._build_identify_request({"video_path": "/tmp/local.mp4"})
    except ValueError as exc:
        assert "local video paths cannot be silently uploaded" in str(exc)
    else:
        raise AssertionError("Local video paths must not be silently uploaded")


def test_advanced_lip_sync_payload_uses_face_and_audio_path(tmp_path):
    audio_path = tmp_path / "voice.mp3"
    audio_path.write_bytes(b"audio")

    request = KlingLipSync()._build_advanced_request(
        {
            "session_id": "session-a",
            "face_id": "face-a",
            "audio_path": str(audio_path),
            "sound_start_time": 0,
            "sound_end_time": 2500,
            "sound_insert_time": 500,
            "callback_url": "https://example.com/kling/callback",
        }
    )

    assert request["path"] == "/v1/videos/advanced-lip-sync"
    assert request["payload"]["session_id"] == "session-a"
    assert request["payload"]["face_choose"] == [
        {
            "face_id": "face-a",
            "sound_file": base64.b64encode(b"audio").decode("ascii"),
            "sound_start_time": 0,
            "sound_end_time": 2500,
            "sound_insert_time": 500,
        }
    ]
    assert "sound_file" not in request["payload"]
    assert request["payload"]["callback_url"] == "https://example.com/kling/callback"


def test_advanced_lip_sync_accepts_official_nested_face_choose():
    face_choose = {
        "face_id": "face-a",
        "audio_id": "audio-a",
        "sound_start_time": 0,
        "sound_end_time": 4000,
        "sound_insert_time": 500,
    }

    request = KlingLipSync()._build_advanced_request(
        {"session_id": "session-a", "face_choose": [face_choose]}
    )

    assert request["payload"]["face_choose"] == [face_choose]
    assert request["audio_source"] == {"type": "audio_id", "value": "audio-a"}


def test_full_lip_sync_preserves_nested_face_timing_defaults():
    inputs = {
        "session_id": "session-a",
        "face_choose": [
            {
                "face_id": "face-a",
                "audio_id": "audio-a",
                "sound_start_time": 250,
                "sound_end_time": 4250,
                "sound_insert_time": 750,
            }
        ],
    }
    tool = KlingLipSync()

    tool._apply_face_timing_defaults(
        inputs, {"face_id": "face-a", "start_time": 0, "end_time": 0}
    )
    request = tool._build_advanced_request(inputs)

    assert request["payload"]["face_choose"][0]["sound_start_time"] == 250
    assert request["payload"]["face_choose"][0]["sound_end_time"] == 4250
    assert request["payload"]["face_choose"][0]["sound_insert_time"] == 750


@pytest.mark.parametrize(
    ("top_level", "nested", "message"),
    [
        ({"audio_id": "audio-top"}, {"audio_id": "audio-nested"}, "audio input"),
        ({"sound_end_time": 5000}, {"sound_end_time": 4000}, "sound_end_time"),
    ],
)
def test_advanced_lip_sync_rejects_conflicting_top_level_and_nested_values(
    top_level, nested, message
):
    inputs = {
        "session_id": "session-a",
        "face_choose": [
            {
                "face_id": "face-a",
                "audio_id": "audio-a",
                "sound_start_time": 0,
                "sound_end_time": 4000,
                "sound_insert_time": 0,
                **nested,
            }
        ],
        **top_level,
    }

    with pytest.raises(ValueError, match=message):
        KlingLipSync()._build_advanced_request(inputs)


def test_identify_face_execute_writes_faces_artifact(monkeypatch, tmp_path, budget_gate_isolated):
    class FakeClient:
        def post(self, path, payload):
            assert path == "/v1/videos/identify-face"
            return {
                "code": 0,
                "data": {
                    "session_id": "session-a",
                    "face_data": [
                        {
                            "face_id": "face-a",
                            "face_image": "https://example.com/face.png",
                            "start_time": 0,
                            "end_time": 5200,
                        }
                    ],
                },
            }

    monkeypatch.setenv("KLING_API_KEY", "test-key")
    # Stub accepts the max_retries kwarg execute() now passes; behavior unchanged.
    monkeypatch.setattr(
        "tools.avatar.kling_lip_sync.KlingClient", lambda *args, **kwargs: FakeClient()
    )

    # Gate active; approve this paid tool via the gate's real API.
    budget_gate_isolated.approve_tool("kling_lip_sync")

    artifact_path = tmp_path / "faces.json"
    result = KlingLipSync().execute(
        {
            "operation": "identify_face",
            "video_url": "https://example.com/source.mp4",
            "faces_artifact_path": str(artifact_path),
        }
    )

    assert result.success
    assert result.data["session_id"] == "session-a"
    data = json.loads(artifact_path.read_text())
    assert data["provider"] == "kling_official"
    assert data["face_count"] == 1


def test_full_lip_sync_requires_confirmation_for_multiple_faces(monkeypatch, tmp_path, budget_gate_isolated):
    class FakeClient:
        def post(self, path, payload):
            return {
                "code": 0,
                "data": {
                    "session_id": "session-a",
                    "face_data": [
                        {"face_id": "face-small", "bbox": [0, 0, 50, 50], "start_time": 0, "end_time": 4000},
                        {"face_id": "face-large", "bbox": [0, 0, 200, 200], "start_time": 500, "end_time": 5500},
                    ],
                },
            }

    monkeypatch.setenv("KLING_API_KEY", "test-key")
    # Stub accepts the max_retries kwarg execute() now passes; behavior unchanged.
    monkeypatch.setattr(
        "tools.avatar.kling_lip_sync.KlingClient", lambda *args, **kwargs: FakeClient()
    )

    # Gate active; approve this paid tool via the gate's real API.
    budget_gate_isolated.approve_tool("kling_lip_sync")

    result = KlingLipSync().execute(
        {
            "operation": "full_lip_sync",
            "video_url": "https://example.com/source.mp4",
            "audio_id": "audio-a",
            "faces_artifact_path": str(tmp_path / "faces.json"),
        }
    )

    assert not result.success
    assert result.data["requires_face_selection"] is True
    assert len(result.data["faces"]) == 2
    assert "Multiple faces detected" in result.error
    assert Path(result.artifacts[0]).is_file()


def test_full_lip_sync_auto_selects_largest_face_and_downloads(monkeypatch, tmp_path, budget_gate_isolated):
    class FakeClient:
        def post(self, path, payload):
            return {
                "code": 0,
                "data": {
                    "session_id": "session-a",
                    "face_data": [
                        {"face_id": "face-small", "bbox": [0, 0, 50, 50], "start_time": 0, "end_time": 4000},
                        {"face_id": "face-large", "bbox": [0, 0, 200, 200], "start_time": 500, "end_time": 5500},
                    ],
                },
            }

        def create_classic_task(self, path, payload):
            self.path = path
            self.payload = payload
            assert payload["face_choose"] == [
                {
                    "face_id": "face-large",
                    "audio_id": "audio-a",
                    "sound_start_time": 0,
                    "sound_end_time": 5000,
                    "sound_insert_time": 500,
                }
            ]
            return "lip-task-1"

        def poll_classic(self, path, task_id, result_key, timeout_seconds, poll_interval):
            assert result_key == "videos"
            return [{"url": "https://example.com/lip.mp4"}]

        def download(self, url, output_path):
            output_path.write_bytes(b"video")
            return output_path

    monkeypatch.setenv("KLING_API_KEY", "test-key")
    # Stub accepts the max_retries kwarg execute() now passes; behavior unchanged.
    monkeypatch.setattr(
        "tools.avatar.kling_lip_sync.KlingClient", lambda *args, **kwargs: FakeClient()
    )
    monkeypatch.setattr("tools.avatar.kling_lip_sync.probe_output", lambda path: {"duration_seconds": 4.0})

    # Gate active; approve this paid tool via the gate's real API.
    budget_gate_isolated.approve_tool("kling_lip_sync")

    result = KlingLipSync().execute(
        {
            "operation": "full_lip_sync",
            "video_url": "https://example.com/source.mp4",
            "audio_id": "audio-a",
            "auto_select_face": True,
            "output_path": str(tmp_path / "lip.mp4"),
        }
    )

    assert result.success
    assert result.data["task_id"] == "lip-task-1"
    assert result.data["face_selection"]["selection_method"] == "auto_selected"
    assert result.data["face_choose"] == [
        {
            "face_id": "face-large",
            "audio_id": "audio-a",
            "sound_start_time": 0,
            "sound_end_time": 5000,
            "sound_insert_time": 500,
        }
    ]
    assert Path(result.artifacts[0]).read_bytes() == b"video"
    faces_artifact = next(Path(path) for path in result.artifacts if Path(path).name == "kling_lip_sync_faces.json")
    assert json.loads(faces_artifact.read_text())["selection"]["selection_method"] == "auto_selected"
    assert result.cost_usd > 0


def test_auto_select_face_area_avoids_position_inflation():
    tool = KlingLipSync()
    assert tool._face_area({"bbox": [10, 20, 110, 220]}) == 100 * 200
    assert tool._face_area({"bbox": [10, 20, 100, 200]}) == 90 * 180
    assert tool._face_area({"box": {"width": 80, "height": 90}}) == 80 * 90


def test_advanced_lip_sync_execute_downloads_video(monkeypatch, tmp_path, budget_gate_isolated):
    audio_path = tmp_path / "voice.mp3"
    audio_path.write_bytes(b"audio")

    class FakeClient:
        def create_classic_task(self, path, payload):
            assert path == "/v1/videos/advanced-lip-sync"
            assert payload["face_choose"] == [
                {
                    "face_id": "face-a",
                    "sound_file": base64.b64encode(b"audio").decode("ascii"),
                    "sound_start_time": 0,
                    "sound_end_time": 4000,
                    "sound_insert_time": 0,
                }
            ]
            return "lip-task-1"

        def poll_classic(self, path, task_id, result_key, timeout_seconds, poll_interval):
            return [{"video_url": "https://example.com/lip.mp4"}]

        def download(self, url, output_path):
            output_path.write_bytes(b"video")
            return output_path

    monkeypatch.setenv("KLING_API_KEY", "test-key")
    # Stub accepts the max_retries kwarg execute() now passes; behavior unchanged.
    monkeypatch.setattr(
        "tools.avatar.kling_lip_sync.KlingClient", lambda *args, **kwargs: FakeClient()
    )
    monkeypatch.setattr("tools.avatar.kling_lip_sync.probe_output", lambda path: {"duration_seconds": 4.0})

    # Gate active; approve this paid tool via the gate's real API.
    budget_gate_isolated.approve_tool("kling_lip_sync")

    result = KlingLipSync().execute(
        {
            "operation": "advanced_lip_sync",
            "session_id": "session-a",
            "face_id": "face-a",
            "audio_path": str(audio_path),
            "sound_start_time": 0,
            "sound_end_time": 4000,
            "sound_insert_time": 0,
            "output_path": str(tmp_path / "lip.mp4"),
        }
    )

    assert result.success
    assert result.data["provider"] == "kling_official"
    assert result.data["task_id"] == "lip-task-1"
    assert result.data["duration_seconds"] == 4.0
    assert result.data["face_choose"] == [
        {
            "face_id": "face-a",
            "sound_start_time": 0,
            "sound_end_time": 4000,
            "sound_insert_time": 0,
            "sound_file_provided": True,
        }
    ]
    assert result.cost_usd > 0


def test_lip_sync_cost_estimate_is_not_zero():
    tool = KlingLipSync()
    assert tool.estimate_cost({"operation": "identify_face"}) > 0
    assert tool.estimate_cost({"operation": "advanced_lip_sync"}) > tool.estimate_cost({"operation": "identify_face"})
    assert tool.dry_run({"operation": "advanced_lip_sync"})["cost_estimate_confidence"] == "low"


class TestKlingAvatarMaxCostBound:
    """max_cost_usd() is a worst-case upper bound whose retry multiplier is the
    same retry_policy.max_retries execute() passes to KlingClient. These touch
    only KlingAvatar -- no network, no real key."""

    def test_bound_scales_with_retry_setting(self):
        from tools.base_tool import RetryPolicy

        # Worst single attempt = pro + local audio = $0.635; bound must equal
        # that times (1 + max_retries), not a hardcoded x3.
        tool = KlingAvatar()
        tool.retry_policy = RetryPolicy(max_retries=0)
        assert tool.max_cost_usd({"prompt": "x"}) == pytest.approx(0.635)
        tool.retry_policy = RetryPolicy(max_retries=2)
        assert tool.max_cost_usd({"prompt": "x"}) == pytest.approx(1.905)
        tool.retry_policy = RetryPolicy(max_retries=5)
        assert tool.max_cost_usd({"prompt": "x"}) == pytest.approx(3.81)

    def test_execute_passes_same_retry_setting_to_client(
        self, monkeypatch, tmp_path, budget_gate_isolated
    ):
        from tools.base_tool import RetryPolicy

        captured = {}

        class FakeClient:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def create_classic_task(self, path, payload):
                return "avatar-task-1"

            def poll_classic(self, path, task_id, result_key, timeout_seconds, poll_interval):
                return [{"url": "https://example.com/avatar.mp4"}]

            def download(self, url, output_path):
                output_path.write_bytes(b"video")
                return output_path

        monkeypatch.setenv("KLING_API_KEY", "test-key")
        monkeypatch.setattr("tools.avatar.kling_avatar.KlingClient", FakeClient)
        monkeypatch.setattr(
            "tools.avatar.kling_avatar.probe_output",
            lambda path: {"duration_seconds": 5.0},
        )

        tool = KlingAvatar()
        tool.retry_policy = RetryPolicy(max_retries=4)
        budget_gate_isolated.approve_tool("kling_avatar")

        result = tool.execute(
            {
                "image_url": "https://example.com/avatar.png",
                "audio_id": "audio-a",
                "output_path": str(tmp_path / "avatar.mp4"),
            }
        )

        assert result.success, result.error
        # The client received exactly the tool's retry_policy setting -- the
        # same value max_cost_usd() multiplies by.
        assert captured.get("max_retries") == 4

    def test_invalid_mode_fails_before_provider_dispatch(
        self, monkeypatch, tmp_path, budget_gate_isolated
    ):
        calls = {"create_classic_task": 0}

        class FakeClient:
            def __init__(self, **kwargs):
                pass

            def create_classic_task(self, path, payload):
                calls["create_classic_task"] += 1
                return "avatar-task-1"

            def poll_classic(self, *args, **kwargs):
                return [{"url": "https://example.com/avatar.mp4"}]

            def download(self, url, output_path):
                output_path.write_bytes(b"video")
                return output_path

        monkeypatch.setenv("KLING_API_KEY", "test-key")
        monkeypatch.setattr("tools.avatar.kling_avatar.KlingClient", FakeClient)

        tool = KlingAvatar()
        budget_gate_isolated.approve_tool("kling_avatar")

        result = tool.execute(
            {
                "image_url": "https://example.com/avatar.png",
                "audio_id": "audio-a",
                "mode": "ultra",  # not in AVATAR_MODES
                "output_path": str(tmp_path / "avatar.mp4"),
            }
        )

        assert result.success is False
        assert "mode must be one of" in (result.error or "")
        assert calls["create_classic_task"] == 0, "provider must not be dispatched"

    def test_bound_is_ge_estimate_for_every_valid_mode(self):
        from tools._kling.schemas import AVATAR_MODES

        tool = KlingAvatar()
        bound = tool.max_cost_usd({"prompt": "x"})
        for mode in AVATAR_MODES:
            for audio in ({}, {"audio_path": "a"}):
                assert bound >= tool.estimate_cost({"mode": mode, **audio})


class TestKlingLipSyncMaxCostBound:
    """max_cost_usd() bounds every operation's full billing path. full_lip_sync
    bills two sequential requests, so its bound sums both before the shared
    retry multiplier. No network, no real key."""

    def test_bounds_per_operation(self):
        tool = KlingLipSync()  # default retry_policy.max_retries == 2
        assert tool.max_cost_usd({"operation": "identify_face"}) == pytest.approx(0.06)
        assert tool.max_cost_usd({"operation": "advanced_lip_sync"}) == pytest.approx(0.96)
        assert tool.max_cost_usd({"operation": "full_lip_sync"}) == pytest.approx(1.02)

    def test_full_bound_sums_both_billed_requests_not_max(self):
        tool = KlingLipSync()
        identify = tool.estimate_cost({"operation": "identify_face"})
        advanced = tool.estimate_cost({"operation": "advanced_lip_sync"})
        full = tool.max_cost_usd({"operation": "full_lip_sync"})
        # Summed then multiplied -- strictly greater than either single-request
        # bound, so it cannot be a max() over operation costs.
        assert full == pytest.approx((identify + advanced) * 3)
        assert full > tool.max_cost_usd({"operation": "advanced_lip_sync"})
        assert full > tool.max_cost_usd({"operation": "identify_face"})

    def test_bound_scales_with_retry_setting(self):
        from tools.base_tool import RetryPolicy

        tool = KlingLipSync()
        tool.retry_policy = RetryPolicy(max_retries=0)
        assert tool.max_cost_usd({"operation": "full_lip_sync"}) == pytest.approx(0.34)
        tool.retry_policy = RetryPolicy(max_retries=5)
        assert tool.max_cost_usd({"operation": "full_lip_sync"}) == pytest.approx(2.04)

    def test_account_usage_flag_fails_closed(self):
        tool = KlingLipSync()
        for op in ("identify_face", "advanced_lip_sync", "full_lip_sync"):
            assert (
                tool.max_cost_usd({"operation": op, "include_account_usage": True})
                is None
            )

    def test_bound_is_ge_estimate_per_operation(self):
        tool = KlingLipSync()
        for op in ("identify_face", "advanced_lip_sync", "full_lip_sync"):
            assert tool.max_cost_usd({"operation": op}) >= tool.estimate_cost(
                {"operation": op}
            )

    def test_execute_passes_same_retry_setting_to_client(
        self, monkeypatch, tmp_path, budget_gate_isolated
    ):
        from tools.base_tool import RetryPolicy

        captured = {}

        class FakeClient:
            def __init__(self, *args, **kwargs):
                captured.update(kwargs)

            def post(self, path, payload):
                return {
                    "code": 0,
                    "data": {
                        "session_id": "session-a",
                        "face_data": [
                            {
                                "face_id": "face-a",
                                "face_image": "https://example.com/face.png",
                                "start_time": 0,
                                "end_time": 5200,
                            }
                        ],
                    },
                }

        monkeypatch.setenv("KLING_API_KEY", "test-key")
        monkeypatch.setattr("tools.avatar.kling_lip_sync.KlingClient", FakeClient)

        tool = KlingLipSync()
        tool.retry_policy = RetryPolicy(max_retries=4)
        budget_gate_isolated.approve_tool("kling_lip_sync")

        result = tool.execute(
            {
                "operation": "identify_face",
                "video_url": "https://example.com/source.mp4",
                "faces_artifact_path": str(tmp_path / "faces.json"),
            }
        )

        assert result.success, result.error
        assert captured.get("max_retries") == tool.retry_policy.max_retries

    def test_invalid_operation_fails_before_provider_dispatch(
        self, monkeypatch, tmp_path, budget_gate_isolated
    ):
        calls = {"post": 0, "create_classic_task": 0}
        captured = {}

        class FakeClient:
            def __init__(self, *args, **kwargs):
                captured.update(kwargs)

            def post(self, path, payload):
                calls["post"] += 1
                return {"code": 0, "data": {}}

            def create_classic_task(self, path, payload):
                calls["create_classic_task"] += 1
                return "task-1"

        monkeypatch.setenv("KLING_API_KEY", "test-key")
        monkeypatch.setattr("tools.avatar.kling_lip_sync.KlingClient", FakeClient)

        tool = KlingLipSync()
        budget_gate_isolated.approve_tool("kling_lip_sync")

        result = tool.execute(
            {"operation": "bogus_op", "video_url": "https://example.com/source.mp4"}
        )

        assert result.success is False
        assert "Unsupported Kling lip-sync operation" in (result.error or "")
        assert calls["post"] == 0
        assert calls["create_classic_task"] == 0
        # Client was constructed with the tool's retry setting even on the
        # no-dispatch path -- but no billed request was ever issued.
        assert captured.get("max_retries") == tool.retry_policy.max_retries
