import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.audio.audio_mixer import AudioMixer

PROJ = ROOT / "projects" / "macaque"
OUT_DIR = PROJ / "renders"
AUDIO_DIR = PROJ / "assets" / "audio"
SUB_DIR = PROJ / "assets" / "subtitles"
TEMP = PROJ / "temp"
DEMUCS_DIR = AUDIO_DIR / "demucs"

OUT_DIR.mkdir(parents=True, exist_ok=True)
TEMP.mkdir(parents=True, exist_ok=True)

# Load beats
beats_path = PROJ / "beats.json"
with open(beats_path, "r", encoding="utf-8") as f:
    BEATS = json.load(f)

# Load artifact info for timings
art_path = PROJ / "artifacts" / "macaque_calls_v1.json"
with open(art_path, "r", encoding="utf-8") as f:
    ART_DATA = json.load(f)

silent_video = OUT_DIR / "silent.mp4"
ass_subtitles = SUB_DIR / "the_ledge_v1.ass"
source_timeline_audio = TEMP / "source_timeline.wav"

def dur(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True
    ).stdout
    return float(out.strip())

video_duration = dur(silent_video)
print(f"[INFO] Silent video duration: {video_duration:.2f}s")

# ==============================================================================
# OPTION 1: Original sound ONLY + Captions
# ==============================================================================
print("\n" + "="*70)
print("BUILDING OPTION 1: Original Sound Only + Captions")
print("="*70)

opt1_final = OUT_DIR / "macaque_option1_original_sound.mp4"
ass_path_escaped = ass_subtitles.as_posix().replace(":", r"\:")

# Mix original audio with video + subtitles + audio loudnorm
cmd_opt1 = [
    "ffmpeg", "-y", "-v", "error",
    "-i", str(silent_video),
    "-i", str(source_timeline_audio),
    "-vf", f"subtitles='{ass_path_escaped}'",
    "-map", "0:v:0", "-map", "1:a:0",
    "-c:v", "libx264", "-preset", "medium", "-crf", "19",
    "-af", "loudnorm=I=-14:TP=-1.0:LRA=11",
    "-c:a", "aac", "-b:a", "192k",
    "-shortest",
    str(opt1_final)
]
print("[CMD Option 1]", " ".join(cmd_opt1))
subprocess.run(cmd_opt1, check=True)
print(f"[SUCCESS] Option 1 rendered: {opt1_final} ({dur(opt1_final):.2f}s)")


# ==============================================================================
# OPTION 2: Our Custom Voiceover + Ducked Music + Clean Ambience (NO orig vocals)
# ==============================================================================
print("\n" + "="*70)
print("BUILDING OPTION 2: Our Custom Voiceover (No Original Voiceover Overlap)")
print("="*70)

# Build vo_tracks from BEATS / artifacts
vo_tracks = []
for beat in ART_DATA["beats"]:
    beat_id = beat["id"]
    vo_file = AUDIO_DIR / f"{beat_id}.mp3"
    vo_tracks.append({
        "path": str(vo_file),
        "role": "speech",
        "start_seconds": round(beat["start"], 3),
        "volume": 1.0
    })

# Clean ambience bed from minus_vocals.wav (Demucs stem with ZERO vocal content)
minus_vocals = DEMUCS_DIR / "htdemucs" / "source_timeline" / "minus_vocals.wav"
clean_ambience = TEMP / "ambience_bed_clean.wav"
subprocess.run([
    "ffmpeg", "-y", "-v", "error",
    "-i", str(minus_vocals),
    "-af", f"highpass=f=80,lowpass=f=10000,afftdn=nf=-24,volume=0.30,apad,atrim=0:{video_duration:.3f}",
    "-c:a", "pcm_s16le", str(clean_ambience)
], check=True)

# Story-directed music tracks
music_seg_0 = TEMP / "music_seg_0.wav"
music_seg_1 = TEMP / "music_seg_1.wav"

music_tracks = []
if music_seg_0.exists() and music_seg_1.exists():
    music_tracks = [
        {"path": str(music_seg_0), "role": "music", "start_seconds": 0.0, "volume": 0.95},
        {"path": str(music_seg_1), "role": "music", "start_seconds": 46.3, "volume": 0.95}
    ]

# Combine all tracks for Option 2:
# 1. ElevenLabs voiceover tracks
# 2. Clean forest ambience (from minus_vocals stem, NO vocals.wav)
# 3. Dynamic background music
all_tracks_opt2 = vo_tracks + [
    {"path": str(clean_ambience), "role": "sfx", "start_seconds": 0.0, "volume": 0.70}
] + music_tracks

mixer = AudioMixer()
mix_opt2 = TEMP / "mix_opt2_clean.wav"
mix_result = mixer.execute({
    "operation": "full_mix",
    "tracks": all_tracks_opt2,
    "ducking": {"enabled": True, "music_volume_during_speech": 0.035, "attack_ms": 70, "release_ms": 750},
    "normalize": True,
    "loudnorm_target": -14.0,
    "target_duration": video_duration,
    "output_path": str(mix_opt2),
})

if not mix_result.success:
    raise RuntimeError(f"AudioMixer failed for Option 2: {mix_result.error}")

# Pad mix to match video duration perfectly
mix_opt2_padded = TEMP / "mix_opt2_padded.wav"
subprocess.run([
    "ffmpeg", "-y", "-v", "error",
    "-i", str(mix_opt2),
    "-af", f"apad=whole_dur={video_duration + 0.4:.3f}",
    "-c:a", "pcm_s16le", str(mix_opt2_padded)
], check=True)

opt2_final = OUT_DIR / "macaque_option2_custom_voiceover.mp4"
cmd_opt2 = [
    "ffmpeg", "-y", "-v", "error",
    "-i", str(silent_video),
    "-i", str(mix_opt2_padded),
    "-vf", f"subtitles='{ass_path_escaped}'",
    "-map", "0:v:0", "-map", "1:a:0",
    "-c:v", "libx264", "-preset", "medium", "-crf", "19",
    "-af", "loudnorm=I=-14:TP=-1.0:LRA=11",
    "-c:a", "aac", "-b:a", "192k",
    "-shortest",
    str(opt2_final)
]
print("[CMD Option 2]", " ".join(cmd_opt2))
subprocess.run(cmd_opt2, check=True)
print(f"[SUCCESS] Option 2 rendered: {opt2_final} ({dur(opt2_final):.2f}s)")

# Summary
print("\n" + "="*70)
print("RENDERING COMPLETE FOR BOTH OPTIONS")
print("="*70)
print(f"1. Option 1 (Original Sound Only + Captions): {opt1_final}")
print(f"2. Option 2 (Custom ElevenLabs VO + Music + Clean Ambience): {opt2_final}")
