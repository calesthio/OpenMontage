"""
Final production: Chef-8080 – Missing You
Mixes FAL AI woman shots + Pexels city rain footage
Two portrait 9:16 720p teaser clips with karaoke subtitles

Edit pattern (per 60s clip):
  CITY  CITY  WOMAN  CITY  CITY  WOMAN  CITY  CITY  WOMAN ...
  ~5s   ~5s   ~5s    ~5s   ~5s   ~5s    ...

Color grade applied uniformly to ALL clips (FAL + Pexels):
  - Slight desaturation (0.75)
  - Cool blue tint via colorchannelmixer
  - Vignette PI/3.5
  - Brightness/contrast tweak
"""

import os, sys, json, shutil, subprocess, requests, random
from pathlib import Path

FFMPEG_DIR = r"C:\Users\ari_v\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin"
os.environ["PATH"] = FFMPEG_DIR + os.pathsep + os.environ.get("PATH", "")
FFMPEG  = os.path.join(FFMPEG_DIR, "ffmpeg.exe")
FFPROBE = os.path.join(FFMPEG_DIR, "ffprobe.exe")

AUDIO_IN = r"C:\Users\ari_v\Downloads\Missing you P1.4 RADIO.mp3"
OUT_DIR  = Path(r"C:\Users\ari_v\Claude apps\Openmontage\output\chef8080_missing_you")
FAL_DIR  = OUT_DIR / "fal_shots"
FOT_DIR  = OUT_DIR / "footage"
OUT_DIR.mkdir(parents=True, exist_ok=True)

from dotenv import load_dotenv
load_dotenv(r"C:\Users\ari_v\Claude apps\Openmontage\.env")
PEXELS_KEY = os.environ.get("PEXELS_API_KEY", "")

# ── Lyric timestamps (from Whisper) ───────────────────────────────────────────
LYRIC_LINES = [
    (7.32,   13.86,  "The room still hums with echoes low,"),
    (13.86,  21.20,  "Your laughter lives in radio snow."),
    (21.20,  28.78,  "Every cup I pour, every midnight blue,"),
    (31.04,  38.70,  "There's a quiet place that still holds you."),
    (38.70,  43.58,  "I breathe your name like it might call you near,"),
    (45.56,  53.44,  "But the wind just answers, no one's here."),
    (53.44,  59.04,  "Missing you, like the stars miss dawn,"),
    (60.82,  66.76,  "Burning bright, but the night feels wrong."),
    (68.06,  74.14,  "Time moves slow where your shadow grew —"),
    (75.08,  81.44,  "Every moment still missing you."),
    (114.96, 122.80, "I reach for warmth that fades like rain,"),
    (122.80, 131.06, "Falling soft against the pane."),
    (132.46, 137.74, "Missing you, like the stars miss dawn,"),
    (138.10, 145.32, "Burning bright, but the night feels wrong."),
    (146.16, 152.94, "Time moves slow where your shadow grew —"),
    (154.80, 160.32, "Every moment still missing you."),
    (169.06, 179.12, "Every moment... still missing you."),
]

CLIPS = [
    {"name": "clip1", "start": 22.0,  "end": 82.0,  "label": "Teaser 1 — Verse & Full Chorus"},
    {"name": "clip2", "start": 103.0, "end": 163.0, "label": "Teaser 2 — Verse 2, Chorus & Outro"},
]

# ── Color grade (same for all clips) ─────────────────────────────────────────
COLOR_GRADE = (
    "eq=brightness=-0.04:saturation=0.75:contrast=1.06,"
    "colorchannelmixer=rr=0.88:rg=0:rb=0.04:ra=0:"
    "gr=0:gg=0.92:gb=0.04:ga=0:br=0:bg=0.02:bb=1.12:ba=0,"
    "vignette=PI/3.5"
)

# ── Pexels city footage ───────────────────────────────────────────────────────
CITY_QUERIES = [
    "rainy city street neon night",
    "wet pavement reflection night",
    "rain window city night",
    "rain street urban night lights",
    "neon reflection rainy street",
]

def search_pexels(query, per_page=4, orientation="portrait"):
    r = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": PEXELS_KEY},
        params={"query": query, "per_page": per_page,
                "orientation": orientation, "size": "medium"},
        timeout=20,
    )
    r.raise_for_status()
    return r.json().get("videos", [])

def best_url(video):
    files = sorted(
        [f for f in video.get("video_files", []) if f.get("height", 0) >= 720],
        key=lambda f: f["height"],
    )
    if files: return files[0]["link"]
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
                if chunk: f.write(chunk)
    print(f"    {dest.stat().st_size // 1024} KB")
    return dest

def collect_city_footage():
    print("\n=== Collecting Pexels city footage ===")
    FOT_DIR.mkdir(exist_ok=True)
    clips, seen = [], set()
    for q in CITY_QUERIES:
        for orient in ("portrait", "landscape"):
            try:
                vids = search_pexels(q, per_page=4, orientation=orient)
                for v in vids:
                    if v["id"] in seen: continue
                    seen.add(v["id"])
                    url = best_url(v)
                    if not url or v.get("duration", 0) < 4: continue
                    dest = FOT_DIR / f"pexels_{v['id']}.mp4"
                    try:
                        download(url, dest)
                        clips.append({"path": str(dest), "duration": v.get("duration", 6),
                                      "width": v.get("width", 0), "height": v.get("height", 0),
                                      "role": "city"})
                    except Exception as e:
                        print(f"    [skip] {e}")
            except Exception as e:
                print(f"  [search error] {e}")
            if len(clips) >= 14: break
        if len(clips) >= 14: break
    print(f"City footage: {len(clips)} clips")
    return clips

def collect_fal_shots():
    print("\n=== Loading FAL woman shots ===")
    manifest = FAL_DIR / "shots_manifest.json"
    if not manifest.exists():
        print("  WARNING: FAL manifest not found — skipping woman shots")
        return []
    shots = json.loads(manifest.read_text())
    clips = []
    for s in shots:
        p = Path(s["path"])
        if p.exists() and p.stat().st_size > 100_000:
            clips.append({"path": str(p), "duration": 5.0,
                          "width": 720, "height": 1280, "role": "woman",
                          "label": s["label"]})
            print(f"  {s['id']}: {s['label']}")
        else:
            print(f"  [missing] {s['id']}")
    print(f"FAL shots loaded: {len(clips)}")
    return clips

# ── ASS subtitles ─────────────────────────────────────────────────────────────
def fmt_ass(s):
    h=int(s//3600); m=int((s%3600)//60); sec=s%60
    return f"{h:01d}:{m:02d}:{sec:05.2f}"

def make_ass(clip_start, clip_end, ass_path):
    clip_dur = clip_end - clip_start
    lines = [(s-clip_start, min(clip_dur, e-clip_start), t)
             for s,e,t in LYRIC_LINES if e>clip_start and s<clip_end]
    lines = [(max(0,s), e, t) for s,e,t in lines]

    header = """[Script Info]
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
    for s, e, text in lines:
        words = text.split(); n = len(words)
        dur = e - s
        wcs = int((dur/n)*100) if n else 100
        kar = " ".join(f"{{\\k{wcs}}}{w}" for w in words)
        events.append(f"Dialogue: 0,{fmt_ass(s)},{fmt_ass(e)},Karaoke,,0,0,0,,{kar}")

    Path(ass_path).write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return ass_path

# ── Prepare one footage clip into portrait + color grade ──────────────────────
def prep_clip(clip, seg_dur, out_path):
    w, h = clip.get("width", 1920), clip.get("height", 1080)
    if h >= w:
        scale_crop = "scale=720:-2,crop=720:1280"
    else:
        scale_crop = "scale=-2:1280,crop=720:1280"

    vf = f"{scale_crop},{COLOR_GRADE}"

    subprocess.run([
        FFMPEG, "-y",
        "-ss", "0.5",
        "-t", str(seg_dur),
        "-i", clip["path"],
        "-vf", vf,
        "-c:v", "libx264", "-crf", "20", "-preset", "medium",
        "-an", "-r", "30",
        str(out_path)
    ], check=True, capture_output=True, timeout=90)

# ── Build one video ───────────────────────────────────────────────────────────
def build_video(clip_info, city_clips, fal_clips):
    name     = clip_info["name"]
    start    = clip_info["start"]
    end      = clip_info["end"]
    duration = end - start

    print(f"\n{'='*55}")
    print(f"  {name}: {clip_info['label']} ({duration:.0f}s)")
    print(f"  City: {len(city_clips)} | Woman (FAL): {len(fal_clips)}")
    print('='*55)

    tmp = OUT_DIR / f"tmp_{name}"
    tmp.mkdir(exist_ok=True)

    # ── Audio segment ────────────────────────────────────────────────
    audio_seg = tmp / "audio.aac"
    subprocess.run([
        FFMPEG, "-y",
        "-ss", str(start), "-t", str(duration),
        "-i", AUDIO_IN,
        "-c:a", "aac", "-b:a", "192k",
        str(audio_seg)
    ], check=True, capture_output=True)
    print(f"  Audio extracted ({duration:.0f}s)")

    # ── Build interleaved shot list ───────────────────────────────────
    # Pattern: CITY CITY WOMAN CITY CITY WOMAN ...
    # FAL shots are ~5s; city shots we cut to 5-6s for rhythm
    random.seed(7 if name == "clip1" else 13)
    city  = city_clips[:]
    woman = fal_clips[:]
    random.shuffle(city)
    random.shuffle(woman)

    shot_list = []  # (clip_dict, target_dur)
    ci = wi = 0
    while True:
        # 2 city shots
        for _ in range(2):
            if ci < len(city):
                shot_list.append((city[ci], 5.5)); ci += 1
            elif city:
                shot_list.append((city[ci % len(city)], 5.5)); ci += 1
        # 1 woman shot
        if woman:
            shot_list.append((woman[wi % len(woman)], 5.0)); wi += 1
        # Check total
        if sum(d for _,d in shot_list) >= duration:
            break
        if ci > len(city)*4 and wi > len(woman)*4:
            break

    # ── Prepare each segment ─────────────────────────────────────────
    prepared = []
    total_dur = 0.0
    for si, (clip, seg_dur) in enumerate(shot_list):
        remaining = duration - total_dur
        if remaining <= 0.5: break
        seg_dur = min(seg_dur, remaining)
        if seg_dur < 1.5: break

        seg_out = tmp / f"seg_{si:03d}.mp4"
        role = clip.get("role", "city")
        try:
            prep_clip(clip, seg_dur, seg_out)
            prepared.append(str(seg_out))
            total_dur += seg_dur
            label = clip.get("label", Path(clip["path"]).name[:28])
            print(f"    seg_{si:03d} [{role:5}] {label} ({seg_dur:.1f}s) tot={total_dur:.1f}s")
        except Exception as e:
            print(f"    [skip] {Path(clip['path']).name}: {e}")

    if not prepared:
        raise RuntimeError(f"No segments prepared for {name}")

    print(f"\n  {len(prepared)} segments, {total_dur:.1f}s total footage")

    # ── Concatenate ───────────────────────────────────────────────────
    raw = tmp / "raw.mp4"
    if len(prepared) == 1:
        shutil.copy(prepared[0], raw)
    else:
        clist = tmp / "concat.txt"
        clist.write_text("\n".join(f"file '{p}'" for p in prepared), encoding="utf-8")
        subprocess.run([
            FFMPEG, "-y", "-f", "concat", "-safe", "0",
            "-i", str(clist), "-c", "copy", str(raw)
        ], check=True, capture_output=True)

    # Trim to exact duration
    trimmed = tmp / "trimmed.mp4"
    subprocess.run([
        FFMPEG, "-y", "-t", str(duration), "-i", str(raw), "-c", "copy", str(trimmed)
    ], check=True, capture_output=True)

    # ── ASS karaoke ───────────────────────────────────────────────────
    ass_path = tmp / "karaoke.ass"
    make_ass(start, end, ass_path)

    # Copy to no-space path for FFmpeg ass= filter
    ass_work = Path("C:/mvy")
    ass_work.mkdir(exist_ok=True)
    ass_local = ass_work / f"{name}.ass"
    shutil.copy(str(ass_path), str(ass_local))

    # ── Final render ──────────────────────────────────────────────────
    out_path = OUT_DIR / f"chef8080_{name}_FINAL_720p.mp4"
    fade_vf = f"fade=t=in:st=0:d=0.8,fade=t=out:st={duration-1.8}:d=1.8"
    print(f"\n  Rendering final {name}...")

    subprocess.run([
        FFMPEG, "-y",
        "-t", str(duration),
        "-i", str(trimmed),
        "-i", str(audio_seg),
        "-vf", f"{fade_vf},ass={name}.ass",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-c:a", "aac", "-b:a", "192k",
        "-map", "0:v:0", "-map", "1:a:0",
        "-shortest", "-movflags", "+faststart",
        "-s", "720x1280",
        str(out_path)
    ], check=True, capture_output=True, timeout=600, cwd=str(ass_work))

    mb = out_path.stat().st_size / 1024 / 1024
    print(f"  DONE: {out_path.name} ({mb:.1f} MB)")
    return out_path

# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("Chef-8080 – Missing You | FINAL MIXED PRODUCTION")
    print("Pexels city rain + FAL AI woman character shots")
    print("=" * 60)

    city_clips = collect_city_footage()
    fal_clips  = collect_fal_shots()

    if not city_clips and not fal_clips:
        print("ERROR: No footage at all — aborting"); sys.exit(1)

    outputs = []
    for clip_info in CLIPS:
        tmp_path = OUT_DIR / f"tmp_{clip_info['name']}"
        if tmp_path.exists():
            shutil.rmtree(tmp_path)
        try:
            out = build_video(clip_info, city_clips, fal_clips)
            outputs.append(out)
        except Exception as e:
            import traceback
            print(f"\nERROR: {e}"); traceback.print_exc()

    print("\n" + "=" * 60)
    if outputs:
        print("VALMIS:")
        for o in outputs:
            print(f"  >> {o}")
    else:
        print("EPÄONNISTUI")
    print("=" * 60)
