#!/usr/bin/env python3
"""scripts/kokoro_torch_narrate.py — Kokoro-82M narration via the torch KPipeline.

Fallback for environments where the kokoro-onnx weights are absent but the
torch venv (output/kokoro_venv) is installed and already downloaded the
Apache-2.0 Kokoro-82M weights from the official HF repo.

Same CLI/output contract as scripts/z3_kokoro_narrate.py:
    python kokoro_torch_narrate.py <script.md> <out.wav>
prints one JSON line (sentences, duration_s, sample_rate, engine, voice).

Spoken text never includes the bracketed claim ids. No network at runtime
beyond the first model fetch (HF cache); no paid routes.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

INTRO_S = 1.0
PAUSE_S = 0.5
TRAIL_S = 1.3
SR = 24000
VOICE = "af_heart"
REPO_ID = "hexgrad/Kokoro-82M"

_CLAIM_MARKER = re.compile(r"\s*\[[^\]]*\]\s*$")
_TABLE_BEAT = re.compile(r"^B\d+(?:-\d+)?$")


def strip_claim_ids(text: str) -> str:
    """Remove a trailing `[SE-01, SE-04]` marker from a spoken sentence."""
    return _CLAIM_MARKER.sub("", str(text)).strip()


def parse_script(path: str | Path) -> list[str]:
    """Parse a script markdown into spoken sentences, in order.

    Supports the pipeline's `| B1 | sentence | claim_ids |` tables and the
    pilot's `- sentence [SE-01]` bullet style. Claim markers are stripped.
    Raises FileNotFoundError when the script is missing.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(str(p))
    table: list[str] = []
    bullets: list[str] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) >= 2 and _TABLE_BEAT.match(cells[0]) and cells[1]:
                table.append(strip_claim_ids(cells[1]))
        elif stripped.startswith("- "):
            text = strip_claim_ids(stripped[2:])
            if text:
                bullets.append(text)
    sentences = table or bullets
    if not sentences:
        raise ValueError(f"no narratable sentences in {p}")
    return sentences


def synthesize(sentences: list[str], out_wav: str | Path) -> dict:
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline

    pipeline = KPipeline(lang_code="a")
    silence = lambda sec: np.zeros(int(sec * SR), dtype=np.float32)  # noqa: E731
    parts = [silence(INTRO_S)]
    for i, text in enumerate(sentences):
        chunks = [np.asarray(audio, dtype=np.float32)
                  for _gs, _ps, audio in pipeline(text, voice=VOICE)]
        if chunks:
            parts.append(np.concatenate(chunks))
        parts.append(silence(PAUSE_S))
    parts[-1] = silence(TRAIL_S)
    narration = np.concatenate(parts)

    out = Path(out_wav)
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), narration, SR)
    return {
        "sentences": len(sentences),
        "duration_s": round(len(narration) / SR, 6),
        "sample_rate": SR,
        "wav": str(out),
        "engine": "kokoro_82m_torch_cpu",
        "voice": VOICE,
        "repo_id": REPO_ID,
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        print("usage: kokoro_torch_narrate.py <script.md> <out.wav>", file=sys.stderr)
        return 2
    sentences = parse_script(argv[0])
    info = synthesize(sentences, argv[1])
    print(json.dumps(info))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
