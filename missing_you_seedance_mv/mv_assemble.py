"""
Missing You × Seedance 2.0 — Full MV Assembly
Chef-8080 | YouTube 16:9 1280x720 | ~3:04
Concatenates numbered scene clips, mixes master audio, fades in/out.
"""

import os, sys, json, subprocess
from pathlib import Path

FFMPEG_DIR = r"C:\Users\ari_v\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin"
os.environ["PATH"] = FFMPEG_DIR + os.pathsep + os.environ.get("PATH", "")
FFMPEG = os.path.join(FFMPEG_DIR, "ffmpeg.exe")

AUDIO_IN  = r"C:\Users\ari_v\Downloads\Missing you P1.4 RADIO.mp3"
MV_DIR    = Path(r"C:\Users\ari_v\Claude apps\Openmontage\output\missing_you_seedance")
SCENE_DIR = MV_DIR / "scenes"
TMP_DIR   = MV_DIR / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

SONG_DUR = 183.98  # 3:03.98

# Ordered timeline — anchor clips (001-003) excluded, production clips in sequence
TIMELINE = [
    "004_intro_2025_sofia_wide",
    "005_cafe_2000_wide",
    "006_cafe_2000_marcus_talking",
    "007_cafe_2000_sofia_laughing",
    "008_cafe_2025_sofia_alone",
    "009_cafe_2025_empty_chair",
    "010_street_2000_jacket",
    "011_street_2025_sofia_alone",
    "012_street_2025_marcus_alone",
    "013_record_2000",
    "014_record_2025_sofia",
    "015_park_2000_reading",
    "016_park_2025_sofia_alone",
    "017_park_2025_marcus_alone",
    "018_dance_2000",
    "019_dance_2025_sofia_watching",
    "020_dance_2025_marcus_bar",
    "021_intimate_2000_kiss",
    "022_intimate_2000_running_rain",
    "023_intimate_2000_walking_away",
    "024_intimate_2000_hands",
    "025_ecus_2000_sofia_happy",
    "026_ecus_2000_marcus_laughing",
    "027_ecus_2025_sofia_tears",
    "028_ecus_2025_marcus_window",
    "029_ecus_2025_sofia_photo",
    "030_ecus_2025_marcus_phone",
    "031_alone_2025_sofia_jacket",
    "032_alone_2025_marcus_bridge",
    "036_reunion_bridge_2025",
]


def prep_segment(clip_name, seg_idx):
    """Scale to 1280x720 @ 24fps, strip audio."""
    src = SCENE_DIR / f"{clip_name}.mp4"
    if not src.exists():
        print(f"  [MISSING] {clip_name}.mp4")
        return None

    out = TMP_DIR / f"seg_{seg_idx:03d}.mp4"
    vf = "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=24"
    try:
        subprocess.run([
            FFMPEG, "-y",
            "-i", str(src),
            "-vf", vf,
            "-c:v", "libx264", "-crf", "20", "-preset", "medium",
            "-an",
            str(out)
        ], check=True, capture_output=True, timeout=120)
        return str(out)
    except subprocess.CalledProcessError as e:
        print(f"  [prep fail] {clip_name}: {e.stderr.decode(errors='replace')[-300:]}")
        return None


def assemble():
    print(f"\nPreparing {len(TIMELINE)} timeline segments...")
    prepared  = []
    total_dur = 0.0

    for idx, clip_name in enumerate(TIMELINE):
        path = prep_segment(clip_name, idx)
        if path:
            prepared.append(path)
            # Read actual duration from source
            res = subprocess.run([
                FFMPEG.replace("ffmpeg.exe", "ffprobe.exe"),
                "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(SCENE_DIR / f"{clip_name}.mp4")
            ], capture_output=True, text=True)
            dur = float(res.stdout.strip()) if res.stdout.strip() else 0
            total_dur += dur
            print(f"  [{idx:02d}] {clip_name:45}  cum={total_dur:.1f}s")
        else:
            print(f"  [{idx:02d}] SKIPPED {clip_name}")

    print(f"\n{len(prepared)}/{len(TIMELINE)} segments prepared, total={total_dur:.1f}s")
    print(f"Song duration: {SONG_DUR}s")

    if not prepared:
        print("ERROR: No segments prepared. Aborting.")
        sys.exit(1)

    # ── Concatenate ────────────────────────────────────────────────────────────
    print("\nConcatenating...")
    raw   = TMP_DIR / "timeline_raw.mp4"
    clist = TMP_DIR / "concat.txt"
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

    # ── Final render ───────────────────────────────────────────────────────────
    out_path = MV_DIR / "chef8080_missing_you_FULLMV_720p.mp4"
    print(f"\nFinal render -> {out_path.name}")

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
        str(out_path)
    ], capture_output=True, timeout=900)

    if res.returncode != 0:
        print(res.stderr.decode(errors="replace"))
        raise RuntimeError("Final render failed")

    mb = out_path.stat().st_size / 1024 / 1024
    print(f"\nDONE: {out_path}  ({mb:.1f} MB)")
    return out_path


if __name__ == "__main__":
    print("=" * 65)
    print("Chef-8080 – Missing You | Full MV Assembly (Seedance 2.0)")
    print("=" * 65)
    assemble()
