"""Runs inside the VieNeu venv (not OpenMontage's). stdin: JSON job, stdout: JSON result.

Kept dependency-light on purpose: only numpy/soundfile/vieneu, all present in any venv
that has `vieneu` installed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf


def _load_profile(engine, path: str) -> None:
    """Register extra preset voices (e.g. a cloned voice exported by VieNeu)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for name, p in data.get("presets", {}).items():
        engine._preset_voices[name] = {
            "description": p.get("description", ""),
            "gender": p.get("gender", ""),
            "style": p.get("style", "tu_nhien"),
            "speaker_emb": np.asarray(p["speaker_emb"], dtype="float32"),
            "codes": np.asarray(p["codes"], dtype="int64") if p.get("codes") else None,
        }


def main() -> int:
    job = json.load(sys.stdin)
    from vieneu import Vieneu  # only importable inside the VieNeu venv

    engine = Vieneu()
    # Repo-level cloned voices (assets/voices/vieneu/*.json) are always available;
    # an explicit voice_profile is loaded on top and wins on name clashes.
    if job.get("voices_dir"):
        for extra in sorted(Path(job["voices_dir"]).glob("*.json")):
            _load_profile(engine, str(extra))
    if job.get("voice_profile"):
        _load_profile(engine, job["voice_profile"])

    voice = job.get("voice")
    known = [vid for _, vid in engine.list_preset_voices()]
    if voice and voice not in known:
        print(json.dumps({"error": f"Unknown voice '{voice}'. Available: {known}"}), flush=True)
        return 2

    sr = engine.sample_rate
    gap = float(job.get("gap_seconds", 0.4))
    pieces, segments, t = [], [], 0.0
    for line in job["lines"]:
        wav = np.asarray(engine.infer(line, voice=voice), dtype=np.float32)
        dur = len(wav) / sr
        segments.append({"text": line, "start": round(t, 3), "end": round(t + dur, 3)})
        pieces.append(wav)
        pieces.append(np.zeros(int(gap * sr), np.float32))
        t += dur + gap

    full = np.concatenate(pieces)
    peak = float(np.max(np.abs(full))) or 1.0
    full = full / peak * 0.891  # peak -1 dBFS
    out = Path(job["output_path"])
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), full, sr)
    print(json.dumps({
        "output": str(out), "sample_rate": sr, "duration_seconds": round(len(full) / sr, 3),
        "voice": voice or getattr(engine, "_default_voice", None), "segments": segments,
        "voices_available": known,
    }), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
