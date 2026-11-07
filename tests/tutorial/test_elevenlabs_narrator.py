"""ElevenLabsNarrator: voice mapping, env parsing, cache, WAV contract. No network."""

from __future__ import annotations

import shutil
import struct
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tools.audio import elevenlabs_narrator as EN  # noqa: E402
from tools.audio.narration_client import NarrationError, wav_duration_ms  # noqa: E402

ffmpeg_missing = shutil.which("ffmpeg") is None


def _fake_mp3(path: Path, seconds: float = 0.5) -> None:
    """Write a real MP3 with ffmpeg so the WAV transcode is exercised for real."""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", f"sine=frequency=440:duration={seconds}",
         "-c:a", "libmp3lame", "-b:a", "64k", str(path)],
        check=True,
    )


def test_parse_voice_map():
    assert EN.parse_voice_map("en:V1,fr:V2") == {"en": "V1", "fr": "V2"}
    assert EN.parse_voice_map(" en : V1 , , fr:V2 ") == {"en": "V1", "fr": "V2"}
    assert EN.parse_voice_map("") == {}
    with pytest.raises(ValueError):
        EN.parse_voice_map("en=V1")


def test_clean_model_id():
    assert EN.clean_model_id("") == "eleven_multilingual_v2"
    assert EN.clean_model_id("eleven_turbo_v2_5") == "eleven_turbo_v2_5"
    assert EN.clean_model_id("${ELEVENLABS_MODEL_ID:-eleven_flash_v2_5}") == "eleven_flash_v2_5"
    assert EN.clean_model_id("ELEVENLABS_MODEL_ID:-eleven_flash_v2_5") == "eleven_flash_v2_5"


def test_from_env_requires_key_and_a_voice(tmp_path):
    with pytest.raises(NarrationError, match="ELEVENLABS_API_KEY"):
        EN.ElevenLabsNarrator.from_env({}, cache_dir=tmp_path)
    with pytest.raises(NarrationError, match="ELEVENLABS_VOICE_IDS"):
        EN.ElevenLabsNarrator.from_env({"ELEVENLABS_API_KEY": "k"}, cache_dir=tmp_path)
    n = EN.ElevenLabsNarrator.from_env(
        {"ELEVENLABS_API_KEY": "k", "ELEVENLABS_VOICE_IDS": "en:V1",
         "ELEVENLABS_MODEL_ID": "ELEVENLABS_MODEL_ID:-eleven_multilingual_v2"},
        cache_dir=tmp_path,
    )
    assert n.model_id == "eleven_multilingual_v2"
    assert n.voice_for("en") == "V1"
    # An explicit override satisfies the "a voice" requirement on its own.
    n2 = EN.ElevenLabsNarrator.from_env({"ELEVENLABS_API_KEY": "k"}, voice_id="VX", cache_dir=tmp_path)
    assert n2.voice_for("de") == "VX"


def test_voice_for_missing_lang(tmp_path):
    n = EN.ElevenLabsNarrator("k", {"en": "V1", "fr": "V2"}, cache_dir=tmp_path)
    with pytest.raises(NarrationError) as exc:
        n.voice_for("de")
    assert "de" in str(exc.value) and "en, fr" in str(exc.value)


def test_voice_id_validation(tmp_path):
    with pytest.raises(NarrationError):
        EN.ElevenLabsNarrator("k", {}, voice_id="../etc", cache_dir=tmp_path)


def test_health_is_offline_and_describes_config(tmp_path):
    n = EN.ElevenLabsNarrator("k", {"en": "V1", "fr": "V2"}, cache_dir=tmp_path)
    h = n.health()
    assert h["status"] == "ok" and h["backend"] == "elevenlabs"
    assert h["languages"] == ["en", "fr"] and h["voices_configured"] == 2
    assert h["voice_override"] == ""


def test_cache_key_depends_on_voice_model_and_text(tmp_path):
    a = EN.ElevenLabsNarrator("k", {"en": "V1"}, cache_dir=tmp_path)
    b = EN.ElevenLabsNarrator("k", {"en": "V2"}, cache_dir=tmp_path)
    c = EN.ElevenLabsNarrator("k", {"en": "V1"}, model_id="eleven_turbo_v2_5", cache_dir=tmp_path)
    assert a.cache_key("en", "hi") == a.cache_key("en", "hi")
    assert a.cache_key("en", "hi") != a.cache_key("en", "hi there")
    assert a.cache_key("en", "hi") != b.cache_key("en", "hi")
    assert a.cache_key("en", "hi") != c.cache_key("en", "hi")
    assert a.cache_path("en", "hi").parent == tmp_path / "en"


@pytest.mark.skipif(ffmpeg_missing, reason="ffmpeg required")
def test_render_writes_cache_atomically_and_hits_second_time(tmp_path, monkeypatch):
    cache = tmp_path / "cache" / "deep" / "er"  # does not exist yet
    n = EN.ElevenLabsNarrator("k", {"en": "V1"}, cache_dir=cache)
    calls: list[str] = []

    def fake_fetch(voice_id: str, text: str, out_mp3: Path) -> None:
        calls.append(voice_id)
        _fake_mp3(out_mp3)

    monkeypatch.setattr(n, "_fetch_mp3", fake_fetch)

    out1 = tmp_path / "proj" / "step_0.wav"
    ms1 = n.render("en", "hello world", str(out1))
    assert calls == ["V1"]
    assert 400 <= ms1 <= 600
    data = out1.read_bytes()
    assert data[:4] == b"RIFF" and wav_duration_ms(data) == ms1
    # WAV contract: 48 kHz mono s16 (fmt chunk: channels @22, rate @24, bits @34).
    channels, rate = struct.unpack_from("<HI", data, 22)
    bits = struct.unpack_from("<H", data, 34)[0]
    assert (channels, rate, bits) == (1, 48000, 16)
    # No temp files left behind, exactly one cached clip.
    assert sorted(p.name for p in (cache / "en").iterdir()) == [n.cache_key("en", "hello world") + ".wav"]

    out2 = tmp_path / "proj" / "again.wav"
    ms2 = n.render("en", "hello world", str(out2))
    assert calls == ["V1"]  # cache hit, no second fetch
    assert ms2 == ms1 and out2.read_bytes() == data


@pytest.mark.skipif(ffmpeg_missing, reason="ffmpeg required")
def test_fetch_error_does_not_cache(tmp_path, monkeypatch):
    n = EN.ElevenLabsNarrator("k", {"en": "V1"}, cache_dir=tmp_path / "cache")

    def failing_fetch(voice_id: str, text: str, out_mp3: Path) -> None:
        raise NarrationError("ElevenLabs 401: invalid api key")

    monkeypatch.setattr(n, "_fetch_mp3", failing_fetch)
    with pytest.raises(NarrationError, match="401"):
        n.render("en", "hello", str(tmp_path / "o.wav"))
    en_dir = tmp_path / "cache" / "en"
    assert not en_dir.exists() or not any(en_dir.iterdir())
    assert not (tmp_path / "o.wav").exists()


def test_render_rejects_empty_text(tmp_path):
    n = EN.ElevenLabsNarrator("k", {"en": "V1"}, cache_dir=tmp_path)
    with pytest.raises(NarrationError, match="empty"):
        n.render("en", "   ", str(tmp_path / "o.wav"))


def test_fetch_mp3_builds_the_elevenlabs_request(tmp_path, monkeypatch):
    """Pin the request shape without touching the network."""
    import requests

    seen: dict = {}

    class Resp:
        status_code = 200
        content = b"ID3fake"
        text = ""

    def fake_post(url, **kw):
        seen["url"] = url
        seen.update(kw)
        return Resp()

    monkeypatch.setattr(requests, "post", fake_post)
    n = EN.ElevenLabsNarrator("sk_test", {"en": "V1"}, cache_dir=tmp_path)
    out = tmp_path / "x.mp3"
    n._fetch_mp3("V1", "Hello.", out)
    assert out.read_bytes() == b"ID3fake"
    assert seen["url"] == "https://api.elevenlabs.io/v1/text-to-speech/V1"
    assert seen["headers"]["xi-api-key"] == "sk_test"
    assert seen["headers"]["Accept"] == "audio/mpeg"
    assert seen["params"] == {"output_format": "mp3_44100_128"}
    assert seen["json"] == {
        "text": "Hello.",
        "model_id": "eleven_multilingual_v2",
        "voice_settings": EN.DEFAULT_VOICE_SETTINGS,
    }
    assert seen["timeout"] == 120.0


def test_fetch_mp3_maps_http_errors(tmp_path, monkeypatch):
    import requests

    class Resp:
        status_code = 422
        content = b""
        text = '{"detail":{"message":"voice not found"}}'

    monkeypatch.setattr(requests, "post", lambda url, **kw: Resp())
    n = EN.ElevenLabsNarrator("sk_test", {"en": "V1"}, cache_dir=tmp_path)
    with pytest.raises(NarrationError) as exc:
        n._fetch_mp3("V1", "Hello.", tmp_path / "x.mp3")
    assert "422" in str(exc.value) and "voice not found" in str(exc.value)
    assert not (tmp_path / "x.mp3").exists()


def test_cache_path_rejects_path_traversal_lang(tmp_path):
    n = EN.ElevenLabsNarrator("k", {"en": "V1"}, voice_id="V1", cache_dir=tmp_path)
    for bad in ("../../etc", "en/../..", "", "de ", "x" * 20):
        with pytest.raises(NarrationError, match="lang"):
            n.cache_path(bad, "hi")
    assert n.cache_path("pt-BR", "hi").parent == tmp_path / "pt-BR"


def test_relative_cache_dir_resolves_against_repo_root(tmp_path):
    n = EN.ElevenLabsNarrator.from_env(
        {"ELEVENLABS_API_KEY": "k", "ELEVENLABS_VOICE_IDS": "en:V1",
         "TUTORIAL_NARRATION_CACHE_DIR": ".cache/narration/elevenlabs"},
    )
    assert n.cache_dir == EN.REPO_ROOT / ".cache" / "narration" / "elevenlabs"
    absolute = EN.ElevenLabsNarrator.from_env(
        {"ELEVENLABS_API_KEY": "k", "ELEVENLABS_VOICE_IDS": "en:V1"}, cache_dir=tmp_path)
    assert absolute.cache_dir == tmp_path
