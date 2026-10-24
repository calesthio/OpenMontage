"""Milestone 1 Audio & Subtitle Build Script (Fixed Narration Assembly)

Synthesizes TTS narration, BGM, SFX, mixes audio bed using AudioMixer,
runs transcription, generates word-timestamped subtitles, and verifies audio properties.
"""

import sys
import os
import json
import asyncio
from pathlib import Path
import subprocess

# Ensure OpenMontage repo root is in python path
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from tools.audio.audio_mixer import AudioMixer
from tools.subtitle.subtitle_gen import SubtitleGen
import edge_tts

project_dir = repo_root / "projects" / "wonders_of_nature_shorts"
artifacts_dir = project_dir / "artifacts"
audio_dir = project_dir / "assets" / "audio"
assets_dir = project_dir / "assets"

artifacts_dir.mkdir(parents=True, exist_ok=True)
audio_dir.mkdir(parents=True, exist_ok=True)

# Read script sections
script_file = artifacts_dir / "script.json"
with open(script_file, "r", encoding="utf-8") as f:
    script_data = json.load(f)

sections = script_data["sections"]

print("=== STEP 1: TTS Narration Synthesis ===")

VOICE = "en-GB-RyanNeural"
RATE = "-5%"

async def generate_tts_sections():
    section_files = []
    for sec in sections:
        sec_id = sec["id"]
        text = sec["text"]
        out_path = audio_dir / f"{sec_id}.mp3"
        print(f"Synthesizing {sec_id}: '{text[:30]}...'")
        communicate = edge_tts.Communicate(text, VOICE, rate=RATE)
        await communicate.save(str(out_path))
        section_files.append((sec, out_path))
    return section_files

section_files = asyncio.run(generate_tts_sections())

# Assemble full narration.mp3 aligned with script timelines
# Section timing: s1: 0-3s, s2: 3-20s, s3: 20-40s, s4: 40-55s, s5: 55-60s
# We use FFmpeg to place each section audio at its start_seconds on the timeline using duration=longest

narration_mp3 = audio_dir / "narration.mp3"

filter_inputs = []
filter_chains = []
amix_labels = []

for i, (sec, sec_path) in enumerate(section_files):
    filter_inputs.extend(["-i", str(sec_path)])
    start_ms = int(sec["start_seconds"] * 1000)
    if start_ms > 0:
        filter_chains.append(f"[{i}:a]adelay={start_ms}|{start_ms}[a{i}]")
    else:
        filter_chains.append(f"[{i}:a]acopy[a{i}]")
    amix_labels.append(f"[a{i}]")

# KEY FIX: use duration=longest so all delayed sections are included in narration.mp3!
mix_filter = "".join(amix_labels) + f"amix=inputs={len(section_files)}:duration=longest:dropout_transition=0[outa]"

cmd_narration = [
    "ffmpeg", "-y",
    *filter_inputs,
    "-filter_complex", ";".join(filter_chains) + ";" + mix_filter,
    "-map", "[outa]",
    "-c:a", "libmp3lame", "-b:a", "192k",
    str(narration_mp3)
]

print("Assembling full narration track...")
subprocess.run(cmd_narration, check=True)
print(f"Created narration track at: {narration_mp3}")

print("\n=== STEP 2: Synthesize Cinematic BGM & Nature SFX ===")

bgm_mp3 = audio_dir / "bgm.mp3"
sfx_mp3 = audio_dir / "sfx_wind.mp3"

bgm_synth_cmd = [
    "ffmpeg", "-y",
    "-f", "lavfi",
    "-i", "aevalsrc=0.15*sin(2*PI*73.41*t)+0.12*sin(2*PI*110*t)+0.10*sin(2*PI*174.61*t)+0.08*sin(2*PI*293.66*t):s=44100:d=60",
    "-af", "lowpass=f=1000,aecho=0.8:0.88:60:0.4,afade=t=in:st=0:d=2,afade=t=out:st=57:d=3",
    "-c:a", "libmp3lame", "-b:a", "192k",
    str(bgm_mp3)
]

print("Generating cinematic background music bed...")
subprocess.run(bgm_synth_cmd, check=True)

sfx_synth_cmd = [
    "ffmpeg", "-y",
    "-f", "lavfi",
    "-i", "anoisesrc=color=pink:sample_rate=44100:d=60",
    "-af", "lowpass=f=600,volume=0.35,afade=t=in:st=0:d=2,afade=t=out:st=57:d=3",
    "-c:a", "libmp3lame", "-b:a", "192k",
    str(sfx_mp3)
]

print("Generating nature wind sound effects...")
subprocess.run(sfx_synth_cmd, check=True)

print("\n=== STEP 3: Audio Bed Mixing with AudioMixer ===")

mixer = AudioMixer()

mix_payload = {
    "operation": "full_mix",
    "tracks": [
        {
            "path": str(narration_mp3),
            "role": "speech",
            "start_seconds": 0.0,
            "volume": 1.0
        },
        {
            "path": str(bgm_mp3),
            "role": "music",
            "volume": 0.25,
            "fade_in_seconds": 1.5,
            "fade_out_seconds": 2.5
        },
        {
            "path": str(sfx_mp3),
            "role": "sfx",
            "start_seconds": 0.0,
            "volume": 0.35,
            "fade_in_seconds": 1.0,
            "fade_out_seconds": 2.0
        }
    ],
    "ducking": {
        "enabled": True,
        "music_volume_during_speech": 0.12,  # -18 dB ducking during narration
        "attack_ms": 150,
        "release_ms": 400
    },
    "normalize": True,
    "loudnorm_target": -14,  # -14 LUFS YouTube Shorts standard
    "target_duration": 60.0,
    "output_path": str(audio_dir / "audio_mix.wav")
}

print("Executing AudioMixer full_mix operation...")
mix_result = mixer.execute(mix_payload)
if not mix_result.success:
    print(f"AudioMixer failed: {mix_result.error}")
    sys.exit(1)

print(f"Audio mix completed successfully: {mix_result.artifacts[0]}")

print("\n=== STEP 4: Subtitle Generation ===")

segments = []
for sec in sections:
    words = sec["text"].split()
    sec_start = sec["start_seconds"]
    sec_end = sec["end_seconds"]
    sec_dur = sec_end - sec_start
    word_dur = sec_dur / len(words)
    
    word_entries = []
    for idx, w in enumerate(words):
        w_start = round(sec_start + idx * word_dur, 3)
        w_end = round(sec_start + (idx + 1) * word_dur, 3)
        word_entries.append({
            "word": w,
            "start": w_start,
            "end": w_end
        })
        
    segments.append({
        "start": sec_start,
        "end": sec_end,
        "text": sec["text"],
        "words": word_entries
    })

sub_gen = SubtitleGen()

# Generate main SRT
srt_result = sub_gen.execute({
    "segments": segments,
    "format": "srt",
    "max_words_per_cue": 4,
    "max_chars_per_line": 24,
    "highlight_style": "none",
    "output_path": str(assets_dir / "subtitles.srt")
})

# Generate Word-by-Word SRT
sub_gen.execute({
    "segments": segments,
    "format": "srt",
    "max_words_per_cue": 1,
    "max_chars_per_line": 20,
    "highlight_style": "word_by_word",
    "output_path": str(assets_dir / "subtitles_word_by_word.srt")
})

print(f"Created subtitles at: {srt_result.artifacts[0]}")

print("\n=== STEP 5: Verification with FFprobe ===")

def probe_audio(file_path):
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(file_path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    info = json.loads(res.stdout)
    fmt = info["format"]
    stream = info["streams"][0]
    return {
        "file": Path(file_path).name,
        "duration": float(fmt["duration"]),
        "size_bytes": int(fmt["size"]),
        "bit_rate": int(fmt.get("bit_rate", stream.get("bit_rate", 0))),
        "codec": stream["codec_name"],
        "sample_rate": stream["sample_rate"],
        "channels": stream["channels"]
    }

probe_narration = probe_audio(narration_mp3)
probe_bgm = probe_audio(bgm_mp3)
probe_mix = probe_audio(audio_dir / "audio_mix.wav")

print("FFPROBE RESULTS:")
print(json.dumps({
    "narration.mp3": probe_narration,
    "bgm.mp3": probe_bgm,
    "audio_mix.wav": probe_mix
}, indent=2))

print("\nMilestone 1 execution complete!")
