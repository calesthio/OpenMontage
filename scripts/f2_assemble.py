#!/usr/bin/env python3
"""F2 step 4: assemble the pilot — per-sentence pan/zoom stills timed to audio.

Frame sequence is JPEG (not PNG): 37k PNG frames would be ~15 GB, JPEG is ~1.5 GB.

Per sentence
  * one 1024x1024 still from the Kaggle batch
  * upscaled to 2304x1296 (lanczos), Ken Burns move from the EDL pan_direction
  * frame count taken from the CUMULATIVE frame grid, so sentence i starts on the
    frame nearest its true audio start (error <= 1/60 s at every boundary, and it
    never accumulates — unlike rounding each duration on its own)
  * JPEG frames written as /tmp/f2/frames/%06d.jpg (q=3, yuvj420p)

Then
  * one x264 CRF18 encode of the whole sequence (no re-encode per segment)
  * narration.wav muxed as AAC 192k
  * music bed only if music_library/ holds a track, at -20 dB under narration,
    otherwise logged as SKIPPED (never silently omitted)
  * pilot.srt written from the SAME frame grid (so subtitle drift is ~0)
  * edit_decisions.json + narration_manifest.json for tools/qa/qc.py

No burned-in captions: the stills carry an empty lower fifth by prompt, and the
SRT is a sidecar only.

Usage:
  python3 scripts/f2_assemble.py --check          # validate inputs, no render
  python3 scripts/f2_assemble.py --workers 2      # render frames + encode
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parent.parent
WORK = Path(os.environ.get("F2_WORK", "/tmp/f2"))   # overridable for the smoke test
EDL = WORK / "edl.csv"
IMAGES = WORK / "images"
FRAMES = WORK / "frames"
AUDIO = WORK / "audio/narration.wav"
FINAL = WORK / "final.mp4"
SRT = WORK / "pilot.srt"
FPS = 30
OUT_W, OUT_H = 1920, 1080
MID_W, MID_H = 2304, 1296          # 1.2x of output: room for the crop, still cheap
PAN_ZOOM = 1.15
ZOOM_DELTA = 0.15
JPEG_Q = "3"
MUSIC_DIR = REPO / "music_library"
MUSIC_DB = -20.0

MOVES = ("left", "right", "up", "down", "zoom_in", "zoom_out")


def read_edl() -> List[Dict[str, Any]]:
    with EDL.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit("BLOCKED: edl.csv is empty")
    return rows


def build_grid(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Cumulative frame grid: boundaries rounded once, never per-segment."""
    t = 0.0
    segs: List[Dict[str, Any]] = []
    for r in rows:
        dur = float(r["duration_s"])
        f0 = round(t * FPS)
        f1 = round((t + dur) * FPS)
        n = max(2, f1 - f0)
        segs.append({"row": r, "start_s": round(t, 3), "dur": dur,
                     "f0": f0, "n": n, "start_frame": f0 + 1})
        t += dur
    return {"segments": segs, "total_s": round(t, 3),
            "total_frames": sum(s["n"] for s in segs)}


def move_filter(move: str, n: int) -> str:
    p = f"min(on/{max(n - 1, 1)},1)"
    if move == "left":       # camera travels right -> left
        z, x, y = f"{PAN_ZOOM}", f"(iw-iw/zoom)*(1-{p})", "(ih-ih/zoom)/2"
    elif move == "right":
        z, x, y = f"{PAN_ZOOM}", f"(iw-iw/zoom)*{p}", "(ih-ih/zoom)/2"
    elif move == "up":
        z, x, y = f"{PAN_ZOOM}", "(iw-iw/zoom)/2", f"(ih-ih/zoom)*(1-{p})"
    elif move == "down":
        z, x, y = f"{PAN_ZOOM}", "(iw-iw/zoom)/2", f"(ih-ih/zoom)*{p}"
    elif move == "zoom_in":
        z, x, y = f"{PAN_ZOOM}+{ZOOM_DELTA}*{p}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif move == "zoom_out":
        z, x, y = f"{PAN_ZOOM}+{ZOOM_DELTA}*(1-{p})", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    else:
        raise SystemExit(f"BLOCKED: unknown pan_direction {move!r}")
    return (f"scale={MID_W}:{MID_H}:flags=lanczos,"
            f"zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={OUT_W}x{OUT_H}:fps={FPS},"
            f"format=yuvj420p")


def render_segment(seg: Dict[str, Any]) -> Dict[str, Any]:
    row, n, start = seg["row"], seg["n"], seg["start_frame"]
    img = IMAGES / f"{row['sentence_id']}.png"
    last = start + n - 1
    if (FRAMES / f"{last:06d}.jpg").is_file() and (FRAMES / f"{start:06d}.jpg").is_file():
        return {"sentence_id": row["sentence_id"], "skipped": True, "frames": n}
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(img),
           "-vf", move_filter(row["pan_direction"], n),
           "-frames:v", str(n), "-q:v", JPEG_Q,
           "-start_number", str(start), str(FRAMES / "%06d.jpg")]
    t0 = time.perf_counter()
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit(f"BLOCKED: {row['sentence_id']} render failed: {p.stderr[-400:]}")
    return {"sentence_id": row["sentence_id"], "skipped": False, "frames": n,
            "seconds": round(time.perf_counter() - t0, 2)}


def find_music() -> Path | None:
    if not MUSIC_DIR.is_dir():
        return None
    for ext in ("*.mp3", "*.wav", "*.m4a", "*.flac", "*.ogg"):
        hits = sorted(MUSIC_DIR.rglob(ext))
        if hits:
            return hits[0]
    return None


def encode(total_frames: int, music: Path | None) -> Dict[str, Any]:
    """One encode pass. Audio = narration (+ optional bed at -20 dB)."""
    cmd = ["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS),
           "-start_number", "1", "-i", str(FRAMES / "%06d.jpg"),
           "-i", str(AUDIO)]
    if music is not None:
        cmd += ["-stream_loop", "-1", "-i", str(music)]
        fc = (f"[2:a]volume={MUSIC_DB}dB,atrim=0:{total_frames / FPS:.3f}[bed];"
              f"[1:a][bed]amix=inputs=2:duration=first:dropout_transition=0,"
              f"alimiter=limit=0.84:level=false[a]")
        cmd += ["-filter_complex", fc, "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
            "-r", str(FPS), "-g", str(FPS * 2), "-movflags", "+faststart",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-frames:v", str(total_frames), str(FINAL)]
    t0 = time.perf_counter()
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit(f"BLOCKED: encode failed: {p.stderr[-600:]}")
    return {"seconds": round(time.perf_counter() - t0, 1),
            "music": str(music) if music else None}


def write_srt(segs: List[Dict[str, Any]]) -> None:
    def ts(t: float) -> str:
        h, r = divmod(max(t, 0.0), 3600)
        m, s = divmod(r, 60)
        ms = int(round((s - int(s)) * 1000))
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{ms:03d}"

    lines: List[str] = []
    for i, seg in enumerate(segs, 1):
        a = seg["f0"] / FPS
        b = (seg["f0"] + seg["n"]) / FPS
        words = seg["row"]["text"].split()
        caps, buf = [], []
        for w in words:
            if len(" ".join(buf + [w])) <= 42:
                buf.append(w)
            else:
                caps.append(" ".join(buf))
                buf = [w]
        if buf:
            caps.append(" ".join(buf))
        if len(caps) > 2:                      # max 2 caption lines per cue
            mid = (len(caps) + 1) // 2
            caps = [" ".join(caps[:mid]), " ".join(caps[mid:])]
        lines += [str(i), f"{ts(a)} --> {ts(b)}", "\n".join(caps), ""]
    SRT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_qc_inputs(segs: List[Dict[str, Any]], total_s: float) -> None:
    cuts = []
    for i, seg in enumerate(segs, 1):
        r = seg["row"]
        cuts.append({
            "id": f"c{i:03d}",
            "sentence_id": r["sentence_id"],
            "start": round(seg["f0"] / FPS, 3),
            "end": round((seg["f0"] + seg["n"]) / FPS, 3),
            "role": "graphic",           # original illustration = original graphic
            "kind": "still",
            "move": r["pan_direction"],
            "generator": "AI",
            "label": "Speculative illustration",
            "description": r["image_prompt"],
            "annotation": f"{r['sentence_id']}: {r['text'][:120]}",
            "source": f"/tmp/f2/images/{r['sentence_id']}.png",
        })
    (WORK / "edit_decisions.json").write_text(json.dumps({
        "schema_version": "1.0", "job_id": "f2-pilot-1",
        "fps": FPS, "resolution": [OUT_W, OUT_H],
        "narration": {"file": str(AUDIO), "duration_s": total_s},
        "cuts": cuts}, indent=2) + "\n", encoding="utf-8")
    (WORK / "narration_manifest.json").write_text(json.dumps({
        "expected_duration": round(total_s, 3),
        "tolerance": 1.0,
        "sentences": len(segs),
        "audio": str(AUDIO)}, indent=2) + "\n", encoding="utf-8")


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--no-encode", action="store_true")
    args = ap.parse_args(argv)

    for p in (EDL, AUDIO):
        if not p.is_file():
            raise SystemExit(f"BLOCKED: missing {p}")
    rows = read_edl()
    missing = [r["sentence_id"] for r in rows
               if not (IMAGES / f"{r['sentence_id']}.png").is_file()]
    if missing:
        raise SystemExit(f"BLOCKED: {len(missing)} stills missing, first {missing[:5]}")
    bad = [r["sentence_id"] for r in rows if r["pan_direction"] not in MOVES]
    if bad:
        raise SystemExit(f"BLOCKED: bad pan_direction on {bad[:5]}")

    grid = build_grid(rows)
    segs = grid["segments"]
    print(f"edl {len(rows)} sentences | audio {grid['total_s']:.2f}s | "
          f"{grid['total_frames']} frames @ {FPS}fps "
          f"({grid['total_frames'] / FPS:.2f}s video)")
    if args.check:
        return 0

    FRAMES.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    done = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        for res in ex.map(render_segment, segs):
            done += 1
            if done % 20 == 0 or done == len(segs):
                el = time.perf_counter() - t0
                print(f"  frames {done}/{len(segs)} elapsed={el:.0f}s "
                      f"eta={el / done * (len(segs) - done):.0f}s", flush=True)
    render_s = round(time.perf_counter() - t0, 1)
    print(f"frame render: {render_s}s | {len(list(FRAMES.glob('*.jpg')))} jpgs")

    write_srt(segs)
    write_qc_inputs(segs, grid["total_s"])

    music = find_music()
    if music is None:
        print(f"music bed: SKIPPED (no audio file under {MUSIC_DIR})")
    else:
        print(f"music bed: {music} at {MUSIC_DB} dB under narration")

    if args.no_encode:
        return 0
    enc = encode(grid["total_frames"], music)
    size = FINAL.stat().st_size if FINAL.is_file() else 0
    print(f"encode: {enc['seconds']}s | {FINAL} {size / 1e6:.1f} MB")
    (WORK / "assemble_report.json").write_text(json.dumps({
        "sentences": len(rows), "frames": grid["total_frames"],
        "audio_s": grid["total_s"], "render_s": render_s,
        "encode_s": enc["seconds"], "music": enc["music"],
        "music_skipped": enc["music"] is None, "final_bytes": size,
        "fps": FPS, "resolution": [OUT_W, OUT_H],
        "frame_format": "jpeg", "jpeg_q": JPEG_Q,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
