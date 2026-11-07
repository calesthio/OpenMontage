"""TTS engine — Kokoro (primary) + Piper CPU fallback.

V7 §3, layer 2 (VOICE). Returns explicit status
(success / fallback_used / failed) per synthesis call; never fails
silently. Zero-cost: Piper is local CPU, no API key/credits. Kokoro path is
kept for quality when available but is not required.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class TtsResult:
    text: str
    output_path: str
    engine: str  # "kokoro" | "piper" | "none"
    status: str  # success | fallback_used | failed
    reason: str
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if not self.created_at:
            d["created_at"] = datetime.now(timezone.utc).isoformat()
        return d


class TtsEngine:
    """Synthesize narration to WAV. Prefers Kokoro when installed, falls
    back to Piper (local CPU, zero-cost). Returns explicit status."""

    def __init__(self, kokoro_bin: str | None = None,
                 piper_bin: str | None = None) -> None:
        self.kokoro_bin = kokoro_bin or os.environ.get("KOKORO_BIN", "kokoro")
        self.piper_bin = piper_bin or os.environ.get("PIPER_BIN", "piper")

    def _have(self, binary: str) -> bool:
        return shutil.which(binary) is not None

    def synthesize(self, text: str, output_path: str | Path,
                   voice: str = "default") -> TtsResult:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        # 1. Try Kokoro (quality primary).
        if self._have(self.kokoro_bin):
            try:
                subprocess.run(
                    [self.kokoro_bin, "--voice", voice, "--text", text,
                     "--output", str(out)],
                    check=True, capture_output=True, timeout=180,
                )
                if out.is_file():
                    return TtsResult(
                        text=text, output_path=str(out), engine="kokoro",
                        status="success",
                        reason="kokoro synthesized successfully",
                    )
            except Exception as exc:  # pragma: no cover - env dependent
                pass  # fall through to Piper

        # 2. Fallback: Piper local CPU TTS (zero-cost, no key).
        if self._have(self.piper_bin):
            try:
                subprocess.run(
                    [self.piper_bin, "--voice", voice, "--output_file",
                     str(out), "--text", text],
                    check=True, capture_output=True, timeout=180,
                )
                if out.is_file():
                    return TtsResult(
                        text=text, output_path=str(out), engine="piper",
                        status="fallback_used",
                        reason="kokoro unavailable; piper CPU fallback used",
                    )
            except Exception as exc:  # pragma: no cover - env dependent
                return TtsResult(
                    text=text, output_path=str(out), engine="none",
                    status="failed",
                    reason=f"kokoro and piper both failed: {exc}",
                )

        return TtsResult(
            text=text, output_path=str(out), engine="none", status="failed",
            reason="no TTS engine available (kokoro/piper not installed)",
        )


def synthesize_speech(text: str, output_path: str | Path,
                      voice: str = "default") -> dict[str, Any]:
    """Module-level convenience entry point."""
    return TtsEngine().synthesize(text, output_path, voice).to_dict()
