"""
Production script v2: Chef-8080 - Missing You
Uses manually-timed lyrics (professional approach for known lyrics)
Two portrait 9:16 720p teaser clips with karaoke subtitles
Melancholic, cinematic style
"""

import os
import sys
import json
import shutil
import subprocess
import requests
from pathlib import Path

# --- Setup paths ---
FFMPEG_DIR = r"C:\Users\ari_v\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin"
os.environ["PATH"] = FFMPEG_DIR + os.pathsep + os.environ.get("PATH", "")

AUDIO_IN = r"C:\Users\ari_v\Downloads\Missing you P1.4 RADIO.mp3"
OUT_DIR  = Path(r"C:\Users\ari_v\Claude apps\Openmontage\output\chef8080_missing_you")
OUT_DIR.mkdir(parents=True, exist_ok=True)

FFMPEG  = os.path.join(FFMPEG_DIR, "ffmpeg.exe")
FFPROBE = os.path.join(FFMPEG_DIR, "ffprobe.exe")

from dotenv import load_dotenv
load_dotenv(r"C:\Users\ari_v\Claude apps\Openmontage\.env")
PEXELS_KEY = os.environ.get("PEXELS_API_KEY", "")

# --- Manually-timed lyrics ---
# Based on energy profile analysis (ebur128) and song structure
# Song total: 183.98s
# Verse1: 3-48s | Chorus1: 55-82s | Verse2: 83-103s
# Chorus2: 103-127s | Outro: 127-183s
LYRIC_LINES = [
    # (start_s, end_s, text)
    # Timestamps derived from actual Whisper word-level transcription
    # --- VERSE 1 ---
    (7.32,  13.86, "The room still hums with echoes low,"),
    (13.86, 21.20, "Your laughter lives in radio snow."),
    (21.20, 28.78, "Every cup I pour, every midnight blue,"),
    (31.04, 38.70, "There's a quiet place that still holds you."),
    # --- PRE-CHORUS ---
    (38.70, 43.58, "I breathe your name like it might call you near,"),
    (45.56, 53.44, "But the wind just answers, no one's here."),
    # --- CHORUS 1 ---
    (53.44, 59.04, "Missing you, like the stars miss dawn,"),
    (60.82, 66.76, "Burning bright, but the night feels wrong."),
    (68.06, 74.14, "Time moves slow where your shadow grew —"),
    (75.08, 81.44, "Every moment still missing you."),
    # --- VERSE 2 ---
    (114.96, 122.80, "I reach for warmth that fades like rain,"),
    (122.80, 131.06, "Falling soft against the pane."),
    # --- CHORUS 2 ---
    (132.46, 137.74, "Missing you, like the stars miss dawn,"),
    (138.10, 145.32, "Burning bright, but the night feels wrong."),
    (146.16, 152.94, "Time moves slow where your shadow grew —"),
    (154.80, 160.32, "Every moment still missing you."),
    # --- OUTRO ---
    (169.06, 179.12, "Every moment... still missing you."),
]

# Clip windows
# Clip 1 now starts at 22s so we fit the FULL chorus (ends ~82s) in 60s
CLIPS = [
    {"name": "clip1", "start": 22.0,  "end": 82.0,  "label": "Teaser 1 — Verse & Full Chorus"},
    {"name": "clip2", "start": 103.0, "end": 163.0, "label": "Teaser 2 — Chorus & Outro"},
]


# --- ASS subtitle generation ---
def fmt_ass_time(s):
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s % 60
    return f"{h:01d}:{m:02d}:{sec:05.2f}"


def make_ass(clip_start, clip_end, ass_path):
    """Generate karaoke-style ASS subtitle for one clip."""
    clip_dur = clip_end - clip_start

    # Filter lines in this window
    clip_lines = [
        (s - clip_start, e - clip_start, t)
        for s, e, t in LYRIC_LINES
        if e > clip_start and s < clip_end
    ]
    # Clamp to clip bounds
    clip_lines = [(max(0, s), min(clip_dur, e), t) for s, e, t in clip_lines]

    ass = """[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,Arial,46,&H00FFFFFF,&H00AAAAFF,&H00000000,&HAA000000,-1,0,0,0,100,100,1.5,0,1,3.5,1.5,2,50,50,130,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for s, e, text in clip_lines:
        # Split into words and create karaoke timing
        words = text.split()
        n = len(words)
        dur = e - s
        word_dur_cs = int((dur / n) * 100) if n > 0 else 100

        karaoke_parts = []
        for w in words:
            karaoke_parts.append(f"{{\\k{word_dur_cs}}}{w}")
        karaoke_text = " ".join(karaoke_parts)

        events.append(
            f"Dialogue: 0,{fmt_ass_time(s)},{fmt_ass_time(e)},Karaoke,,0,0,0,,{karaoke_text}"
        )

    ass += "\n".join(events) + "\n"
    Path(ass_path).write_text(ass, encoding="utf-8")
    print(f"  ASS karaoke: {ass_path}")
    return ass_path


# --- Pexels footage ---
def search_pexels(query, per_page=4, orientation="portrait"):
    headers = {"Authorization": PEXELS_KEY}
    r = requests.get(
        "https://api.pexels.com/videos/search",
        headers=headers,
        params={"query": query, "per_page": per_page, "orientation": orientation, "size": "medium"},
        timeout=20,
    )
    r.raise_for_status()
    return r.json().get("videos", [])


def best_url(video):
    files = sorted(
        [f for f in video.get("video_files", []) if f.get("height", 0) >= 720],
        key=lambda f: f.get("height", 0),
    )
    if files:
        return files[0]["link"]
    all_f = sorted(video.get("video_files", []), key=lambda f: f.get("height", 0), reverse=True)
    return all_f[0]["link"] if all_f else None


def download(url, dest):
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 100_000:
        print(f"    [cached] {dest.name}")
        return dest
    print(f"    Downloading {dest.name}...")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                if chunk:
                    f.write(chunk)
    print(f"    {dest.stat().st_size // 1024} KB")
    return dest


# Queries split into two roles: CITY (atmosphere) and WOMAN (performance)
# We'll download separately and interleave them for a music video edit
CITY_QUERIES = [
    "rainy city street neon night",
    "wet pavement reflection night",
    "rain window city night",
    "rain street urban night lights",
    "neon reflection rainy street",
]
WOMAN_QUERIES = [
    "singer woman close up emotional",
    "woman singing rain city night",
    "woman performer emotional rain",
    "woman night portrait rain street",
    "woman umbrella city rain walking",
]
# Combined for legacy collect_footage()
QUERIES = CITY_QUERIES + WOMAN_QUERIES


def collect_footage():
    print("\n=== Collecting footage from Pexels ===")
    footage_dir = OUT_DIR / "footage"
    footage_dir.mkdir(exist_ok=True)
    clips = []
    seen = set()

    for q in QUERIES:
        print(f"\n  '{q}'")
        for orientation in ("portrait", "landscape"):
            try:
                videos = search_pexels(q, per_page=3, orientation=orientation)
                for v in videos:
                    if v["id"] in seen:
                        continue
                    seen.add(v["id"])
                    url = best_url(v)
                    if not url:
                        continue
                    dur = v.get("duration", 0)
                    if dur < 3:
                        continue
                    dest = footage_dir / f"pexels_{v['id']}.mp4"
                    try:
                        download(url, dest)
                        clips.append({
                            "path": str(dest),
                            "duration": dur,
                            "width": v.get("width", 0),
                            "height": v.get("height", 0),
                        })
                    except Exception as e:
                        print(f"    [skip] {e}")
                if len(clips) >= 14:
                    break
            except Exception as e:
                print(f"    [search skip] {e}")
        if len(clips) >= 14:
            break

    print(f"\nTotal footage: {len(clips)} clips")
    return clips


# --- Build one video ---
def build_video(clip_info, footage_clips):
    name     = clip_info["name"]
    start    = clip_info["start"]
    end      = clip_info["end"]
    duration = end - start

    print(f"\n{'='*50}")
    print(f"Building {name}: {clip_info['label']} ({duration:.0f}s)")
    print('='*50)

    tmp = OUT_DIR / f"tmp_{name}"
    tmp.mkdir(exist_ok=True)

    # 1. Extract audio segment
    audio_seg = tmp / "audio.aac"
    print(f"  Extracting audio {start}s-{end}s...")
    subprocess.run([
        FFMPEG, "-y",
        "-ss", str(start), "-t", str(duration),
        "-i", AUDIO_IN,
        "-c:a", "aac", "-b:a", "192k",
        str(audio_seg)
    ], check=True, capture_output=True)

    # 2. Prepare portrait footage segments
    print(f"  Preparing visual segments...")
    prepared = []
    total_dur = 0.0
    fi = 0
    si = 0

    # Split footage into city atmosphere and woman performance clips
    # City clips: larger Pexels IDs from city queries tend to be city scenes
    # Woman clips: singer/portrait queries
    import random
    random.seed(42 if name == "clip1" else 99)

    woman_ids = {7586629, 7586634, 7586642, 8039633, 8478458, 8042704,
                 35900306, 7817370, 32093955, 13689923, 28441962, 36573570,
                 28513432, 28495837, 19277499, 28513742, 34853141, 31521814,
                 35675329, 35099181}

    city_clips  = [c for c in footage_clips if not any(str(wid) in c["path"] for wid in woman_ids)]
    woman_clips = [c for c in footage_clips if any(str(wid) in c["path"] for wid in woman_ids)]

    print(f"  City clips: {len(city_clips)}, Woman clips: {len(woman_clips)}")

    random.shuffle(city_clips)
    random.shuffle(woman_clips)

    # Build interleaved shot list: 2 city → 1 woman → 2 city → 1 woman ...
    interleaved = []
    ci, wi = 0, 0
    while ci < len(city_clips) or wi < len(woman_clips):
        # 2 city shots
        for _ in range(2):
            if ci < len(city_clips):
                interleaved.append(("city", city_clips[ci])); ci += 1
        # 1 woman shot
        if wi < len(woman_clips):
            interleaved.append(("woman", woman_clips[wi])); wi += 1

    if not interleaved:
        interleaved = [("city", c) for c in footage_clips]

    while total_dur < duration and fi < len(interleaved) * 4:
        role, clip = interleaved[fi % len(interleaved)]
        fi += 1

        clip_path = clip["path"]
        w, h = clip.get("width", 1920), clip.get("height", 1080)
        clip_native_dur = clip.get("duration", 6.0)

        seg_dur = min(6.5, max(3.5, clip_native_dur * 0.7), duration - total_dur)
        if seg_dur < 2.0:
            break

        seg_out = tmp / f"seg_{si:03d}.mp4"

        # Smart crop to portrait 720x1280
        # If source is portrait: scale and crop width
        # If source is landscape: scale height to 1280, crop center 720px wide
        if h >= w:
            # Already portrait-ish
            vf = f"scale=720:-2,crop=720:1280"
        else:
            # Landscape -> portrait: scale height to 1280, crop width
            vf = f"scale=-2:1280,crop=720:1280"

        # Melancholic color grade: cool blue tones, desaturated
        # eq: lower brightness/saturation, slight contrast boost
        # colorchannelmixer: boost blue, reduce red/green slightly for cool melancholic look
        color_grade = (
            "eq=brightness=-0.04:saturation=0.70:contrast=1.06,"
            "colorchannelmixer=rr=0.88:rg=0:rb=0.04:ra=0:gr=0:gg=0.92:gb=0.04:ga=0:br=0:bg=0.02:bb=1.12:ba=0,"
            "vignette=PI/3.5"
        )

        full_vf = f"{vf},{color_grade}"

        try:
            subprocess.run([
                FFMPEG, "-y",
                "-ss", "0.5",  # skip first half-second
                "-t", str(seg_dur),
                "-i", clip_path,
                "-vf", full_vf,
                "-c:v", "libx264", "-crf", "21", "-preset", "medium",
                "-an", "-r", "30",
                str(seg_out)
            ], check=True, capture_output=True, timeout=90)
            prepared.append(str(seg_out))
            total_dur += seg_dur
            si += 1
            print(f"    seg_{si-1:03d}: {Path(clip_path).name[:30]} ({seg_dur:.1f}s) total={total_dur:.1f}s")
        except Exception as e:
            print(f"    [skip] {Path(clip_path).name}: {e}")

    if not prepared:
        raise RuntimeError(f"No visual segments for {name}")

    print(f"\n  {len(prepared)} segments, {total_dur:.1f}s footage")

    # 3. Concatenate segments
    raw_vid = tmp / "footage_raw.mp4"
    if len(prepared) == 1:
        shutil.copy(prepared[0], raw_vid)
    else:
        clist = tmp / "concat.txt"
        clist.write_text("\n".join(f"file '{p}'" for p in prepared), encoding="utf-8")
        subprocess.run([
            FFMPEG, "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(clist),
            "-c", "copy",
            str(raw_vid)
        ], check=True, capture_output=True)

    # Trim to exact duration
    trimmed_vid = tmp / "footage_trimmed.mp4"
    subprocess.run([
        FFMPEG, "-y",
        "-t", str(duration),
        "-i", str(raw_vid),
        "-c", "copy",
        str(trimmed_vid)
    ], check=True, capture_output=True)

    # 4. Generate ASS karaoke subtitles
    ass_path = tmp / "karaoke.ass"
    make_ass(start, end, ass_path)

    # 5. Final render: video + audio + karaoke subtitles + fades
    out_path = OUT_DIR / f"chef8080_missing_you_{name}_720p.mp4"
    print(f"\n  Rendering final video...")

    # FFmpeg ass= filter on Windows: the colon in drive letter (C:) is parsed
    # as an option separator. Fix: copy ASS to a directory without spaces,
    # then run FFmpeg with cwd set to that dir, and use just the filename.
    ass_work_dir = Path("C:/mvy")
    ass_work_dir.mkdir(exist_ok=True)
    ass_local = ass_work_dir / f"{name}.ass"
    shutil.copy(str(ass_path), str(ass_local))

    fade_vf = f"fade=t=in:st=0:d=1.0,fade=t=out:st={duration-1.8}:d=1.8"

    # Use relative filename (no drive letter) to avoid colon parsing issue
    subprocess.run([
        FFMPEG, "-y",
        "-t", str(duration),
        "-i", str(trimmed_vid),
        "-i", str(audio_seg),
        "-vf", f"{fade_vf},ass={name}.ass",
        "-c:v", "libx264", "-crf", "18", "-preset", "slow",
        "-c:a", "aac", "-b:a", "192k",
        "-map", "0:v:0", "-map", "1:a:0",
        "-shortest",
        "-movflags", "+faststart",
        "-s", "720x1280",
        str(out_path)
    ], check=True, capture_output=True, timeout=300, cwd=str(ass_work_dir))

    size_mb = out_path.stat().st_size / 1024 / 1024
    print(f"\n  DONE: {out_path.name} ({size_mb:.1f} MB)")
    return out_path


# --- MAIN ---
if __name__ == "__main__":
    print("=" * 60)
    print("Chef-8080  Missing You  |  Teaser Production v2")
    print("=" * 60)

    footage = collect_footage()
    if not footage:
        print("ERROR: No footage")
        sys.exit(1)

    outputs = []
    for clip_info in CLIPS:
        try:
            out = build_video(clip_info, footage)
            outputs.append(out)
        except Exception as e:
            import traceback
            print(f"\nERROR: {e}")
            traceback.print_exc()

    print("\n" + "=" * 60)
    if outputs:
        print("VALMIS! Klipit:")
        for o in outputs:
            print(f"  {o}")
    else:
        print("TUOTANTO EPÄONNISTUI")
    print("=" * 60)
