#!/usr/bin/env python3
"""
_qa — QA gates for the Thiền Đạo pipeline (SOP Stage 8), used by the _validate_*.py drivers.

Three gates, all read-only ffprobe/ffmpeg:
  assert_video        — codec / resolution / duration sanity (raises on mismatch)
  assert_voice_present — silencedetect: prove the narration timeline actually carries voice
  copyright_gate      — HARD BLOCK: scan format_tags for Content-ID / CC-BY music artists

These are validation tooling (underscore-prefixed), NOT part of the montage_lib public surface.
"""
from __future__ import annotations
import subprocess

# Banned music-source markers. Copyright gate is a BLOCKING publish condition (plan 260630-0044),
# not a hint: meditation music must be AI-generated / Content-ID-safe (see memory: avoid Kevin MacLeod).
BANNED_MUSIC_MARKERS = (
    "kevin macleod", "macleod", "incompetech",
    "creative commons", "cc-by", "cc by", "licensed under",
)


def _ffprobe(args: list[str]) -> str:
    """Run ffprobe with the given trailing args; return stdout (stripped)."""
    r = subprocess.run(["ffprobe", "-v", "error", *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "").strip()


def assert_video(path: str, *, want_w: int = 1920, want_h: int = 1080,
                 want_dur: float | None = None, dur_tol: float = 2.5) -> dict:
    """ffprobe gate: video stream present, resolution == want, duration within tolerance.
    Returns the probed {codec,w,h,dur}. Raises AssertionError on any mismatch."""
    vs = _ffprobe(["-select_streams", "v:0", "-show_entries",
                   "stream=codec_name,width,height", "-of", "csv=p=0", path])
    if not vs:
        raise AssertionError(f"[QA] no video stream in {path!r}")
    parts = vs.split(",")
    codec, w, h = parts[0], int(parts[1]), int(parts[2])
    dur_raw = _ffprobe(["-show_entries", "format=duration",
                        "-of", "default=nokey=1:noprint_wrappers=1", path]).replace(",", ".")
    dur = float(dur_raw)
    if (w, h) != (want_w, want_h):
        raise AssertionError(f"[QA] {path}: resolution {w}x{h} != expected {want_w}x{want_h}")
    if want_dur is not None and abs(dur - want_dur) > dur_tol:
        raise AssertionError(
            f"[QA] {path}: duration {dur:.2f}s off target {want_dur:.2f}s (tol {dur_tol}s)")
    print(f"[QA] OK video {path}: {codec} {w}x{h} {dur:.2f}s")
    return {"codec": codec, "w": w, "h": h, "dur": dur}


def assert_voice_present(path: str, *, noise: str = "-30dB", min_speech_frac: float = 0.05) -> float:
    """silencedetect gate: confirm the mixed audio actually carries voice (not all-silent).
    Returns the non-silent fraction. Raises if the track is effectively silent."""
    total_raw = _ffprobe(["-show_entries", "format=duration",
                          "-of", "default=nokey=1:noprint_wrappers=1", path]).replace(",", ".")
    total = float(total_raw)
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", path, "-af",
         f"silencedetect=noise={noise}:d=0.5", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    # silencedetect reports cumulative silence via "silence_duration" lines on stderr.
    silence = 0.0
    for line in (r.stderr or "").splitlines():
        if "silence_duration:" in line:
            silence += float(line.split("silence_duration:")[1].strip())
    speech_frac = max(0.0, (total - silence) / total) if total > 0 else 0.0
    if speech_frac < min_speech_frac:
        raise AssertionError(
            f"[QA] {path}: only {speech_frac:.1%} non-silent — voice timeline missing?")
    print(f"[QA] OK voice {path}: {speech_frac:.0%} non-silent (silence {silence:.1f}s/{total:.1f}s)")
    return speech_frac


def copyright_gate(*paths: str) -> None:
    """HARD BLOCK: scan format_tags of each file; raise if any Content-ID / CC-BY marker appears.
    Pass the music bed and/or the final render. This is a blocking publish gate, not advisory."""
    for path in paths:
        tags = _ffprobe(["-show_entries", "format_tags", "-of", "default=noprint_wrappers=1", path])
        low = tags.lower()
        hit = [m for m in BANNED_MUSIC_MARKERS if m in low]
        if hit:
            raise AssertionError(
                f"[QA][COPYRIGHT] {path}: banned music marker(s) {hit} in tags:\n{tags}\n"
                f"Replace with AI-generated / Content-ID-safe music before publishing.")
        print(f"[QA] OK copyright {path}: no Content-ID/CC-BY markers in format_tags")
