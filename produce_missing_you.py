"""
Production script: Chef-8080 - Missing You
Two portrait 9:16 720p teaser clips with karaoke subtitles
Melancholic, cinematic style
"""

import os
import sys
import json
import shutil
import subprocess
import requests
import urllib.request
from pathlib import Path

# --- Setup paths ---
FFMPEG_DIR = r"C:\Users\ari_v\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin"
os.environ["PATH"] = FFMPEG_DIR + os.pathsep + os.environ.get("PATH", "")

AUDIO_IN  = r"C:\Users\ari_v\Downloads\Missing you P1.4 RADIO.mp3"
OUT_DIR   = Path(r"C:\Users\ari_v\Claude apps\Openmontage\output\chef8080_missing_you")
OUT_DIR.mkdir(parents=True, exist_ok=True)

FFMPEG  = os.path.join(FFMPEG_DIR, "ffmpeg.exe")
FFPROBE = os.path.join(FFMPEG_DIR, "ffprobe.exe")

# Load .env for API keys
from dotenv import load_dotenv
load_dotenv(r"C:\Users\ari_v\Claude apps\Openmontage\.env")
PEXELS_KEY = os.environ.get("PEXELS_API_KEY", "")

# Clip segments
CLIPS = [
    {"name": "clip1", "start": 3.0,   "end": 63.0,  "label": "Teaser 1"},
    {"name": "clip2", "start": 103.0, "end": 163.0, "label": "Teaser 2"},
]

# --- Step 1: Transcribe with faster-whisper ---
def transcribe():
    print("\n=== STEP 1: Transcribing audio (word-level timestamps) ===")
    from faster_whisper import WhisperModel
    model = WhisperModel("small", device="cpu", compute_type="int8")
    segments, info = model.transcribe(
        AUDIO_IN,
        word_timestamps=True,
        language="en",
        beam_size=5,
    )
    print(f"Detected language: {info.language}")

    word_timestamps = []
    for seg in segments:
        for w in (seg.words or []):
            word_timestamps.append({
                "word": w.word.strip(),
                "start": round(w.start, 3),
                "end": round(w.end, 3),
            })

    out = OUT_DIR / "transcript_words.json"
    out.write_text(json.dumps(word_timestamps, ensure_ascii=False, indent=2))
    print(f"Transcribed {len(word_timestamps)} words → {out}")
    return word_timestamps


# --- Step 2: Generate karaoke SRT for a time window ---
def make_srt(words, clip_start, clip_end, srt_path):
    """
    Generate karaoke-style SRT for a clip window.
    Each cue shows full line, active word in uppercase bold (via bold tag not supported in srt,
    so we use all-caps for the active word instead — works cleanly for burned subtitles).
    We use ASS format for real karaoke highlight.
    """
    # Filter words in this time range
    clip_words = [w for w in words if w["end"] > clip_start and w["start"] < clip_end]

    # Shift timestamps to be relative to clip start
    shifted = []
    for w in clip_words:
        shifted.append({
            "word": w["word"],
            "start": max(0.0, w["start"] - clip_start),
            "end": min(clip_end - clip_start, w["end"] - clip_start),
        })

    # Group into lines of ~5 words
    MAX_WORDS = 5
    lines = []
    i = 0
    while i < len(shifted):
        group = shifted[i:i+MAX_WORDS]
        if group:
            lines.append(group)
        i += MAX_WORDS

    # Build ASS subtitle file for karaoke highlighting
    ass_path = Path(str(srt_path).replace(".srt", ".ass"))

    ass_header = """[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,Montserrat,52,&H00FFFFFF,&H000000FF,&H00000000,&H99000000,-1,0,0,0,100,100,2,0,1,3,1,2,60,60,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def fmt_time(s):
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sec = s % 60
        return f"{h:01d}:{m:02d}:{sec:05.2f}"

    ass_events = []
    for line_words in lines:
        if not line_words:
            continue
        line_start = line_words[0]["start"]
        line_end   = line_words[-1]["end"]

        # Build karaoke line: {\\k<dur>}word for each word
        # duration in centiseconds
        parts = []
        for w in line_words:
            dur_cs = int((w["end"] - w["start"]) * 100)
            parts.append(f"{{\\k{dur_cs}}}{w['word']} ")
        text = "".join(parts).strip()

        # Also write one event that shows the full line highlighted word-by-word
        event = f"Dialogue: 0,{fmt_time(line_start)},{fmt_time(line_end)},Karaoke,,0,0,0,,{text}"
        ass_events.append(event)

    ass_content = ass_header + "\n".join(ass_events) + "\n"
    ass_path.write_text(ass_content, encoding="utf-8")
    print(f"Generated ASS karaoke: {ass_path}")
    return ass_path


# --- Step 3: Search and download Pexels footage ---
def search_pexels(query, per_page=5, orientation="portrait"):
    """Search Pexels for portrait video clips."""
    headers = {"Authorization": PEXELS_KEY}
    params = {
        "query": query,
        "per_page": per_page,
        "orientation": orientation,
        "size": "medium",
    }
    r = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params, timeout=20)
    r.raise_for_status()
    return r.json().get("videos", [])


def best_video_url(video, min_h=720):
    """Pick best quality video file at or above target height."""
    files = sorted(
        [f for f in video.get("video_files", []) if f.get("height", 0) >= min_h],
        key=lambda f: f.get("height", 0),
    )
    if files:
        return files[0]["link"]
    # fallback: any file
    all_files = sorted(video.get("video_files", []), key=lambda f: f.get("height", 0), reverse=True)
    return all_files[0]["link"] if all_files else None


def download_file(url, dest):
    """Download with progress."""
    dest = Path(dest)
    if dest.exists():
        print(f"  [cached] {dest.name}")
        return dest
    print(f"  Downloading → {dest.name}")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                if chunk:
                    f.write(chunk)
    print(f"  Done: {dest.stat().st_size // 1024} KB")
    return dest


MELANCHOLY_QUERIES = [
    "rain window night",
    "lonely city night rain",
    "misty fog melancholy",
    "silhouette person alone night",
    "empty street rain night",
    "foggy night lights bokeh",
]


def collect_footage():
    print("\n=== STEP 3: Searching Pexels for melancholic footage ===")
    footage_dir = OUT_DIR / "footage"
    footage_dir.mkdir(exist_ok=True)

    all_clips = []
    seen_ids = set()

    for query in MELANCHOLY_QUERIES:
        print(f"\n  Query: '{query}'")
        try:
            videos = search_pexels(query, per_page=3, orientation="portrait")
            if not videos:
                # try landscape as fallback
                videos = search_pexels(query, per_page=3, orientation="landscape")
            for v in videos:
                if v["id"] in seen_ids:
                    continue
                seen_ids.add(v["id"])
                url = best_video_url(v)
                if not url:
                    continue
                dur = v.get("duration", 0)
                if dur < 4:
                    continue  # skip very short clips
                ext = ".mp4"
                dest = footage_dir / f"pexels_{v['id']}{ext}"
                try:
                    download_file(url, dest)
                    all_clips.append({
                        "path": str(dest),
                        "duration": dur,
                        "query": query,
                        "width": v.get("width", 0),
                        "height": v.get("height", 0),
                    })
                except Exception as e:
                    print(f"  [skip] download failed: {e}")
        except Exception as e:
            print(f"  [skip] search failed: {e}")

    print(f"\nCollected {len(all_clips)} footage clips")
    return all_clips


# --- Step 4: Build the video ---
def build_video(clip_info, footage_clips, words, output_path):
    """
    Compose one 1-minute teaser:
    1. Loop/assemble footage as background (portrait 720x1280)
    2. Color grade: cool, desaturated, slight vignette
    3. Mix audio segment
    4. Burn karaoke subtitles
    """
    name      = clip_info["name"]
    start     = clip_info["start"]
    end       = clip_info["end"]
    duration  = end - start

    print(f"\n=== Building {name} ({duration}s) ===")

    tmp_dir = OUT_DIR / f"tmp_{name}"
    tmp_dir.mkdir(exist_ok=True)

    # -- 4a. Extract audio segment --
    audio_seg = tmp_dir / "audio.aac"
    subprocess.run([
        FFMPEG, "-y",
        "-ss", str(start), "-t", str(duration),
        "-i", AUDIO_IN,
        "-c:a", "aac", "-b:a", "192k",
        str(audio_seg)
    ], check=True, capture_output=True)
    print(f"  Audio segment extracted: {audio_seg}")

    # -- 4b. Prepare footage segments (portrait 720x1280, color graded) --
    # We need ~duration seconds of footage total
    # Cycle through footage clips
    prepared_clips = []
    total_footage_dur = 0.0
    footage_idx = 0
    seg_idx = 0

    while total_footage_dur < duration and footage_idx < len(footage_clips) * 3:
        clip = footage_clips[footage_idx % len(footage_clips)]
        footage_idx += 1
        clip_path = clip["path"]

        # Use 4-8s per visual segment for dynamic cutting
        seg_dur = min(7.0, clip["duration"] if clip["duration"] > 0 else 6.0, duration - total_footage_dur)
        if seg_dur < 2.0:
            break

        seg_out = tmp_dir / f"seg_{seg_idx:03d}.mp4"

        # FFmpeg filter: crop to portrait, scale to 720x1280, color grade
        # Smart crop: center-crop to 9:16 from whatever the source is
        vf_parts = [
            # First scale to fit height 1280
            "scale=-2:1280",
            # Then crop width to 720 from center
            "crop=720:1280",
            # Color grade: melancholic cool tone
            # eq: lower brightness slightly, reduce saturation, add blue tint
            "eq=brightness=-0.05:saturation=0.75:contrast=1.05",
            # Subtle blue overlay via colorbalance
            "colorbalance=rs=-0.1:gs=-0.05:bs=0.15:rm=-0.05:gm=0:bm=0.1:rh=-0.05:gh=0:bh=0.1",
            # Vignette
            "vignette=PI/4",
        ]
        vf = ",".join(vf_parts)

        try:
            subprocess.run([
                FFMPEG, "-y",
                "-ss", "0",
                "-t", str(seg_dur),
                "-i", clip_path,
                "-vf", vf,
                "-c:v", "libx264", "-crf", "22",
                "-an",  # strip audio
                "-r", "30",
                str(seg_out)
            ], check=True, capture_output=True, timeout=60)

            prepared_clips.append(str(seg_out))
            total_footage_dur += seg_dur
            seg_idx += 1
        except Exception as e:
            print(f"  [skip] footage prep failed for {Path(clip_path).name}: {e}")

    print(f"  Prepared {len(prepared_clips)} visual segments ({total_footage_dur:.1f}s total)")

    if not prepared_clips:
        raise RuntimeError("No footage clips prepared — aborting")

    # -- 4c. Concatenate footage --
    raw_video = tmp_dir / "footage_raw.mp4"
    if len(prepared_clips) == 1:
        shutil.copy(prepared_clips[0], raw_video)
    else:
        concat_list = tmp_dir / "concat.txt"
        concat_list.write_text("\n".join(f"file '{p}'" for p in prepared_clips))
        subprocess.run([
            FFMPEG, "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            str(raw_video)
        ], check=True, capture_output=True)
    print(f"  Footage concatenated: {raw_video}")

    # -- 4d. Generate karaoke ASS subtitles --
    srt_path = tmp_dir / "karaoke.srt"
    ass_path = make_srt(words, start, end, srt_path)

    # -- 4e. Final composite: video + audio + burned subtitles --
    # Also add subtle fade-in / fade-out
    final_vf = f"fade=t=in:st=0:d=0.8,fade=t=out:st={duration-1.5}:d=1.5"

    subprocess.run([
        FFMPEG, "-y",
        "-t", str(duration),
        "-i", str(raw_video),
        "-i", str(audio_seg),
        "-vf", f"{final_vf},subtitles={str(ass_path).replace(chr(92), '/')}:force_style='Fontname=Arial,Fontsize=44,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=3,Shadow=1,Alignment=2,MarginV=120'",
        "-c:v", "libx264", "-crf", "20", "-preset", "slow",
        "-c:a", "aac", "-b:a", "192k",
        "-map", "0:v", "-map", "1:a",
        "-shortest",
        "-movflags", "+faststart",
        str(output_path)
    ], check=True, capture_output=True, timeout=300)

    size_mb = Path(output_path).stat().st_size / 1024 / 1024
    print(f"\n  ✓ {name} rendered → {output_path} ({size_mb:.1f} MB)")
    return output_path


# --- MAIN ---
if __name__ == "__main__":
    print("=" * 60)
    print("Chef-8080 – Missing You | Teaser Production")
    print("=" * 60)

    # Step 1: Transcribe
    transcript_cache = OUT_DIR / "transcript_words.json"
    if transcript_cache.exists():
        print(f"\n[cached] Loading transcript from {transcript_cache}")
        words = json.loads(transcript_cache.read_text())
        print(f"  {len(words)} words loaded")
    else:
        words = transcribe()

    # Step 2: Collect footage
    footage = collect_footage()
    if not footage:
        print("ERROR: No footage collected from Pexels")
        sys.exit(1)

    # Step 3: Build both clips
    outputs = []
    for clip_info in CLIPS:
        out_path = OUT_DIR / f"chef8080_missing_you_{clip_info['name']}_720p.mp4"
        try:
            build_video(clip_info, footage, words, out_path)
            outputs.append(out_path)
        except Exception as e:
            print(f"\nERROR building {clip_info['name']}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("DONE")
    for o in outputs:
        print(f"  → {o}")
    print("=" * 60)
