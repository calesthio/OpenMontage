# Circuit-video: direct ElevenLabs narration backend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the circuit-video MCP (and the `render_tutorial.py` / `author_tutorial.py` CLIs behind it) narrate a tutorial by calling ElevenLabs directly, with a selectable voice, instead of requiring the `ttsd` Docker sidecar on `TUTORIAL_NARRATION_URL`.

**Architecture:** A new `ElevenLabsNarrator` class exposes the same two-method interface as the existing `NarrationClient` (`health()` and `render(lang, text, out_path) -> duration_ms`), so every caller keeps working unchanged. It calls the ElevenLabs REST API, transcodes the MP3 reply to the 48 kHz mono PCM WAV the pipeline expects, and keeps a content-addressed clip cache (keyed on voice, model, settings and text) so authoring and rendering reuse the same clip at zero extra cost — exactly what `ttsd` does today. A `narration_backend` setting (`ttsd` | `elevenlabs`) plus an optional `voice_id` flow through MCP config → `render_tutorial` tool → `render_argv` → the CLI scripts, with per-tutorial defaults allowed in the recipe JSON.

**Tech Stack:** Python 3 stdlib + `requests` (already used by `narration_client.py`), ffmpeg (already required), pytest (`requirements-dev.txt`).

**Spec:** No separate spec document. The design is captured in this header and in "Design decisions" below; the user's request was: "add an option to use 11labs voices" to the circuit_video MCP whose narration today goes through `TUTORIAL_NARRATION_URL=http://127.0.0.1:5557`.

## Design decisions (read before starting)

- **`ttsd` already uses ElevenLabs** under the hood (one fixed voice per language from `ELEVENLABS_VOICE_IDS`, baked into the container). It ignores any `voice_id` in the request body (verified: a `/render` POST with `voice_id` set still returns 200 using the configured voice). The Go source is not in the sibling `circuit-bid/redis-bridge` checkout, so we cannot extend it. Hence a **second backend in OpenMontage** rather than a change to `ttsd`.
- **Default stays `ttsd`.** Nothing changes for existing users until they set `narration_backend` or pass it in a tool call. The k8s render-api path (`CIRCUIT_VIDEO_RENDER_API_URL`) keeps using the `ttsd` sidecar; the new fields are forwarded in the POST body but the remote worker is out of scope.
- **Precedence** for both `narration_backend` and `voice_id`: CLI flag (what the MCP passes) > recipe JSON (`<name>.tutorial.json`) > environment (`TUTORIAL_NARRATION_BACKEND`, `TUTORIAL_VOICE_ID`) > default (`ttsd`, per-language voice from `ELEVENLABS_VOICE_IDS`). The MCP only passes the flags when they were set in the tool call or in its own config, so a recipe-pinned voice is honoured.
- **Audio contract** (must match `ttsd`): WAV, PCM s16le, 48000 Hz, mono. `render_tutorial.py` concatenates these with `narration_bed()` at `AR = 48000`. ElevenLabs is asked for `mp3_44100_128` (available on every plan tier; the `pcm_*` formats are tier-gated) and ffmpeg transcodes.
- **Cache**: `<repo>/.cache/narration/elevenlabs/<lang>/<sha256>.wav`, where the hash covers `{provider, voice_id, model_id, voice_settings, text}`. Override with `TUTORIAL_NARRATION_CACHE_DIR`. Authoring (`author_tutorial.py`, which commits `timings.json`) and rendering therefore produce byte-identical clips and identical durations.
- **Voice changes pacing**: `timings.json` durations drive the Cypress capture pacing. The timings file therefore records which backend/voice produced it, and `render_tutorial.py` warns when the voice it resolves differs.
- **Direct HTTP call, not `tools/audio/elevenlabs_tts.py`**: that tool reads the key only from `os.environ`, writes MP3 and returns a `ToolResult`; we need an explicit key (from `.env`), WAV output, caching and precise error messages. The request shape is copied from it so the two stay consistent.
- **`.env` handling**: the CLI scripts currently never read `OpenMontage/.env` (only the MCP and `tutorialctl` do). A tiny shared `lib/envfile.py` fixes that so `python render_tutorial.py --narration-backend elevenlabs` works without exporting keys. The existing `.env` has a mangled `ELEVENLABS_MODEL_ID=ELEVENLABS_MODEL_ID:-eleven_multilingual_v2` line; `tutorialctl._clean_value` already tolerates it and the narrator must too.

## Global Constraints

- Python 3.10+ syntax (`str | None`, `from __future__ import annotations`), matching the rest of the repo.
- No test may open a non-loopback network connection (`tests/conftest.py` blocks sockets; a violation raises `NetworkCallInTestError`).
- MCP `server.py` must never `print()` to stdout (stdout is the JSON-RPC channel); use `sys.stderr`.
- `tests/mcp/test_circuit_video.py` must keep passing; it asserts on `TOOLS`, `_call`, `_handle`, `render_argv`.
- Never commit real keys. `.env` is git-ignored; `env.example` holds placeholders only.
- Narration WAV contract: PCM s16le, 48000 Hz, mono (see Design decisions).
- Voice ids and backend names are validated before they reach a shell argv or a URL path: backend ∈ {`ttsd`, `elevenlabs`}; voice id matches `^[A-Za-z0-9_-]{1,64}$`.
- Run tests with `.venv/bin/python -m pytest` from the repo root (install once: `.venv/bin/python -m pip install -r requirements-dev.txt`, or at minimum `pytest`).
- Commit after each task. Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

1. `ELEVENLABS_VOICE_IDS` is set but has no entry for the recipe `lang` and no `voice_id` override → a clear `NarrationError` naming the configured languages, not a KeyError mid-render. (Pinned in Task 2, `test_voice_for_missing_lang`.)
2. ElevenLabs returns 401 (bad key) or 404/422 (bad voice id) → the render fails fast with the HTTP status and the reason, and nothing is written to the cache. (Pinned in Task 2, `test_fetch_error_does_not_cache`.)
3. The cache path from `TUTORIAL_NARRATION_CACHE_DIR` does not exist yet → it is created; a crash between download and transcode never leaves a half-written `.wav` that later renders would treat as a cache hit. (Pinned in Task 2, `test_render_writes_cache_atomically`.)
4. The MCP is called with `narration_backend="elevenlabs"` but no key is configured → `doctor` reports `fail` with the fix, and `render_tutorial` returns an `isError` result before launching Cypress (a 5–20 minute capture). (Pinned in Task 5, `test_render_tutorial_elevenlabs_without_key_fails_early`.)
5. `timings.json` was authored with voice A and the render now resolves voice B → a WARN on stderr about pacing. (Pinned in Task 4, `test_timings_voice_mismatch_warning`.)

---

### Task 1: Shared `.env` reader

**Files:**
- Create: `lib/envfile.py`
- Test: `tests/lib/test_envfile.py`

**Interfaces:**
- Produces: `parse_env_file(path: Path) -> dict[str, str]` — tolerant parser: skips blanks/comments, strips `export `, strips one layer of matching quotes, returns `{}` on OSError. Same semantics as `_parse_env_file` in `mcp_servers/circuit_video/config.py` and `tutorialctl.py` (those two keep their private copies; de-duplicating them is an optional follow-up, not part of this plan).

- [ ] **Step 1: Write the failing test**

```python
# tests/lib/test_envfile.py
from pathlib import Path

from lib.envfile import parse_env_file


def test_parse_env_file_handles_comments_quotes_and_export(tmp_path: Path):
    p = tmp_path / ".env"
    p.write_text(
        "# comment\n"
        "\n"
        "export ELEVENLABS_API_KEY=\"sk_abc\"\n"
        "ELEVENLABS_VOICE_IDS='en:V1,fr:V2'\n"
        "NOT_A_PAIR\n"
        "ELEVENLABS_MODEL_ID=ELEVENLABS_MODEL_ID:-eleven_multilingual_v2\n"
    )
    out = parse_env_file(p)
    assert out == {
        "ELEVENLABS_API_KEY": "sk_abc",
        "ELEVENLABS_VOICE_IDS": "en:V1,fr:V2",
        "ELEVENLABS_MODEL_ID": "ELEVENLABS_MODEL_ID:-eleven_multilingual_v2",
    }


def test_parse_env_file_missing_returns_empty(tmp_path: Path):
    assert parse_env_file(tmp_path / "nope.env") == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/lib/test_envfile.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lib.envfile'`

- [ ] **Step 3: Write minimal implementation**

```python
# lib/envfile.py
"""Minimal KEY=VALUE .env reader shared by the tutorial CLIs.

Deliberately tiny: no interpolation, no multi-line values. Shell environment
should always win over the file (callers do `{**parse_env_file(p), **os.environ}`).
"""

from __future__ import annotations

from pathlib import Path


def parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        lines = Path(path).read_text().splitlines()
    except OSError:
        return out
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        if key:
            out[key] = val
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/lib/test_envfile.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add lib/envfile.py tests/lib/test_envfile.py
git commit -m "feat(tutorial): add shared .env reader for the tutorial CLIs

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: `ElevenLabsNarrator` with content-addressed WAV cache

**Files:**
- Create: `tools/audio/elevenlabs_narrator.py`
- Test: `tests/tutorial/test_elevenlabs_narrator.py`
- Modify: `.gitignore` (add `.cache/`)

**Interfaces:**
- Consumes: `tools.audio.narration_client.NarrationError`, `tools.audio.narration_client.wav_duration_ms(bytes) -> int` (both exist).
- Produces:
  - `DEFAULT_MODEL_ID = "eleven_multilingual_v2"`, `DEFAULT_VOICE_SETTINGS: dict`, `VOICE_ID_RE`
  - `parse_voice_map(raw: str) -> dict[str, str]`
  - `clean_model_id(raw: str) -> str`
  - `class ElevenLabsNarrator` with `__init__(api_key, voices, *, model_id=DEFAULT_MODEL_ID, voice_id=None, cache_dir, voice_settings=None, sample_rate=48000, timeout=120.0)`, `from_env(env, *, voice_id=None, cache_dir=None) -> ElevenLabsNarrator`, `voice_for(lang) -> str`, `cache_key(lang, text) -> str`, `cache_path(lang, text) -> Path`, `health() -> dict`, `render(lang, text, out_path) -> int`, and the two seams used by tests: `_fetch_mp3(voice_id, text, out_mp3: Path) -> None`, `_to_wav(src: Path, dst: Path) -> None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/tutorial/test_elevenlabs_narrator.py
"""ElevenLabsNarrator: voice mapping, env parsing, cache, WAV contract. No network."""

from __future__ import annotations

import shutil
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
    import struct
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
    assert not (tmp_path / "cache" / "en").exists() or not any((tmp_path / "cache" / "en").iterdir())
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/tutorial/test_elevenlabs_narrator.py -v`
Expected: FAIL at import with `ModuleNotFoundError: No module named 'tools.audio.elevenlabs_narrator'`

- [ ] **Step 3: Write the implementation**

```python
# tools/audio/elevenlabs_narrator.py
"""Direct ElevenLabs narration backend for the Circuit tutorial pipeline.

Drop-in alternative to `tools.audio.narration_client.NarrationClient` (the
`ttsd` sidecar). Same contract:

    health() -> dict
    render(lang, text, out_path) -> duration_ms   (WAV, PCM s16le, 48 kHz, mono)

Like ttsd, clips are cached content-addressed on (voice_id, model_id,
voice_settings, text) so author_tutorial.py and render_tutorial.py get the
same audio and the same duration without paying twice.

Request shape mirrors tools/audio/elevenlabs_tts.py; we do not reuse that
BaseTool because it reads the key only from os.environ, emits MP3 and has no cache.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Mapping, Optional

from tools.audio.narration_client import NarrationError, wav_duration_ms

REPO_ROOT = Path(__file__).resolve().parents[2]
API_BASE = "https://api.elevenlabs.io/v1"
DEFAULT_MODEL_ID = "eleven_multilingual_v2"
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"  # available on every ElevenLabs tier
DEFAULT_CACHE_DIR = REPO_ROOT / ".cache" / "narration" / "elevenlabs"
DEFAULT_VOICE_SETTINGS: dict = {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0.0,
    "speed": 1.0,
    "use_speaker_boost": True,
}
VOICE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_SELF_REF_RE = re.compile(r"^\$?\{?ELEVENLABS_MODEL_ID(?::-?(.*?))?\}?$")


def parse_voice_map(raw: str) -> dict[str, str]:
    """'en:V1,fr:V2' -> {'en': 'V1', 'fr': 'V2'}. Blank entries are ignored."""
    out: dict[str, str] = {}
    for entry in (raw or "").split(","):
        entry = entry.strip()
        if not entry:
            continue
        if ":" not in entry:
            raise ValueError(f"ELEVENLABS_VOICE_IDS entry {entry!r} must look like lang:voice_id")
        lang, _, vid = entry.partition(":")
        lang, vid = lang.strip(), vid.strip()
        if lang and vid:
            out[lang] = vid
    return out


def clean_model_id(raw: str) -> str:
    """Resolve the self-referential '${ELEVENLABS_MODEL_ID:-x}' (or brace-less
    'ELEVENLABS_MODEL_ID:-x') that OpenMontage/.env may contain; else pass through."""
    val = (raw or "").strip()
    m = _SELF_REF_RE.match(val)
    if m:
        val = (m.group(1) or "").strip()
    return val or DEFAULT_MODEL_ID


class ElevenLabsNarrator:
    def __init__(
        self,
        api_key: str,
        voices: Mapping[str, str],
        *,
        model_id: str = DEFAULT_MODEL_ID,
        voice_id: Optional[str] = None,
        cache_dir: Path | str = DEFAULT_CACHE_DIR,
        voice_settings: Optional[dict] = None,
        sample_rate: int = 48000,
        timeout: float = 120.0,
    ):
        if not api_key:
            raise NarrationError("ELEVENLABS_API_KEY is not set")
        for vid in [voice_id, *voices.values()]:
            if vid and not VOICE_ID_RE.match(vid):
                raise NarrationError(f"invalid ElevenLabs voice id {vid!r}")
        self.api_key = api_key
        self.voices = dict(voices)
        self.model_id = model_id or DEFAULT_MODEL_ID
        self.voice_id = voice_id or None
        self.cache_dir = Path(cache_dir)
        self.voice_settings = dict(voice_settings or DEFAULT_VOICE_SETTINGS)
        self.sample_rate = sample_rate
        self.timeout = timeout

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str],
        *,
        voice_id: Optional[str] = None,
        cache_dir: Path | str | None = None,
    ) -> "ElevenLabsNarrator":
        api_key = (env.get("ELEVENLABS_API_KEY") or "").strip()
        if not api_key:
            raise NarrationError(
                "ELEVENLABS_API_KEY is not set (export it or add it to OpenMontage/.env)"
            )
        try:
            voices = parse_voice_map(env.get("ELEVENLABS_VOICE_IDS", ""))
        except ValueError as e:
            raise NarrationError(str(e)) from e
        if not voices and not voice_id:
            raise NarrationError(
                "no voice configured: set ELEVENLABS_VOICE_IDS (e.g. en:<voice_id>,fr:<voice_id>) "
                "or pass a voice_id"
            )
        return cls(
            api_key,
            voices,
            model_id=clean_model_id(env.get("ELEVENLABS_MODEL_ID", "")),
            voice_id=voice_id,
            cache_dir=cache_dir or env.get("TUTORIAL_NARRATION_CACHE_DIR") or DEFAULT_CACHE_DIR,
        )

    # --- config / introspection -------------------------------------------

    def voice_for(self, lang: str) -> str:
        if self.voice_id:
            return self.voice_id
        vid = self.voices.get(lang)
        if not vid:
            langs = ", ".join(sorted(self.voices)) or "none"
            raise NarrationError(
                f"no ElevenLabs voice for lang {lang!r} (configured: {langs}); "
                "add it to ELEVENLABS_VOICE_IDS or pass a voice_id"
            )
        return vid

    def health(self) -> dict:
        """Offline readiness report shaped like ttsd's /health (plus backend info)."""
        langs = sorted(self.voices)
        return {
            "status": "ok",
            "backend": "elevenlabs",
            "languages": langs,
            "voices_configured": len(langs) if not self.voice_id else max(1, len(langs)),
            "voice_override": self.voice_id or "",
            "model_id": self.model_id,
            "cache_dir": str(self.cache_dir),
        }

    def cache_key(self, lang: str, text: str) -> str:
        payload = {
            "provider": "elevenlabs",
            "voice_id": self.voice_for(lang),
            "model_id": self.model_id,
            "voice_settings": self.voice_settings,
            "sample_rate": self.sample_rate,
            "text": text,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def cache_path(self, lang: str, text: str) -> Path:
        return self.cache_dir / lang / f"{self.cache_key(lang, text)}.wav"

    # --- rendering ----------------------------------------------------------

    def render(self, lang: str, text: str, out_path: str) -> int:
        text = (text or "").strip()
        if not text:
            raise NarrationError("empty narration text")
        voice_id = self.voice_for(lang)
        cached = self.cache_path(lang, text)
        if not cached.exists():
            cached.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=cached.parent, prefix=".tmp-") as tmp:
                mp3 = Path(tmp) / "clip.mp3"
                wav = Path(tmp) / "clip.wav"
                self._fetch_mp3(voice_id, text, mp3)
                self._to_wav(mp3, wav)
                os.replace(wav, cached)  # atomic: a reader never sees a partial file
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cached, out)
        return wav_duration_ms(out.read_bytes())

    def _fetch_mp3(self, voice_id: str, text: str, out_mp3: Path) -> None:
        import requests

        url = f"{API_BASE}/text-to-speech/{voice_id}"
        last_err = ""
        for attempt in range(2):
            try:
                resp = requests.post(
                    url,
                    headers={
                        "xi-api-key": self.api_key,
                        "Content-Type": "application/json",
                        "Accept": "audio/mpeg",
                    },
                    params={"output_format": DEFAULT_OUTPUT_FORMAT},
                    json={
                        "text": text,
                        "model_id": self.model_id,
                        "voice_settings": self.voice_settings,
                    },
                    timeout=self.timeout,
                )
            except requests.RequestException as e:
                raise NarrationError(f"ElevenLabs request failed: {e}") from e
            if resp.status_code == 200:
                out_mp3.parent.mkdir(parents=True, exist_ok=True)
                out_mp3.write_bytes(resp.content)
                return
            last_err = f"ElevenLabs {resp.status_code}: {(resp.text or '')[:300]}"
            if resp.status_code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(2.0)
                continue
            break
        if "401" in last_err:
            last_err += " (check ELEVENLABS_API_KEY)"
        elif any(code in last_err for code in ("404", "422")):
            last_err += f" (check voice id {voice_id!r})"
        raise NarrationError(last_err)

    def _to_wav(self, src: Path, dst: Path) -> None:
        cmd = [
            "ffmpeg", "-y", "-v", "error", "-i", str(src),
            "-ar", str(self.sample_rate), "-ac", "1", "-c:a", "pcm_s16le", str(dst),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except (OSError, subprocess.CalledProcessError) as e:
            detail = getattr(e, "stderr", b"") or b""
            raise NarrationError(
                f"ffmpeg transcode failed: {detail.decode('utf-8', 'replace')[:300] or e}"
            ) from e
```

Add to `.gitignore` (near the `projects/` entry):

```
# Narration clip cache (ElevenLabs backend)
.cache/
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/tutorial/test_elevenlabs_narrator.py -v`
Expected: all PASS (two tests are skipped only if ffmpeg is absent)

- [ ] **Step 5: Commit**

```bash
git add tools/audio/elevenlabs_narrator.py tests/tutorial/test_elevenlabs_narrator.py .gitignore
git commit -m "feat(tutorial): add direct ElevenLabs narration backend with clip cache

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Backend/voice resolution and client factory in `lib/tutorial.py`

**Files:**
- Modify: `lib/tutorial.py` (append after `build_subtitle_segments`, before `build_edit_decisions`)
- Test: `tests/tutorial/test_tutorial_lib.py` (append)

**Interfaces:**
- Consumes: `tools.audio.narration_client.NarrationClient`, `tools.audio.elevenlabs_narrator.ElevenLabsNarrator.from_env` (Task 2). Imports are lazy so `lib.tutorial` stays import-light.
- Produces:
  - `NARRATION_BACKENDS = ("ttsd", "elevenlabs")`
  - `resolve_narration_choice(*, cli_backend, cli_voice_id, recipe, env) -> tuple[str, str]` — pure, implements the precedence CLI > recipe > env > default; raises `ValueError` on an unknown backend or malformed voice id.
  - `narration_client_for(backend, *, narration_url, voice_id="", env=None, cache_dir=None)` — returns an object with `.health()` and `.render(lang, text, out_path) -> int`.

- [ ] **Step 1: Write the failing tests** (append to `tests/tutorial/test_tutorial_lib.py`)

```python
def test_resolve_narration_choice_precedence():
    env = {"TUTORIAL_NARRATION_BACKEND": "elevenlabs", "TUTORIAL_VOICE_ID": "ENVV"}
    recipe = {"narration_backend": "ttsd", "voice_id": "RECV"}
    # CLI beats recipe beats env.
    assert T.resolve_narration_choice(cli_backend="elevenlabs", cli_voice_id="CLIV",
                                      recipe=recipe, env=env) == ("elevenlabs", "CLIV")
    assert T.resolve_narration_choice(cli_backend=None, cli_voice_id=None,
                                      recipe=recipe, env=env) == ("ttsd", "RECV")
    assert T.resolve_narration_choice(cli_backend=None, cli_voice_id=None,
                                      recipe={}, env=env) == ("elevenlabs", "ENVV")
    assert T.resolve_narration_choice(cli_backend=None, cli_voice_id=None,
                                      recipe={}, env={}) == ("ttsd", "")


def test_resolve_narration_choice_validates():
    with pytest.raises(ValueError, match="narration backend"):
        T.resolve_narration_choice(cli_backend="piper", cli_voice_id=None, recipe={}, env={})
    with pytest.raises(ValueError, match="voice_id"):
        T.resolve_narration_choice(cli_backend=None, cli_voice_id="bad id!", recipe={}, env={})


def test_narration_client_for_builds_each_backend(tmp_path):
    ttsd = T.narration_client_for("ttsd", narration_url="http://127.0.0.1:5557/")
    assert ttsd.base_url == "http://127.0.0.1:5557"
    el = T.narration_client_for(
        "elevenlabs", narration_url="", voice_id="VX",
        env={"ELEVENLABS_API_KEY": "k"}, cache_dir=str(tmp_path),
    )
    assert el.health()["backend"] == "elevenlabs" and el.voice_for("en") == "VX"
    with pytest.raises(ValueError):
        T.narration_client_for("nope", narration_url="")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/tutorial/test_tutorial_lib.py -v -k narration`
Expected: FAIL with `AttributeError: module 'lib.tutorial' has no attribute 'resolve_narration_choice'`

- [ ] **Step 3: Implement** (in `lib/tutorial.py`; add `import os` and `import re` to the imports if missing, and `Mapping` to the `typing` import)

```python
# --- narration backend selection -------------------------------------------

NARRATION_BACKENDS = ("ttsd", "elevenlabs")
_VOICE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def resolve_narration_choice(
    *,
    cli_backend: Optional[str],
    cli_voice_id: Optional[str],
    recipe: Mapping[str, Any],
    env: Mapping[str, str],
) -> tuple[str, str]:
    """(backend, voice_id) with precedence CLI > recipe > env > default.

    backend default is "ttsd"; voice_id default is "" (= per-language voice
    from the backend's own config). Pure function so the precedence is testable.
    """
    backend = (
        (cli_backend or "").strip()
        or str(recipe.get("narration_backend") or "").strip()
        or (env.get("TUTORIAL_NARRATION_BACKEND") or "").strip()
        or "ttsd"
    )
    if backend not in NARRATION_BACKENDS:
        raise ValueError(
            f"unknown narration backend {backend!r}; expected one of {', '.join(NARRATION_BACKENDS)}"
        )
    voice_id = (
        (cli_voice_id or "").strip()
        or str(recipe.get("voice_id") or "").strip()
        or (env.get("TUTORIAL_VOICE_ID") or "").strip()
    )
    if voice_id and not _VOICE_ID_RE.match(voice_id):
        raise ValueError("voice_id must be 1-64 letters, digits, underscores, or hyphens")
    return backend, voice_id


def narration_client_for(
    backend: str,
    *,
    narration_url: str,
    voice_id: str = "",
    env: Optional[Mapping[str, str]] = None,
    cache_dir: Optional[str] = None,
):
    """Return a narration client: `.health() -> dict`, `.render(lang, text, out_path) -> ms`."""
    if backend == "ttsd":
        from tools.audio.narration_client import NarrationClient

        return NarrationClient(narration_url)
    if backend == "elevenlabs":
        from tools.audio.elevenlabs_narrator import ElevenLabsNarrator

        return ElevenLabsNarrator.from_env(
            env if env is not None else os.environ,
            voice_id=voice_id or None,
            cache_dir=cache_dir,
        )
    raise ValueError(f"unknown narration backend {backend!r}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/tutorial/test_tutorial_lib.py -v`
Expected: all PASS (existing tests included)

- [ ] **Step 5: Commit**

```bash
git add lib/tutorial.py tests/tutorial/test_tutorial_lib.py
git commit -m "feat(tutorial): resolve narration backend/voice and build the matching client

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Wire the CLIs (`render_tutorial.py`, `author_tutorial.py`)

**Files:**
- Modify: `render_tutorial.py` — imports (line ~29), `HttpNarrator` (lines 244-251), argparse (after line 262), main narration block (lines 329-339), timings handling (lines ~318-327)
- Modify: `author_tutorial.py` — argparse (line ~50), client construction (lines 60-65), timings payload (line ~88)
- Test: `tests/tutorial/test_render_tutorial_narration.py`

**Interfaces:**
- Consumes: `lib.envfile.parse_env_file` (Task 1); `lib.tutorial.resolve_narration_choice`, `lib.tutorial.narration_client_for`, `lib.tutorial.NARRATION_BACKENDS` (Task 3); `NarrationError`.
- Produces:
  - `render_tutorial.ClientNarrator(client)` replaces `HttpNarrator(base_url)` — same `.render(lang, text, index, out_wav) -> int`.
  - `render_tutorial.timings_voice_warning(timings: dict, backend: str, voice_id: str) -> str | None` — pure helper, returns the WARN text or None.
  - CLI flags on both scripts: `--narration-backend {ttsd,elevenlabs}` (default: unset → resolution rules) and `--voice-id`.
  - `author_tutorial.py` writes `timings["narration"] = {"backend": ..., "voice_id": ...}` (voice_id is the override or "").

- [ ] **Step 1: Write the failing tests**

```python
# tests/tutorial/test_render_tutorial_narration.py
"""CLI-level narration wiring: argv flags, narrator adapter, pacing warning."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import render_tutorial as RT  # noqa: E402


class _Client:
    def __init__(self):
        self.calls = []

    def render(self, lang, text, out_path):
        self.calls.append((lang, text, out_path))
        return 1234


def test_client_narrator_delegates(tmp_path):
    c = _Client()
    n = RT.ClientNarrator(c)
    assert n.render("en", "hi", 3, tmp_path / "step_3.wav") == 1234
    assert c.calls == [("en", "hi", str(tmp_path / "step_3.wav"))]


def test_timings_voice_mismatch_warning():
    timings = {"narration": {"backend": "elevenlabs", "voice_id": "A"}}
    assert RT.timings_voice_warning(timings, "elevenlabs", "A") is None
    msg = RT.timings_voice_warning(timings, "elevenlabs", "B")
    assert msg and "A" in msg and "B" in msg and "author_tutorial" in msg
    msg2 = RT.timings_voice_warning(timings, "ttsd", "")
    assert msg2 and "elevenlabs" in msg2 and "ttsd" in msg2
    # Old timings files (no narration block) never warn.
    assert RT.timings_voice_warning({}, "elevenlabs", "B") is None


def test_cli_accepts_backend_and_voice_flags():
    ap = RT.build_arg_parser()
    args = ap.parse_args([
        "--tutorial", "t", "--client-dir", "/c", "--project-id", "p",
        "--narration-backend", "elevenlabs", "--voice-id", "VX",
    ])
    assert args.narration_backend == "elevenlabs" and args.voice_id == "VX"
    args = ap.parse_args(["--tutorial", "t", "--client-dir", "/c", "--project-id", "p"])
    assert args.narration_backend is None and args.voice_id is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/tutorial/test_render_tutorial_narration.py -v`
Expected: FAIL with `AttributeError: module 'render_tutorial' has no attribute 'ClientNarrator'`

- [ ] **Step 3: Modify `render_tutorial.py`**

Add to the imports block (after `from lib import tutorial as T`):

```python
import os  # (top-level stdlib imports)
from lib.envfile import parse_env_file  # noqa: E402
```

Replace the `HttpNarrator` class:

```python
class ClientNarrator:
    """Adapter from a narration client (ttsd or ElevenLabs) to the step narrator API."""

    def __init__(self, client):
        self.client = client

    def render(self, lang: str, text: str, index: int, out_wav: Path) -> int:
        return self.client.render(lang, text, str(out_wav))


def timings_voice_warning(timings: dict, backend: str, voice_id: str) -> Optional[str]:
    """Pacing guard: timings.json durations were measured with one voice; a
    different voice/backend speaks at a different pace, so the capture no
    longer lines up. Returns the warning text, or None when consistent/unknown."""
    rec = (timings or {}).get("narration") or {}
    if not rec:
        return None
    old_backend = rec.get("backend") or ""
    old_voice = rec.get("voice_id") or ""
    if old_backend == backend and old_voice == voice_id:
        return None
    return (
        f"WARN: timings.json was authored with backend={old_backend or '?'} "
        f"voice_id={old_voice or '(per-lang default)'} but this render uses "
        f"backend={backend} voice_id={voice_id or '(per-lang default)'}. Durations "
        "(and therefore capture pacing) may differ — re-run author_tutorial.py with "
        "the same backend/voice and re-capture."
    )
```

Extract the parser so tests can call it: rename the body of `main()` that builds `ap` into `build_arg_parser() -> argparse.ArgumentParser` and have `main()` call `args = build_arg_parser().parse_args()`. Add these two arguments right after `--narration-url`:

```python
    ap.add_argument("--narration-backend", choices=list(T.NARRATION_BACKENDS), default=None,
                    help="ttsd (sidecar at --narration-url) or elevenlabs (direct API; needs "
                         "ELEVENLABS_API_KEY and ELEVENLABS_VOICE_IDS or --voice-id). "
                         "Default: recipe.narration_backend, else $TUTORIAL_NARRATION_BACKEND, else ttsd.")
    ap.add_argument("--voice-id", default=None,
                    help="ElevenLabs voice id override. Default: recipe.voice_id, else "
                         "$TUTORIAL_VOICE_ID, else the per-language voice.")
```

Right after `lang = recipe.get("lang", "en")` in `main()`:

```python
    env = {**parse_env_file(REPO_ROOT / ".env"), **os.environ}  # shell wins over .env
    try:
        backend, voice_id = T.resolve_narration_choice(
            cli_backend=args.narration_backend, cli_voice_id=args.voice_id,
            recipe=recipe, env=env,
        )
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
```

Replace the `else:` branch of the narration block (the one that builds `HttpNarrator`):

```python
    else:
        if not any(durations_ms):
            print("WARN: no committed timings.json for this tutorial — the capture was not "
                  f"paced to the narration. Synthesizing fresh via {backend}; run author_tutorial.py "
                  "to commit timings and re-capture for correct pacing.", file=sys.stderr)
        warn = timings_voice_warning(tut["timings"], backend, voice_id)
        if warn:
            print(warn, file=sys.stderr)
        try:
            client = T.narration_client_for(
                backend, narration_url=args.narration_url, voice_id=voice_id, env=env,
            )
        except (ValueError, NarrationError) as e:
            print(f"ERROR: narration backend {backend!r} not ready: {e}", file=sys.stderr)
            return 2
        narrator = ClientNarrator(client)
```

and add `from tools.audio.narration_client import NarrationError  # noqa: E402` to the imports. Also record the choice in the project for traceability — right after `init_project(...)` returns `project_dir`, nothing else is needed; the `mcp_job.json` written by the MCP (Task 5) carries backend/voice.

- [ ] **Step 4: Modify `author_tutorial.py`**

Add imports:

```python
import os
from lib.envfile import parse_env_file  # noqa: E402
from lib import tutorial as T  # noqa: E402
from tools.audio.narration_client import NarrationError  # noqa: E402
```

(`NarrationClient` import can be removed once unused.) Add the same two arguments after `--narration-url`:

```python
    ap.add_argument("--narration-backend", choices=list(T.NARRATION_BACKENDS), default=None)
    ap.add_argument("--voice-id", default=None)
```

Replace the client construction + health check:

```python
    env = {**parse_env_file(REPO_ROOT / ".env"), **os.environ}
    try:
        backend, voice_id = T.resolve_narration_choice(
            cli_backend=args.narration_backend, cli_voice_id=args.voice_id,
            recipe=tut["recipe"], env=env,
        )
        client = T.narration_client_for(
            backend, narration_url=args.narration_url, voice_id=voice_id, env=env,
        )
        client.health()
    except (ValueError, NarrationError) as e:
        print(f"ERROR: narration backend not ready: {e}", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001  (ttsd unreachable)
        print(f"ERROR: ttsd not reachable at {args.narration_url}: {e}", file=sys.stderr)
        return 2
```

(`REPO_ROOT` already exists in `author_tutorial.py` as the path inserted into `sys.path`; if it is named differently there, use that name.) Change the timings payload:

```python
    timings = {
        "spec": tut["spec_rel"],
        "lang": lang,
        "narration": {"backend": backend, "voice_id": voice_id},
        "steps": out_steps,
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/tutorial -v`
Expected: all PASS

- [ ] **Step 6: Smoke the CLI help and an offline render**

Run: `.venv/bin/python render_tutorial.py --help | grep -A2 narration-backend`
Expected: the two new flags are listed.

Run (no network, no ttsd; uses the committed timings and a prior capture if one exists — otherwise skip):
`.venv/bin/python render_tutorial.py --tutorial support-tickets --client-dir ../circuitauction-backoffice/client --project-id narr-smoke --offline-narration --capture projects/release-3.5-support-tickets/assets/video/raw.mp4 --manifest projects/release-3.5-support-tickets/assets/manifest.json`
Expected: exit 0 and `projects/narr-smoke/renders/final.mp4` exists (paths of the capture/manifest may differ; `ls projects/release-3.5-support-tickets/assets` to find them).

- [ ] **Step 7: Commit**

```bash
git add render_tutorial.py author_tutorial.py tests/tutorial/test_render_tutorial_narration.py
git commit -m "feat(tutorial): select narration backend/voice from CLI, recipe or env

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: MCP config, service, and tool schema

**Files:**
- Modify: `mcp_servers/circuit_video/config.py` — `DEFAULTS`, `_ENV`, `load_config`, add validators
- Modify: `mcp_servers/circuit_video/service.py` — `doctor`, `render_argv`, `_run_local`, `_run_remote`, `render_tutorial`
- Modify: `mcp_servers/circuit_video/server.py` — `INSTRUCTIONS`, `TOOLS` (`doctor`, `render_tutorial`), `_call`
- Test: `tests/mcp/test_circuit_video.py` (append)

**Interfaces:**
- Consumes: `tools.audio.elevenlabs_narrator.ElevenLabsNarrator.from_env` (Task 2) for `doctor`; `render_tutorial.py` flags (Task 4).
- Produces:
  - `config.validate_narration_backend(value: str) -> str` ("" passes through; else must be `ttsd`/`elevenlabs`), `config.validate_voice_id(value: str) -> str` ("" passes through).
  - `cfg` keys: `narration_backend` ("" = script default), `voice_id`, `narration_cache_dir`, `elevenlabs_api_key`, `elevenlabs_voice_ids`, `elevenlabs_model_id`.
  - `service.render_argv(cfg, ..., narration_backend=None, voice_id=None)`, `service.render_tutorial(..., narration_backend=None, voice_id=None)`, `service.elevenlabs_env(cfg) -> dict[str, str]` (the ELEVENLABS_*/cache vars to inject into the worker subprocess).
  - Tool `render_tutorial` gains `narration_backend` (enum) and `voice_id` (string); `doctor` output gains `"narration_backend"`.

- [ ] **Step 1: Write the failing tests** (append to `tests/mcp/test_circuit_video.py`)

```python
from circuit_video.config import (  # noqa: E402
    load_config,
    validate_narration_backend,
    validate_voice_id,
)
from circuit_video.service import doctor, elevenlabs_env  # noqa: E402


def test_validate_narration_inputs():
    assert validate_narration_backend("") == ""
    assert validate_narration_backend("elevenlabs") == "elevenlabs"
    with pytest.raises(ValueError):
        validate_narration_backend("piper")
    assert validate_voice_id("") == ""
    assert validate_voice_id("21m00Tcm4TlvDq8ikWAM") == "21m00Tcm4TlvDq8ikWAM"
    with pytest.raises(ValueError):
        validate_voice_id("../x")


def test_render_argv_narration_flags_only_when_set():
    cfg = {"client_dir": "/tmp/client", "narration_url": "http://127.0.0.1:5557",
           "render_runtime": "ffmpeg", "narration_backend": "", "voice_id": ""}
    argv = render_argv(cfg, tutorial="t", project_id="p", base_url="https://d.example.com")
    assert "--narration-backend" not in argv and "--voice-id" not in argv
    argv = render_argv(cfg, tutorial="t", project_id="p", base_url="https://d.example.com",
                       narration_backend="elevenlabs", voice_id="VX")
    assert argv[argv.index("--narration-backend") + 1] == "elevenlabs"
    assert argv[argv.index("--voice-id") + 1] == "VX"
    cfg2 = {**cfg, "narration_backend": "elevenlabs"}
    argv = render_argv(cfg2, tutorial="t", project_id="p", base_url="https://d.example.com")
    assert argv[argv.index("--narration-backend") + 1] == "elevenlabs"


def test_load_config_reads_narration_env(monkeypatch):
    monkeypatch.setenv("TUTORIAL_NARRATION_BACKEND", "elevenlabs")
    monkeypatch.setenv("TUTORIAL_VOICE_ID", "VX")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk_test")
    monkeypatch.setenv("ELEVENLABS_VOICE_IDS", "en:V1")
    monkeypatch.setenv("ELEVENLABS_MODEL_ID", "ELEVENLABS_MODEL_ID:-eleven_multilingual_v2")
    cfg = load_config()
    assert cfg["narration_backend"] == "elevenlabs" and cfg["voice_id"] == "VX"
    assert cfg["elevenlabs_api_key"] == "sk_test"
    assert elevenlabs_env(cfg) == {
        "ELEVENLABS_API_KEY": "sk_test",
        "ELEVENLABS_VOICE_IDS": "en:V1",
        "ELEVENLABS_MODEL_ID": "ELEVENLABS_MODEL_ID:-eleven_multilingual_v2",
    }


def test_tools_list_exposes_narration_params():
    tool = next(t for t in TOOLS if t["name"] == "render_tutorial")
    props = tool["inputSchema"]["properties"]
    assert props["narration_backend"]["enum"] == ["ttsd", "elevenlabs"]
    assert props["voice_id"]["type"] == "string"


def test_render_tutorial_elevenlabs_without_key_fails_early(monkeypatch, tmp_path):
    for k in ("ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_IDS", "TUTORIAL_NARRATION_BACKEND"):
        monkeypatch.delenv(k, raising=False)
    spec_dir = tmp_path / "cypress" / "e2e-tutorials"
    spec_dir.mkdir(parents=True)
    (spec_dir / "t.tutorial.cy.js").write_text("")
    cfg = {**load_config(), "client_dir": str(tmp_path), "elevenlabs_api_key": "",
           "elevenlabs_voice_ids": "", "render_api_url": "", "projects_dir": str(tmp_path / "p")}
    monkeypatch.setattr("circuit_video.service.load_config", lambda: cfg)
    out = _call("render_tutorial", {"base_url": "https://d.example.com", "tutorial": "t",
                                    "narration_backend": "elevenlabs"})
    assert out.get("isError") is True
    assert "ELEVENLABS_API_KEY" in out["content"][0]["text"]
    assert not (tmp_path / "p").exists()  # nothing was launched


def test_doctor_reports_elevenlabs_backend(monkeypatch, tmp_path):
    cfg = {**load_config(), "client_dir": str(tmp_path), "base_url": "",
           "narration_backend": "elevenlabs", "voice_id": "",
           "elevenlabs_api_key": "sk", "elevenlabs_voice_ids": "en:V1",
           "elevenlabs_model_id": "", "render_api_url": ""}
    rep = doctor(cfg)
    assert rep["narration_backend"] == "elevenlabs"
    check = next(c for c in rep["checks"] if c["label"] == "elevenlabs narration")
    assert check["status"] == "ok" and "en" in check["detail"]
    assert not any(c["label"] == "ttsd narration" for c in rep["checks"])
    bad = doctor({**cfg, "elevenlabs_api_key": ""})
    check = next(c for c in bad["checks"] if c["label"] == "elevenlabs narration")
    assert check["status"] == "fail" and "ELEVENLABS_API_KEY" in check["detail"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/mcp/test_circuit_video.py -v`
Expected: FAIL at import with `ImportError: cannot import name 'validate_narration_backend'`

- [ ] **Step 3: Modify `config.py`**

Add to `DEFAULTS`:

```python
    "narration_backend": "",   # "" = let render_tutorial.py resolve (recipe/env/ttsd)
    "voice_id": "",
    "narration_cache_dir": "",
```

Add to `_ENV`:

```python
    "narration_backend": "TUTORIAL_NARRATION_BACKEND",
    "voice_id": "TUTORIAL_VOICE_ID",
    "narration_cache_dir": "TUTORIAL_NARRATION_CACHE_DIR",
```

In `load_config`, extend the `tutorial.config.json` key tuple to include `"narration_backend", "voice_id"`, and after the AWS lines add:

```python
    cfg["elevenlabs_api_key"] = env("ELEVENLABS_API_KEY")
    cfg["elevenlabs_voice_ids"] = env("ELEVENLABS_VOICE_IDS")
    cfg["elevenlabs_model_id"] = env("ELEVENLABS_MODEL_ID")
```

Add validators at the bottom:

```python
NARRATION_BACKENDS = ("ttsd", "elevenlabs")
VOICE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def validate_narration_backend(value: str) -> str:
    value = (value or "").strip()
    if value and value not in NARRATION_BACKENDS:
        raise ValueError(f"narration_backend must be one of {', '.join(NARRATION_BACKENDS)}")
    return value


def validate_voice_id(value: str) -> str:
    value = (value or "").strip()
    if value and not VOICE_ID_RE.match(value):
        raise ValueError("voice_id must be 1-64 letters, digits, underscores, or hyphens")
    return value
```

- [ ] **Step 4: Modify `service.py`**

Imports: add `validate_narration_backend, validate_voice_id` to the `.config` import.

Add the env helper (near `_maybe_upload`):

```python
_ELEVENLABS_KEYS = (
    ("elevenlabs_api_key", "ELEVENLABS_API_KEY"),
    ("elevenlabs_voice_ids", "ELEVENLABS_VOICE_IDS"),
    ("elevenlabs_model_id", "ELEVENLABS_MODEL_ID"),
    ("narration_cache_dir", "TUTORIAL_NARRATION_CACHE_DIR"),
)


def elevenlabs_env(cfg: dict) -> dict[str, str]:
    """ELEVENLABS_* (+ cache dir) to hand to the render subprocess, from MCP config."""
    return {env_name: cfg[key] for key, env_name in _ELEVENLABS_KEYS if cfg.get(key)}


def _elevenlabs_narrator(cfg: dict, voice_id: str = ""):
    """Build (offline) the ElevenLabs narrator from MCP config; raises NarrationError."""
    import sys as _sys
    if str(REPO_ROOT) not in _sys.path:
        _sys.path.insert(0, str(REPO_ROOT))
    from tools.audio.elevenlabs_narrator import ElevenLabsNarrator

    return ElevenLabsNarrator.from_env(
        elevenlabs_env(cfg), voice_id=voice_id or cfg.get("voice_id") or None,
    )
```

`render_argv`: add keyword params `narration_backend: Optional[str] = None, voice_id: Optional[str] = None` and after the `--music` block:

```python
    backend = narration_backend or cfg.get("narration_backend") or ""
    if backend:
        argv += ["--narration-backend", backend]
    vid = voice_id or cfg.get("voice_id") or ""
    if vid:
        argv += ["--voice-id", vid]
```

`doctor`: replace the ttsd block with:

```python
    backend = cfg.get("narration_backend") or "ttsd"
    if backend == "elevenlabs":
        try:
            h = _elevenlabs_narrator(cfg).health()
            langs = ",".join(h["languages"]) or "none"
            detail = f"model={h['model_id']} voices: {langs}"
            if h["voice_override"]:
                detail += f" override={h['voice_override']}"
            add("elevenlabs narration", "ok", detail)
        except Exception as e:  # noqa: BLE001
            add("elevenlabs narration", "fail", f"{e} — see mcp_servers/circuit_video/env.example")
    else:
        narr = cfg["narration_url"].rstrip("/")
        try:
            body = _http_json(f"{narr}/health", timeout=5)
            langs = ",".join(body.get("languages", [])) or "none configured"
            status = "ok" if body.get("voices_configured") else "warn"
            add("ttsd narration", status, f"{narr} — voices: {langs}")
        except Exception as e:  # noqa: BLE001
            add("ttsd narration", "fail",
                f"{narr} unreachable: {e} (run `tutorialctl up`, or set "
                "narration_backend=elevenlabs)")
```

and add `"narration_backend": backend,` to the returned dict.

`_run_local`: pass `narration_backend=job.get("narration_backend"), voice_id=job.get("voice_id")` to `render_argv`, and after `env["OPENMONTAGE_PROJECTS_DIR"] = ...` add `env.update(elevenlabs_env(cfg))`.

`_run_remote`: after the `render_runtime` line add:

```python
    for key in ("narration_backend", "voice_id"):
        if job.get(key):
            body[key] = job[key]  # forwarded; the k8s worker keeps ttsd today
```

`render_tutorial`: add params `narration_backend: Optional[str] = None, voice_id: Optional[str] = None`; after the `render_runtime` validation:

```python
    narration_backend = validate_narration_backend(narration_backend or "")
    voice_id = validate_voice_id(voice_id or "")
    effective_backend = narration_backend or cfg.get("narration_backend") or ""
    if effective_backend == "elevenlabs" and not offline and not cfg.get("render_api_url"):
        # Fail before a 5–20 minute Cypress capture when the key/voice is missing.
        try:
            _elevenlabs_narrator(cfg, voice_id).health()
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"ElevenLabs narration not ready: {e}") from e
```

and add `"narration_backend": narration_backend, "voice_id": voice_id,` to the `job` dict. In the background branch, `env.update(elevenlabs_env(cfg))` as well (the `--job` worker re-reads config, but this keeps the two paths identical).

- [ ] **Step 5: Modify `server.py`**

`INSTRUCTIONS`: append `" Narration comes from the ttsd sidecar by default; pass narration_backend=\"elevenlabs\" (and optionally voice_id) to call ElevenLabs directly — run doctor first."`

`doctor` description: `"... ttsd or ElevenLabs narration (per narration_backend), ..."`.

`render_tutorial` properties, after `"offline"`:

```python
            "narration_backend": {
                "type": "string",
                "enum": ["ttsd", "elevenlabs"],
                "description": "ttsd (default; sidecar at TUTORIAL_NARRATION_URL) or elevenlabs "
                               "(direct ElevenLabs API using ELEVENLABS_API_KEY and "
                               "ELEVENLABS_VOICE_IDS; cached per clip). Recipe narration_backend "
                               "is used when omitted.",
            },
            "voice_id": {
                "type": "string",
                "description": "ElevenLabs voice id to narrate with (elevenlabs backend). "
                               "Omit for the per-language voice from ELEVENLABS_VOICE_IDS "
                               "or the recipe's voice_id.",
            },
```

`_call` → `render_tutorial`: add `narration_backend=args.get("narration_backend") or None, voice_id=args.get("voice_id") or None,`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/mcp/test_circuit_video.py -v`
Expected: all PASS

- [ ] **Step 7: Protocol smoke**

Run:
```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"t","version":"0"}}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"doctor","arguments":{}}}' \
  | TUTORIAL_NARRATION_BACKEND=elevenlabs .venv/bin/python mcp_servers/circuit_video/server.py | tail -1 | grep -o '"elevenlabs narration[^}]*'
```
Expected: one `elevenlabs narration` check line, `ok` on this machine (keys exist in `.env`).

- [ ] **Step 8: Commit**

```bash
git add mcp_servers/circuit_video/config.py mcp_servers/circuit_video/service.py mcp_servers/circuit_video/server.py tests/mcp/test_circuit_video.py
git commit -m "feat(circuit-video mcp): narration_backend and voice_id options (ElevenLabs direct)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: `tutorialctl` parity

**Files:**
- Modify: `tutorialctl.py` — `DEFAULTS` (line ~45), `_ENV` (line ~56), `cmd_doctor` (lines 143-156), `cmd_author` (line 390), `cmd_render` (line 401), argparse `common` (line ~443)

**Interfaces:**
- Consumes: CLI flags from Task 4; `tools.audio.elevenlabs_narrator.ElevenLabsNarrator.from_env` and `_narration_env` (existing) for the doctor check.
- Produces: `tutorial.config.json` keys `narration_backend`, `voice_id`; `tutorialctl author|render --narration-backend X --voice-id Y`.

- [ ] **Step 1: Add config keys**

In `DEFAULTS` add `"narration_backend": "", "voice_id": "",`; in `_ENV` add `"narration_backend": "TUTORIAL_NARRATION_BACKEND", "voice_id": "TUTORIAL_VOICE_ID",`. In the `common` argparse group add:

```python
    common.add_argument("--narration-backend", dest="narration_backend", default=S,
                        choices=[S, "ttsd", "elevenlabs"], help="ttsd sidecar or direct ElevenLabs")
    common.add_argument("--voice-id", dest="voice_id", default=S, help="ElevenLabs voice id override")
```

(`S` is the existing "unset" sentinel used by the other common args; keep the same merge logic the file applies to `narration_url`.)

- [ ] **Step 2: Forward the flags**

In `cmd_author` and `cmd_render`, after the `--narration-url` argv entries:

```python
    if cfg.get("narration_backend"):
        argv += ["--narration-backend", cfg["narration_backend"]]
    if cfg.get("voice_id"):
        argv += ["--voice-id", cfg["voice_id"]]
```

- [ ] **Step 3: Doctor check per backend**

Wrap the existing ttsd block in `cmd_doctor`:

```python
    backend = cfg.get("narration_backend") or "ttsd"
    if backend == "elevenlabs":
        nenv, _src = _narration_env(cfg)
        try:
            sys.path.insert(0, str(REPO_ROOT))
            from tools.audio.elevenlabs_narrator import ElevenLabsNarrator
            h = ElevenLabsNarrator.from_env(nenv, voice_id=cfg.get("voice_id") or None).health()
            add("elevenlabs narration", "ok",
                f"model={h['model_id']} voices: {','.join(h['languages']) or 'none'}"
                + (f" override={h['voice_override']}" if h['voice_override'] else ""))
        except Exception as e:  # noqa: BLE001
            add("elevenlabs narration", "fail", str(e))
    else:
        ...existing ttsd check unchanged...
```

and change the trailing hint so it only mentions `tutorialctl up` when `backend == "ttsd"`.

- [ ] **Step 4: Verify**

Run: `.venv/bin/python tutorialctl.py doctor --narration-backend elevenlabs`
Expected: an `elevenlabs narration ok` row, no `ttsd narration` row.

Run: `.venv/bin/python tutorialctl.py doctor`
Expected: unchanged output (ttsd row present).

- [ ] **Step 5: Commit**

```bash
git add tutorialctl.py
git commit -m "feat(tutorialctl): pass narration backend/voice through author, render and doctor

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Docs and examples

**Files:**
- Modify: `mcp_servers/circuit_video/env.example`, `mcp_servers/circuit_video/README.md` ("Local vs remote" section, line ~62), `circuit-mcp.md` (Needs list, line ~31), `tutorial.config.example.json`, `.agents/skills/circuit-video/SKILL.md` (line 25), `deploy/README.md` (one sentence under the ttsd bullet)

- [ ] **Step 1: `env.example`** — append:

```
# Narration backend: "ttsd" (default; sidecar at TUTORIAL_NARRATION_URL) or
# "elevenlabs" (direct API, no Docker). The ElevenLabs keys below are only read
# for the elevenlabs backend; ttsd gets them via `tutorialctl up`.
# TUTORIAL_NARRATION_BACKEND=elevenlabs
# TUTORIAL_VOICE_ID=            # optional single-voice override (else per-lang map)
# ELEVENLABS_API_KEY=
# ELEVENLABS_VOICE_IDS=en:<voice_id>,fr:<voice_id>
# ELEVENLABS_MODEL_ID=eleven_multilingual_v2
# TUTORIAL_NARRATION_CACHE_DIR=.cache/narration/elevenlabs
```

- [ ] **Step 2: `README.md`** — add under "Local vs remote":

```markdown
## Narration

- Default: the `ttsd` sidecar (`tutorialctl up`), one fixed voice per language.
- `narration_backend: "elevenlabs"` (tool argument, `TUTORIAL_NARRATION_BACKEND`,
  or `narration_backend` in the tutorial recipe) calls ElevenLabs directly using
  `ELEVENLABS_API_KEY` + `ELEVENLABS_VOICE_IDS`; pass `voice_id` to pick any
  voice. Clips are cached under `.cache/narration/elevenlabs/` keyed on voice,
  model and text, so authoring and rendering never pay twice.
- Changing the voice changes durations: re-run `tutorialctl author <name>` with
  the same backend/voice before rendering, or the capture pacing drifts (the
  render prints a WARN when `timings.json` disagrees).
- The k8s render-api path still uses the ttsd sidecar.
```

- [ ] **Step 3: `circuit-mcp.md`** — change the narration bullet to:
`- For spoken narration: ttsd on http://127.0.0.1:5557 (tutorialctl up), or narration_backend=elevenlabs with ELEVENLABS_API_KEY + ELEVENLABS_VOICE_IDS / voice_id`
and add `TUTORIAL_NARRATION_BACKEND`, `TUTORIAL_VOICE_ID` to the override list.

- [ ] **Step 4: `tutorial.config.example.json`** — add `"narration_backend": "", "voice_id": ""` with the existing keys. **`SKILL.md`** line 25 → `3. Narration: ttsd sidecar (default) or ElevenLabs direct (narration_backend=elevenlabs, optional voice_id); --offline skips it.` **`deploy/README.md`** ttsd bullet → append `Local renders can bypass it with narration_backend=elevenlabs (see mcp_servers/circuit_video/README.md).` Also update the recipe `notes` text quoted in the client repo's `*.tutorial.json` is out of scope (other repo) — mention in the README that recipes may set `narration_backend` and `voice_id`.

- [ ] **Step 5: Run the whole suite and commit**

Run: `.venv/bin/python -m pytest tests/mcp tests/tutorial tests/lib/test_envfile.py -q`
Expected: all PASS

```bash
git add mcp_servers/circuit_video/env.example mcp_servers/circuit_video/README.md circuit-mcp.md tutorial.config.example.json .agents/skills/circuit-video/SKILL.md deploy/README.md
git commit -m "docs(circuit-video): document the ElevenLabs narration backend and voice_id

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: Live verification (one real render, costs ElevenLabs credits)

Not a code task; do it once at the end with the user's `.env` keys.

- [ ] **Step 1:** `.venv/bin/python tutorialctl.py doctor --narration-backend elevenlabs` → `ok`.
- [ ] **Step 2:** `.venv/bin/python author_tutorial.py --tutorial support-tickets --client-dir ../circuitauction-backoffice/client --narration-backend elevenlabs` → writes `support-tickets.timings.json` with a `narration` block; `.cache/narration/elevenlabs/en/` now holds one WAV per step.
- [ ] **Step 3:** Re-run Step 2 → completes in under a second (all cache hits; check with `ls -l --time-style=+%T .cache/narration/elevenlabs/en` that no file changed).
- [ ] **Step 4:** Through the MCP: `render_tutorial` with `narration_backend="elevenlabs"`, `base_url` the demo app → `final.mp4` narrated; listen to the first step.
- [ ] **Step 5:** Repeat with a different `voice_id` → the render logs the pacing WARN from `timings_voice_warning`; the clip sounds different.
- [ ] **Step 6:** Commit the regenerated `timings.json` in the client repo if the user wants the ElevenLabs voice as the new default pacing.
