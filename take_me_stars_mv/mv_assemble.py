"""
Take Me Where The Stars Go – Full Music Video Assembly
Chef-8080 | YouTube 16:9 1280x720 | ~4:34
Single timeline (present): club/city/apartment/sunrise scenes with per-style color grades
"""

import os, sys, json, subprocess
from pathlib import Path

FFMPEG_DIR = r"C:\Users\ari_v\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin"
os.environ["PATH"] = FFMPEG_DIR + os.pathsep + os.environ.get("PATH", "")
FFMPEG = os.path.join(FFMPEG_DIR, "ffmpeg.exe")

AUDIO_IN  = r"C:\Users\ari_v\Downloads\Chef-8080 - Take me where the stars go MASTERED.mp3"
MV_DIR    = Path(r"C:\Users\ari_v\Claude apps\Openmontage\output\take_me_stars_mv")
SCENE_DIR = MV_DIR / "scenes"
TMP_DIR   = MV_DIR / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

SONG_DUR  = 274.52   # 4:34.52

# ── Color grades per scene style ──────────────────────────────────────────────
# Base: vintage curves (lifted blacks + faded highlights) + desat + grain
# Each style adds a colour push on top.
_BASE = "curves=preset=vintage,noise=alls=4"
GRADES = {
    # Apartment: kylmä sinertävä sisävalo, vahvempi desat, hämärä
    # colorbalance: rs/gs/bs = red/green/blue shadows, rm/gm/bm = midtones
    "apartment": (
        f"{_BASE},"
        "eq=saturation=0.72:contrast=0.90:brightness=-0.02,"
        "colorbalance=rs=-0.04:gs=-0.02:bs=0.06:rm=-0.02:gm=0.0:bm=0.03"
    ),
    # City: neonin lämmin amberi/roosa, kevyt kontrasti
    "city": (
        f"{_BASE},"
        "eq=saturation=0.88:contrast=0.93:brightness=0.01,"
        "colorbalance=rs=0.04:gs=0.01:bs=-0.03:rm=0.02:gm=0.0:bm=-0.02"
    ),
    # Club: lämmin amberi/punainen, syvät mustat
    "club": (
        f"{_BASE},"
        "eq=saturation=0.84:contrast=0.91:brightness=-0.01,"
        "colorbalance=rs=0.06:gs=0.01:bs=-0.06:rm=0.03:gm=0.0:bm=-0.03"
    ),
    # Sunrise: kultainen lämpö, pehmeä lift
    "sunrise": (
        f"{_BASE},"
        "eq=saturation=0.90:contrast=0.92:brightness=0.02,"
        "colorbalance=rs=0.06:gs=0.03:bs=-0.04:rm=0.03:gm=0.01:bm=-0.02"
    ),
}

# ── EDIT TIMELINE ─────────────────────────────────────────────────────────────
# Format: (scene_id, start_offset_in_clip, duration_seconds, style)
# Total must fit ~274.52 s

TIMELINE = [
    # INTRO 0-20s
    ("intro_apartment_wide",   0, 6.0, "apartment"),
    ("intro_mia_face",         0, 5.0, "apartment"),
    ("intro_piano_detail",     0, 5.0, "apartment"),
    # VERSE 1 20-65s
    ("v1_mia_window",          0, 8.0, "apartment"),
    ("v1_window_close",        0, 5.0, "apartment"),
    ("v1_past_piano",          0, 5.0, "apartment"),
    ("v1_hallway_jacket",      0, 8.0, "apartment"),
    ("v1_hallway_jacket",      4, 5.0, "apartment"),  # hold on decision
    # CHORUS 1 65-95s
    ("chorus1_door_opens",     0, 5.0, "city"),
    ("chorus1_city_walk",      0, 8.0, "city"),
    ("chorus1_neon_details",   0, 5.0, "city"),
    ("chorus1_city_walk",      4, 4.0, "city"),
    ("chorus1_club_door",      0, 5.0, "city"),
    # VERSE 2 95-140s
    ("v2_club_enter",          0, 5.0, "club"),
    ("v2_back_against_wall",   0, 8.0, "club"),
    ("v2_dancer_spotted",      0, 5.0, "club"),
    ("v2_mia_watches_dancer",  0, 5.0, "club"),
    ("v2_back_against_wall",   4, 4.0, "club"),
    ("v2_dancer_spotted",      2, 3.0, "club"),
    # PRE-CHORUS 2
    ("v2_mia_watches_dancer",  2, 4.0, "club"),
    ("chorus2_eyes_close",     0, 5.0, "club"),
    # CHORUS 2 140-190s
    ("chorus2_first_step",     0, 5.0, "club"),
    ("chorus2_dancing_begins", 0, 8.0, "club"),
    ("chorus2_laugh",          0, 5.0, "club"),
    ("peak_dancing_free",      0, 5.0, "club"),
    # CHORUS 3 / PEAK 157-197s
    ("peak_dancing_free",      3, 4.0, "club"),
    ("peak_crowd_energy",      0, 4.0, "club"),
    ("peak_face_release",      0, 4.0, "club"),
    ("chorus2_dancing_begins", 4, 3.0, "club"),
    ("peak_dancing_free",      5, 3.0, "club"),
    ("peak_crowd_energy",      2, 3.0, "club"),
    # EXTENDED PEAK 197-230s  (fills out the missing 33s)
    ("chorus2_dancing_begins", 2, 3.0, "club"),
    ("peak_face_release",      2, 3.0, "club"),
    ("chorus2_laugh",          2, 4.0, "club"),
    ("peak_dancing_free",      1, 4.0, "club"),
    ("peak_crowd_energy",      1, 4.0, "club"),
    ("chorus2_eyes_close",     2, 4.0, "club"),
    ("peak_face_release",      1, 3.0, "club"),
    ("peak_dancing_free",      4, 4.0, "club"),
    ("peak_crowd_energy",      3, 4.0, "club"),
    # OUTRO / SUNRISE 230-274s
    ("outro_club_empty",       0, 5.0, "sunrise"),
    ("outro_street_morning",   0, 8.0, "sunrise"),
    ("outro_home_door",        0, 5.0, "sunrise"),
    ("outro_piano_approach",   0, 5.0, "sunrise"),
    ("outro_piano_sits",       0, 8.0, "sunrise"),
    ("outro_piano_keys_close", 0, 5.0, "sunrise"),
    # EXTENDED OUTRO 267-275s  (fills the remaining ~48s)
    ("outro_piano_keys_close", 1, 5.0, "sunrise"),
    ("outro_piano_sits",       2, 8.0, "sunrise"),
    ("outro_street_morning",   4, 6.0, "sunrise"),
    ("outro_piano_approach",   1, 5.0, "sunrise"),
    ("outro_piano_keys_close", 0, 5.0, "sunrise"),
    ("outro_piano_sits",       0, 8.0, "sunrise"),
    ("outro_street_morning",   2, 5.0, "sunrise"),
    ("outro_piano_keys_close", 0, 6.0, "sunrise"),
]


def prep_segment(scene_id, clip_in, dur, style, seg_idx, manifest_map):
    """Trim a scene clip, apply style color grade, scale to 1280x720 @ 24fps."""
    if scene_id not in manifest_map:
        print(f"  [MISSING scene] {scene_id}")
        return None

    src   = manifest_map[scene_id]
    grade = GRADES.get(style, GRADES["apartment"])

    out = TMP_DIR / f"seg_{seg_idx:03d}_{style}.mp4"
    vf = (
        f"scale=1280:720:force_original_aspect_ratio=decrease,"
        f"pad=1280:720:(ow-iw)/2:(oh-ih)/2,"
        f"fps=24,"
        f"{grade}"
    )
    try:
        subprocess.run([
            FFMPEG, "-y",
            "-ss", str(clip_in),
            "-t",  str(dur),
            "-i",  src,
            "-vf", vf,
            "-c:v", "libx264", "-crf", "20", "-preset", "medium",
            "-an",
            str(out)
        ], check=True, capture_output=True, timeout=90)
        return str(out)
    except subprocess.CalledProcessError as e:
        print(f"  [prep fail] {scene_id}: {e.stderr.decode(errors='replace')[-300:]}")
        return None
    except Exception as e:
        print(f"  [prep fail] {scene_id}: {e}")
        return None


def assemble():
    # ── Load manifest ──────────────────────────────────────────────────────────
    manifest_path = MV_DIR / "scenes_manifest.json"
    if not manifest_path.exists():
        print("ERROR: scenes_manifest.json not found. Run mv_generate_scenes.py first.")
        sys.exit(1)

    manifest     = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_map = {s["id"]: s["path"] for s in manifest if Path(s["path"]).exists()}
    print(f"Loaded {len(manifest_map)}/{len(manifest)} scenes from manifest")

    # Warn about missing scenes
    needed = {row[0] for row in TIMELINE}
    missing = needed - set(manifest_map.keys())
    if missing:
        print(f"\nWARNING: {len(missing)} scene(s) missing from manifest and will be skipped:")
        for m in sorted(missing):
            print(f"  - {m}")

    # ── Prepare segments ───────────────────────────────────────────────────────
    print(f"\nPreparing {len(TIMELINE)} timeline segments...")
    prepared   = []
    total_dur  = 0.0

    for idx, (scene_id, clip_in, dur, style) in enumerate(TIMELINE):
        path = prep_segment(scene_id, clip_in, dur, style, idx, manifest_map)
        if path:
            prepared.append(path)
            total_dur += dur
            print(f"  [{idx:02d}] {scene_id[:38]:38} {style:10} {dur:.1f}s  cum={total_dur:.1f}s")
        else:
            print(f"  [{idx:02d}] SKIPPED {scene_id}")

    print(f"\n{len(prepared)}/{len(TIMELINE)} segments prepared, total={total_dur:.1f}s")
    print(f"Song duration: {SONG_DUR}s")

    if not prepared:
        print("ERROR: No segments were prepared. Aborting.")
        sys.exit(1)

    # ── Concatenate segments ───────────────────────────────────────────────────
    print("\nConcatenating timeline...")
    raw    = TMP_DIR / "timeline_raw.mp4"
    clist  = TMP_DIR / "concat.txt"
    clist.write_text("\n".join(f"file '{p}'" for p in prepared), encoding="utf-8")
    subprocess.run([
        FFMPEG, "-y", "-f", "concat", "-safe", "0",
        "-i", str(clist), "-c", "copy", str(raw)
    ], check=True, capture_output=True)

    # ── Trim to song length ────────────────────────────────────────────────────
    trimmed = TMP_DIR / "timeline_trimmed.mp4"
    subprocess.run([
        FFMPEG, "-y",
        "-t", str(SONG_DUR),
        "-i", str(raw),
        "-c", "copy",
        str(trimmed)
    ], check=True, capture_output=True)

    # ── Final render (no subtitles — burned in separate pass) ─────────────────
    no_subs = MV_DIR / "chef8080_take_me_stars_FULLMV_720p_nosubs.mp4"
    out_path = MV_DIR / "chef8080_take_me_stars_FULLMV_720p.mp4"
    print(f"\nFinal render (pass 1 – no subtitles) -> {no_subs.name}")

    vf_final = (
        f"fade=t=in:st=0:d=1.5,"
        f"fade=t=out:st={SONG_DUR - 2.5:.2f}:d=2.5"
    )

    res = subprocess.run([
        FFMPEG, "-y",
        "-i", str(trimmed),
        "-i", AUDIO_IN,
        "-vf", vf_final,
        "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-c:a", "aac", "-b:a", "192k",
        "-map", "0:v:0", "-map", "1:a:0",
        "-t", str(SONG_DUR),
        "-s", "1280x720",
        "-movflags", "+faststart",
        str(no_subs)
    ], capture_output=True, timeout=900)
    if res.returncode != 0:
        print(res.stderr.decode(errors="replace"))
        raise RuntimeError("Pass 1 failed")

    mb = no_subs.stat().st_size / 1024 / 1024
    print(f"  Pass 1 OK: {mb:.1f} MB")

    # ── Subtitle burn (pass 2) ─────────────────────────────────────────────────
    project_dir = Path(__file__).parent
    ass_path    = project_dir / "lyrics.ass"
    if not ass_path.exists():
        print("WARNING: lyrics.ass not found — skipping subtitle burn")
        no_subs.rename(out_path)
    else:
        import shutil
        # Copy to a flat temp dir with no spaces — gives us a simple filename
        ass_tmp_dir = Path("C:/Temp/openmontage")
        ass_tmp_dir.mkdir(parents=True, exist_ok=True)
        ass_tmp = ass_tmp_dir / "mv_lyrics.ass"
        shutil.copy2(ass_path, ass_tmp)
        # KEY FIX: run FFmpeg with cwd=ass_tmp_dir so we can pass a relative
        # filename ("mv_lyrics.ass") to the ass filter — no drive-letter colon,
        # no filter-parser escaping headaches on Windows.
        print(f"\nSubtitle burn (pass 2) -> {out_path.name}")
        res2 = subprocess.run([
            FFMPEG, "-y",
            "-i", str(no_subs),
            "-vf", "ass=mv_lyrics.ass",
            "-c:v", "libx264", "-crf", "18", "-preset", "medium",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(out_path)
        ], capture_output=True, timeout=900, cwd=str(ass_tmp_dir))
        if res2.returncode != 0:
            print("Subtitle burn failed, using no-subs version:")
            print(res2.stderr.decode(errors="replace")[-2000:])
            shutil.copy2(no_subs, out_path)
        else:
            mb2 = out_path.stat().st_size / 1024 / 1024
            print(f"  Pass 2 OK: {mb2:.1f} MB")

    print(f"\nDONE: {out_path}  ({out_path.stat().st_size/1024/1024:.1f} MB)")
    return out_path


if __name__ == "__main__":
    print("=" * 65)
    print("Chef-8080 – Take Me Where The Stars Go | Full MV Assembly")
    print("=" * 65)
    assemble()
