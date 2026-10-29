"""Client for the `ttsd` narration sidecar (circuit-bid redis-bridge/narration).

The sidecar wraps the existing ElevenLabs + ffmpeg + content-addressed clip
cache as a synchronous HTTP endpoint:

    POST /render {"lang": "en", "text": "..."}  ->  WAV body + X-Duration-Ms header

Because the cache is content-addressed by (lang, voice, text), rendering the same
utterance twice (authoring vs render) returns identical audio and duration with
no extra ElevenLabs cost. This replaces OpenMontage's tts_selector for the
tutorial pipeline, so no ElevenLabs key lives on the OpenMontage side.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import requests


class NarrationError(RuntimeError):
    pass


class NarrationClient:
    def __init__(self, base_url: str = "http://127.0.0.1:5557", timeout: float = 90.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def health(self) -> dict:
        r = requests.get(f"{self.base_url}/health", timeout=10)
        r.raise_for_status()
        return r.json()

    def render(self, lang: str, text: str, out_path: str) -> int:
        """Synthesize (or cache-hit) `text` in `lang`, write a WAV to out_path.

        Returns the clip duration in milliseconds (from the X-Duration-Ms header,
        falling back to a WAV-header computation).
        """
        text = (text or "").strip()
        if not text:
            raise NarrationError("empty narration text")
        try:
            r = requests.post(
                f"{self.base_url}/render",
                json={"lang": lang, "text": text},
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise NarrationError(f"ttsd request failed: {e}") from e
        if r.status_code != 200:
            raise NarrationError(f"ttsd {r.status_code}: {r.text[:300]}")

        data = r.content
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)

        dur_header = r.headers.get("X-Duration-Ms")
        if dur_header:
            try:
                return int(dur_header)
            except ValueError:
                pass
        return wav_duration_ms(data)


def wav_duration_ms(wav_bytes: bytes) -> int:
    """Duration of a PCM WAV in ms, read from its header (no external deps)."""
    import struct

    if len(wav_bytes) < 44 or wav_bytes[0:4] != b"RIFF" or wav_bytes[8:12] != b"WAVE":
        return 0
    # Walk chunks to find fmt (sample rate/block align) and data (length).
    sample_rate = 0
    byte_rate = 0
    data_len = 0
    pos = 12
    while pos + 8 <= len(wav_bytes):
        cid = wav_bytes[pos : pos + 4]
        (csize,) = struct.unpack_from("<I", wav_bytes, pos + 4)
        body = pos + 8
        if cid == b"fmt ":
            (_, _, sample_rate, byte_rate) = struct.unpack_from("<HHII", wav_bytes, body)
        elif cid == b"data":
            data_len = csize
            break
        pos = body + csize + (csize & 1)
    if byte_rate:
        return int(data_len * 1000 / byte_rate)
    if sample_rate:
        return int((data_len / 2) * 1000 / sample_rate)  # assume s16 mono
    return 0
