from __future__ import annotations

from pathlib import Path
import re
import textwrap

import pytest
import requests

from lib.wavespeed_config import (
    WaveSpeedConfigError,
    resolve_wavespeed_task,
    active_wavespeed_profile,
    get_wavespeed_candidates_for_task,
)
from tools.graphics.wavespeed_text_to_image import WaveSpeedTextToImage
import tools.wavespeed_generation as wavespeed_generation
from tools.wavespeed_client import (
    WaveSpeedAuthError,
    WaveSpeedClient,
    WaveSpeedPrediction,
    WaveSpeedTaskFailedError,
    WaveSpeedTimeoutError,
)


class FakeResponse:
    def __init__(self, json_data=None, *, status_code=200, content=b"asset-bytes"):
        self._json_data = json_data if json_data is not None else {}
        self.status_code = status_code
        self.content = content

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(
        self, *, submit_json=None, poll_json=None, download_content=b"asset-bytes"
    ):
        self.submit_json = (
            submit_json if submit_json is not None else {"id": "task_123"}
        )
        self.poll_json = list(
            poll_json
            or [{"status": "succeeded", "outputs": ["https://cdn.example/out.png"]}]
        )
        self.download_content = download_content
        self.post_calls = []
        self.get_calls = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.post_calls.append(
            {"url": url, "headers": headers, "json": json, "timeout": timeout}
        )
        return FakeResponse(self.submit_json)

    def get(self, url, headers=None, timeout=None):
        self.get_calls.append({"url": url, "headers": headers, "timeout": timeout})
        if "/predictions/" in url:
            data = self.poll_json.pop(0) if self.poll_json else {"status": "running"}
            return FakeResponse(data)
        return FakeResponse({}, content=self.download_content)


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def write_config(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def test_missing_api_key_raises_clear_error():
    client = WaveSpeedClient(api_key="", session=FakeSession())
    with pytest.raises(WaveSpeedAuthError, match="WAVESPEED_API_KEY"):
        client.submit_task("model/test", {"prompt": "hello"})


def test_missing_model_id_fails_before_guessing(tmp_path, monkeypatch):
    config_path = write_config(
        tmp_path,
        """
        wavespeed:
          active_profile: default
          profiles:
            default:
              text_to_image:
                model_id: ""
                params: {}
        """,
    )
    monkeypatch.delenv("WAVESPEED_MODEL_PROFILE", raising=False)

    with pytest.raises(WaveSpeedConfigError, match="Do not guess model IDs"):
        resolve_wavespeed_task("text_to_image", config_path=config_path)


def test_profile_based_model_resolution_and_param_merge(tmp_path, monkeypatch):
    config_path = write_config(
        tmp_path,
        """
        wavespeed:
          active_profile: default
          profiles:
            default:
              text_to_image:
                model_id: "default/model"
                params:
                  steps: 8
                  aspect_ratio: "1:1"
            fast:
              text_to_image:
                model_id: "fast/model"
                params:
                  steps: 4
        """,
    )
    monkeypatch.setenv("WAVESPEED_MODEL_PROFILE", "fast")

    resolved = resolve_wavespeed_task(
        "text_to_image",
        explicit_params={"aspect_ratio": "16:9"},
        config_path=config_path,
    )

    assert resolved.profile == "fast"
    assert resolved.model_id == "fast/model"
    assert resolved.params == {"steps": 4, "aspect_ratio": "16:9"}


def test_explicit_model_id_overrides_profile_model(tmp_path, monkeypatch):
    config_path = write_config(
        tmp_path,
        """
        wavespeed:
          active_profile: default
          profiles:
            default:
              text_to_video:
                model_id: "profile/model"
                params: {}
        """,
    )
    monkeypatch.delenv("WAVESPEED_MODEL_PROFILE", raising=False)

    resolved = resolve_wavespeed_task(
        "text_to_video",
        explicit_model_id="override/model",
        config_path=config_path,
    )

    assert resolved.model_id == "override/model"


def test_payload_construction_and_completed_response_parsing(tmp_path):
    session = FakeSession(
        submit_json={"data": {"id": "task_abc"}},
        poll_json=[
            {
                "data": {
                    "status": "succeeded",
                    "outputs": [{"url": "https://cdn.example/out.mp4"}],
                }
            }
        ],
    )
    client = WaveSpeedClient(
        api_key="test-key", base_url="https://unit.test/api/v3", session=session
    )

    prediction = client.run_prediction(
        model_id="models/video",
        task_type="text_to_video",
        payload={"prompt": "camera move", "duration": 5},
        poll_interval_seconds=1,
        max_wait_seconds=5,
    )

    assert session.post_calls[0]["url"] == "https://unit.test/api/v3/models/video"
    assert session.post_calls[0]["headers"]["Authorization"] == "Bearer test-key"
    assert session.post_calls[0]["json"] == {"prompt": "camera move", "duration": 5}
    assert prediction.task_id == "task_abc"
    assert prediction.outputs == ["https://cdn.example/out.mp4"]
    assert prediction.status == "completed"


def test_failed_response_preserves_task_metadata():
    session = FakeSession(
        submit_json={"id": "task_bad"},
        poll_json=[{"status": "failed", "error": "model rejected prompt"}],
    )
    client = WaveSpeedClient(api_key="test-key", session=session)

    with pytest.raises(WaveSpeedTaskFailedError) as exc_info:
        client.run_prediction(
            model_id="models/video",
            task_type="text_to_video",
            payload={"prompt": "bad"},
            poll_interval_seconds=1,
            max_wait_seconds=5,
        )

    assert exc_info.value.metadata["task_id"] == "task_bad"
    assert exc_info.value.metadata["status"] == "failed"
    assert (
        exc_info.value.metadata["result_response"]["error"] == "model rejected prompt"
    )


def test_timeout_behavior_preserves_last_response():
    clock = FakeClock()
    session = FakeSession(
        submit_json={"id": "task_slow"},
        poll_json=[
            {"status": "running", "progress": 0.1},
            {"status": "running", "progress": 0.2},
            {"status": "running", "progress": 0.3},
        ],
    )
    client = WaveSpeedClient(
        api_key="test-key",
        session=session,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )

    with pytest.raises(WaveSpeedTimeoutError) as exc_info:
        client.run_prediction(
            model_id="models/video",
            task_type="text_to_video",
            payload={"prompt": "slow"},
            poll_interval_seconds=0.1,
            max_wait_seconds=2,
        )

    assert exc_info.value.metadata["task_id"] == "task_slow"
    assert exc_info.value.metadata["status"] == "timeout"
    assert exc_info.value.metadata["result_response"]["status"] == "running"
    assert len(session.get_calls) >= 2


def test_output_contract_shape_from_tool_execute(tmp_path, monkeypatch):
    class FakeClient:
        def run_prediction(
            self,
            *,
            model_id,
            task_type,
            payload,
            poll_interval_seconds=None,
            max_wait_seconds=None,
        ):
            assert payload["prompt"] == "make an image"
            assert payload["aspect_ratio"] == "16:9"
            return WaveSpeedPrediction(
                provider="wavespeed",
                model_id=model_id,
                task_id="task_image",
                task_type=task_type,
                status="completed",
                outputs=["https://cdn.example/out.png"],
                submit_response={"id": "task_image"},
                result_response={
                    "status": "succeeded",
                    "outputs": ["https://cdn.example/out.png"],
                },
            )

        def download_url(self, url, timeout=180):
            return b"not-a-real-image-but-downloaded"

    monkeypatch.setattr(wavespeed_generation, "WaveSpeedClient", lambda: FakeClient())

    result = WaveSpeedTextToImage().execute(
        {
            "prompt": "make an image",
            "output_dir": str(tmp_path),
            "model_id": "models/image",
            "params": {"aspect_ratio": "16:9"},
        }
    )

    assert result.success
    data = result.data
    assert data["asset_type"] == "image"
    assert data["provider"] == "wavespeed"
    assert data["task_type"] == "text_to_image"
    assert data["model_id"] == "models/image"
    assert data["profile"] == "default"
    assert data["task_id"] == "task_image"
    assert data["status"] == "completed"
    assert data["outputs"] == ["https://cdn.example/out.png"]
    assert len(data["local_paths"]) == 1
    assert Path(data["local_paths"][0]).exists()
    assert Path(data["metadata_path"]).exists()
    assert re.search(
        r"text_to_image_\d{8}T\d{12}Z_metadata\.json$", data["metadata_path"]
    )


# ============================================================================
# Multi-Provider Scoring Refactoring Tests
# Tests for profile resolution, candidate discovery, and selector integration
# ============================================================================


def test_active_profile_none(tmp_path):
    """Test that active_wavespeed_profile() returns None when set to null."""
    config_path = write_config(
        tmp_path,
        """
        wavespeed:
          active_profile: null
          profiles:
            default:
              text_to_image:
                model_id: "test/model"
        """,
    )
    profile = active_wavespeed_profile(config_path)
    assert profile is None


def test_active_profile_named(tmp_path):
    """Test that active_wavespeed_profile() returns profile name when set."""
    config_path = write_config(
        tmp_path,
        """
        wavespeed:
          active_profile: quality
          profiles:
            default:
              text_to_image:
                model_id: "test/model"
            quality:
              text_to_image:
                model_id: "test/quality"
        """,
    )
    profile = active_wavespeed_profile(config_path)
    assert profile == "quality"


def test_get_candidates_multi_profile_mode(tmp_path):
    """Test get_wavespeed_candidates_for_task() in multi-profile mode (active_profile=null)."""
    config_path = write_config(
        tmp_path,
        """
        wavespeed:
          active_profile: null
          profiles:
            default:
              text_to_image:
                model_id: "google/nano/text-to-image"
            quality:
              text_to_image:
                model_id: "openai/gpt/text-to-image"
            fast:
              text_to_image:
                model_id: "google/fast/text-to-image"
        """,
    )
    candidates = get_wavespeed_candidates_for_task("text_to_image", config_path)
    assert len(candidates) == 3
    profiles = {p for _, p in candidates}
    assert profiles == {"default", "quality", "fast"}


def test_get_candidates_single_profile_mode(tmp_path):
    """Test get_wavespeed_candidates_for_task() in single-profile mode (returns empty)."""
    config_path = write_config(
        tmp_path,
        """
        wavespeed:
          active_profile: default
          profiles:
            default:
              text_to_image:
                model_id: "test/model"
            quality:
              text_to_image:
                model_id: "test/quality"
        """,
    )
    candidates = get_wavespeed_candidates_for_task("text_to_image", config_path)
    assert len(candidates) == 0


def test_resolve_task_single_profile_mode(tmp_path):
    """Test resolve_wavespeed_task() in single-profile mode (active_profile='default')."""
    config_path = write_config(
        tmp_path,
        """
        wavespeed:
          active_profile: default
          profiles:
            default:
              text_to_image:
                model_id: "default/model"
            quality:
              text_to_image:
                model_id: "quality/model"
        """,
    )
    result = resolve_wavespeed_task(
        "text_to_image",
        explicit_model_id=None,
        explicit_params=None,
        explicit_profile=None,
        config_path=config_path,
    )
    assert result is not None


def test_unsupported_task_type(tmp_path):
    """Test that unsupported task types are handled gracefully."""
    config_path = write_config(
        tmp_path,
        """
        wavespeed:
          active_profile: default
          profiles:
            default:
              text_to_image:
                model_id: "test/model"
        """,
    )

    # Trying to resolve an unsupported task should raise an error
    with pytest.raises(WaveSpeedConfigError):
        resolve_wavespeed_task(
            "unsupported_task",
            config_path=config_path,
        )


def test_text_to_audio_profile_resolution(tmp_path):
    """text_to_audio resolution: only profiles with a non-empty model_id are candidates."""
    config_path = write_config(
        tmp_path,
        """
        wavespeed:
          active_profile: null
          profiles:
            default:
              text_to_audio:
                model_id: ""
                params: {}
            quality:
              text_to_audio:
                model_id: "elevenlabs/multilingual-v2"
                params: {language: "en", voice_stability: 0.75}
        """,
    )

    candidates = get_wavespeed_candidates_for_task("text_to_audio", config_path)
    assert len(candidates) == 1
    assert {p for _, p in candidates} == {"quality"}


def test_avatar_profile_resolution(tmp_path):
    """digital_human resolution: empty default excluded, populated quality kept."""
    config_path = write_config(
        tmp_path,
        """
        wavespeed:
          active_profile: null
          profiles:
            default:
              digital_human:
                model_id: ""
                params: {}
            quality:
              digital_human:
                model_id: "heygen/avatar-v/digital-twin"
                params: {quality: "high"}
        """,
    )

    candidates = get_wavespeed_candidates_for_task("digital_human", config_path)
    assert len(candidates) == 1
    assert any("heygen" in m.lower() for m, _ in candidates)


def test_audio_and_avatar_tools_discoverable_by_capability():
    """Regression guard: these tools must declare a real capability/provider so
    selectors and capability lookups find them, not the BaseTool 'generic' default."""
    from tools.tool_registry import registry
    from tools.audio.wavespeed_text_to_audio import WaveSpeedTextToAudio
    from tools.avatar.wavespeed_digital_human import WaveSpeedDigitalHuman

    assert WaveSpeedTextToAudio.capability == "tts"
    assert WaveSpeedTextToAudio.provider == "wavespeed"
    assert WaveSpeedDigitalHuman.capability == "avatar"
    assert WaveSpeedDigitalHuman.provider == "wavespeed"

    registry.discover()
    tts_names = {t.name for t in registry.get_by_capability("tts")}
    avatar_names = {t.name for t in registry.get_by_capability("avatar")}
    assert "wavespeed_text_to_audio" in tts_names
    assert "wavespeed_digital_human" in avatar_names


def test_additional_type_tools_discoverable_by_capability():
    """image_edit, image_upscale, text_to_music must map to real project capabilities."""
    from tools.tool_registry import registry
    from tools.graphics.wavespeed_image_edit import WaveSpeedImageEdit
    from tools.enhancement.wavespeed_image_upscale import WaveSpeedImageUpscale
    from tools.audio.wavespeed_text_to_music import WaveSpeedTextToMusic

    assert (WaveSpeedImageEdit.capability, WaveSpeedImageEdit.provider) == (
        "image_generation",
        "wavespeed",
    )
    assert (WaveSpeedImageUpscale.capability, WaveSpeedImageUpscale.provider) == (
        "enhancement",
        "wavespeed",
    )
    assert (WaveSpeedTextToMusic.capability, WaveSpeedTextToMusic.provider) == (
        "music_generation",
        "wavespeed",
    )

    registry.discover()
    assert "wavespeed_image_edit" in {t.name for t in registry.get_by_capability("image_generation")}
    assert "wavespeed_image_upscale" in {t.name for t in registry.get_by_capability("enhancement")}
    assert "wavespeed_text_to_music" in {t.name for t in registry.get_by_capability("music_generation")}


def test_image_upscale_prompt_optional_but_image_required(tmp_path):
    """Upscale needs no prompt but does need a source image (helper generalization)."""
    from tools.enhancement.wavespeed_image_upscale import WaveSpeedImageUpscale

    result = WaveSpeedImageUpscale().execute({"output_dir": str(tmp_path)})
    assert not result.success
    # Fails on missing image, NOT on missing prompt.
    assert "requires image" in (result.error or "").lower()


def test_background_removal_and_lipsync_discoverable_by_capability():
    from tools.tool_registry import registry
    from tools.enhancement.wavespeed_background_removal import WaveSpeedBackgroundRemoval
    from tools.avatar.wavespeed_lip_sync import WaveSpeedLipSync

    assert (WaveSpeedBackgroundRemoval.capability, WaveSpeedBackgroundRemoval.provider) == (
        "enhancement",
        "wavespeed",
    )
    assert (WaveSpeedLipSync.capability, WaveSpeedLipSync.provider) == ("avatar", "wavespeed")

    registry.discover()
    assert "wavespeed_background_removal" in {t.name for t in registry.get_by_capability("enhancement")}
    assert "wavespeed_lip_sync" in {t.name for t in registry.get_by_capability("avatar")}


def test_lip_sync_requires_audio_after_image(tmp_path):
    """lip_sync needs both image and audio; with image present it must ask for audio."""
    from tools.avatar.wavespeed_lip_sync import WaveSpeedLipSync

    result = WaveSpeedLipSync().execute(
        {"image_url": "https://example.com/face.png", "output_dir": str(tmp_path)}
    )
    assert not result.success
    assert "requires audio" in (result.error or "").lower()


def test_text_to_audio_maps_text_alias_to_prompt(monkeypatch):
    """tts_selector routes with `text`; the tool must normalize it to `prompt`."""
    from tools.audio.wavespeed_text_to_audio import WaveSpeedTextToAudio

    captured = {}

    def fake_run(*, task_type, asset_type, inputs, client=None):
        captured["task_type"] = task_type
        captured["asset_type"] = asset_type
        captured["prompt"] = inputs.get("prompt")
        return wavespeed_generation.ToolResult(success=True, data={})

    monkeypatch.setattr(
        "tools.audio.wavespeed_text_to_audio.run_wavespeed_generation", fake_run
    )
    WaveSpeedTextToAudio().execute({"text": "hello world"})
    assert captured == {
        "task_type": "text_to_audio",
        "asset_type": "audio",
        "prompt": "hello world",
    }
