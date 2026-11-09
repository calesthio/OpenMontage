#!/usr/bin/env python3
"""QA Test 05: Video composition — image + mixed audio → video, verify A/V sync.

Creates a video from static images with audio and optional subtitles.
Uses ffmpeg-generated fixtures if prior test outputs don't exist.
"""

import sys, os, json, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.env_loader import load_env
load_env()

from tools.video.video_compose import VideoCompose

OUT = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUT, exist_ok=True)

# --- Fixture generation ---

def ensure_image(path, width=1280, height=720, color="blue"):
    """Generate a test image with ffmpeg if it doesn't exist."""
    if os.path.exists(path):
        print(f"  [fixture] Using existing: {path}")
        return
    print(f"  [fixture] Generating {color} image: {path}")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"color=c={color}:s={width}x{height}:d=1",
         "-frames:v", "1", path],
        capture_output=True, check=True,
    )

def ensure_video(path, duration=5, width=1280, height=720, color="blue"):
    """Generate a test video clip with ffmpeg if it doesn't exist.

    Uses forced keyframes every 1s so copy-mode trimming retains the video stream.
    """
    if os.path.exists(path):
        print(f"  [fixture] Using existing: {path}")
        return
    print(f"  [fixture] Generating {duration}s {color} video: {path}")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"color=c={color}:s={width}x{height}:d={duration}:r=30",
         "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
         "-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p",
         "-g", "30", "-keyint_min", "30",
         "-c:a", "aac", "-shortest", path],
        capture_output=True, check=True,
    )

def ensure_audio(path, duration=5):
    """Generate a test audio file if it doesn't exist."""
    if os.path.exists(path):
        print(f"  [fixture] Using existing: {path}")
        return
    print(f"  [fixture] Generating {duration}s audio: {path}")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"sine=frequency=440:duration={duration}",
         "-ar", "44100", "-ac", "2", path],
        capture_output=True, check=True,
    )

def ensure_subtitle(path):
    """Write a minimal SRT subtitle file."""
    if os.path.exists(path):
        print(f"  [fixture] Using existing: {path}")
        return
    print(f"  [fixture] Generating subtitle: {path}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("1\n00:00:00,000 --> 00:00:03,000\nWelcome to OpenMontage\n\n")
        f.write("2\n00:00:03,000 --> 00:00:06,000\nBuilding amazing videos with AI\n\n")
        f.write("3\n00:00:06,000 --> 00:00:10,000\nLet's see what we can create\n\n")

# Create fixtures
CLIP_A = os.path.join(OUT, "compose_clip_a.mp4")
CLIP_B = os.path.join(OUT, "compose_clip_b.mp4")
AUDIO_MIX = os.path.join(OUT, "compose_audio.wav")
SUBTITLE = os.path.join(OUT, "compose_subs.srt")

# Use 10s clips so -c copy has keyframe headroom (5s clips lose video stream)
ensure_video(CLIP_A, duration=10, color="darkblue")
ensure_video(CLIP_B, duration=10, color="darkgreen")
ensure_audio(AUDIO_MIX, duration=10)
ensure_subtitle(SUBTITLE)

# --- Tool setup ---

tool = VideoCompose()
print(f"Tool status: {tool.get_status()}")

# --- Test 1: Compose with cuts + audio ---
print("\n--- Test 1: Compose from edit_decisions ---")
r1 = tool.execute({
    "operation": "compose",
    "edit_decisions": {
        "version": "1.0",
        "render_runtime": "ffmpeg",
        "cuts": [
            {"source": CLIP_A, "in_seconds": 0, "out_seconds": 5},
            {"source": CLIP_B, "in_seconds": 0, "out_seconds": 5},
        ],
    },
    "audio_path": AUDIO_MIX,
    "output_path": os.path.join(OUT, "compose_basic.mp4"),
})
print(f"Success: {r1.success}, Duration: {r1.duration_seconds:.2f}s")
if r1.error: print(f"Error: {r1.error}")
if r1.artifacts: print(f"Artifacts: {r1.artifacts}")

# --- Test 2: Compose with subtitles ---
print("\n--- Test 2: Compose with subtitles ---")
r2 = tool.execute({
    "operation": "compose",
    "edit_decisions": {
        "version": "1.0",
        "render_runtime": "ffmpeg",
        "cuts": [
            {"source": CLIP_A, "in_seconds": 0, "out_seconds": 5},
            {"source": CLIP_B, "in_seconds": 0, "out_seconds": 5},
        ],
    },
    "audio_path": AUDIO_MIX,
    "subtitle_path": SUBTITLE,
    "subtitle_style": {
        "font": "Arial",
        "font_size": 24,
        "primary_color": "&HFFFFFF",
        "outline_color": "&H000000",
        "outline_width": 2,
        "margin_v": 40,
    },
    "output_path": os.path.join(OUT, "compose_subtitled.mp4"),
})
print(f"Success: {r2.success}, Duration: {r2.duration_seconds:.2f}s")
if r2.error: print(f"Error: {r2.error}")
if r2.artifacts: print(f"Artifacts: {r2.artifacts}")

# --- Test 3: Burn subtitles onto existing video ---
print("\n--- Test 3: Burn subtitles standalone ---")
r3 = tool.execute({
    "operation": "burn_subtitles",
    "input_path": CLIP_A,
    "subtitle_path": SUBTITLE,
    "subtitle_style": {
        "font": "Arial",
        "font_size": 20,
        "bold": True,
    },
    "output_path": os.path.join(OUT, "compose_burn_subs.mp4"),
})
print(f"Success: {r3.success}, Duration: {r3.duration_seconds:.2f}s")
if r3.error: print(f"Error: {r3.error}")
if r3.artifacts: print(f"Artifacts: {r3.artifacts}")

# --- Test 4: Encode with media profile ---
print("\n--- Test 4: Re-encode with profile ---")
r4 = tool.execute({
    "operation": "encode",
    "input_path": CLIP_A,
    "profile": "YOUTUBE_LANDSCAPE",
    "crf": 20,
    "preset": "fast",
    "output_path": os.path.join(OUT, "compose_encoded.mp4"),
})
print(f"Success: {r4.success}, Duration: {r4.duration_seconds:.2f}s")
if r4.error: print(f"Error: {r4.error}")
if r4.artifacts: print(f"Artifacts: {r4.artifacts}")

# --- Test 5: Overlay ---
print("\n--- Test 5: Overlay image on video ---")
OVERLAY_IMG = os.path.join(OUT, "compose_overlay.png")
ensure_image(OVERLAY_IMG, width=200, height=200, color="red")

r5 = tool.execute({
    "operation": "overlay",
    "input_path": CLIP_A,
    "overlays": [
        {
            "asset_path": OVERLAY_IMG,
            "x": 50, "y": 50,
            "width": 150, "height": 150,
            "start_seconds": 1,
            "end_seconds": 4,
            "opacity": 0.8,
        },
    ],
    "output_path": os.path.join(OUT, "compose_overlay.mp4"),
})
print(f"Success: {r5.success}, Duration: {r5.duration_seconds:.2f}s")
if r5.error: print(f"Error: {r5.error}")
if r5.artifacts: print(f"Artifacts: {r5.artifacts}")

# --- Probe all outputs ---
print("\n--- Output inspection ---")
outputs = [
    "compose_basic.mp4",
    "compose_subtitled.mp4",
    "compose_burn_subs.mp4",
    "compose_encoded.mp4",
    "compose_overlay.mp4",
]
for name in outputs:
    path = os.path.join(OUT, name)
    if os.path.exists(path):
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", path],
            capture_output=True, text=True,
        )
        info = json.loads(probe.stdout)
        fmt = info.get("format", {})
        video = {}
        audio = {}
        for s in info.get("streams", []):
            if s.get("codec_type") == "video" and not video:
                video = s
            elif s.get("codec_type") == "audio" and not audio:
                audio = s
        print(f"\n[{name}]"
              f" Duration: {fmt.get('duration', '?')}s"
              f" | Video: {video.get('width', '?')}x{video.get('height', '?')}"
              f" {video.get('codec_name', '?')}@{video.get('r_frame_rate', '?')}fps"
              f" | Audio: {audio.get('codec_name', '?')}"
              f" {audio.get('sample_rate', '?')}Hz"
              f" {audio.get('channels', '?')}ch"
              f" | Size: {os.path.getsize(path)} bytes")
    else:
        print(f"\n[{name}] FILE NOT FOUND")

print("\n=== VIDEO COMPOSE TEST COMPLETE ===")
