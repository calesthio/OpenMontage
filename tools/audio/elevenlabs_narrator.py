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
