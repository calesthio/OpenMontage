#!/usr/bin/env python3
"""QA Test 06: Video stitch — sequential concat, crossfade, fade, spatial PIP.

Tests the VideoStitch tool with both matching and mismatched clips.
Generates fixtures via ffmpeg — no API keys needed.
"""

import sys
import os
import json
import subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.env_loader import load_env
load_env()

from tools.video.video_stitch import VideoStitch  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUT, exist_ok=True)

# --- Fixture generation ---

def ensure_video(path, duration=4, width=1280, height=720, fps=30, color="blue"):
    """Generate a test video clip with ffmpeg.

    Uses forced keyframes every 1s so copy-mode operations retain the video stream.
    """
    if os.path.exists(path):
        print(f"  [fixture] Using existing: {path}")
        return
    print(f"  [fixture] Generating {duration}s {width}x{height}@{fps}fps {color}: {path}")
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", f"color=c={color}:s={width}x{height}:d={duration}:r={fps}",
         "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
         "-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p",
         "-g", str(fps), "-keyint_min", str(fps),
         "-c:a", "aac", "-ar", "44100", "-ac", "2",
         "-shortest", path],
        capture_output=True, check=True,
    )

# Matching clips (same resolution/fps/codec)
CLIP_1 = os.path.join(OUT, "stitch_clip1.mp4")
CLIP_2 = os.path.join(OUT, "stitch_clip2.mp4")
CLIP_3 = os.path.join(OUT, "stitch_clip3.mp4")
ensure_video(CLIP_1, duration=4, color="darkblue")
ensure_video(CLIP_2, duration=4, color="darkgreen")
ensure_video(CLIP_3, duration=4, color="darkred")

# Mismatched clip (different resolution + fps)
CLIP_MISMATCH = os.path.join(OUT, "stitch_clip_mismatch.mp4")
ensure_video(CLIP_MISMATCH, duration=4, width=640, height=480, fps=24, color="purple")

# --- Tool setup ---

tool = VideoStitch()
print(f"Tool status: {tool.get_status()}")

# --- Test 1: Validate matching clips ---
print("\n--- Test 1: Validate matching clips ---")
r1 = tool.execute({
    "operation": "validate",
    "clips": [CLIP_1, CLIP_2, CLIP_3],
})
print(f"Success: {r1.success}")
if r1.data:
    print(f"  Compatible: {r1.data.get('compatible')}")
    print(f"  Total duration: {r1.data.get('total_duration')}s")
    print(f"  Mismatches: {len(r1.data.get('mismatches', []))}")
if r1.error: print(f"Error: {r1.error}")  # noqa: E701

# --- Test 2: Validate mismatched clips ---
print("\n--- Test 2: Validate mismatched clips ---")
r2 = tool.execute({
    "operation": "validate",
    "clips": [CLIP_1, CLIP_MISMATCH],
})
print(f"Success: {r2.success}")
if r2.data:
    print(f"  Compatible: {r2.data.get('compatible')}")
    mismatches = r2.data.get("mismatches", [])
    for m in mismatches:
        print(f"  Clip[{m['clip_index']}]: {', '.join(m['differences'])}")

# --- Test 3: Simple cut stitch (matching clips) ---
print("\n--- Test 3: Cut stitch (2 clips) ---")
r3 = tool.execute({
    "operation": "stitch",
    "clips": [CLIP_1, CLIP_2],
    "transition": "cut",
    "output_path": os.path.join(OUT, "stitch_cut.mp4"),
})
print(f"Success: {r3.success}, Duration: {r3.duration_seconds:.2f}s")
if r3.data: print(f"  Output duration: {r3.data.get('duration')}s, Method: {r3.data.get('method')}")  # noqa: E701
if r3.error: print(f"Error: {r3.error}")  # noqa: E701

# --- Test 4: Crossfade stitch ---
print("\n--- Test 4: Crossfade stitch (2 clips) ---")
r4 = tool.execute({
    "operation": "stitch",
    "clips": [CLIP_1, CLIP_2],
    "transition": "crossfade",
    "transition_duration": 1.0,
    "output_path": os.path.join(OUT, "stitch_crossfade.mp4"),
})
print(f"Success: {r4.success}, Duration: {r4.duration_seconds:.2f}s")
if r4.data: print(f"  Output duration: {r4.data.get('duration')}s, Method: {r4.data.get('method')}")  # noqa: E701
if r4.error: print(f"Error: {r4.error}")  # noqa: E701

# --- Test 5: Fade-through-black (3 clips) ---
print("\n--- Test 5: Fade through black (3 clips) ---")
r5 = tool.execute({
    "operation": "stitch",
    "clips": [CLIP_1, CLIP_2, CLIP_3],
    "transition": "fade",
    "transition_duration": 0.5,
    "output_path": os.path.join(OUT, "stitch_fadeblack.mp4"),
})
print(f"Success: {r5.success}, Duration: {r5.duration_seconds:.2f}s")
if r5.data: print(f"  Output duration: {r5.data.get('duration')}s, Method: {r5.data.get('method')}")  # noqa: E701
if r5.error: print(f"Error: {r5.error}")  # noqa: E701

# --- Test 6: Auto-normalize mismatched clips ---
print("\n--- Test 6: Stitch mismatched clips (auto_normalize) ---")
r6 = tool.execute({
    "operation": "stitch",
    "clips": [CLIP_1, CLIP_MISMATCH],
    "transition": "cut",
    "auto_normalize": True,
    "output_path": os.path.join(OUT, "stitch_normalized.mp4"),
})
print(f"Success: {r6.success}, Duration: {r6.duration_seconds:.2f}s")
if r6.data: print(f"  Output duration: {r6.data.get('duration')}s, Normalized: {r6.data.get('auto_normalized')}")  # noqa: E701
if r6.error: print(f"Error: {r6.error}")  # noqa: E701

# --- Test 7: Preview stitch (low-res) ---
print("\n--- Test 7: Preview stitch ---")
r7 = tool.execute({
    "operation": "preview_stitch",
    "clips": [CLIP_1, CLIP_2, CLIP_3],
    "transition": "cut",
    "output_path": os.path.join(OUT, "stitch_preview.mp4"),
})
print(f"Success: {r7.success}, Duration: {r7.duration_seconds:.2f}s")
if r7.data: print(f"  Preview resolution: {r7.data.get('preview_resolution')}")  # noqa: E701
if r7.error: print(f"Error: {r7.error}")  # noqa: E701

# --- Test 8: Spatial — side by side ---
print("\n--- Test 8: Spatial side-by-side ---")
r8 = tool.execute({
    "operation": "spatial",
    "clips": [CLIP_1, CLIP_2],
    "layout": "side_by_side",
    "output_path": os.path.join(OUT, "stitch_side_by_side.mp4"),
})
print(f"Success: {r8.success}, Duration: {r8.duration_seconds:.2f}s")
if r8.data: print(f"  Layout: {r8.data.get('layout')}, Duration: {r8.data.get('duration')}s")  # noqa: E701
if r8.error: print(f"Error: {r8.error}")  # noqa: E701

# --- Test 9: Spatial — picture-in-picture ---
print("\n--- Test 9: Spatial PIP (bottom-right) ---")
r9 = tool.execute({
    "operation": "spatial",
    "clips": [CLIP_1, CLIP_2],
    "layout": "picture_in_picture",
    "pip_position": "bottom_right",
    "pip_scale": 0.3,
    "pip_margin": 20,
    "output_path": os.path.join(OUT, "stitch_pip.mp4"),
})
print(f"Success: {r9.success}, Duration: {r9.duration_seconds:.2f}s")
if r9.data: print(f"  Layout: {r9.data.get('layout')}, Duration: {r9.data.get('duration')}s")  # noqa: E701
if r9.error: print(f"Error: {r9.error}")  # noqa: E701

# --- Test 10: Spatial — vertical stack ---
print("\n--- Test 10: Spatial vertical stack ---")
r10 = tool.execute({
    "operation": "spatial",
    "clips": [CLIP_1, CLIP_2],
    "layout": "vertical_stack",
    "output_path": os.path.join(OUT, "stitch_vstack.mp4"),
})
print(f"Success: {r10.success}, Duration: {r10.duration_seconds:.2f}s")
if r10.data: print(f"  Layout: {r10.data.get('layout')}, Duration: {r10.data.get('duration')}s")  # noqa: E701
if r10.error: print(f"Error: {r10.error}")  # noqa: E701

# --- Probe all video outputs ---
print("\n--- Output inspection ---")
outputs = [
    "stitch_cut.mp4",
    "stitch_crossfade.mp4",
    "stitch_fadeblack.mp4",
    "stitch_normalized.mp4",
    "stitch_preview.mp4",
    "stitch_side_by_side.mp4",
    "stitch_pip.mp4",
    "stitch_vstack.mp4",
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
              f" {video.get('codec_name', '?')}"
              f" | Audio: {audio.get('codec_name', '?')}"
              f" | Size: {os.path.getsize(path)} bytes")
    else:
        print(f"\n[{name}] FILE NOT FOUND")

print("\n=== VIDEO STITCH TEST COMPLETE ===")
