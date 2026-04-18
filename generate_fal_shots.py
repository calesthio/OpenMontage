"""
FAL video generation: 5 shots of the same woman character
for Chef-8080 – Missing You music video teasers.

Character: ~35-year-old woman, dark brown wet hair, pale skin,
dark coat, rain-soaked urban street at night, cool blue/neon aesthetic.
All shots generated in 9:16 portrait for 720p social media.
"""

import os, json, time, requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(r"C:\Users\ari_v\Claude apps\Openmontage\.env")
os.environ["FAL_KEY"] = os.environ.get("FAL_KEY", "")

import fal_client

OUT_DIR = Path(r"C:\Users\ari_v\Claude apps\Openmontage\output\chef8080_missing_you\fal_shots")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Character anchor — repeated in every prompt for consistency
CHAR = (
    "a 35-year-old woman, dark brown slightly wavy wet hair, pale skin, "
    "natural makeup, wearing a dark navy wool coat"
)

SETTING = (
    "rain-soaked urban street at night, neon signs reflecting blue and amber "
    "on wet pavement, rain falling, bokeh city lights in background, "
    "cinematic blue-toned lighting"
)

NEG = (
    "blurry, cartoon, anime, painting, illustration, extra limbs, "
    "distorted face, ugly, low quality, watermark, text overlay, "
    "bright daylight, sunny, indoor, studio"
)

SHOTS = [
    {
        "id": "shot_01_closeup_singing",
        "label": "ECU – Face singing, eyes closed",
        "prompt": (
            f"Extreme close-up cinematic portrait of {CHAR}, "
            "eyes gently closed, lips parted in silent song, "
            "rain droplets catching neon light on her cheeks and wet hair, "
            f"{SETTING}, 9:16 vertical portrait, shallow depth of field, "
            "photorealistic, 4K, music video cinematography, "
            "emotional raw performance, slow motion rain"
        ),
    },
    {
        "id": "shot_02_direct_gaze",
        "label": "MCU – Direct emotional gaze to camera",
        "prompt": (
            f"Medium close-up of {CHAR} standing on a "
            "rain-soaked city street at night, looking directly into the camera "
            "with a raw, aching emotional expression, mouth slightly open as if "
            "about to sing, rain falling lightly around her, neon blue and amber "
            f"light on her face, {SETTING}, 9:16 portrait, "
            "photorealistic, cinematic music video shot, slow camera push-in"
        ),
    },
    {
        "id": "shot_03_head_back_rain",
        "label": "MS – Head tilted back, rain on face",
        "prompt": (
            f"Medium shot of {CHAR}, standing in the rain "
            "on an empty city street at night, head tilted slightly back, "
            "rain falling on her upturned face, singing with eyes closed, "
            "arms loosely at her sides, dark coat glistening with rain, "
            f"{SETTING}, 9:16 vertical, photorealistic, "
            "cinematic slow motion, emotional music video performance"
        ),
    },
    {
        "id": "shot_04_silhouette_neon",
        "label": "Wide – Silhouette against neon glow",
        "prompt": (
            f"Wide cinematic shot of {CHAR} "
            "from a low angle on a wet city street at night, "
            "her silhouette dramatic against glowing neon signs and blurred "
            "city lights, rain streaks visible in the neon glow, "
            "reflections shimmering in puddles at her feet, "
            "she stands still, head slightly bowed, "
            f"{SETTING}, 9:16 portrait, photorealistic, "
            "cinematic composition, music video aesthetic"
        ),
    },
    {
        "id": "shot_05_walking_turning",
        "label": "MS – Walking, turns to look back",
        "prompt": (
            f"Medium shot following {CHAR} "
            "as she walks slowly away on a rain-soaked urban street at night, "
            "she pauses and turns to look over her shoulder with a melancholic "
            "expression, neon reflections glimmering on the wet pavement, "
            "rain falling softly around her, "
            f"{SETTING}, 9:16 vertical, photorealistic, "
            "slow cinematic movement, music video mood"
        ),
    },
]

MODEL = "fal-ai/kling-video/v1.6/standard/text-to-video"

def generate_shot(shot):
    out_path = OUT_DIR / f"{shot['id']}.mp4"
    if out_path.exists() and out_path.stat().st_size > 500_000:
        print(f"  [cached] {shot['id']}")
        return str(out_path)

    print(f"\n  Generating: {shot['label']}")
    print(f"  Model: {MODEL}")

    result = fal_client.subscribe(
        MODEL,
        arguments={
            "prompt": shot["prompt"],
            "negative_prompt": NEG,
            "duration": "5",
            "aspect_ratio": "9:16",
            "cfg_scale": 0.5,
        },
        with_logs=False,
    )

    video_url = result["video"]["url"]
    print(f"  URL: {video_url[:60]}...")

    r = requests.get(video_url, stream=True, timeout=120)
    r.raise_for_status()
    with open(out_path, "wb") as f:
        for chunk in r.iter_content(1 << 16):
            if chunk:
                f.write(chunk)

    size_mb = out_path.stat().st_size / 1024 / 1024
    print(f"  Saved: {out_path.name} ({size_mb:.1f} MB)")
    return str(out_path)


if __name__ == "__main__":
    print("=" * 60)
    print("FAL Video Generation – Chef-8080 Woman Character Shots")
    print("=" * 60)
    print(f"Model: {MODEL}")
    print(f"Shots: {len(SHOTS)}")
    print(f"Estimated cost: ~{len(SHOTS) * 0.45:.2f}–{len(SHOTS) * 0.60:.2f} USD")
    print()

    results = []
    for i, shot in enumerate(SHOTS, 1):
        print(f"[{i}/{len(SHOTS)}] {shot['id']}")
        try:
            path = generate_shot(shot)
            results.append({"id": shot["id"], "label": shot["label"], "path": path})
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback; traceback.print_exc()

    manifest = OUT_DIR / "shots_manifest.json"
    manifest.write_text(json.dumps(results, indent=2))

    print("\n" + "=" * 60)
    print(f"Done: {len(results)}/{len(SHOTS)} shots generated")
    for r in results:
        print(f"  {r['id']}: {r['path']}")
    print("=" * 60)
