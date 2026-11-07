#!/usr/bin/env python3
"""scripts/iss_narrate_all.py — narrate the ISS script via isolated kokoro subprocesses,
concatenate with pauses, run finish_audio, write subtitles.srt + narration_manifest.json."""
import json
import re
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import soundfile as sf

SRC = "docs/openmontage/slice/iss/ISS_FULL_SCRIPT_v0.md"
AUDIO_DIR = Path("docs/openmontage/slice/iss/audio")
SR = 24000
INTRO_S, PAUSE_S, TRAIL_S = 1.0, 0.5, 1.3
PYTHON = "/workspaces/OpenMontage/output/kokoro_venv/bin/python3"
ONE = str(Path(__file__).parent / "iss_narrate_one.py")


def parse_sentences(path):
    sents = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("| "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        if not re.fullmatch(r"B\d+", cells[0]):
            continue
        sents.append(cells[1])
    return sents


def hmsms(sec):
    td = timedelta(seconds=sec)
    total_ms = int(td.total_seconds() * 1000)
    h = total_ms // 3_600_000
    m = (total_ms % 3_600_000) // 60_000
    s = (total_ms % 60_000) // 1000
    ms = total_ms % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    sentences = parse_sentences(SRC)
    print(f"{len(sentences)} sentences to narrate")
    sent_dir = AUDIO_DIR / "sentences"
    sent_dir.mkdir(parents=True, exist_ok=True)

    cues = []  # (start, end, text)
    spoken = []
    t = INTRO_S
    seg_paths = []
    for i, text in enumerate(sentences):
        out_wav = str(sent_dir / f"sent_{i:02d}.wav")
        if Path(out_wav).exists() and Path(out_wav).stat().st_size > 1000:
            print(f"  sentence {i} cached", flush=True)
        else:
            r = subprocess.run([PYTHON, ONE, str(i), text, out_wav], capture_output=True, text=True, timeout=120)
            if r.returncode != 0:
                print(f"  sentence {i} FAILED: {r.stderr[-200:]}", flush=True)
        info = sf.info(out_wav)
        start = t
        dur = info.frames / SR
        seg_paths.append(out_wav)
        t += dur
        part_end = t
        t += PAUSE_S
        cues.append((start, part_end, text))
        spoken.append(text)

    # build raw wav: intro + sentences + pauses + trail
    parts = []
    parts.append(np.zeros(int(INTRO_S * SR), dtype=np.float32))
    for i, text in enumerate(sentences):
        audio, _ = sf.read(str(sent_dir / f"sent_{i:02d}.wav"))
        parts.append(np.asarray(audio, dtype=np.float32))
        parts.append(np.zeros(int(PAUSE_S * SR), dtype=np.float32))
    parts[-1] = np.zeros(int(TRAIL_S * SR), dtype=np.float32)
    narration = np.concatenate(parts)
    raw_wav = AUDIO_DIR / "narration_raw.wav"
    sf.write(raw_wav, narration, SR)
    dur = len(narration) / SR
    Path(AUDIO_DIR / "narration_spoken.txt").write_text(" ".join(spoken), encoding="utf-8")

    # subtitles
    srt_lines = []
    for i, (start, end, text) in enumerate(cues, 1):
        srt_lines.append(str(i))
        srt_lines.append(f"{hmsms(start)} --> {hmsms(end)}")
        srt_lines.append(text)
        srt_lines.append("")
    (AUDIO_DIR / "subtitles.srt").write_text("\n".join(srt_lines), encoding="utf-8")

    # finish_audio
    sys.path.insert(0, ".")
    from tools.audio.finish_audio import FinishAudioTool
    fin = FinishAudioTool()
    res = fin.execute({
        "input_path": str(raw_wav),
        "output_path": str(AUDIO_DIR / "narration_finished.wav"),
    })
    print("finish_audio:", res.success, res.error)
    if res.data:
        print("  measured_loudness:", res.data.get("measured_loudness"))

    manifest = {
        "sentences": len(sentences),
        "duration_s": round(dur, 6),
        "finished_duration_s": None,
        "sample_rate": SR,
        "beats": [f"B{i}" for i in range(1, 9)],
        "engine": "kokoro_82m_cpu",
        "voice": "af_heart",
        "script": SRC,
    }
    (AUDIO_DIR / "narration_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("DONE raw dur=%.2fs" % dur)


if __name__ == "__main__":
    main()
