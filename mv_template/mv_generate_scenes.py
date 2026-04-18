"""
OpenMontage – Music Video Scene Generator (Template)
=====================================================
WORKFLOW:
  1. Fill in PROJECT, CHARS, STYLES, SCENES below
  2. Drop character reference images into refs/ folder
  3. Run:  python mv_generate_scenes.py --refs-only
           → generates one anchor scene per character for approval
  4. Approve looks, then run:
           python mv_generate_scenes.py
           → generates all remaining scenes (cached ones skipped)

CHARACTER SYSTEM:
  - Each scene can specify a 'char' key pointing to a CHARS entry
  - If that character's ref image exists → image-to-video (consistent look)
  - If no ref image → text-to-video (fallback)
  - Ref images are uploaded to FAL once and the URL is cached in refs/urls.json
"""

import os, json, time, argparse, requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(r"C:\Users\ari_v\Claude apps\Openmontage\.env")
os.environ["FAL_KEY"] = os.environ.get("FAL_KEY", "")

import fal_client

# ── PROJECT SETTINGS ──────────────────────────────────────────────────────────
PROJECT   = "my_project"          # used for output folder name
ARTIST    = "artist_name"         # used in final filename
SONG      = "song_title"

OUT_DIR   = Path(r"C:\Users\ari_v\Claude apps\Openmontage\output") / f"{PROJECT}_mv" / "scenes"
REFS_DIR  = Path(__file__).parent / "refs"
MODEL_T2V = "fal-ai/kling-video/v1.6/standard/text-to-video"
MODEL_I2V = "fal-ai/kling-video/v1.6/standard/image-to-video"

OUT_DIR.mkdir(parents=True, exist_ok=True)
REFS_DIR.mkdir(parents=True, exist_ok=True)

# ── CHARACTER DEFINITIONS ─────────────────────────────────────────────────────
# 'ref': filename inside refs/ folder (jpg/png). Leave None until image provided.
# 'desc': text description used in prompts AND as fallback if no ref image yet.
CHARS = {
    "protagonist_young": {
        "ref": None,              # e.g. "sofia_2000.jpg" once provided
        "desc": (
            "a 22-year-old woman with dark brown hair, bright warm eyes, "
            "natural smile, casual early 2000s style"
        ),
    },
    "protagonist_old": {
        "ref": None,              # e.g. "sofia_2025.jpg" once provided
        "desc": (
            "a 47-year-old woman with dark hair streaked with grey and silver, "
            "life-worn melancholic expression, dark wool coat"
        ),
    },
    "love_interest_young": {
        "ref": None,
        "desc": (
            "a 26-year-old man with dark curly hair, warm charismatic smile, "
            "slightly stubbled, open-collar button shirt, early 2000s style"
        ),
    },
    "love_interest_old": {
        "ref": None,
        "desc": (
            "a 51-year-old man with salt-and-pepper hair, handsome but weathered, "
            "contemplative expression, dark grey jacket"
        ),
    },
}

# ── VISUAL STYLES ─────────────────────────────────────────────────────────────
STYLES = {
    "era_a": (
        "warm golden tones, slight film grain, early 2000s MiniDV aesthetic, "
        "soft nostalgic lighting, intimate framing, 16:9 cinematic"
    ),
    "era_b": (
        "cool blue-grey cinematic tones, overcast light, modern, "
        "melancholic atmosphere, rain or autumn, 16:9 widescreen"
    ),
}

# ── NEGATIVE PROMPT ───────────────────────────────────────────────────────────
NEG = (
    "blurry, cartoon, anime, painting, extra limbs, distorted face, "
    "ugly, watermark, text, bad quality, unrealistic, cgi look"
)

# ── SCENE DEFINITIONS ─────────────────────────────────────────────────────────
# Fields:
#   id      – unique filename (no .mp4)
#   dur     – "5" or "10" seconds
#   style   – key into STYLES dict
#   char    – key into CHARS dict (the primary character for this scene)
#             If ref image exists for this char → image-to-video is used
#             If multiple chars, put the most important one here
#   anchor  – True = this is the first/defining scene for this character.
#             These are generated first in --refs-only mode.
#   prompt  – full scene description. Use {char} as placeholder for the
#             character description (auto-filled from CHARS[char]['desc'])
#   label   – human-readable label for logging

SCENES = [

    # ── ANCHOR SCENES (one per character – generated first for approval) ───────
    {
        "id":     "anchor_protagonist_young",
        "dur":    "5",
        "style":  "era_a",
        "char":   "protagonist_young",
        "anchor": True,
        "label":  "Anchor – protagonist young, face reveal",
        "prompt": (
            "Close-up of {char} sitting in a warm café, looking out the window "
            "with a gentle smile. Soft golden light. Still, simple, character-defining shot. "
            "{style}"
        ),
    },
    {
        "id":     "anchor_protagonist_old",
        "dur":    "5",
        "style":  "era_b",
        "char":   "protagonist_old",
        "anchor": True,
        "label":  "Anchor – protagonist older, face reveal",
        "prompt": (
            "Close-up of {char} standing by a rain-streaked window at night, "
            "looking out with a quiet melancholic expression. Still, simple, character-defining shot. "
            "{style}"
        ),
    },
    {
        "id":     "anchor_love_interest_young",
        "dur":    "5",
        "style":  "era_a",
        "char":   "love_interest_young",
        "anchor": True,
        "label":  "Anchor – love interest young, face reveal",
        "prompt": (
            "Close-up of {char} laughing naturally, eyes full of warmth, "
            "in a warm indoor setting. Still, simple, character-defining shot. "
            "{style}"
        ),
    },
    {
        "id":     "anchor_love_interest_old",
        "dur":    "5",
        "style":  "era_b",
        "char":   "love_interest_old",
        "anchor": True,
        "label":  "Anchor – love interest older, face reveal",
        "prompt": (
            "Close-up of {char} sitting alone at night, looking at something "
            "off-camera with a distant, contemplative expression. "
            "Still, simple, character-defining shot. "
            "{style}"
        ),
    },

    # ── ACTUAL SCENES (add your scenes below) ─────────────────────────────────
    # Example:
    # {
    #     "id":     "cafe_era_a_wide",
    #     "dur":    "10",
    #     "style":  "era_a",
    #     "char":   "protagonist_young",
    #     "anchor": False,
    #     "label":  "Café – wide shot, two people at table",
    #     "prompt": (
    #         "Wide shot of {char} and her companion sitting across from each other "
    #         "at a small café table by a rain-streaked window. "
    #         "Warm café interior, coffee cups on table. "
    #         "{style}, slow subtle camera push-in"
    #     ),
    # },
]


# ── REF IMAGE UPLOAD CACHE ────────────────────────────────────────────────────

def load_url_cache() -> dict:
    cache_file = REFS_DIR / "urls.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    return {}

def save_url_cache(cache: dict):
    (REFS_DIR / "urls.json").write_text(json.dumps(cache, indent=2), encoding="utf-8")

def get_ref_url(char_id: str) -> str | None:
    """Upload ref image for a character if not already uploaded. Returns FAL URL or None."""
    char = CHARS.get(char_id, {})
    ref_filename = char.get("ref")
    if not ref_filename:
        return None
    ref_path = REFS_DIR / ref_filename
    if not ref_path.exists():
        print(f"  [warning] Ref image not found: {ref_path}")
        return None

    cache = load_url_cache()
    cache_key = f"{char_id}:{ref_filename}"
    if cache_key in cache:
        return cache[cache_key]

    print(f"  Uploading ref image for '{char_id}': {ref_filename}")
    url = fal_client.upload_file(str(ref_path))
    cache[cache_key] = url
    save_url_cache(cache)
    print(f"  Uploaded: {url}")
    return url


# ── PROMPT BUILDER ────────────────────────────────────────────────────────────

def build_prompt(scene: dict) -> str:
    char_id   = scene.get("char", "")
    char_desc = CHARS.get(char_id, {}).get("desc", "")
    style     = STYLES.get(scene.get("style", ""), "")
    return scene["prompt"].replace("{char}", char_desc).replace("{style}", style)


# ── GENERATOR ─────────────────────────────────────────────────────────────────

def generate(scene: dict, force: bool = False) -> str:
    out = OUT_DIR / f"{scene['id']}.mp4"

    if not force and out.exists() and out.stat().st_size > 200_000:
        print(f"  [cached] {scene['id']}")
        return str(out)

    prompt    = build_prompt(scene)
    char_id   = scene.get("char", "")
    ref_url   = get_ref_url(char_id)
    use_i2v   = ref_url is not None

    if use_i2v:
        print(f"  Generating i2v ({scene['dur']}s) [{char_id} ref]: {scene['label']}")
        result = fal_client.subscribe(
            MODEL_I2V,
            arguments={
                "image_url":        ref_url,
                "prompt":           prompt,
                "negative_prompt":  NEG,
                "duration":         scene["dur"],
                "aspect_ratio":     "16:9",
                "cfg_scale":        0.5,
            },
            with_logs=False,
        )
    else:
        print(f"  Generating t2v ({scene['dur']}s) [no ref]: {scene['label']}")
        result = fal_client.subscribe(
            MODEL_T2V,
            arguments={
                "prompt":           prompt,
                "negative_prompt":  NEG,
                "duration":         scene["dur"],
                "aspect_ratio":     "16:9",
                "cfg_scale":        0.5,
            },
            with_logs=False,
        )

    url = result["video"]["url"]
    r   = requests.get(url, stream=True, timeout=120)
    r.raise_for_status()
    with open(out, "wb") as f:
        for chunk in r.iter_content(1 << 16):
            if chunk: f.write(chunk)

    mb = out.stat().st_size / 1024 / 1024
    print(f"  Saved {out.name} ({mb:.1f} MB)")
    return str(out)


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OpenMontage scene generator")
    parser.add_argument(
        "--refs-only", action="store_true",
        help="Generate only anchor scenes (one per character) for approval"
    )
    args = parser.parse_args()

    scenes_to_run = (
        [s for s in SCENES if s.get("anchor")]
        if args.refs_only else SCENES
    )

    fives = sum(1 for s in scenes_to_run if s["dur"] == "5")
    tens  = sum(1 for s in scenes_to_run if s["dur"] == "10")
    cost  = fives * 0.45 + tens * 0.90

    print("=" * 65)
    print(f"OpenMontage – {ARTIST} / {SONG}")
    mode = "ANCHOR SCENES ONLY" if args.refs_only else "ALL SCENES"
    print(f"Mode: {mode} | {len(scenes_to_run)} scenes | Est. ~${cost:.2f} USD")
    # Show ref status
    for cid, cdata in CHARS.items():
        ref = cdata.get("ref")
        has = (REFS_DIR / ref).exists() if ref else False
        status = f"✓ {ref}" if has else ("(filename set, file missing)" if ref else "— no ref yet")
        print(f"  {cid}: {status}")
    print("=" * 65)

    if args.refs_only:
        print("\nGenerating anchor scenes for character approval.")
        print("After reviewing, drop ref images into refs/ and update CHARS['ref'] fields.\n")

    results = []
    for i, scene in enumerate(scenes_to_run, 1):
        print(f"\n[{i}/{len(scenes_to_run)}]")
        try:
            path = generate(scene)
            results.append({**scene, "path": path})
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback; traceback.print_exc()

    manifest = OUT_DIR.parent / "scenes_manifest.json"
    # Merge with existing manifest if present
    existing = {}
    if manifest.exists():
        for entry in json.loads(manifest.read_text(encoding="utf-8")):
            existing[entry["id"]] = entry
    for r in results:
        existing[r["id"]] = r
    manifest.write_text(json.dumps(list(existing.values()), indent=2), encoding="utf-8")

    print(f"\nManifest: {manifest}")
    print(f"Done: {len(results)}/{len(scenes_to_run)} scenes")

    if args.refs_only:
        print("\n── NEXT STEPS ──────────────────────────────────────────────")
        print("1. Review anchor clips in:", OUT_DIR)
        print("2. Drop approved character images into:", REFS_DIR)
        print("3. Set 'ref' filenames in CHARS dict above")
        print("4. Run: python mv_generate_scenes.py  (all scenes)")


if __name__ == "__main__":
    main()
