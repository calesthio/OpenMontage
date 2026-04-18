"""
Take Me Where The Stars Go - Music Video Scene Generator  (v2 — Kling v3)

Workflow:
  1. python mv_generate_frames.py          <- still frames + film grade
  2. (review frames)
  3. python mv_generate_scenes.py          <- animate each frame with Kling v3 i2v

Kling v3 i2v:
  - start_image_url : graded frame (correct scene environment)
  - elements        : Mia ref image (character consistency, NOT first frame)
  - aspect_ratio    : 16:9
  - generate_audio  : False  (we have the master track)
"""

import os, json, argparse, requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(r"C:\Users\ari_v\Claude apps\Openmontage\.env")
os.environ["FAL_KEY"] = os.environ.get("FAL_KEY", "")
import fal_client

ARTIST    = "chef8080"
OUT_DIR   = Path(r"C:\Users\ari_v\Claude apps\Openmontage\output\take_me_stars_mv\scenes")
FRAMES_DIR = Path(r"C:\Users\ari_v\Claude apps\Openmontage\output\take_me_stars_mv\frames")
REFS_DIR  = Path(__file__).parent / "refs"
MV_DIR    = Path(r"C:\Users\ari_v\Claude apps\Openmontage\output\take_me_stars_mv")

MODEL_I2V = "fal-ai/kling-video/v3/standard/image-to-video"
MODEL_T2V = "fal-ai/kling-video/v3/standard/text-to-video"   # fallback

OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Characters ─────────────────────────────────────────────────────────────────
CHARS = {
    "mia_casual": {
        "ref":  "Mia_casual.png",
        "desc": ("a 32-year-old woman named Mia, wavy shoulder-length brown hair, "
                 "minimal natural makeup, tired but beautiful face, wearing a sage green cardigan "
                 "over a floral shirt, straight blue jeans, dark red ankle boots"),
    },
    "mia_party": {
        "ref":  "Mia_party.png",
        "desc": ("a 32-year-old woman named Mia, wavy shoulder-length brown hair, "
                 "dark eye makeup and subtle lipstick, wearing a fitted black blazer "
                 "over a black satin top, dark slim jeans, black platform shoes"),
    },
    "dancer": {
        "ref":  None,
        "desc": ("a young woman in her mid-20s dancing alone on a dancefloor, "
                 "eyes closed, arms loose, expression of pure joy and freedom"),
    },
    "none": {
        "ref":  None,
        "desc": "",
    },
}

# ── Style motion cues ─────────────────────────────────────────────────────────
STYLES = {
    "apartment": "dim apartment interior, cold blue-grey light, static slow camera, cinematic 16:9",
    "city":      "neon-lit city street at night, wet pavement, warm amber and pink neon, cinematic 16:9",
    "club":      "dimly lit club interior, strobe and amber stage lighting, shallow depth of field, cinematic 16:9",
    "sunrise":   "early morning golden light, soft warm tones, quiet and still, cinematic 16:9",
}

NEG = (
    "blurry, cartoon, anime, painting, extra limbs, distorted face, "
    "ugly, watermark, text, bad quality, portrait studio background, "
    "grey backdrop, white background, static frozen image"
)

# ── Scenes (same order as TIMELINE in mv_assemble.py) ────────────────────────
SCENES = [
    # ANCHORS
    {"id":"anchor_mia_apartment","dur":"5","style":"apartment","char":"mia_casual","anchor":True,
     "prompt":"Close-up of {char} sitting alone on a couch in a dim apartment at night. "
              "Expression empty and tired. Blue TV glow on her face. Piano visible blurred in background. "
              "Very slow camera drift. {style}"},
    {"id":"anchor_mia_city","dur":"5","style":"city","char":"mia_party","anchor":True,
     "prompt":"Close-up of {char} on a wet neon-lit city street at night. "
              "Pink and amber neon reflections. She looks up at the sky. Slow camera. {style}"},
    {"id":"anchor_mia_club","dur":"5","style":"club","char":"mia_party","anchor":True,
     "prompt":"Close-up of {char} in a dimly lit club, strobe light across her face. "
              "Expression quiet and internal. Very subtle sway. {style}"},

    # INTRO 0-20s
    {"id":"intro_apartment_wide","dur":"5","style":"apartment","char":"mia_casual","anchor":False,
     "prompt":"Wide shot of a small apartment at night. An upright piano stands against one wall, untouched. "
              "{char} sits on the couch across the room, back to the piano, lit by faint blue TV glow. "
              "Room feels still and heavy. Very slow camera drift forward. {style}"},
    {"id":"intro_mia_face","dur":"5","style":"apartment","char":"mia_casual","anchor":False,
     "prompt":"Extreme close-up of {char} face in dark apartment. "
              "Stares forward, expression vacant and drained, not crying, just empty. "
              "Blue TV light flickers gently on her face. {style}"},
    {"id":"intro_piano_detail","dur":"5","style":"apartment","char":"none","anchor":False,
     "prompt":"Extreme close-up of piano keys in a dark apartment. "
              "Keys slightly dusty, clearly untouched for a long time. "
              "Faint blue light catches the ivory edges. No hands. Very slow drift across keys. {style}"},

    # VERSE 1 20-65s
    {"id":"v1_mia_window","dur":"10","style":"apartment","char":"mia_casual","anchor":False,
     "prompt":"Medium shot of {char} slowly getting up and walking to the apartment window. "
              "She looks down at the street below. Neon light from outside colours her face faintly. "
              "She stands still, listening to something far away. {style}"},
    {"id":"v1_window_close","dur":"5","style":"apartment","char":"mia_casual","anchor":False,
     "prompt":"Close-up of {char} hands slowly closing an apartment window. "
              "Her reflection shows briefly in the glass as she shuts it. "
              "The city sounds disappear. {style}"},
    {"id":"v1_past_piano","dur":"5","style":"apartment","char":"mia_casual","anchor":False,
     "prompt":"Medium shot of {char} walking through her apartment. "
              "The piano is clearly visible in the background. "
              "She walks past it without looking at it, deliberately avoiding it. {style}"},
    {"id":"v1_hallway_jacket","dur":"10","style":"apartment","char":"mia_casual","anchor":False,
     "prompt":"Medium shot of {char} standing still in a dark apartment hallway. "
              "A jacket hangs on a hook by the front door. "
              "She stares at it for a long moment, perfectly still. Internal conflict. {style}"},

    # CHORUS 1 65-95s
    {"id":"chorus1_door_opens","dur":"5","style":"city","char":"mia_party","anchor":False,
     "prompt":"Medium shot of {char} stepping out of a building door onto a neon-lit city street at night. "
              "She pauses on the doorstep, looks up at the sky. A faint smile, or maybe just relief. {style}"},
    {"id":"chorus1_city_walk","dur":"10","style":"city","char":"mia_party","anchor":False,
     "prompt":"Wide tracking shot of {char} walking alone down a neon-lit city street at night. "
              "Wet pavement reflects pink and amber light. She walks slowly, taking it in. "
              "The city is alive around her but she is still separate from it. Slow camera follows. {style}"},
    {"id":"chorus1_neon_details","dur":"5","style":"city","char":"none","anchor":False,
     "prompt":"Cinematic details of a neon-lit city street at night: "
              "glowing signs reflected in puddles, light rain through neon, blurred figures. "
              "Pure atmosphere and colour. Slow drift. {style}"},
    {"id":"chorus1_club_door","dur":"5","style":"city","char":"mia_party","anchor":False,
     "prompt":"Medium shot of {char} slowing to a stop in front of an unmarked club door. "
              "Faint bass from inside, glow under the door. She stands there, hand not yet raised. {style}"},

    # VERSE 2 95-140s
    {"id":"v2_club_enter","dur":"5","style":"club","char":"mia_party","anchor":False,
     "prompt":"Medium shot of {char} stepping into a dimly lit club interior. "
              "Strobe light and coloured stage lighting flash around her. "
              "She pauses just inside the door, taking in the scene. People dancing, blurred. {style}"},
    {"id":"v2_back_against_wall","dur":"10","style":"club","char":"mia_party","anchor":False,
     "prompt":"Medium shot of {char} standing with her back literally against the club wall, "
              "arms loosely folded, watching the dancefloor. "
              "Strobe light cuts across her face. She is outside of it all. {style}"},
    {"id":"v2_dancer_spotted","dur":"5","style":"club","char":"dancer","anchor":False,
     "prompt":"Medium close-up of {char} on a dancefloor, dancing completely alone, eyes closed, "
              "arms loose, totally surrendered to the music. No self-consciousness at all. "
              "Coloured club light washes over her. {style}"},
    {"id":"v2_mia_watches_dancer","dur":"5","style":"club","char":"mia_party","anchor":False,
     "prompt":"Extreme close-up of {char} face watching something off-camera. "
              "Strobe light flickers across her face. Her expression shifts: "
              "recognition, longing, something unlocking inside her. {style}"},

    # CHORUS 2 140-190s
    {"id":"chorus2_eyes_close","dur":"5","style":"club","char":"mia_party","anchor":False,
     "prompt":"Extreme close-up of {char} face as she slowly closes her eyes. "
              "Strobe light across her closed eyelids. Expression softens completely. "
              "First moment of peace in the whole video. {style}"},
    {"id":"chorus2_first_step","dur":"5","style":"club","char":"mia_party","anchor":False,
     "prompt":"Medium shot of {char} pushing off the wall and taking one slow uncertain step "
              "toward the dancefloor. She hesitates, then another step. People dance around her. {style}"},
    {"id":"chorus2_dancing_begins","dur":"10","style":"club","char":"mia_party","anchor":False,
     "prompt":"Medium shot of {char} on the dancefloor beginning to move. "
              "At first small cautious movements, then gradually more natural. "
              "Not yet free, but the walls are coming down. {style}"},
    {"id":"chorus2_laugh","dur":"5","style":"club","char":"mia_party","anchor":False,
     "prompt":"Close-up of {char} laughing genuinely on the dancefloor. "
              "A real laugh, she is surprised by it herself. Club light warm on her face. "
              "First real joy of the whole video. {style}"},

    # PEAK 190-230s
    {"id":"peak_dancing_free","dur":"10","style":"club","char":"mia_party","anchor":False,
     "prompt":"Medium close-up of {char} dancing on the dancefloor, eyes closed, completely present. "
              "Moves naturally, without self-consciousness. Strobe and warm amber wash over her. "
              "This is who she was. This is who she is. {style}"},
    {"id":"peak_crowd_energy","dur":"5","style":"club","char":"mia_party","anchor":False,
     "prompt":"Wide shot of a full dancefloor, everyone moving together. "
              "{char} visible among the crowd, no longer separate, part of something larger. "
              "Strobe light, energy, warmth. {style}"},
    {"id":"peak_face_release","dur":"5","style":"club","char":"mia_party","anchor":False,
     "prompt":"Extreme close-up of {char} face tilted slightly upward, eyes closed, "
              "expression of complete release and surrender. "
              "Coloured light moves across her face. No more walls. {style}"},

    # OUTRO / SUNRISE 230-274s
    {"id":"outro_club_empty","dur":"5","style":"sunrise","char":"mia_party","anchor":False,
     "prompt":"Wide shot of an empty club interior in early morning. Chairs on tables, lights off, "
              "only pale golden morning light through high windows. "
              "{char} stands alone on the empty dancefloor, looking around quietly. {style}"},
    {"id":"outro_street_morning","dur":"10","style":"sunrise","char":"mia_party","anchor":False,
     "prompt":"Wide shot of {char} walking alone down a city street in early morning. "
              "Golden sunrise light fills the empty street. Same street as before, now warm and quiet. "
              "She walks slowly, unhurried. {style}"},
    {"id":"outro_home_door","dur":"5","style":"sunrise","char":"mia_party","anchor":False,
     "prompt":"Medium shot of {char} opening her apartment door and stepping inside. "
              "Warm morning light floods in behind her. She pauses in the doorway, then steps in. {style}"},
    {"id":"outro_piano_approach","dur":"5","style":"sunrise","char":"mia_party","anchor":False,
     "prompt":"Wide shot of the apartment in morning light. {char} walks slowly toward the piano. "
              "For the first time she is walking toward it, not past it. "
              "Golden light falls on the piano keys ahead of her. {style}"},
    {"id":"outro_piano_sits","dur":"10","style":"sunrise","char":"mia_party","anchor":False,
     "prompt":"Medium close-up of {char} sitting down at the piano in morning light. "
              "She looks at the keys a moment. Then slowly places both hands on them, "
              "gently, carefully, like touching something sacred. She does not play yet. "
              "Camera holds. {style}"},
    {"id":"outro_piano_keys_close","dur":"5","style":"sunrise","char":"none","anchor":False,
     "prompt":"Extreme close-up of two hands resting gently on piano keys. "
              "Warm golden morning light on the fingers and ivory keys. "
              "The hands are still, not playing, just there. Just returned. Very slow fade. {style}"},
]


# ── URL cache (frames + refs) ─────────────────────────────────────────────────
CACHE_FILE = REFS_DIR / "urls_v3.json"

def load_cache():
    return json.loads(CACHE_FILE.read_text(encoding="utf-8")) if CACHE_FILE.exists() else {}

def save_cache(cache):
    CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")

def get_or_upload(filepath, cache, key):
    if key in cache:
        return cache[key]
    print(f"  Uploading {Path(filepath).name}...")
    url = fal_client.upload_file(str(filepath))
    cache[key] = url
    save_cache(cache)
    print(f"  -> {url[:60]}...")
    return url


def build_prompt(scene):
    char_desc = CHARS.get(scene.get("char", "none"), {}).get("desc", "")
    style     = STYLES.get(scene.get("style", ""), "")
    p = scene["prompt"].replace("{char}", char_desc).replace("{style}", style)
    return p


def generate(scene, frames_manifest, cache):
    out = OUT_DIR / f"{scene['id']}.mp4"
    if out.exists() and out.stat().st_size > 200_000:
        print(f"  [cached] {scene['id']}")
        return str(out)

    prompt = build_prompt(scene)
    char_key = scene.get("char", "none")

    # ── Start frame ────────────────────────────────────────────────────────────
    frame_entry = frames_manifest.get(scene["id"])
    frame_path  = frame_entry.get("frame_path") if frame_entry else None
    if not frame_path or not Path(frame_path).exists():
        print(f"  [warn] No frame for {scene['id']} — falling back to t2v")
        result = fal_client.subscribe(MODEL_T2V, arguments={
            "prompt": prompt, "negative_prompt": NEG,
            "duration": scene["dur"], "aspect_ratio": "16:9",
            "generate_audio": False, "cfg_scale": 0.5,
        }, with_logs=False)
        url = result["video"]["url"]
    else:
        frame_url = get_or_upload(frame_path, cache, f"frame:{scene['id']}")

        # ── Character reference via elements ───────────────────────────────────
        ref_filename = CHARS.get(char_key, {}).get("ref")
        elements = None
        if ref_filename:
            ref_path = REFS_DIR / ref_filename
            if ref_path.exists():
                ref_url = get_or_upload(str(ref_path), cache, f"ref:{char_key}")
                elements = [{"frontal_image_url": ref_url,
                            "reference_image_urls": [ref_url]}]

        mode = "i2v+elements" if elements else "i2v"
        print(f"  {mode} ({scene['dur']}s) [{char_key}]: {scene['id']}")

        args = {
            "start_image_url": frame_url,
            "prompt": prompt,
            "negative_prompt": NEG,
            "duration": scene["dur"],
            "aspect_ratio": "16:9",
            "generate_audio": False,
            "cfg_scale": 0.5,
        }
        if elements:
            args["elements"] = elements

        result = fal_client.subscribe(MODEL_I2V, arguments=args, with_logs=False)
        url = result["video"]["url"]

    r = requests.get(url, stream=True, timeout=120)
    r.raise_for_status()
    with open(out, "wb") as f:
        for chunk in r.iter_content(1 << 16):
            if chunk: f.write(chunk)
    mb = out.stat().st_size / 1024 / 1024
    print(f"  Saved {out.name} ({mb:.1f} MB)")
    return str(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refs-only", action="store_true",
                        help="Generate only anchor scenes (3 clips) for approval")
    parser.add_argument("--scene", help="Regenerate one scene by ID")
    parser.add_argument("--force", action="store_true",
                        help="Ignore cache and regenerate everything")
    args = parser.parse_args()

    # Load frames manifest
    frames_manifest_path = MV_DIR / "frames_manifest.json"
    frames_manifest = {}
    if frames_manifest_path.exists():
        for entry in json.loads(frames_manifest_path.read_text(encoding="utf-8")):
            frames_manifest[entry["id"]] = entry
    print(f"Frames manifest: {len(frames_manifest)} entries")

    # Load URL cache
    cache = load_cache()

    # Select scenes
    if args.scene:
        scenes_to_run = [s for s in SCENES if s["id"] == args.scene]
        if not scenes_to_run:
            print(f"ERROR: scene '{args.scene}' not found"); return
    elif args.refs_only:
        scenes_to_run = [s for s in SCENES if s.get("anchor")]
    else:
        scenes_to_run = SCENES

    if args.force:
        for s in scenes_to_run:
            p = OUT_DIR / f"{s['id']}.mp4"
            if p.exists(): p.unlink()
            cache.pop(f"frame:{s['id']}", None)
        save_cache(cache)

    # Cost estimate (v3 standard: $0.084/s)
    total_s = sum(int(s["dur"]) for s in scenes_to_run)
    cost    = total_s * 0.084
    fives   = sum(1 for s in scenes_to_run if s["dur"] == "5")
    tens    = sum(1 for s in scenes_to_run if s["dur"] == "10")
    print("=" * 65)
    print("Take Me Where The Stars Go — Kling v3 standard i2v")
    print(f"Scenes : {len(scenes_to_run)}  ({fives}×5s + {tens}×10s = {total_s}s)")
    print(f"Est.   : ~${cost:.2f} USD")
    print(f"Model  : {MODEL_I2V}")
    print("=" * 65)

    results = []
    for i, scene in enumerate(scenes_to_run, 1):
        print(f"\n[{i}/{len(scenes_to_run)}] {scene['id']}")
        try:
            path = generate(scene, frames_manifest, cache)
            if path:
                results.append({**scene, "path": path})
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback; traceback.print_exc()

    # Update manifest
    manifest_path = MV_DIR / "scenes_manifest.json"
    existing = {}
    if manifest_path.exists():
        for entry in json.loads(manifest_path.read_text(encoding="utf-8")):
            existing[entry["id"]] = entry
    for r in results:
        existing[r["id"]] = r
    manifest_path.write_text(json.dumps(list(existing.values()), indent=2), encoding="utf-8")

    print(f"\nDone: {len(results)}/{len(scenes_to_run)}")
    if args.refs_only:
        print("Tarkista ankkuriklippit, sitten aja ilman --refs-only")


if __name__ == "__main__":
    main()
