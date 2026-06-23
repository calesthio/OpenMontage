#!/usr/bin/env python3
"""QA Test 04: Audio mixing — mix TTS + music with ducking, verify levels.

Depends on test_01 and test_03 outputs (TTS + music files).
If those don't exist, generates minimal test fixtures via ffmpeg.
"""

import sys
import os
import json
import subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.env_loader import load_env
load_env()

from tools.audio.audio_mixer import AudioMixer  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUT, exist_ok=True)

# --- Fixture generation (if test_01/test_03 outputs don't exist) ---

SPEECH_FILE = os.path.join(OUT, "tts_short.mp3")
MUSIC_FILE = os.path.join(OUT, "music_calm.mp3")

def generate_fixture(path, description, duration=5):
    """Generate a minimal audio fixture with ffmpeg if the file doesn't exist."""
    if os.path.exists(path):
        print(f"  [fixture] Using existing: {path}")
        return
    print(f"  [fixture] Generating {description}: {path}")
    # Sine wave for speech stand-in, pink noise for music stand-in
    if "speech" in description or "tts" in description:
        src = f"sine=frequency=440:duration={duration}"
    else:
        src = f"anoisesrc=d={duration}:c=pink"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", src, "-ar", "44100", "-ac", "1", path],
        capture_output=True, check=True,
    )

generate_fixture(SPEECH_FILE, "speech/tts fixture", duration=8)
generate_fixture(MUSIC_FILE, "music fixture", duration=15)

# --- Tool setup ---

tool = AudioMixer()
print(f"Tool status: {tool.get_status()}")

# --- Test 1: Basic mix (speech + music, no ducking) ---
print("\n--- Test 1: Basic mix (speech + music) ---")
r1 = tool.execute({
    "operation": "mix",
    "tracks": [
        {"path": SPEECH_FILE, "role": "speech", "volume": 1.0},
        {"path": MUSIC_FILE, "role": "music", "volume": 0.3},
    ],
    "normalize": True,
    "output_path": os.path.join(OUT, "mix_basic.wav"),
})
print(f"Success: {r1.success}, Duration: {r1.duration_seconds:.2f}s")
if r1.error: print(f"Error: {r1.error}")  # noqa: E701
if r1.artifacts: print(f"Artifacts: {r1.artifacts}")  # noqa: E701

# --- Test 2: Mix with fades ---
print("\n--- Test 2: Mix with fades ---")
r2 = tool.execute({
    "operation": "mix",
    "tracks": [
        {"path": SPEECH_FILE, "role": "speech", "volume": 1.0, "fade_in_seconds": 0.5},
        {"path": MUSIC_FILE, "role": "music", "volume": 0.25, "fade_in_seconds": 1.0, "fade_out_seconds": 2.0},
    ],
    "normalize": True,
    "output_path": os.path.join(OUT, "mix_fades.wav"),
})
print(f"Success: {r2.success}, Duration: {r2.duration_seconds:.2f}s")
if r2.error: print(f"Error: {r2.error}")  # noqa: E701
if r2.artifacts: print(f"Artifacts: {r2.artifacts}")  # noqa: E701

# --- Test 3: Ducking (sidechain compress music under speech) ---
print("\n--- Test 3: Ducking ---")
r3 = tool.execute({
    "operation": "duck",
    "tracks": [
        {"path": SPEECH_FILE, "role": "speech"},
        {"path": MUSIC_FILE, "role": "music"},
    ],
    "ducking": {
        "enabled": True,
        "music_volume_during_speech": 0.15,
        "attack_ms": 200,
        "release_ms": 500,
    },
    "output_path": os.path.join(OUT, "mix_ducked.wav"),
})
print(f"Success: {r3.success}, Duration: {r3.duration_seconds:.2f}s")
if r3.error: print(f"Error: {r3.error}")  # noqa: E701
if r3.artifacts: print(f"Artifacts: {r3.artifacts}")  # noqa: E701

# --- Test 4: Mix with delayed music start ---
print("\n--- Test 4: Delayed music start ---")
r4 = tool.execute({
    "operation": "mix",
    "tracks": [
        {"path": SPEECH_FILE, "role": "speech", "volume": 1.0},
        {"path": MUSIC_FILE, "role": "music", "volume": 0.2, "start_seconds": 3.0},
    ],
    "normalize": False,
    "output_path": os.path.join(OUT, "mix_delayed.wav"),
})
print(f"Success: {r4.success}, Duration: {r4.duration_seconds:.2f}s")
if r4.error: print(f"Error: {r4.error}")  # noqa: E701
if r4.artifacts: print(f"Artifacts: {r4.artifacts}")  # noqa: E701

# --- Probe all outputs ---
print("\n--- Output inspection ---")
for name in ["mix_basic.wav", "mix_fades.wav", "mix_ducked.wav", "mix_delayed.wav"]:
    path = os.path.join(OUT, name)
    if os.path.exists(path):
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path],
            capture_output=True, text=True,
        )
        info = json.loads(probe.stdout)
        fmt = info.get("format", {})
        streams = info.get("streams", [{}])
        audio = streams[0] if streams else {}
        print(f"\n[{name}] Duration: {fmt.get('duration', '?')}s, "
              f"Sample rate: {audio.get('sample_rate', '?')}Hz, "
              f"Channels: {audio.get('channels', '?')}, "
              f"Codec: {audio.get('codec_name', '?')}, "
              f"Size: {os.path.getsize(path)} bytes")

        # Check for clipping via loudnorm stats
        loud = subprocess.run(
            ["ffmpeg", "-i", path, "-af", "loudnorm=print_format=json", "-f", "null", "-"],
            capture_output=True, text=True,
        )
        # Parse loudnorm JSON from stderr (ffmpeg writes it there)
        stderr = loud.stderr
        json_start = stderr.rfind("{")
        json_end = stderr.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            try:
                loudness = json.loads(stderr[json_start:json_end])
                print(f"  Loudness: I={loudness.get('input_i', '?')} LUFS, "
                      f"TP={loudness.get('input_tp', '?')} dBTP, "
                      f"LRA={loudness.get('input_lra', '?')} LU")
            except json.JSONDecodeError:
                print("  (Could not parse loudness stats)")
    else:
        print(f"\n[{name}] FILE NOT FOUND")

print("\n=== AUDIO MIX TEST COMPLETE ===")
