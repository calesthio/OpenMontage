#!/usr/bin/env python3
"""Assemble the ISS Earth-view video: scenes + animated graphics + narration + cards."""
import json, subprocess, sys
from pathlib import Path

ROOT = Path("/workspaces/OpenMontage")
SCENES_DIR = ROOT / "projects/slice_iss/scenes"
GRAPHICS_DIR = ROOT / "projects/slice_iss/graphics"
NARRATION = ROOT / "docs/openmontage/slice/iss/audio/narration_finished.wav"
OUT = ROOT / "projects/slice_iss/renders/final_iss_draft.mp4"

# Select scenes whose total duration covers the narration (~298s) with headroom.
scene_order = ["scn_01","scn_02","scn_03","scn_04","scn_05","scn_06","scn_07"]
manifest = json.load(open(SCENES_DIR / "scenes_manifest.json"))
scene_by_id = {s["scene_id"]: s for s in manifest["scenes"]}

TARGET = 298.35  # narration duration
sel_dur = 0.0
selected = []
for sid in scene_order:
    s = scene_by_id[sid]
    selected.append(s)
    sel_dur += s["duration"]
    if sel_dur >= TARGET + 30:
        break

print("Selected scenes:", [s["scene_id"] for s in selected], "total", sel_dur, "s")

# Build concat list for video (no audio; narration muxed later)
concat_txt = ROOT / "projects/slice_iss/_concat_scenes.txt"
with open(concat_txt, "w") as f:
    for s in selected:
        f.write(f"file '{s['file']}'\n")

OUT.parent.mkdir(parents=True, exist_ok=True)

# Step 1: concatenate scenes (video only)
tmp_video = ROOT / "projects/slice_iss/_concat_raw.mp4"
cmd = ["ffmpeg","-y","-v","error","-f","concat","-safe","0","-i",str(concat_txt),
    "-c","copy",str(tmp_video)]
r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
print("concat rc:", r.returncode, r.stderr[-200:] if r.returncode!=0 else "")

# Step 2: trim to narration duration + mix audio, scale to 1280x720
cmd = ["ffmpeg","-y","-v","error",
    "-i",str(tmp_video),"-i",str(NARRATION),
    "-filter_complex","[0:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1[v]",
    "-map","[v]","-map","1:a",
    "-t",str(TARGET),
    "-c:v","libx264","-crf","20","-preset","ultrafast",
    "-c:a","aac","-b:a","128k",
    "-shortest",
    str(OUT)]
r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
print("mux rc:", r.returncode, r.stderr[-300:] if r.returncode!=0 else "")
if r.returncode != 0:
    sys.exit(1)

# Verify
pr = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-show_entries","stream=codec_type,width,height,r_frame_rate","-of","default=noprint_wrappers=1",str(OUT)],capture_output=True,text=True)
print(pr.stdout)
print("OUT:", OUT, OUT.stat().st_size, "bytes")
