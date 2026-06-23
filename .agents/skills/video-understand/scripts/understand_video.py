#!/usr/bin/env python3
"""Understand video content locally using ffmpeg and Whisper.

Extracts key frames and transcribes audio from a video file, outputting
structured JSON for downstream analysis. No API keys needed.

Examples:
    # Scene detection + transcribe
    python3 understand_video.py video.mp4

    # Keyframe extraction
    python3 understand_video.py video.mp4 -m keyframe

    # Regular intervals, limit to 10 frames
    python3 understand_video.py video.mp4 -m interval --max-frames 10

    # Frames only, skip transcription
    python3 understand_video.py video.mp4 --no-transcribe

    # Quiet mode, output to file
    python3 understand_video.py video.mp4 -q -o result.json
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_YOUTUBE_PATTERNS = (
    "youtube.com/", "youtu.be/", "youtube-nocookie.com/",
)

_SCENE_THRESHOLD = 0.3
_DEFAULT_MAX_FRAMES = 20
_DEFAULT_WHISPER_MODEL = "base"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_quiet = False


def log(msg):
    """Print a progress message to stderr (suppressed in quiet mode)."""
    if not _quiet:
        print(f"[video-understand] {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd, check=True, capture=True):
    """Run a subprocess command, logging it and returning the result."""
    log(f"  $ {' '.join(cmd)}")
    return subprocess.run(
        cmd, capture_output=capture, text=True, check=check,
    )


def _format_timestamp(seconds):
    """Format seconds into MM:SS or HH:MM:SS."""
    seconds = max(0.0, seconds)
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _is_youtube_url(path):
    """Check if a path looks like a YouTube URL."""
    lower = path.lower()
    return any(p in lower for p in _YOUTUBE_PATTERNS)


# ---------------------------------------------------------------------------
# FFprobe: video metadata
# ---------------------------------------------------------------------------

def probe_video(video_path):
    """Extract duration, width, and height from a video file via ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        video_path,
    ]
    result = _run(cmd)
    data = json.loads(result.stdout)

    width, height = 0, 0
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            width = int(stream.get("width", 0))
            height = int(stream.get("height", 0))
            break

    duration = float(data.get("format", {}).get("duration", 0.0))
    return duration, width, height


# ---------------------------------------------------------------------------
# Frame extraction
# ---------------------------------------------------------------------------

def extract_frames_scene(video_path, frames_dir):
    """Extract frames at scene changes. Returns list of frame paths."""
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"select='gt(scene,{_SCENE_THRESHOLD})',showinfo",
        "-vsync", "vfr",
        "-q:v", "2",
        os.path.join(frames_dir, "frame_%04d.jpg"),
    ]
    result = _run(cmd, check=False)

    # Collect extracted frame files
    frames = sorted(
        f for f in os.listdir(frames_dir) if f.startswith("frame_") and f.endswith(".jpg")
    )
    frame_paths = [os.path.join(frames_dir, f) for f in frames]

    # Parse timestamps from showinfo output (logged to stderr by ffmpeg)
    timestamps = _parse_showinfo_timestamps(result.stderr)

    return frame_paths, timestamps


def extract_frames_keyframe(video_path, frames_dir):
    """Extract I-frames (keyframes). Returns list of frame paths."""
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", "select='eq(pict_type,I)'",
        "-vsync", "vfr",
        "-q:v", "2",
        os.path.join(frames_dir, "frame_%04d.jpg"),
    ]
    _run(cmd, check=False)

    frames = sorted(
        f for f in os.listdir(frames_dir) if f.startswith("frame_") and f.endswith(".jpg")
    )
    frame_paths = [os.path.join(frames_dir, f) for f in frames]

    # Keyframe mode: we cannot easily get timestamps from the filter, so
    # we will assign them later via ffprobe or estimate them.
    return frame_paths, []


def extract_frames_interval(video_path, frames_dir, duration, max_frames):
    """Extract frames at regular intervals. Returns list of frame paths."""
    if duration <= 0 or max_frames <= 0:
        return [], []

    interval = max(duration / max_frames, 0.1)
    fps_value = f"1/{interval:.4f}"

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"fps={fps_value}",
        "-q:v", "2",
        os.path.join(frames_dir, "frame_%04d.jpg"),
    ]
    _run(cmd, check=False)

    frames = sorted(
        f for f in os.listdir(frames_dir) if f.startswith("frame_") and f.endswith(".jpg")
    )
    frame_paths = [os.path.join(frames_dir, f) for f in frames]

    # Calculate timestamps based on interval
    timestamps = [i * interval for i in range(len(frame_paths))]
    return frame_paths, timestamps


def _parse_showinfo_timestamps(stderr_text):
    """Parse pts_time values from ffmpeg showinfo filter output."""
    timestamps = []
    # showinfo outputs lines like: [Parsed_showinfo_1 ...] n:  0 pts:  12345 pts_time:1.234 ...
    pattern = re.compile(r"pts_time:\s*([\d.]+)")
    for line in stderr_text.split("\n"):
        if "showinfo" in line:
            match = pattern.search(line)
            if match:
                timestamps.append(float(match.group(1)))
    return timestamps


# ---------------------------------------------------------------------------
# Subsampling
# ---------------------------------------------------------------------------

def subsample_frames(frame_paths, timestamps, max_frames):
    """Subsample to at most max_frames, keeping first and last."""
    if len(frame_paths) <= max_frames:
        return frame_paths, timestamps

    log(f"Subsampling {len(frame_paths)} frames down to {max_frames}")

    if max_frames <= 0:
        return [], []
    if max_frames == 1:
        return [frame_paths[0]], [timestamps[0]] if timestamps else [0.0]
    if max_frames == 2:
        ts = []
        if timestamps:
            ts = [timestamps[0], timestamps[-1]]
        return [frame_paths[0], frame_paths[-1]], ts

    # Keep first and last, evenly sample the middle
    indices = [0]
    middle_count = max_frames - 2
    step = (len(frame_paths) - 1) / (middle_count + 1)
    for i in range(1, middle_count + 1):
        idx = int(round(i * step))
        if idx not in indices:
            indices.append(idx)
    indices.append(len(frame_paths) - 1)

    # Deduplicate while preserving order
    seen = set()
    unique_indices = []
    for idx in indices:
        if idx not in seen:
            seen.add(idx)
            unique_indices.append(idx)

    sampled_paths = [frame_paths[i] for i in unique_indices]
    sampled_ts = []
    if timestamps:
        sampled_ts = [timestamps[i] for i in unique_indices if i < len(timestamps)]

    return sampled_paths, sampled_ts


# ---------------------------------------------------------------------------
# Frame timestamp assignment
# ---------------------------------------------------------------------------

def assign_timestamps(frame_paths, timestamps, duration):
    """Ensure every frame has a timestamp. Fill gaps with estimates."""
    if len(timestamps) >= len(frame_paths):
        return timestamps[:len(frame_paths)]

    # If we have no timestamps, distribute evenly across duration
    if not timestamps:
        if len(frame_paths) == 1:
            return [0.0]
        step = duration / max(len(frame_paths) - 1, 1)
        return [round(i * step, 3) for i in range(len(frame_paths))]

    # Pad remaining with estimates
    result = list(timestamps)
    if len(result) < len(frame_paths):
        remaining = len(frame_paths) - len(result)
        last_ts = result[-1] if result else 0.0
        gap = (duration - last_ts) / (remaining + 1) if duration > last_ts else 1.0
        for i in range(1, remaining + 1):
            result.append(round(last_ts + i * gap, 3))

    return result[:len(frame_paths)]


# ---------------------------------------------------------------------------
# Audio extraction and transcription
# ---------------------------------------------------------------------------

def extract_audio(video_path, output_wav):
    """Extract 16 kHz mono WAV audio from a video file."""
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        output_wav,
    ]
    result = _run(cmd, check=False)
    if result.returncode != 0:
        log("Warning: audio extraction failed (video may have no audio track)")
        return None
    if not os.path.isfile(output_wav) or os.path.getsize(output_wav) == 0:
        log("Warning: extracted audio is empty")
        return None
    return output_wav


def transcribe_with_whisper(wav_path, model_name):
    """Transcribe audio using local Whisper. Returns (segments, full_text) or (None, None)."""
    # Try 1: Python import
    try:
        import whisper
        log(f"Loading Whisper model '{model_name}' (Python)...")
        model = whisper.load_model(model_name)
        log("Transcribing...")
        result = model.transcribe(wav_path)

        segments = []
        for seg in result.get("segments", []):
            segments.append({
                "start": round(seg["start"], 3),
                "end": round(seg["end"], 3),
                "text": seg["text"].strip(),
            })

        full_text = result.get("text", "").strip()
        return segments, full_text

    except ImportError:
        log("Whisper Python package not available, trying CLI...")

    # Try 2: whisper CLI
    whisper_bin = shutil.which("whisper")
    if whisper_bin:
        return _transcribe_with_cli(wav_path, model_name, whisper_bin)

    log("Warning: Whisper is not installed. Skipping transcription.")
    log("  Install with: pip install openai-whisper")
    return None, None


def _transcribe_with_cli(wav_path, model_name, whisper_bin):
    """Transcribe using the whisper CLI tool."""
    tmp_dir = tempfile.mkdtemp(prefix="whisper_cli_")
    try:
        cmd = [
            whisper_bin,
            wav_path,
            "--model", model_name,
            "--output_format", "json",
            "--output_dir", tmp_dir,
        ]
        log(f"Transcribing via CLI with model '{model_name}'...")
        result = _run(cmd, check=False)

        if result.returncode != 0:
            log(f"Warning: whisper CLI failed: {result.stderr[:200]}")
            return None, None

        # Find the JSON output
        json_files = [f for f in os.listdir(tmp_dir) if f.endswith(".json")]
        if not json_files:
            log("Warning: whisper CLI produced no JSON output")
            return None, None

        with open(os.path.join(tmp_dir, json_files[0]), "r") as f:
            data = json.load(f)

        segments = []
        for seg in data.get("segments", []):
            segments.append({
                "start": round(seg.get("start", 0.0), 3),
                "end": round(seg.get("end", 0.0), 3),
                "text": seg.get("text", "").strip(),
            })

        full_text = data.get("text", "").strip()
        return segments, full_text

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Auto-install
# ---------------------------------------------------------------------------

def _check_and_offer_install():
    """Check for Whisper and offer to install if missing."""
    try:
        import whisper  # noqa: F401
        return
    except ImportError:
        pass

    if shutil.which("whisper"):
        return

    log("openai-whisper is not installed. Transcription requires it.")
    log(f"  Install with: {sys.executable} -m pip install openai-whisper")
    log("")

    # Only prompt if stderr is a terminal (interactive session)
    if hasattr(sys.stderr, "isatty") and sys.stderr.isatty():
        try:
            answer = input("Install openai-whisper now? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return
        if answer in ("", "y", "yes"):
            log("Installing openai-whisper...")
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", "--quiet", "openai-whisper"]
                )
                log("Installed successfully.")
            except subprocess.CalledProcessError:
                log("Auto-install failed. Please install manually.")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def understand_video(video_path, mode="scene", max_frames=_DEFAULT_MAX_FRAMES,
                     whisper_model=_DEFAULT_WHISPER_MODEL, do_transcribe=True):
    """Run the full video understanding pipeline. Returns result dict."""

    video_abs = os.path.abspath(video_path)
    video_dir = os.path.dirname(video_abs)
    video_stem = os.path.splitext(os.path.basename(video_abs))[0]

    # Output directory for frames
    frames_dir = os.path.join(video_dir, f"{video_stem}_frames")
    os.makedirs(frames_dir, exist_ok=True)

    # Step 1: Probe video
    log(f"Probing video: {os.path.basename(video_abs)}")
    duration, width, height = probe_video(video_abs)
    log(f"  Duration: {duration:.1f}s, Resolution: {width}x{height}")

    # Step 2: Extract frames
    log(f"Extracting frames (mode={mode})...")
    actual_mode = mode
    frame_paths = []
    timestamps = []

    if mode == "scene":
        frame_paths, timestamps = extract_frames_scene(video_abs, frames_dir)
        if not frame_paths:
            log("No scene changes detected, falling back to interval mode")
            actual_mode = "interval"
            frame_paths, timestamps = extract_frames_interval(
                video_abs, frames_dir, duration, max_frames
            )
    elif mode == "keyframe":
        frame_paths, timestamps = extract_frames_keyframe(video_abs, frames_dir)
    elif mode == "interval":
        frame_paths, timestamps = extract_frames_interval(
            video_abs, frames_dir, duration, max_frames
        )

    log(f"  Extracted {len(frame_paths)} frames")

    # Step 3: Subsample if needed
    frame_paths, timestamps = subsample_frames(frame_paths, timestamps, max_frames)

    # Step 4: Assign timestamps
    timestamps = assign_timestamps(frame_paths, timestamps, duration)

    log(f"  Final frame count: {len(frame_paths)}")

    # Build frame data
    frames_data = []
    for i, fpath in enumerate(frame_paths):
        ts = timestamps[i] if i < len(timestamps) else 0.0
        frames_data.append({
            "path": os.path.abspath(fpath),
            "timestamp": round(ts, 3),
            "timestamp_formatted": _format_timestamp(ts),
        })

    # Step 5: Transcribe
    transcript_segments = []
    full_text = ""

    if do_transcribe:
        _check_and_offer_install()

        tmp_wav = os.path.join(frames_dir, "_audio.wav")
        log("Extracting audio...")
        wav_result = extract_audio(video_abs, tmp_wav)

        if wav_result:
            transcript_segments, full_text = transcribe_with_whisper(wav_result, whisper_model)
            # Clean up temp audio
            try:
                os.remove(tmp_wav)
            except OSError:
                pass

        if not transcript_segments:
            log("Transcription unavailable (no audio or Whisper not installed)")

    # Build result
    result = {
        "video": os.path.basename(video_abs),
        "duration": round(duration, 3),
        "resolution": {"width": width, "height": height},
        "mode": actual_mode,
        "frames": frames_data,
        "frame_count": len(frames_data),
        "transcript": transcript_segments,
        "text": full_text,
        "note": "Use the Read tool to view frame images for visual understanding.",
    }

    return result


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser():
    """Build the argparse parser."""
    parser = argparse.ArgumentParser(
        prog="understand_video",
        description="Understand video content locally using ffmpeg frame "
                    "extraction and Whisper transcription. No API keys needed.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  %(prog)s video.mp4                          Scene detection + transcribe
  %(prog)s video.mp4 -m keyframe              Keyframe extraction
  %(prog)s video.mp4 -m interval              Regular intervals
  %(prog)s video.mp4 --max-frames 10          Limit frames
  %(prog)s video.mp4 --whisper-model small    Use larger whisper model
  %(prog)s video.mp4 --no-transcribe          Frames only
  %(prog)s video.mp4 -q -o result.json        Quiet mode, output to file

extraction modes: scene (default), keyframe, interval
whisper models: tiny, base, small, medium, large
""",
    )

    parser.add_argument(
        "video",
        help="Input video file path",
    )
    parser.add_argument(
        "-m", "--mode",
        choices=["scene", "keyframe", "interval"],
        default="scene",
        help="Frame extraction mode (default: scene)",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=_DEFAULT_MAX_FRAMES,
        metavar="N",
        help=f"Maximum number of frames to extract (default: {_DEFAULT_MAX_FRAMES})",
    )
    parser.add_argument(
        "--whisper-model",
        default=_DEFAULT_WHISPER_MODEL,
        choices=["tiny", "base", "small", "medium", "large"],
        help=f"Whisper model size (default: {_DEFAULT_WHISPER_MODEL})",
    )
    parser.add_argument(
        "--no-transcribe",
        action="store_true",
        help="Skip audio transcription, extract frames only",
    )
    parser.add_argument(
        "-o", "--output",
        metavar="FILE",
        help="Write result JSON to file instead of stdout",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress progress messages, output only JSON",
    )

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    global _quiet

    parser = build_parser()
    args = parser.parse_args()

    _quiet = args.quiet
    video_path = args.video

    # Detect YouTube URLs
    if _is_youtube_url(video_path):
        print(
            "Error: YouTube URLs are not supported directly. "
            "Use the video-download skill to download the video first:\n"
            "  python3 skills/video-download/scripts/download_video.py \"" + video_path + "\"\n"
            "Then run this script on the downloaded file.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Validate input file
    if not os.path.isfile(video_path):
        print(f"Error: video file not found: {video_path}", file=sys.stderr)
        sys.exit(1)

    # Check ffmpeg/ffprobe
    for cmd in ("ffmpeg", "ffprobe"):
        if not shutil.which(cmd):
            print(f"Error: {cmd} not found. Install FFmpeg first.", file=sys.stderr)
            sys.exit(1)

    # Run pipeline
    result = understand_video(
        video_path=video_path,
        mode=args.mode,
        max_frames=args.max_frames,
        whisper_model=args.whisper_model,
        do_transcribe=not args.no_transcribe,
    )

    # Output
    result_json = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result_json)
            f.write("\n")
        log(f"Result JSON written to: {args.output}")
    else:
        print(result_json)


if __name__ == "__main__":
    main()
