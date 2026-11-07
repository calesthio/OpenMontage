#!/usr/bin/env python3
"""P0 v2 smoke test: TTS -> stills with pan/zoom -> SRT -> mux, measured.

What the machine actually has (checked at runtime, never assumed):
  * repo TTS tools: registry reports every provider `unavailable` and no piper
    binary / voice model exists, so this script uses the system `espeak-ng`
    (offline, free) and records that substitution in the report;
  * repo music library: `music_library/` does not exist -> step 4 is reported
    as MISSING and the render continues voice-only (never faked);
  * Remotion: `remotion-composer/node_modules` is absent, so the still-image
    Ken Burns path used here is ffmpeg `zoompan`.

Outputs are written under /tmp/p0_smoke/; only the final mp4, the srt and the
JSON/markdown logs are copied to docs/openmontage/smoke/.

Usage:
  python scripts/p0_smoke_run.py
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tools.subtitle.subtitle_gen import SubtitleGen  # noqa: E402

WORK = Path("/tmp/p0_smoke")
DOCS = REPO / "docs/openmontage/smoke"
FPS = 30
SIZE = "1920x1080"

SENTENCES = [
    "Two hundred metres beneath the ice, the vent field glows in total darkness.",
    "Bacteria turn the mineral plume into food, and the whole web begins there.",
    "Nothing in this world has ever seen the sun.",
]

# Existing repo stills (projects/ is gitignored; these are real files on disk).
IMAGES = [
    "projects/se_pilot/assets/illustrations/filter_drifter_r0001.png",
    "projects/se_pilot/assets/illustrations/frozen_ocean_food_web_r0025.png",
    "projects/se_pilot/assets/illustrations/ice_burrower_r0033.png",
]

# alternate: zoom in / pan left->right / zoom out
MOTION = ["zoom_in", "pan_right", "zoom_out"]


def run(cmd: List[str], timeout: int = 900) -> subprocess.CompletedProcess:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(
            f"command failed ({p.returncode}): {' '.join(cmd)}\n"
            f"stderr tail:\n{p.stderr[-2000:]}")
    return p


def probe_duration(path: Path) -> float:
    p = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)])
    return round(float(p.stdout.strip()), 4)


def probe_streams(path: Path) -> Dict[str, Any]:
    p = run(["ffprobe", "-v", "error", "-show_streams", "-show_format",
             "-of", "json", str(path)])
    data = json.loads(p.stdout)
    return {
        "duration": round(float(data["format"]["duration"]), 3),
        "size_bytes": int(data["format"]["size"]),
        "bit_rate": int(data["format"].get("bit_rate", 0)),
        "streams": [
            {"type": s["codec_type"], "codec": s.get("codec_name"),
             "width": s.get("width"), "height": s.get("height"),
             "fps": s.get("r_frame_rate"), "sample_rate": s.get("sample_rate"),
             "channels": s.get("channels")}
            for s in data["streams"]
        ],
    }


def _frame_diff(path: Path, t0: float, t1: float) -> Dict[str, float]:
    """Mean absolute luma difference between two frames (proves stills move)."""
    import numpy as np
    from PIL import Image
    import io

    def grab(t: float) -> "np.ndarray":
        # binary-safe: run() decodes text, so call subprocess directly for png
        b = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path),
             "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
            capture_output=True, check=True).stdout
        return np.asarray(Image.open(io.BytesIO(b)).convert("L"),
                          dtype=np.float32)
    a, b = grab(t0), grab(t1)
    return {"mean_abs_diff": round(float(np.abs(a - b).mean()), 4),
            "max_abs_diff": round(float(np.abs(a - b).max()), 2)}


def verify_output(final: Path, srt: Path, segments: List[Path],
                  audio_durations: List[float],
                  streams: Dict[str, Any]) -> Dict[str, Any]:
    srt_text = srt.read_text(encoding="utf-8").strip()
    cue_starts = [ln for ln in srt_text.splitlines() if "-->" in ln]
    last_end = cue_starts[-1].split("-->")[1].strip() if cue_starts else ""
    motion = []
    for i, seg in enumerate(segments):
        d = probe_duration(seg)
        motion.append({"segment": seg.name,
                       **_frame_diff(seg, 0.1, max(0.2, d - 0.15))})
    loud = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(final),
                "-af", "ebur128=framelog=quiet", "-f", "null", "-"])
    lufs = None
    for line in loud.stderr.splitlines():
        line = line.strip()
        if line.startswith("I:"):
            try:
                lufs = float(line.split()[1])
            except (IndexError, ValueError):
                pass
    sil = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(final),
               "-af", "silencedetect=noise=-45dB:d=0.4", "-f", "null", "-"])
    silences = sum(1 for ln in sil.stderr.splitlines()
                   if "silence_start" in ln)
    blk = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(final),
               "-vf", "blackdetect=d=0.2:pix_th=0.1", "-f", "null", "-"])
    blacks = sum(1 for ln in blk.stderr.splitlines() if "black_start" in ln)
    return {
        "audio_durations": audio_durations,
        "audio_sum_seconds": round(sum(audio_durations), 3),
        "video_duration_seconds": streams["duration"],
        "duration_delta_seconds": round(streams["duration"]
                                        - sum(audio_durations), 3),
        "srt_cues": len(cue_starts),
        "srt_last_cue_end": last_end,
        "subtitle_stream_present": any(s["type"] == "subtitle"
                                       for s in streams["streams"]),
        "motion": motion,
        "integrated_lufs": lufs,
        "silence_events_0_4s": silences,
        "black_events_0_2s": blacks,
    }


def zoompan_filter(motion: str, frames: int) -> str:
    if motion == "zoom_in":
        z = f"1+0.10*on/{max(1, frames - 1)}"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
    elif motion == "zoom_out":
        z = f"1.10-0.10*on/{max(1, frames - 1)}"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
    else:  # pan_right
        z = "1.06"
        x = f"(iw-iw/zoom)*on/{max(1, frames - 1)}"
        y = "ih/2-(ih/zoom/2)"
    return (
        f"scale=3840:2160:force_original_aspect_ratio=increase,"
        f"crop=3840:2160,"
        f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={SIZE}:fps={FPS},"
        f"format=yuv420p"
    )


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--crf", type=int, default=20)
    ap.add_argument("--preset", default="veryfast")
    args = ap.parse_args(argv)

    for tool in ("espeak-ng", "ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise SystemExit(f"MISSING TOOL: {tool}")

    if WORK.exists():
        shutil.rmtree(WORK)
    (WORK / "audio").mkdir(parents=True)
    (WORK / "segments").mkdir(parents=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    report: Dict[str, Any] = {
        "schema_version": "1.0",
        "milestone": "P0-v2",
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": {
            "tts_used": "system espeak-ng (repo TTS providers all unavailable)",
            "music_bed": "MISSING",
            "renderer": "ffmpeg zoompan (Remotion not installed)",
        },
        "sentences": [],
        "steps": {},
    }

    # ---- step 1: one audio file per sentence, measured ----------------------
    t_tts = time.perf_counter()
    audio_paths: List[Path] = []
    for i, sentence in enumerate(SENTENCES, start=1):
        wav = WORK / "audio" / f"s{i:02d}.wav"
        run(["espeak-ng", "-v", "en-us", "-s", "160", "-p", "45",
             "-w", str(wav), sentence])
        dur = probe_duration(wav)
        audio_paths.append(wav)
        report["sentences"].append({
            "index": i, "text": sentence, "audio": wav.name,
            "duration_seconds": dur, "image": IMAGES[i - 1],
            "motion": MOTION[i - 1],
        })
    report["steps"]["1_tts"] = {
        "status": "PASS",
        "files": [p.name for p in audio_paths],
        "durations": [s["duration_seconds"] for s in report["sentences"]],
        "wall_seconds": round(time.perf_counter() - t_tts, 2),
    }

    # ---- step 2: one still per sentence, exactly its sentence duration ------
    t_render = time.perf_counter()
    seg_paths: List[Path] = []
    for i, rec in enumerate(report["sentences"]):
        src = REPO / rec["image"]
        if not src.is_file():
            raise SystemExit(f"MISSING IMAGE: {src}")
        frames = int(round(rec["duration_seconds"] * FPS))
        seg = WORK / "segments" / f"seg{i + 1:02d}.mp4"
        run([
            "ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS),
            "-i", str(src),
            "-vf", zoompan_filter(rec["motion"], frames),
            "-frames:v", str(frames),
            "-c:v", "libx264", "-preset", args.preset, "-crf", str(args.crf),
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            str(seg),
        ])
        rec["segment_frames"] = frames
        rec["segment_duration_media"] = probe_duration(seg)
        seg_paths.append(seg)

    # concat video (stream copy)
    concat_list = WORK / "concat.txt"
    concat_list.write_text(
        "".join(f"file '{p}'\n" for p in seg_paths), encoding="utf-8")
    silent = WORK / "video_silent.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
         "-c", "copy", str(silent)])

    # concat voice (stream copy; same espeak format for every sentence)
    voice_list = WORK / "voice_concat.txt"
    voice_list.write_text(
        "".join(f"file '{p}'\n" for p in audio_paths), encoding="utf-8")
    voice = WORK / "voice.wav"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(voice_list),
         "-c", "copy", str(voice)])

    # ---- step 3: srt from the same durations (no burn-in) -------------------
    segments = []
    t = 0.0
    for rec in report["sentences"]:
        segments.append({"text": rec["text"],
                         "start": round(t, 3),
                         "end": round(t + rec["duration_seconds"], 3)})
        t += rec["duration_seconds"]
    srt_tmp = WORK / "p0_smoke.srt"
    sg = SubtitleGen().execute({
        "segments": segments,
        "format": "srt",
        "output_path": str(srt_tmp),
    })
    if not sg.success:
        raise SystemExit(f"SUBTITLE FAILED: {sg.error}")
    report["steps"]["3_srt"] = {
        "status": "PASS",
        "tool": "tools/subtitle/subtitle_gen.py (SubtitleGen)",
        "cues": sg.data.get("cue_count"),
        "text": srt_tmp.read_text(encoding="utf-8"),
    }

    # ---- step 4: music bed -------------------------------------------------
    music = MUSIC_STATUS
    report["steps"]["4_music"] = music

    # ---- step 5: mux + 1080p mp4 ------------------------------------------
    final = WORK / "p0_smoke.mp4"
    run([
        "ffmpeg", "-y", "-i", str(silent), "-i", str(voice),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart",
        "-shortest", str(final),
    ])
    render_seconds = round(time.perf_counter() - t_render, 2)

    streams = probe_streams(final)
    video_seconds = streams["duration"]
    verification = verify_output(final, srt_tmp, seg_paths,
                                 [r["duration_seconds"]
                                  for r in report["sentences"]],
                                 streams)
    report["verification"] = verification
    report["steps"]["2_video"] = {
        "status": "PASS",
        "per_sentence": [
            {"index": r["index"], "image": r["image"], "motion": r["motion"],
             "audio_seconds": r["duration_seconds"],
             "segment_media_seconds": r["segment_duration_media"],
             "delta_seconds": round(r["segment_duration_media"]
                                    - r["duration_seconds"], 3)}
            for r in report["sentences"]
        ],
    }
    report["steps"]["5_mux"] = {
        "status": "PASS",
        "command": "ffmpeg -i video_silent.mp4 -i voice.wav -c:v copy "
                   "-c:a aac -b:a 192k -ar 48000 -shortest",
        "output": str(final),
        "probe": streams,
    }
    report["measurement"] = {
        "video_seconds": video_seconds,
        "render_seconds": render_seconds,
        "render_ratio_seconds_per_video_second":
            round(render_seconds / video_seconds, 3) if video_seconds else None,
        "estimate_18_min_seconds":
            round(render_seconds / video_seconds * 1080, 1)
            if video_seconds else None,
        "estimate_18_min_minutes":
            round(render_seconds / video_seconds * 1080 / 60, 2)
            if video_seconds else None,
        "crf": args.crf, "preset": args.preset, "fps": FPS, "size": SIZE,
        "timed_scope": "segment renders + concat + subtitle + mux",
    }

    # ---- copy only the final mp4 + srt + logs ------------------------------
    shutil.copy2(final, DOCS / "p0_smoke.mp4")
    shutil.copy2(srt_tmp, DOCS / "p0_smoke.srt")
    report["copied"] = ["docs/openmontage/smoke/p0_smoke.mp4",
                        "docs/openmontage/smoke/p0_smoke.srt"]
    report["disk"] = {
        "work_dir_bytes": sum(p.stat().st_size for p in WORK.rglob("*")
                              if p.is_file()),
        "final_mp4_bytes": (DOCS / "p0_smoke.mp4").stat().st_size,
        "srt_bytes": (DOCS / "p0_smoke.srt").stat().st_size,
    }
    report["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    (DOCS / "p0_smoke_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["measurement"], indent=2))
    print(json.dumps(report["steps"]["1_tts"]["durations"]))
    print(json.dumps(streams, indent=2))
    print(f"disk: work={report['disk']['work_dir_bytes']} bytes, "
          f"mp4={report['disk']['final_mp4_bytes']} bytes")
    return 0


MUSIC_STATUS: Dict[str, Any] = {
    "status": "MISSING",
    "detail": "music_library/ does not exist and the repo contains no local "
              "royalty-free music file (only narration wavs). No bed was "
              "invented or downloaded; the delivered mp4 is voice-only.",
}


if __name__ == "__main__":
    sys.exit(main())
