"""Regression: leapfast/indextts is an ASYNC job per
docs/multimodal-call-guide-v4.md (POST /v1/audio/speech returns
{"id": ..., "status": "processing"} immediately — the WAV only appears after
polling /v1/audio/jobs/{id} and downloading /v1/audio/jobs/{id}/result).
maas_tts used to always stream the raw POST response straight to disk,
which for indextts (this tool's own DEFAULT_MODEL) wrote the small JSON
status envelope to disk as if it were the audio file.
"""

from __future__ import annotations

import pytest

from tools.audio.maas_tts import MaasTTS


@pytest.fixture(autouse=True)
def _fake_api_key(monkeypatch):
    monkeypatch.setenv("MAAS_API_KEY", "sk-dlp-test-key")


class _FakeResponse:
    def __init__(self, json_data=None, content=b"RIFF....WAVEfmt "):
        self._json = json_data or {}
        self._content = content

    def raise_for_status(self):
        pass

    def json(self):
        return self._json

    def iter_content(self, chunk_size=8192):
        yield self._content


def test_build_payload_passes_emo_alpha_zero_not_dropped():
    """emo_alpha=0.0 is a valid, meaningful value (flattest delivery) — a
    truthy check (`if inputs.get("emo_alpha")`) would wrongly treat it as
    unset and silently fall back to the 1.0 default."""
    tool = MaasTTS()
    payload, _ = tool._build_payload({
        "text": "你好",
        "model": "leapfast/indextts",
        "emo_alpha": 0.0,
    })
    assert payload["emo_alpha"] == 0.0


def test_build_payload_emo_text_requires_use_emo_text():
    tool = MaasTTS()
    payload, _ = tool._build_payload({
        "text": "太棒了",
        "model": "leapfast/indextts",
        "use_emo_text": True,
        "emo_text": "excited",
    })
    assert payload["use_emo_text"] is True
    assert payload["emo_text"] == "excited"


def test_build_payload_emotion_params_omitted_for_non_indextts_model():
    tool = MaasTTS()
    payload, _ = tool._build_payload({
        "text": "hello",
        "model": "qwen3-tts-flash",
        "emo_alpha": 0.0,
    })
    assert "emo_alpha" not in payload


def test_build_payload_emo_text_without_use_emo_text_still_sent():
    """A caller who sets emo_text but forgets use_emo_text=True clearly wants
    emotion-guided synthesis — this must not silently drop emo_text."""
    tool = MaasTTS()
    payload, _ = tool._build_payload({
        "text": "太棒了",
        "model": "leapfast/indextts",
        "emo_text": "excited",
    })
    assert payload["use_emo_text"] is True
    assert payload["emo_text"] == "excited"


def test_build_payload_maps_openai_voice_name_to_native_indextts_voice():
    tool = MaasTTS()
    payload, _ = tool._build_payload({
        "text": "你好",
        "model": "leapfast/indextts",
        "voice": "alloy",
    })
    assert payload["voice"] == "zh_female_intellectual"


def test_build_payload_passes_through_already_native_voice_unchanged():
    tool = MaasTTS()
    payload, _ = tool._build_payload({
        "text": "你好",
        "model": "leapfast/indextts",
        "voice": "zh_male_deep",
    })
    assert payload["voice"] == "zh_male_deep"


def test_build_payload_voice_not_mapped_for_non_indextts_model():
    tool = MaasTTS()
    payload, _ = tool._build_payload({
        "text": "hello",
        "model": "qwen3-tts-flash",
        "voice": "alloy",
    })
    assert payload["voice"] == "alloy"


def test_estimate_cost_qwen3_tts_flash_is_nonzero():
    tool = MaasTTS()
    cost = tool.estimate_cost({
        "text": "a" * 1000,
        "model": "qwen3-tts-flash",
    })
    assert cost > 0.0


def test_estimate_cost_free_models_are_zero():
    tool = MaasTTS()
    assert tool.estimate_cost({"text": "hello", "model": "leapfast/indextts"}) == 0.0
    assert tool.estimate_cost({"text": "hello", "model": "cosyvoice-v3.5-flash"}) == 0.0


def test_indextts_uses_async_submit_poll_download(monkeypatch, tmp_path):
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None, stream=None):
        calls.append(("POST", url))
        assert url.endswith("/v1/audio/speech")
        return _FakeResponse({"id": "tts-abc123", "status": "processing"})

    def fake_get(url, headers=None, timeout=None, stream=None):
        calls.append(("GET", url))
        if url.endswith("/v1/audio/jobs/tts-abc123"):
            return _FakeResponse({"status": "succeeded"})
        if url.endswith("/v1/audio/jobs/tts-abc123/result"):
            return _FakeResponse(content=b"RIFF-fake-wav-bytes")
        raise AssertionError(f"unexpected GET {url}")

    import requests
    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr("time.sleep", lambda *_: None)

    output_path = tmp_path / "indextts_output.wav"
    tool = MaasTTS()
    result = tool.execute({
        "text": "欢迎使用语音合成服务",
        "model": "leapfast/indextts",
        "output_path": str(output_path),
    })

    assert result.success is True
    # Must have actually polled the job endpoint and downloaded the result —
    # not just written the submit response's JSON envelope to disk.
    urls = [u for _, u in calls]
    assert any(u.endswith("/v1/audio/jobs/tts-abc123") for u in urls)
    assert any(u.endswith("/v1/audio/jobs/tts-abc123/result") for u in urls)
    content = output_path.read_bytes()
    assert content == b"RIFF-fake-wav-bytes"
    assert b"processing" not in content


def test_indextts_poll_gives_up_after_max_poll_errors(monkeypatch, tmp_path):
    """A persistently broken poll endpoint must fail fast instead of retrying
    silently until the 60s deadline — mirrors maas_video.py's poll-error cap."""
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None, stream=None):
        calls.append(("POST", url))
        return _FakeResponse({"id": "tts-broken-poll", "status": "processing"})

    def fake_get(url, headers=None, timeout=None, stream=None):
        calls.append(("GET", url))
        raise ConnectionError("simulated transient failure")

    import requests
    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr("time.sleep", lambda *_: None)

    tool = MaasTTS()
    result = tool.execute({
        "text": "欢迎使用语音合成服务",
        "model": "leapfast/indextts",
        "output_path": str(tmp_path / "out.wav"),
    })

    assert result.success is False
    assert "poll failed 5x" in result.error
    # Must have given up after the cap, not spun until the 60s deadline.
    poll_calls = [c for c in calls if c[0] == "GET"]
    assert len(poll_calls) == 5


def test_non_async_model_still_uses_direct_streaming(monkeypatch, tmp_path):
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None, stream=None):
        calls.append(("POST", url))
        return _FakeResponse(content=b"direct-audio-bytes")

    import requests
    monkeypatch.setattr(requests, "post", fake_post)

    output_path = tmp_path / "qwen_output.mp3"
    tool = MaasTTS()
    result = tool.execute({
        "text": "hello",
        "model": "qwen3-tts-flash",
        "output_path": str(output_path),
    })

    assert result.success is True
    assert len(calls) == 1  # single direct call, no polling
    assert output_path.read_bytes() == b"direct-audio-bytes"
