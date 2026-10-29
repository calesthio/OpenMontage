#!/usr/bin/env python3
"""F2 step 1: per-sentence Kokoro narration + normalized mix + EDL CSV.

Pipeline
  1. parse docs/openmontage/pilot/script.md (S001..S214, one sentence each)
  2. synthesize one WAV per sentence (kokoro, af_heart, 24 kHz mono PCM16)
  3. concatenate raw -> measure (ebur128) -> constant gain + true-peak limiter
     to the qc_thresholds targets (-14 LUFS, -1.5 dBTP) -> narration.wav
  4. split the normalized track back at the raw sample offsets -> per-sentence
     normalized WAVs (same audio as the final mix, not a second render)
  5. write EDL CSV: sentence_id,text,audio_file,duration_s,image_prompt,
     image_file,pan_direction

Resumable: existing non-empty WAVs are kept. No network, no paid calls.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import time
import wave
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "docs/openmontage/pilot/script.md"
WORK = Path("/tmp/f2")
RAW = WORK / "audio/raw"
NORM = WORK / "audio/norm"
EDL = WORK / "edl.csv"
DURATIONS = WORK / "audio/durations.json"
TARGET_LUFS = -14.0
TRUE_PEAK = -1.5

SENT_RE = re.compile(r"^S(\d{3})\s+\[([^\]]+)\]\s+(.*\S)\s*$")
PAN_CYCLE = ["left", "right", "up", "down", "zoom_in", "zoom_out"]


def parse_script() -> List[Dict[str, str]]:
    lines = SCRIPT.read_text(encoding="utf-8").splitlines()
    rows: List[Dict[str, str]] = []
    i = 0
    while i < len(lines):
        m = SENT_RE.match(lines[i])
        if m:
            prompt = ""
            if i + 1 < len(lines) and lines[i + 1].strip().startswith("PROMPT:"):
                prompt = lines[i + 1].split("PROMPT:", 1)[1].strip()
            if not prompt:
                raise SystemExit(f"BLOCKED: S{m.group(1)} has no PROMPT line")
            rows.append({"sentence_id": f"S{m.group(1)}", "claim": m.group(2),
                         "text": m.group(3), "image_prompt": prompt})
            i += 2
            continue
        i += 1
    return rows


def synth(rows: List[Dict[str, str]], limit: int | None = None) -> None:
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline

    RAW.mkdir(parents=True, exist_ok=True)
    todo = [r for r in rows if not (RAW / f"{r['sentence_id']}.wav").is_file()
            or (RAW / f"{r['sentence_id']}.wav").stat().st_size < 1000]
    if limit:
        todo = todo[:limit]
    if not todo:
        print("all sentences already synthesized")
        return

    pipe = KPipeline(lang_code="a")
    t0 = time.perf_counter()
    for n, r in enumerate(todo, 1):
        chunks = [np.asarray(a, dtype=np.float32)
                  for _, _, a in pipe(r["text"], voice="af_heart", speed=1.0)]
        audio = np.concatenate(chunks) if chunks else np.zeros(1, dtype=np.float32)
        out = RAW / f"{r['sentence_id']}.wav"
        sf.write(out, audio, 24000, subtype="PCM_16")
        if n % 10 == 0 or n == len(todo):
            el = time.perf_counter() - t0
            print(f"  tts {n}/{len(todo)} {r['sentence_id']} "
                  f"{len(audio)/24000:.2f}s elapsed={el:.0f}s "
                  f"eta={el/n*(len(todo)-n):.0f}s", flush=True)


def wav_info(path: Path) -> Dict[str, Any]:
    with wave.open(str(path), "rb") as w:
        return {"frames": w.getnframes(), "rate": w.getframerate(),
                "channels": w.getnchannels(), "width": w.getsampwidth()}


def concat_raw(rows: List[Dict[str, str]]) -> Path:
    out = WORK / "audio/narration_raw.wav"
    lst = WORK / "audio/concat.txt"
    lst.write_text("".join(f"file '{(RAW / (r['sentence_id'] + '.wav')).as_posix()}'\n"
                           for r in rows), encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-c", "copy", str(out)], check=True)
    return out


def measure(path: Path) -> Dict[str, float]:
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
                        "-filter_complex", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, check=True)
    txt = p.stderr
    def grab_last(pat: str) -> float:
        # ebur128 prints per-block "I:" lines before the summary block; the
        # summary integrated loudness is the LAST "I:" match, so take it.
        ms = re.findall(pat, txt)
        return float(ms[-1]) if ms else float("nan")
    return {"I": grab_last(r"I:\s+(-?\d+\.\d+)\s+LUFS"),
            "LRA": grab_last(r"LRA:\s+(-?\d+\.\d+)\s+LU"),
            "TP": grab_last(r"Peak:\s+(-?\d+\.\d+)\s+dBFS")}


def loudnorm_measure(path: Path) -> Dict[str, float]:
    """Two-pass loudnorm pass 1: measure integrated loudness/LRA/true peak."""
    p = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
         "-af", "loudnorm=print_format=json", "-f", "null", "-"],
        capture_output=True, text=True, check=True)
    txt = p.stderr
    def grab(pat: str) -> float:
        m = re.search(pat, txt)
        return float(m.group(1)) if m else float("nan")
    return {
        "measured_I": grab(r'"input_i"\s*:\s*"?([-\d.]+)"?'),
        "measured_LRA": grab(r'"input_lra"\s*:\s*"?([-\d.]+)"?'),
        "measured_TP": grab(r'"input_tp"\s*:\s*"?([-\d.]+)"?'),
        "measured_thresh": grab(r'"input_thresh"\s*:\s*"?([-\d.]+)"?'),
    }


def normalize(raw: Path) -> tuple[Path, Dict[str, float], float]:
    """EBU R128 two-pass loudnorm to TARGET_LUFS with true-peak ceiling."""
    before = loudnorm_measure(raw)
    out = WORK / "audio/narration.wav"
    af = (f"loudnorm=I={TARGET_LUFS}:TP={TRUE_PEAK - 0.3}:LRA=11:"
          f"measured_I={before['measured_I']}:measured_LRA={before['measured_LRA']}:"
          f"measured_TP={before['measured_TP']}:measured_thresh={before['measured_thresh']}:"
          f"offset=0:linear=true,aresample=24000")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw),
                    "-af", af, "-ac", "1", "-c:a", "pcm_s16le", str(out)], check=True)
    after = measure(out)
    return out, {"before": before, "after": after,
                 "target_lufs": TARGET_LUFS, "target_tp": TRUE_PEAK - 0.3,
                 "filter": af, "gain_db": 0.0}


def split_norm(rows: List[Dict[str, str]], narration: Path) -> List[Dict[str, Any]]:
    """Cut the normalized mix back at raw sentence boundaries (sample-exact)."""
    NORM.mkdir(parents=True, exist_ok=True)
    info = wav_info(narration)
    rate = info["rate"]
    meta: List[Dict[str, Any]] = []
    pos = 0
    for r in rows:
        raw_info = wav_info(RAW / f"{r['sentence_id']}.wav")
        frames = raw_info["frames"]
        start = pos / rate
        dur = frames / rate
        out = NORM / f"{r['sentence_id']}.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.6f}",
                        "-t", f"{dur:.6f}", "-i", str(narration),
                        "-c:a", "pcm_s16le", str(out)], check=True)
        got = wav_info(out)["frames"] / rate
        meta.append({"sentence_id": r["sentence_id"], "start_s": round(start, 3),
                     "duration_s": round(got, 3), "audio_file": str(out),
                     "text": r["text"], "image_prompt": r["image_prompt"],
                     "claim": r["claim"]})
        pos += frames
    return meta


def write_edl(meta: List[Dict[str, Any]]) -> None:
    EDL.parent.mkdir(parents=True, exist_ok=True)
    with EDL.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sentence_id", "text", "audio_file", "duration_s",
                    "image_prompt", "image_file", "pan_direction"])
        for i, m in enumerate(meta):
            w.writerow([m["sentence_id"], m["text"], m["audio_file"],
                        f"{m['duration_s']:.3f}", m["image_prompt"],
                        f"/tmp/f2/images/{m['sentence_id']}.png",
                        PAN_CYCLE[i % len(PAN_CYCLE)]])


def write_srt(meta: List[Dict[str, Any]]) -> None:
    def ts(t: float) -> str:
        h, r = divmod(t, 3600); m, s = divmod(r, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}"
    out = WORK / "pilot.srt"
    t = 0.0
    lines = []
    for i, m in enumerate(meta, 1):
        a, b = t, t + m["duration_s"]
        # split long sentences into <= 42-char caption lines, max 2 lines
        words, buf, caps = m["text"].split(), [], []
        for word in words:
            if len(" ".join(buf + [word])) <= 42:
                buf.append(word)
            else:
                caps.append(" ".join(buf)); buf = [word]
        if buf:
            caps.append(" ".join(buf))
        if len(caps) > 2:
            mid = len(caps) // 2
            caps = [" ".join(caps[:mid]), " ".join(caps[mid:])]
        lines += [str(i), f"{ts(a)} --> {ts(b)}", "\n".join(caps), ""]
        t = b
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"srt: {out} ({len(meta)} cues, {t:.1f}s)")


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=None,
                    help="synthesize only the first N missing sentences")
    ap.add_argument("--skip-synth", action="store_true")
    args = ap.parse_args(argv)

    rows = parse_script()
    print(f"script: {len(rows)} sentences")
    if not args.skip_synth:
        synth(rows, args.limit)
        if args.limit:
            print("limit mode: stopping before mix")
            return 0
    raw = concat_raw(rows)
    narration, stats = normalize(raw)
    b = stats["before"]
    print(f"loudness before: I={b['measured_I']} TP={b['measured_TP']} | "
          f"after: I={stats['after']['I']} TP={stats['after']['TP']} "
          f"(target {TARGET_LUFS} LUFS / <={TRUE_PEAK} dBTP)")
    meta = split_norm(rows, narration)
    total = sum(m["duration_s"] for m in meta)
    DURATIONS.write_text(json.dumps({"total_s": round(total, 3),
                                     "loudness": stats, "sentences": meta},
                                    indent=2) + "\n", encoding="utf-8")
    write_edl(meta)
    write_srt(meta)
    print(f"total narration: {total:.1f}s ({total/60:.2f} min) | edl: {EDL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
