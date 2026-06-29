#!/usr/bin/env python3
"""
montage_lib — recipe library for the Thiền Đạo video pipeline (Stage 6–7).

Proven FFmpeg recipes extracted from projects/bon-mua-cua-hoi-tho/build_meditation_video.py,
generalized into pure parameterized functions. Each video keeps its own thin driver that
imports these — see scripts/video/README.md. SOP: docs/video-production-pipeline.md.

Design rules (locked by plan 260630-0044):
- Pure functions, no globals / no env reads. Each returns the output path, raises on failure.
- subprocess via ARG LISTS (never shell=True) so titles/paths can't inject shell metachars.
- All on-screen text goes through drawtext `textfile=` (UTF-8) — never interpolated into the graph.
- Idempotent: every renderer skips work when the output already exists (crash-resumable).
- Fail-fast: missing assets and narration overflow raise/warn loudly, never silent black/quiet video.

Surface (≤6 recipes + 1 helper):
  slow_loop_scene · make_card · concat_segments · build_narration_track · duck_mux · remux_audio
  narration_offsets_from_durations  (helper)
"""
from __future__ import annotations
import os
import sys
import subprocess
import tempfile

# Plain path; escaped for the filtergraph at use-site via _esc_filter_path().
DEFAULT_FONT = "C:/Windows/Fonts/arialbd.ttf"


def _esc_filter_path(p: str) -> str:
    """Escape a filesystem path for use INSIDE an ffmpeg filter (drawtext fontfile/textfile).
    Windows paths carry backslashes + a drive colon, both of which are filter metacharacters."""
    return p.replace("\\", "/").replace(":", "\\:")


# --------------------------------------------------------------------------- #
# Internal utilities
# --------------------------------------------------------------------------- #
def _run(args: list[str]) -> None:
    """Run ffmpeg/ffprobe as an arg list (no shell). Raise with stderr tail on failure."""
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        tail = (r.stderr or "")[-1500:]
        raise RuntimeError(f"FFmpeg failed ({args[0]} exit {r.returncode}):\n{tail}")


def _require(path: str, what: str = "asset") -> str:
    """Fail-fast: raise a clear error if an input asset is missing."""
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(f"missing {what}: {path!r}")
    return path


def probe_duration(path: str) -> float:
    """Read media duration in seconds. Locale-safe float parse (handles ',' decimal)."""
    _require(path, "media")
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nokey=1:noprint_wrappers=1", path],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    raw = (r.stdout or "").strip().replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        raise RuntimeError(f"could not read duration of {path!r} (ffprobe: {raw!r})")


def _has_audio(path: str) -> bool:
    """True if the file contains at least one audio stream."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index", "-of", "csv=p=0", path],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return bool((r.stdout or "").strip())


def _check_font(font: str) -> None:
    """drawtext fails cryptically on a missing font — surface it early. Expects a plain path."""
    if not os.path.isfile(font):
        raise FileNotFoundError(
            f"font not found: {font!r} (pass font=... to override the Windows default)")


def _write_textfile(text: str, tmpdir: str, tag: str) -> str:
    """Write on-screen text to a UTF-8 file for drawtext `textfile=` (diacritic-safe, injection-safe)."""
    p = os.path.join(tmpdir, f"_text_{tag}.txt")
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def _write_filtergraph(graph: str, tmpdir: str, tag: str) -> str:
    """Write a (possibly huge) filtergraph to a file, consumed via `-/filter_complex <file>`."""
    p = os.path.join(tmpdir, f"_fc_{tag}.txt")
    with open(p, "w", encoding="utf-8") as f:
        f.write(graph)
    return p


# --------------------------------------------------------------------------- #
# Recipe 1 — slow_loop_scene
# --------------------------------------------------------------------------- #
def slow_loop_scene(scene: str, dur: float, out: str, *, pts: float = 1.2,
                    fps: int = 30, size: str = "1920x1080") -> str:
    """Stream-loop a scene clip, slow it (setpts), scale, and cut to `dur`. Idempotent."""
    if os.path.isfile(out):
        return out
    _require(scene, "scene clip")
    w, h = size.split("x")
    _run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", scene,
          "-vf", f"setpts={pts}*PTS,scale={w}:{h},fps={fps}",
          "-an", "-t", f"{dur}", "-c:v", "libx264", "-pix_fmt", "yuv420p", out])
    return out


# --------------------------------------------------------------------------- #
# Recipe 2 — make_card (intro / outro / title)
# --------------------------------------------------------------------------- #
def make_card(bg: str, text_big: str, dur: float, out: str, *, text_small: str = "",
              font: str = DEFAULT_FONT, fps: int = 30, size: str = "1920x1080",
              color_big: str = "0xFFE9B0", color_small: str = "0xD8E8FF",
              pts: float = 1.2) -> str:
    """
    Title/intro/outro card: slowed bg + centered big text (+ optional subtitle), fade in/out.
    All text via drawtext `textfile=` (UTF-8) — safe for Vietnamese diacritics and any chars.
    Idempotent.
    """
    if os.path.isfile(out):
        return out
    _require(bg, "card background")
    _check_font(font)
    w, h = size.split("x")
    fade = f"alpha='if(lt(t\\,1)\\,t\\,if(gt(t\\,{dur-1.2})\\,{dur}-t\\,1))'"
    with tempfile.TemporaryDirectory() as td:
        font_e = _esc_filter_path(font)
        big_tf = _esc_filter_path(_write_textfile(text_big, td, "big"))
        draw = (f"drawtext=fontfile='{font_e}':textfile='{big_tf}':fontcolor={color_big}:"
                f"fontsize=56:x=(w-text_w)/2:y=(h-text_h)/2-20:{fade}")
        if text_small:
            small_tf = _esc_filter_path(_write_textfile(text_small, td, "small"))
            draw += (f",drawtext=fontfile='{font_e}':textfile='{small_tf}':fontcolor={color_small}:"
                     f"fontsize=30:x=(w-text_w)/2:y=(h-text_h)/2+50:{fade}")
        graph = f"[0:v]setpts={pts}*PTS,scale={w}:{h},fps={fps},eq=brightness=-0.04:saturation=1.05,{draw}[v]"
        fc = _write_filtergraph(graph, td, "card")
        _run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", bg,
              "-/filter_complex", fc, "-map", "[v]",
              "-t", f"{dur}", "-c:v", "libx264", "-pix_fmt", "yuv420p", out])
    return out


# --------------------------------------------------------------------------- #
# Recipe 3 — concat_segments
# --------------------------------------------------------------------------- #
def concat_segments(paths: list[str], out: str, *, reencode: bool = True,
                    fps: int = 30, size: str = "1920x1080") -> str:
    """
    Concat video segments. reencode=True (default) normalizes mismatched segments
    (30fps/yuv420p) — the safe choice when cards + clips differ. reencode=False uses
    `-c copy` (fast) only when every segment shares the exact same encode params.
    Idempotent.
    """
    if os.path.isfile(out):
        return out
    for p in paths:
        _require(p, "segment")
    with tempfile.TemporaryDirectory() as td:
        listfile = os.path.join(td, "concat.txt")
        with open(listfile, "w", encoding="utf-8") as f:
            for p in paths:
                # concat demuxer needs forward slashes + escaped single quotes
                safe = os.path.abspath(p).replace("\\", "/").replace("'", r"'\''")
                f.write(f"file '{safe}'\n")
        args = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile]
        if reencode:
            w, h = size.split("x")
            args += ["-vf", f"scale={w}:{h},fps={fps}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an"]
        else:
            args += ["-c", "copy"]
        args += [out]
        _run(args)
    return out


# --------------------------------------------------------------------------- #
# Helper — narration_offsets_from_durations
# --------------------------------------------------------------------------- #
def narration_offsets_from_durations(cues: list[dict], *, start: float = 0.0,
                                     sentence_gap: float = 0.7, para_gap: float = 1.8,
                                     line_gap: float = 3.5) -> list[tuple[str, float]]:
    """
    Compute absolute narration offsets from per-clip durations + silence gaps — kills the
    manual-offset error class (the narration_dry/wet bug).

    cues: list of dicts, each:
      {"path": "a.mp3", "gap": "sentence"|"paragraph"|"line", "offset": <float optional>}
    - "offset" present  → manual override, used verbatim (cursor jumps past this clip).
    - "offset" absent   → placed at the running cursor; cursor advances by clip duration + gap.
    Returns [(path, absolute_offset_seconds), ...] ready for build_narration_track.
    """
    gaps = {"sentence": sentence_gap, "paragraph": para_gap, "line": line_gap}
    out: list[tuple[str, float]] = []
    cursor = start
    for c in cues:
        path = c["path"]
        if c.get("offset") is not None:
            off = float(c["offset"])
            out.append((path, off))
            cursor = max(cursor, off + probe_duration(path))
        else:
            out.append((path, cursor))
            cursor += probe_duration(path) + gaps.get(c.get("gap", "sentence"), sentence_gap)
    return out


# --------------------------------------------------------------------------- #
# Recipe 4 — build_narration_track
# --------------------------------------------------------------------------- #
def build_narration_track(cues: list[tuple[str, float]], total: float, out: str, *,
                          reverb: bool = False, batch_size: int = 30) -> str:
    """
    Delay each narration cue to its absolute offset and sum them into one track of length `total`.
    cues: [(audio_path, offset_seconds), ...] (e.g. from narration_offsets_from_durations).

    Scale: amix is summed in BATCHES (batch_size, then a final amix of the batch mixes) so a
    60-min sleep video with hundreds of cues doesn't blow up one giant amix (OOM / arg limits).
    amix uses normalize=0 (straight sum) throughout — batching is associative, result identical.
    Idempotent. Overflow (offset+dur > total) is warned, not fatal.
    """
    if os.path.isfile(out):
        return out
    # Filter empty / silence-only cues, validate, warn on overflow.
    real: list[tuple[str, float]] = []
    for path, off in cues:
        _require(path, "narration cue")
        d = probe_duration(path)
        if d <= 0.05:
            continue  # skip empty / placeholder
        if off + d > total + 0.5:
            print(f"[warn] narration cue {os.path.basename(path)} ends at "
                  f"{off + d:.1f}s > total {total:.1f}s (will be trimmed)", file=sys.stderr)
        real.append((path, off))
    if not real:
        raise ValueError("no non-empty narration cues to mix")

    rev = "bass=g=2:f=120,aecho=0.85:0.9:55:0.15," if reverb else ""
    with tempfile.TemporaryDirectory() as td:
        inputs: list[str] = []
        lines: list[str] = []
        for i, (path, off) in enumerate(real):
            inputs += ["-i", path]
            ms = int(off * 1000)
            lines.append(f"[{i}:a]{rev}adelay={ms}|{ms}[n{i}];")

        # Batch the per-cue streams, then mix the batch results.
        batch_labels: list[str] = []
        for b, s in enumerate(range(0, len(real), batch_size)):
            members = "".join(f"[n{j}]" for j in range(s, min(s + batch_size, len(real))))
            n = min(s + batch_size, len(real)) - s
            lines.append(f"{members}amix=inputs={n}:duration=longest:normalize=0[b{b}];")
            batch_labels.append(f"[b{b}]")
        if len(batch_labels) == 1:
            # single batch: alias [b0] -> [a]
            graph = "\n".join(lines) + f"{batch_labels[0]}anull[a]"
        else:
            graph = ("\n".join(lines) +
                     f"{''.join(batch_labels)}amix=inputs={len(batch_labels)}:"
                     f"duration=longest:normalize=0[a]")
        fc = _write_filtergraph(graph, td, "narr")
        _run(["ffmpeg", "-y", *inputs, "-/filter_complex", fc, "-map", "[a]",
              "-t", f"{total}", "-c:a", "aac", "-b:a", "192k", out])
    return out


# --------------------------------------------------------------------------- #
# Recipe 5 — duck_mux
# --------------------------------------------------------------------------- #
def duck_mux(video_silent: str, narration: str, music: str, out: str, *,
             total: float | None = None, music_vol: float = 0.40,
             loudnorm_i: float = -16.0, loudnorm_tp: float = -1.5) -> str:
    """
    Final mux: silent video + narration + looped music, with music sidechain-ducked under the
    voice and a loudness pass. Locked defaults: music_vol 0.40, duck ratio 8 @ thresh 0.03,
    loudnorm I=-16 TP=-1.5. Idempotent.
    """
    if os.path.isfile(out):
        return out
    _require(video_silent, "silent video")
    _require(narration, "narration track")
    _require(music, "music bed")
    if total is None:
        total = probe_duration(video_silent)
    with tempfile.TemporaryDirectory() as td:
        graph = (
            f"[2:a]atrim=0:{total},volume={music_vol},"
            f"afade=t=in:st=0:d=3,afade=t=out:st={total-4}:d=4[mus];\n"
            # sidechain: duck music whenever narration is present
            f"[mus][1:a]sidechaincompress=threshold=0.03:ratio=8:attack=200:release=800[ducked];\n"
            f"[1:a][ducked]amix=inputs=2:duration=first:normalize=0,"
            f"loudnorm=I={loudnorm_i}:TP={loudnorm_tp}:LRA=11,alimiter=limit=0.95[a]"
        )
        fc = _write_filtergraph(graph, td, "mix")
        _run(["ffmpeg", "-y", "-i", video_silent, "-i", narration,
              "-stream_loop", "-1", "-i", music, "-/filter_complex", fc,
              "-map", "0:v", "-map", "[a]", "-t", f"{total}",
              "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", out])
    return out


# --------------------------------------------------------------------------- #
# Recipe 6 — remux_audio
# --------------------------------------------------------------------------- #
def remux_audio(video_silent: str, audio: str, out: str) -> str:
    """
    Swap the audio of an ALREADY-RENDERED video without re-encoding video (-c:v copy).
    GUARD: refuses a video that already carries an audio stream — remuxing onto a non-silent
    master double-layers the music (a real shipped bug). Pass renders/final-clean.mp4 (silent).
    Idempotent.
    """
    if os.path.isfile(out):
        return out
    _require(video_silent, "video")
    _require(audio, "audio")
    if _has_audio(video_silent):
        raise ValueError(
            f"refusing to remux: {video_silent!r} already has an audio stream "
            f"(would double-layer music). Use the silent/clean master.")
    _run(["ffmpeg", "-y", "-i", video_silent, "-i", audio,
          "-map", "0:v", "-c:v", "copy", "-map", "1:a", "-c:a", "aac", "-b:a", "192k", out])
    return out
