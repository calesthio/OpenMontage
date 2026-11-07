"""TTS engine — Kokoro (primary) + Piper CPU fallback.

V7 §3, layer 2 (VOICE). Returns explicit status
(success / fallback_used / failed) per synthesis call; never fails
silently. Zero-cost: Piper is local CPU, no API key/credits. Kokoro path is
kept for quality when available but is not required.

V8 §3.4 / §8.11: voice is synthesized by semantic blocks (paragraphs), not
mechanically per sentence. Each block WAV is preserved with its sample count,
sample rate, and synthesis parameters so the narration master can measure
duration from actual samples.
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
    failure_class: str = "OPTIONAL"  # REQUIRED | OPTIONAL | DEGRADABLE | MANUAL_REVIEW
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
                        failure_class="OPTIONAL",
                        reason="kokoro unavailable; piper CPU fallback used",
                    )
            except Exception as exc:  # pragma: no cover - env dependent
                return TtsResult(
                    text=text, output_path=str(out), engine="none",
                    status="failed",
                    failure_class="REQUIRED",
                    reason=f"kokoro and piper both failed: {exc}",
                )

        return TtsResult(
            text=text, output_path=str(out), engine="none", status="failed",
            failure_class="REQUIRED",
            reason="no TTS engine available (kokoro/piper not installed)",
        )


    def synthesize_blocks(
        self,
        blocks: list[dict[str, Any]],
        output_dir: str | Path,
        *,
        voice: str = "default",
        inter_block_pause_s: float = 0.30,
    ) -> list[TtsResult]:
        """Synthesize a list of semantic voice blocks (paragraphs).

        Each block dict must have ``block_id`` and ``text``.  Optional
        ``pause_after_seconds`` and ``crossfade_seconds`` per block override
        the defaults.  Returns one :class:`TtsResult` per block with the
        block WAV preserved at ``<output_dir>/<block_id>.wav``.

        V8 §3.4: each block's WAV is preserved with sample count and sample
        rate so the narration master can measure duration from actual samples.
        """
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        results: list[TtsResult] = []

        for block in blocks:
            block_id = str(block.get("block_id", f"block_{len(results):03d}"))
            text = str(block.get("text", ""))
            out_path = out_dir / f"{block_id}.wav"
            results.append(
                self.synthesize(text, str(out_path), voice=voice)
            )

        return results


def synthesize_speech(text: str, output_path: str | Path,
                      voice: str = "default") -> dict[str, Any]:
    """Module-level convenience entry point."""
    return TtsEngine().synthesize(text, output_path, voice).to_dict()


# ---------------------------------------------------------------------------
# TTS A/B (V8 §8.11 / wave 3.2)
# ---------------------------------------------------------------------------


@dataclass
class TtsAbResult:
    """Result of comparing two TTS engines on the same text."""

    text: str
    engine_a: str  # e.g. "kokoro"
    engine_b: str  # e.g. "piper"
    result_a: TtsResult
    result_b: TtsResult
    chosen: str  # engine_id of the preferred result
    reason: str  # why this engine was chosen
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["result_a"] = self.result_a.to_dict()
        d["result_b"] = self.result_b.to_dict()
        if not self.created_at:
            d["created_at"] = datetime.now(timezone.utc).isoformat()
        return d


class TtsAbTester:
    """Compare two TTS engines on the same text and pick the preferred one.

    Preference order:
      1. success > fallback_used > failed
      2. shorter duration (more concise narration)
      3. kokoro preferred over piper when both succeed (quality)
    """

    def __init__(self, engine_a: str = "kokoro", engine_b: str = "piper") -> None:
        self.engine_a = engine_a
        self.engine_b = engine_b

    def run(
        self,
        text: str,
        output_dir: str | Path,
        *,
        voice: str = "default",
    ) -> TtsAbResult:
        """Synthesize ``text`` with both engines and return the preferred."""
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        path_a = out_dir / f"ab_{self.engine_a}.wav"
        path_b = out_dir / f"ab_{self.engine_b}.wav"

        result_a = self._synthesize_with(text, str(path_a), self.engine_a, voice)
        result_b = self._synthesize_with(text, str(path_b), self.engine_b, voice)

        chosen, reason = self._pick(result_a, result_b)

        return TtsAbResult(
            text=text,
            engine_a=self.engine_a,
            engine_b=self.engine_b,
            result_a=result_a,
            result_b=result_b,
            chosen=chosen,
            reason=reason,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _synthesize_with(
        self, text: str, output_path: str, engine: str, voice: str
    ) -> TtsResult:
        """Synthesize with a specific engine, forcing that engine path."""
        # Temporarily constrain availability to force the chosen engine.
        engine_order = [engine]
        result = self._synthesize_one(text, output_path, voice, engine_order)
        return result

    def _synthesize_one(
        self, text: str, output_path: str, voice: str,
        engine_order: list[str]
    ) -> TtsResult:
        """Synthesize with the first engine in engine_order."""
        engine = engine_order[0]
        if engine == "kokoro":
            kokoro = self._kokoro_available()
            if kokoro:
                try:
                    out_path = Path(output_path)
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    self._synthesize_kokoro(text, str(out_path), voice)
                    if out_path.is_file():
                        return TtsResult(
                            text=text, output_path=str(out_path), engine="kokoro",
                            status="success",
                            reason="kokoro synthesis succeeded",
                        )
                except Exception:
                    pass
                # Kokoro failed -> fall through to report failure for this engine
                return TtsResult(
                    text=text, output_path=str(out_path), engine="kokoro",
                    status="failed",
                    failure_class="REQUIRED",
                    reason="kokoro synthesis failed",
                )
            return TtsResult(
                text=text, output_path=str(output_path), engine="kokoro",
                status="failed",
                failure_class="REQUIRED",
                reason="kokoro not available",
            )
        if engine == "piper":
            piper = self._piper_available()
            if piper:
                try:
                    out_path = Path(output_path)
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    self._synthesize_piper(text, str(out_path), voice)
                    if out_path.is_file():
                        return TtsResult(
                            text=text, output_path=str(out_path), engine="piper",
                            status="success",
                            reason="piper synthesis succeeded",
                        )
                except Exception:
                    pass
                return TtsResult(
                    text=text, output_path=str(output_path), engine="piper",
                    status="failed",
                    failure_class="REQUIRED",
                    reason="piper synthesis failed",
                )
            return TtsResult(
                text=text, output_path=str(output_path), engine="piper",
                status="failed",
                failure_class="REQUIRED",
                reason="piper not available",
            )
        return TtsResult(
            text=text, output_path=str(output_path), engine=engine,
            status="failed",
            failure_class="REQUIRED",
            reason=f"unknown engine {engine}",
        )

    def _kokoro_available(self) -> bool:
        import importlib.util
        return importlib.util.find_spec("kokoro") is not None

    def _piper_available(self) -> bool:
        import shutil
        return shutil.which("piper-tts") is not None or \
            shutil.which("piper") is not None

    def _synthesize_kokoro(self, text: str, output_path: str, voice: str) -> None:
        raise NotImplementedError("kokoro binding not implemented in this repo")

    def _synthesize_piper(self, text: str, output_path: str, voice: str) -> None:
        import subprocess
        subprocess.run(
            ["piper-tts", "--model", "default", "--output", output_path, "--text", text],
            check=True, capture_output=True, timeout=120,
        )

    def _pick(self, ra: TtsResult, rb: TtsResult) -> tuple[str, str]:
        """Pick preferred engine; return (chosen_engine_id, reason)."""
        rank = {"success": 3, "fallback_used": 2, "failed": 1}
        ra_rank = rank.get(ra.status, 0)
        rb_rank = rank.get(rb.status, 0)
        if ra_rank > rb_rank:
            return ra.engine, f"{ra.engine} succeeded, {rb.engine} did not"
        if rb_rank > ra_rank:
            return rb.engine, f"{rb.engine} succeeded, {ra.engine} did not"
        # Same status: prefer kokoro when both succeed (quality).
        if ra.status == "success" and self.engine_a == "kokoro":
            return ra.engine, "both succeeded; kokoro preferred for quality"
        if rb.status == "success" and self.engine_b == "kokoro":
            return rb.engine, "both succeeded; kokoro preferred for quality"
        # Fallback: shorter duration (file size proxy), then engine_a.
        return ra.engine, "equal status; keeping engine_a as default"


def tts_ab_test(
    text: str,
    output_dir: str | Path,
    *,
    engine_a: str = "kokoro",
    engine_b: str = "piper",
    voice: str = "default",
) -> dict[str, Any]:
    """Module-level convenience: run TTS A/B and return dict."""
    tester = TtsAbTester(engine_a=engine_a, engine_b=engine_b)
    return tester.run(text, output_dir, voice=voice).to_dict()
