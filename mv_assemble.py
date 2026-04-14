"""
Missing You – Full Music Video Assembly
YouTube 16:9 1280x720, ~3 minutes
Professional cut rhythm with color-graded past/present distinction
"""

import os, sys, json, shutil, subprocess, random
from pathlib import Path

FFMPEG_DIR = r"C:\Users\ari_v\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin"
os.environ["PATH"] = FFMPEG_DIR + os.pathsep + os.environ.get("PATH", "")
FFMPEG  = os.path.join(FFMPEG_DIR, "ffmpeg.exe")

AUDIO_IN  = r"C:\Users\ari_v\Downloads\Missing you P1.4 RADIO.mp3"
MV_DIR    = Path(r"C:\Users\ari_v\Claude apps\Openmontage\output\missing_you_mv")
SCENE_DIR = MV_DIR / "scenes"
TMP_DIR   = MV_DIR / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

from dotenv import load_dotenv
load_dotenv(r"C:\Users\ari_v\Claude apps\Openmontage\.env")

# ── Color grades ──────────────────────────────────────────────────────────────
# 2000: warm golden, film grain simulation
GRADE_2000 = (
    "eq=brightness=0.04:saturation=1.15:contrast=0.96,"
    "colorchannelmixer=rr=1.08:rg=0.02:rb=-0.04:ra=0:"
    "gr=0.02:gg=1.02:gb=-0.02:ga=0:br=-0.06:bg=-0.02:bb=0.88:ba=0,"
    "unsharp=3:3:0.3:3:3:0,"
    "noise=alls=6:allf=t"
)
# 2025: cool blue-grey, desaturated
GRADE_2025 = (
    "eq=brightness=-0.04:saturation=0.72:contrast=1.06,"
    "colorchannelmixer=rr=0.88:rg=0:rb=0.04:ra=0:"
    "gr=0:gg=0.92:gb=0.04:ga=0:br=0:bg=0.02:bb=1.12:ba=0,"
    "vignette=PI/4"
)

# ── EDIT TIMELINE ─────────────────────────────────────────────────────────────
# Format: (scene_id, clip_start_in_scene, clip_dur, era)
# era: "2000" or "2025" (determines color grade)
# Times in seconds within the generated clip

TIMELINE = [
    # ── INTRO 0–10s ─────────────────────────────────────────────────────────
    # Wide establishing shot, then photo close-up plays once through to end
    ("intro_2025_sofia_wide",     0, 5.0, "2025"),  # 0–5s
    ("ecus_2025_sofia_photo",     0, 5.0, "2025"),  # 5–10s  single continuous play

    # ── VERSE 1: CAFÉ 10–44s ─────────────────────────────────────────────────
    ("cafe_2000_wide",            0, 4.5, "2000"),  # 4–8.5s
    ("cafe_2000_marcus_talking",  0, 3.5, "2000"),  # 8.5–12s
    ("cafe_2000_sofia_laughing",  0, 3.5, "2000"),  # 12–15.5s
    ("cafe_2000_wide",            5, 4.0, "2000"),  # 15.5–19.5s — second half of same clip
    ("cafe_2025_sofia_alone",     0, 4.5, "2025"),  # 19.5–24s
    ("cafe_2025_empty_chair",     0, 3.5, "2025"),  # 24–27.5s
    ("cafe_2025_sofia_alone",     5, 4.0, "2025"),  # 27.5–31.5s
    ("intimate_2000_hands",       0, 3.5, "2000"),  # 31.5–35s
    ("ecus_2025_sofia_tears",     0, 3.0, "2025"),  # 35–38s

    # ── PRE-CHORUS 38–53s ────────────────────────────────────────────────────
    ("street_2000_jacket",        0, 4.0, "2000"),  # 38–42s
    ("street_2000_jacket",        4, 4.0, "2000"),  # 42–46s
    ("street_2025_sofia_alone",   0, 3.5, "2025"),  # 46–49.5s
    ("street_2025_marcus_alone",  0, 3.5, "2025"),  # 49.5–53s

    # ── CHORUS 1 53–82s — fast cuts ──────────────────────────────────────────
    ("ecus_2000_sofia_happy",     0, 2.5, "2000"),  # 53–55.5s
    ("ecus_2025_sofia_tears",     2, 2.5, "2025"),  # 55.5–58s
    ("intimate_2000_running_rain",0, 2.5, "2000"),  # 58–60.5s
    ("alone_2025_sofia_walking_toward", 0, 2.5, "2025"), # 60.5–63s
    ("ecus_2000_marcus_laughing", 0, 2.5, "2000"),  # 63–65.5s
    ("street_2025_marcus_alone",  2, 2.5, "2025"),  # 65.5–68s
    ("park_2000_reading",         0, 3.0, "2000"),  # 68–71s
    ("park_2025_sofia_alone",     0, 3.0, "2025"),  # 71–74s
    ("intimate_2000_kiss",        0, 2.5, "2000"),  # 74–76.5s
    ("ecus_2025_marcus_window",   0, 2.5, "2025"),  # 76.5–79s
    ("intimate_2000_hands",       2, 3.0, "2000"),  # 79–82s

    # ── INSTRUMENTAL 82–114s — narrative pace ────────────────────────────────
    ("record_2000",               0, 5.0, "2000"),  # 82–87s
    ("record_2000",               5, 4.0, "2000"),  # 87–91s
    ("record_2025_sofia",         0, 5.0, "2025"),  # 91–96s
    ("park_2000_reading",         5, 5.0, "2000"),  # 96–101s
    ("park_2025_sofia_alone",     0, 4.5, "2025"),  # 101–105.5s
    ("park_2025_marcus_alone",    0, 4.5, "2025"),  # 105.5–110s
    ("dance_2000",                0, 4.0, "2000"),  # 110–114s

    # ── VERSE 2 114–131s ─────────────────────────────────────────────────────
    ("dance_2025_sofia_watching", 0, 4.0, "2025"),  # 114–118s
    ("dance_2025_marcus_bar",     0, 4.0, "2025"),  # 118–122s
    ("intimate_2000_running_rain",2, 4.0, "2000"),  # 122–126s
    ("alone_2025_sofia_jacket",   0, 5.0, "2025"),  # 126–131s

    # ── CHORUS 2 131–160s — fast cuts ────────────────────────────────────────
    ("ecus_2000_sofia_happy",     2, 2.0, "2000"),  # 131–133s
    ("ecus_2025_sofia_tears",     0, 2.0, "2025"),  # 133–135s
    ("ecus_2000_marcus_laughing", 2, 2.0, "2000"),  # 135–137s
    ("ecus_2025_marcus_window",   2, 2.0, "2025"),  # 137–139s
    ("cafe_2000_wide",            2, 2.5, "2000"),  # 139–141.5s
    ("cafe_2025_sofia_alone",     3, 2.5, "2025"),  # 141.5–144s
    ("park_2000_reading",         2, 2.5, "2000"),  # 144–146.5s
    ("park_2025_sofia_alone",     2, 2.5, "2025"),  # 146.5–149s
    ("bridge_2000",               0, 3.0, "2000"),  # 149–152s
    ("alone_2025_marcus_bridge",  0, 3.0, "2025"),  # 152–155s
    ("alone_2025_sofia_walking_away", 0, 2.5, "2025"),  # 155–157.5s
    ("alone_2025_marcus_insomnia",0, 2.5, "2025"),  # 157.5–160s

    # ── OUTRO 160–184s ───────────────────────────────────────────────────────
    ("ecus_2025_sofia_photo",     2, 5.0, "2025"),  # 160–165s
    ("ecus_2025_marcus_phone",    0, 4.5, "2025"),  # 165–169.5s
    ("intimate_2000_walking_away",0, 5.0, "2000"),  # 169.5–174.5s
    ("alone_2025_sofia_walking_away", 2, 4.5, "2025"),  # 174.5–179s
    ("outro_sofia_window",        0, 5.0, "2025"),  # 179–184s — FADE OUT
]

# ── Lyric subtitles ───────────────────────────────────────────────────────────
LYRICS = [
    (7.32,   13.86, "The room still hums with echoes low,"),
    (13.86,  21.20, "Your laughter lives in radio snow."),
    (21.20,  28.78, "Every cup I pour, every midnight blue,"),
    (31.04,  38.70, "There's a quiet place that still holds you."),
    (38.70,  43.58, "I breathe your name like it might call you near,"),
    (45.56,  53.44, "But the wind just answers, no one's here."),
    (53.44,  59.04, "Missing you, like the stars miss dawn,"),
    (60.82,  66.76, "Burning bright, but the night feels wrong."),
    (68.06,  74.14, "Time moves slow where your shadow grew"),
    (75.08,  81.44, "Every moment still missing you."),
    (114.96, 122.80,"I reach for warmth that fades like rain,"),
    (122.80, 131.06,"Falling soft against the pane."),
    (132.46, 137.74,"Missing you, like the stars miss dawn,"),
    (138.10, 145.32,"Burning bright, but the night feels wrong."),
    (146.16, 152.94,"Time moves slow where your shadow grew"),
    (154.80, 160.32,"Every moment still missing you."),
    (169.06, 179.12,"Every moment...  still missing you."),
]

def fmt_ass(s):
    h=int(s//3600); m=int((s%3600)//60); sec=s%60
    return f"{h:01d}:{m:02d}:{sec:05.2f}"

def make_ass(out_path, total_dur):
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Lyric,Arial,38,&H00FFFFFF,&H00AAAAFF,&H00000000,&H88000000,-1,0,0,0,100,100,1.5,0,1,3,1.5,2,80,80,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for s, e, text in LYRICS:
        if e > total_dur: continue
        words = text.split(); n = len(words)
        wcs = int(((e-s)/n)*100) if n else 100
        kar = " ".join(f"{{\\k{wcs}}}{w}" for w in words)
        events.append(f"Dialogue: 0,{fmt_ass(s)},{fmt_ass(e)},Lyric,,0,0,0,,{kar}")
    Path(out_path).write_text(header + "\n".join(events) + "\n", encoding="utf-8")


def prep_segment(scene_id, clip_in, dur, era, seg_idx, manifest_map):
    """Trim a scene clip and apply era color grade. Returns path to prepared seg."""
    if scene_id not in manifest_map:
        print(f"  [MISSING scene] {scene_id}")
        return None

    src = manifest_map[scene_id]
    grade = GRADE_2000 if era == "2000" else GRADE_2025

    out = TMP_DIR / f"seg_{seg_idx:03d}_{era}.mp4"
    try:
        subprocess.run([
            FFMPEG, "-y",
            "-ss", str(clip_in),
            "-t", str(dur),
            "-i", src,
            "-vf", f"scale=1280:720:force_original_aspect_ratio=decrease,"
                   f"pad=1280:720:(ow-iw)/2:(oh-ih)/2,{grade}",
            "-c:v", "libx264", "-crf", "20", "-preset", "medium",
            "-an", "-r", "30",
            str(out)
        ], check=True, capture_output=True, timeout=60)
        return str(out)
    except Exception as e:
        print(f"  [prep fail] {scene_id}: {e}")
        return None


def assemble():
    # Load manifest
    manifest_path = MV_DIR / "scenes_manifest.json"
    if not manifest_path.exists():
        print("ERROR: scenes_manifest.json not found. Run mv_generate_scenes.py first.")
        sys.exit(1)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_map = {s["id"]: s["path"] for s in manifest if Path(s["path"]).exists()}
    print(f"Loaded {len(manifest_map)}/{len(manifest)} scenes from manifest")

    # Build segments
    print(f"\nPreparing {len(TIMELINE)} timeline segments...")
    prepared = []
    total_dur = 0.0

    for idx, (scene_id, clip_in, dur, era) in enumerate(TIMELINE):
        path = prep_segment(scene_id, clip_in, dur, era, idx, manifest_map)
        if path:
            prepared.append(path)
            total_dur += dur
            print(f"  [{idx:02d}] {scene_id[:35]:35} {era} {dur:.1f}s  cum={total_dur:.1f}s")

    print(f"\n{len(prepared)}/{len(TIMELINE)} segments prepared, total={total_dur:.1f}s")
    print(f"Song duration: 183.98s")

    # Concatenate
    print("\nConcatenating timeline...")
    raw = TMP_DIR / "timeline_raw.mp4"
    clist = TMP_DIR / "concat.txt"
    clist.write_text("\n".join(f"file '{p}'" for p in prepared), encoding="utf-8")
    subprocess.run([
        FFMPEG, "-y", "-f", "concat", "-safe", "0",
        "-i", str(clist), "-c", "copy", str(raw)
    ], check=True, capture_output=True)

    # Trim to song length
    trimmed = TMP_DIR / "timeline_trimmed.mp4"
    subprocess.run([
        FFMPEG, "-y", "-t", "183.98", "-i", str(raw), "-c", "copy", str(trimmed)
    ], check=True, capture_output=True)

    # ASS subtitles
    ass_path = Path("C:/mvy/mv_lyrics.ass")
    ass_path.parent.mkdir(exist_ok=True)
    make_ass(str(ass_path), 183.98)

    # Final render
    out_path = MV_DIR / "chef8080_missing_you_FULLMV_720p.mp4"
    print(f"\nFinal render -> {out_path.name}")
    subprocess.run([
        FFMPEG, "-y",
        "-i", str(trimmed),
        "-i", AUDIO_IN,
        "-vf", "fade=t=in:st=0:d=1.5,fade=t=out:st=182:d=2,ass=mv_lyrics.ass",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-c:a", "aac", "-b:a", "192k",
        "-map", "0:v:0", "-map", "1:a:0",
        "-t", "183.98",
        "-movflags", "+faststart",
        "-s", "1280x720",
        str(out_path)
    ], check=True, capture_output=True, timeout=600, cwd="C:/mvy")

    mb = out_path.stat().st_size / 1024 / 1024
    print(f"DONE: {out_path} ({mb:.1f} MB)")
    return out_path


if __name__ == "__main__":
    print("=" * 65)
    print("Missing You – Full MV Assembly")
    print("=" * 65)
    assemble()
