"""
Take Me Where The Stars Go - Scene Frame Generator (pass 1 of 2)

Generates one still image per scene using FLUX on FAL.
Files are numbered 001_..., 002_... so they sort correctly in the folder.

Review the frames/ folder, then run mv_generate_scenes.py to animate them.
"""

import os, json, requests, argparse, subprocess
from pathlib import Path
from dotenv import load_dotenv

# ── FFmpeg for post-grade ──────────────────────────────────────────────────────
FFMPEG_DIR = r"C:\Users\ari_v\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin"
FFMPEG = os.path.join(FFMPEG_DIR, "ffmpeg.exe")

# Tapa C: vintage curves + desat 15% + kontrasti -8% + grain 4
# Antaa elokuvamaisen faded-lookin joka pitää kuvat realistisina i2v:tä varten
FILM_GRADE = "curves=preset=vintage,eq=saturation=0.85:contrast=0.92,noise=alls=4"

load_dotenv(r"C:\Users\ari_v\Claude apps\Openmontage\.env")
os.environ["FAL_KEY"] = os.environ.get("FAL_KEY", "")
import fal_client

# ── Paths ──────────────────────────────────────────────────────────────────────
MV_DIR    = Path(__file__).parent
REFS_DIR  = MV_DIR / "refs"
FRAMES_DIR = Path(r"C:\Users\ari_v\Claude apps\Openmontage\output\take_me_stars_mv\frames")
FRAMES_DIR.mkdir(parents=True, exist_ok=True)

MODEL_IMG = "fal-ai/flux-pro/v1.1"   # High quality 16:9 landscape

# ── Character descriptions ─────────────────────────────────────────────────────
CHARS = {
    "mia_casual": (
        "a 32-year-old woman named Mia, wavy shoulder-length brown hair, "
        "minimal natural makeup, tired but beautiful face, wearing a sage green cardigan "
        "over a floral shirt, straight blue jeans, dark red ankle boots"
    ),
    "mia_party": (
        "a 32-year-old woman named Mia, wavy shoulder-length brown hair, "
        "dark eye makeup and subtle lipstick, wearing a fitted black blazer "
        "over a black satin top, dark slim jeans, black platform shoes"
    ),
    "dancer": (
        "a young woman in her mid-20s, dancing alone on a dancefloor, "
        "eyes closed, arms loose, expression of pure joy and freedom"
    ),
    "none": "",
}

# ── Style suffixes ─────────────────────────────────────────────────────────────
STYLES = {
    "apartment": (
        "dim apartment interior at night, single lamp or cold blue TV glow, "
        "long shadows, stillness and quiet, cinematic 16:9, photorealistic film still"
    ),
    "city": (
        "neon-lit city street at night, wet pavement with pink and amber reflections, "
        "light rain, warm bokeh lights, cinematic 16:9, photorealistic film still"
    ),
    "club": (
        "dimly lit intimate club interior, strobe and warm amber stage lighting, "
        "deep red accents, shallow depth of field, cinematic 16:9, photorealistic film still"
    ),
    "sunrise": (
        "early morning golden hour light, soft warm long shadows, quiet and hopeful, "
        "cinematic 16:9, photorealistic film still"
    ),
}

NEG = (
    "cartoon, anime, illustration, painting, blurry, low quality, "
    "watermark, text overlay, extra limbs, deformed face, ugly, cgi, "
    "portrait studio background, grey backdrop, white background"
)

# ── Scenes (same order as TIMELINE) ───────────────────────────────────────────
# Each entry: (scene_id, style, char_key, still_description)
SCENES = [
    # ANCHORS (001-003)
    ("anchor_mia_apartment", "apartment", "mia_casual",
     "Close-up portrait of {char}, sitting alone on a worn couch in a dark apartment at night. "
     "Empty expression, blue TV light washing across her face. Piano visible blurred in background. {style}"),

    ("anchor_mia_city", "city", "mia_party",
     "Close-up portrait of {char} standing on a wet neon-lit city street at night. "
     "She looks upward, pink and amber neon light falling on her face. {style}"),

    ("anchor_mia_club", "club", "mia_party",
     "Close-up portrait of {char} in a dimly lit club. "
     "Strobe light cuts across her face, expression quiet and internal. {style}"),

    # INTRO 0-20s (004-006)
    ("intro_apartment_wide", "apartment", "mia_casual",
     "Wide shot of a small urban apartment at night. An upright piano stands against one wall, dusty and untouched. "
     "{char} sits far across the room on a couch, back to the piano, lit by faint blue TV glow. "
     "The room feels still and heavy. {style}"),

    ("intro_mia_face", "apartment", "mia_casual",
     "Extreme close-up of {char} face in a dark apartment. "
     "She stares forward, expression vacant and drained, not crying—just empty. "
     "Blue TV light flickers on her face. {style}"),

    ("intro_piano_detail", "apartment", "none",
     "Extreme close-up of upright piano keys in a dark apartment at night. "
     "Keys slightly dusty, clearly untouched for years. "
     "Faint cold blue light catches the ivory edges. No hands. Just silence. {style}"),

    # VERSE 1 20-65s (007-010)
    ("v1_mia_window", "apartment", "mia_casual",
     "Medium shot of {char} standing at an apartment window at night, looking down at the street below. "
     "Neon light from outside colours her face faintly. She is very still, listening. {style}"),

    ("v1_window_close", "apartment", "mia_casual",
     "Close-up of {char} hands on an apartment window frame, the glass fogged slightly. "
     "Her face is partially visible as a reflection in the dark glass. {style}"),

    ("v1_past_piano", "apartment", "mia_casual",
     "Medium shot of {char} walking through her apartment. "
     "The upright piano is clearly visible in the background—she walks past it, "
     "deliberately not looking at it. {style}"),

    ("v1_hallway_jacket", "apartment", "mia_casual",
     "Medium shot of {char} standing completely still in a narrow dark hallway. "
     "A jacket hangs on a hook by the front door ahead of her. "
     "Her face shows internal conflict, frozen in indecision. {style}"),

    # CHORUS 1 65-95s (011-015)
    ("chorus1_door_opens", "city", "mia_party",
     "Medium shot of {char} on the doorstep of a building, stepping out onto a neon-lit city street at night. "
     "She has paused, face tilted slightly upward, taking her first breath of city air. "
     "A faint expression of relief. {style}"),

    ("chorus1_city_walk", "city", "mia_party",
     "Wide cinematic shot of {char} walking alone down a glistening neon-lit city street at night. "
     "Wet pavement reflects pink and amber light all around her. "
     "She walks slowly, separate from the city but beginning to feel it. {style}"),

    ("chorus1_neon_details", "city", "none",
     "Cinematic close-up details of a neon-lit city street at night: "
     "glowing signs reflected in rain puddles, light rain falling through neon, "
     "blurred figures in background. Pure atmosphere and colour. {style}"),

    ("chorus1_club_door", "city", "mia_party",
     "Medium shot of {char} standing in front of an unmarked club door on a side street. "
     "Faint bass music seeps through, warm amber glow under the door. "
     "Her hand is not raised yet—she hesitates. {style}"),

    # VERSE 2 95-140s (015-020)
    ("v2_club_enter", "club", "mia_party",
     "Medium shot of {char} just inside the entrance of a dimly lit club. "
     "Strobe and coloured stage lighting flash around her. "
     "She has stopped just inside the door, taking in the scene—people dancing, blurred. {style}"),

    ("v2_back_against_wall", "club", "mia_party",
     "Medium shot of {char} with her back literally pressed against the club wall, "
     "arms loosely folded across her chest, watching the dancefloor. "
     "Strobe light cuts across her face. She is an observer, not a participant. {style}"),

    ("v2_dancer_spotted", "club", "dancer",
     "Medium close-up of {char} on a dancefloor, dancing completely alone, eyes closed, "
     "arms loose at her sides, face upturned—totally surrendered to the music. "
     "Coloured club light washes over her. {style}"),

    ("v2_mia_watches_dancer", "club", "mia_party",
     "Extreme close-up of {char} face watching something off-camera. "
     "Strobe light flickers across her. Her expression shifts: "
     "recognition, longing, something unlocking deep inside her. {style}"),

    # PRE-CHORUS / CHORUS 2 (019-024)
    ("chorus2_eyes_close", "club", "mia_party",
     "Extreme close-up of {char} face as she slowly closes her eyes. "
     "Strobe light across her closed eyelids. Her expression softens completely—"
     "first moment of peace in the whole story. {style}"),

    ("chorus2_first_step", "club", "mia_party",
     "Medium shot of {char} taking one slow uncertain step away from the club wall "
     "toward the dancefloor. She is mid-step, hesitating, people dancing blurred around her. {style}"),

    ("chorus2_dancing_begins", "club", "mia_party",
     "Medium shot of {char} on the dancefloor beginning to move. "
     "Small, cautious movements—not yet free, but the walls are coming down. "
     "Warm amber light falls across her. {style}"),

    ("chorus2_laugh", "club", "mia_party",
     "Close-up of {char} laughing genuinely on the dancefloor—surprised by her own laugh. "
     "A real, unguarded smile. Club light warm on her face. "
     "First genuine joy of the whole story. {style}"),

    # PEAK 190-230s (025-027)
    ("peak_dancing_free", "club", "mia_party",
     "Medium close-up of {char} dancing on the dancefloor with eyes closed, completely present. "
     "Natural fluid movement, no self-consciousness. "
     "Strobe and warm amber wash over her. This is who she was. {style}"),

    ("peak_crowd_energy", "club", "mia_party",
     "Wide shot of a full dancefloor, everyone moving together under strobe lights. "
     "{char} is visible among the crowd—no longer separate, part of something larger. "
     "Energy, warmth, belonging. {style}"),

    ("peak_face_release", "club", "mia_party",
     "Extreme close-up of {char} face tilted slightly upward, eyes closed, "
     "expression of complete surrender and release. "
     "Coloured light moves across her face. No more walls. {style}"),

    # OUTRO / SUNRISE 230-274s (028-033)
    ("outro_club_empty", "sunrise", "mia_party",
     "Wide shot of an empty club interior in early morning. "
     "Chairs on tables, house lights on, pale golden dawn light through high windows. "
     "{char} stands alone on the empty dancefloor, looking around quietly. {style}"),

    ("outro_street_morning", "sunrise", "mia_party",
     "Wide cinematic shot of {char} walking alone down a city street in early morning golden light. "
     "The same street as before—now warm, quiet, and empty. "
     "She walks slowly, unhurried, at peace. {style}"),

    ("outro_home_door", "sunrise", "mia_party",
     "Medium shot of {char} opening her apartment door in warm morning light. "
     "She pauses in the doorway—sunlight floods in behind her. {style}"),

    ("outro_piano_approach", "sunrise", "mia_party",
     "Wide shot of the apartment in golden morning light. "
     "{char} walks slowly toward the upright piano. "
     "For the first time, she walks toward it—not past it. "
     "Golden light falls on the piano keys ahead of her. {style}"),

    ("outro_piano_sits", "sunrise", "mia_party",
     "Medium close-up of {char} sitting at the upright piano in morning light, "
     "looking at the keys a long moment. "
     "Both hands rest gently on the keys—not playing yet, just touching them. "
     "Careful. Like touching something sacred. {style}"),

    ("outro_piano_keys_close", "sunrise", "none",
     "Extreme close-up of two hands resting gently on piano keys in warm golden morning light. "
     "Fingers still, not playing—just returned. "
     "Ivory keys glow in the light. Stillness. Hope. {style}"),
]


def build_prompt(still_desc, char_key, style_key):
    char = CHARS.get(char_key, "")
    style = STYLES.get(style_key, "")
    p = still_desc.replace("{char}", char).replace("{style}", style)
    return p


def generate_frame(idx, scene_id, style, char_key, still_desc):
    """Generate a single still frame image."""
    num = f"{idx:03d}"
    out = FRAMES_DIR / f"{num}_{scene_id}.png"

    if out.exists() and out.stat().st_size > 50_000:
        print(f"  [cached] {out.name}")
        return str(out)

    prompt = build_prompt(still_desc, char_key, style)
    print(f"  Generating frame: {out.name}")

    result = fal_client.subscribe(MODEL_IMG, arguments={
        "prompt": prompt,
        "negative_prompt": NEG,
        "image_size": "landscape_16_9",   # 1360x768, close to 720p
        "num_inference_steps": 25,
        "guidance_scale": 3.5,
        "num_images": 1,
        "safety_tolerance": "2",
        "output_format": "png",
    }, with_logs=False)

    url = result["images"][0]["url"]
    r = requests.get(url, stream=True, timeout=60)
    r.raise_for_status()
    with open(out, "wb") as f:
        for chunk in r.iter_content(1 << 16):
            if chunk:
                f.write(chunk)

    kb = out.stat().st_size / 1024
    print(f"  Saved {out.name} ({kb:.0f} KB)")

    # Apply film grade in-place
    tmp = out.with_suffix(".tmp.png")
    out.rename(tmp)
    r = subprocess.run(
        [FFMPEG, "-y", "-i", str(tmp), "-vf", FILM_GRADE, "-q:v", "1", str(out)],
        capture_output=True, timeout=30
    )
    tmp.unlink(missing_ok=True)
    if r.returncode != 0:
        print(f"  [grade warn] {r.stderr.decode(errors='replace')[-200:]}")
    else:
        print(f"  Graded  {out.name} ({out.stat().st_size//1024:.0f} KB)")

    return str(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--anchors-only", action="store_true",
                        help="Generate only the first 3 anchor frames")
    parser.add_argument("--scene", help="Generate only one scene by ID (for retries)")
    args = parser.parse_args()

    scenes_to_run = SCENES
    if args.anchors_only:
        scenes_to_run = SCENES[:3]
    elif args.scene:
        scenes_to_run = [(sid, sty, ch, desc) for (sid, sty, ch, desc) in SCENES
                         if sid == args.scene]
        if not scenes_to_run:
            print(f"ERROR: scene '{args.scene}' not found")
            return

    # Cost estimate: FLUX Pro ~$0.05 per image
    cost = len(scenes_to_run) * 0.05
    print("=" * 65)
    print("Take Me Where The Stars Go — Scene Frame Generation")
    print(f"Model : {MODEL_IMG}")
    print(f"Scenes: {len(scenes_to_run)} | Est. cost: ~${cost:.2f} USD")
    print(f"Output: {FRAMES_DIR}")
    print("=" * 65)

    manifest = {}
    manifest_path = FRAMES_DIR.parent / "frames_manifest.json"
    if manifest_path.exists():
        for entry in json.loads(manifest_path.read_text(encoding="utf-8")):
            manifest[entry["id"]] = entry

    results = []
    for (scene_id, style, char_key, still_desc) in scenes_to_run:
        # Find index in full SCENES list for numbering
        idx = next((i + 1 for i, s in enumerate(SCENES) if s[0] == scene_id), 0)
        print(f"\n[{idx:02d}/{len(SCENES)}] {scene_id}")
        try:
            path = generate_frame(idx, scene_id, style, char_key, still_desc)
            results.append({"id": scene_id, "frame_path": path,
                            "style": style, "char": char_key})
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback; traceback.print_exc()

    for r in results:
        manifest[r["id"]] = r
    manifest_path.write_text(
        json.dumps(list(manifest.values()), indent=2), encoding="utf-8"
    )
    print(f"\nDone: {len(results)}/{len(scenes_to_run)} frames")
    print(f"Review: {FRAMES_DIR}")
    print(f"Manifest: {manifest_path}")
    if not args.anchors_only and not args.scene:
        print("\nNext steps:")
        print("  1. Review frames in the output folder")
        print("  2. Retry any bad frames: python mv_generate_frames.py --scene <id>")
        print("  3. When happy: python mv_generate_scenes.py  (animates each frame)")


if __name__ == "__main__":
    main()
