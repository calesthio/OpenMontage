"""
Missing You × Seedance 2.0 — Character Reference Generator

Generates 4 portrait reference images (FLUX Pro) for use as @Image1..4
in Seedance 2.0 reference-to-video prompts.

Characters:
  sofia_2000  — Sofia age 22, 2000s casual, warm and alive
  sofia_2025  — Sofia age 47, same woman, 25 years later
  marcus_2000 — Marcus age 26, charismatic, early 2000s
  marcus_2025 — Marcus age 51, same man, weathered and contemplative

Run:
  python mv_generate_chars.py
  -> review output/missing_you_seedance/chars/
  -> retry one: python mv_generate_chars.py --char marcus_2000
"""

import os, json, requests, argparse, subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(r"C:\Users\ari_v\Claude apps\Openmontage\.env")
os.environ["FAL_KEY"] = os.environ.get("FAL_KEY", "")
import fal_client

FFMPEG_DIR = r"C:\Users\ari_v\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin"
FFMPEG = os.path.join(FFMPEG_DIR, "ffmpeg.exe")

OUT_DIR = Path(r"C:\Users\ari_v\Claude apps\Openmontage\output\missing_you_seedance\chars")
OUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL_IMG = "fal-ai/flux-pro/v1.1"

# Film grade — same as Take Me Where The Stars Go frames
FILM_GRADE = "curves=preset=vintage,eq=saturation=0.85:contrast=0.92,noise=alls=4"

NEG = (
    "cartoon, anime, illustration, painting, blurry, low quality, "
    "watermark, text overlay, extra limbs, deformed face, ugly, cgi, "
    "grey backdrop, white background, studio lighting, fake look"
)

CHARS = {
    "sofia_2000": {
        "file": "sofia_2000.png",
        "prompt": (
            "Portrait of a 22-year-old woman named Sofia. Wavy dark brown hair to her shoulders, "
            "bright warm brown eyes, natural light makeup, genuine warm smile. "
            "Wearing a light blue denim jacket over a white t-shirt, small silver earrings. "
            "Early 2000s casual style. She is beautiful, alive, and full of joy. "
            "Soft indoor café light, slightly warm tone. "
            "Half-body portrait, looking slightly toward camera. "
            "Photorealistic, cinematic 16:9 film still, natural skin texture."
        ),
    },
    "sofia_2025": {
        "file": "sofia_2025.png",
        "prompt": (
            "Portrait of a 47-year-old woman named Sofia. The same woman as in her twenties — "
            "same face structure, same warm brown eyes — but 25 years have passed. "
            "Dark hair with natural silver streaks at the temples, worn loose. "
            "Subtle lines at the eyes and mouth, still beautiful but life-worn and melancholic. "
            "Wearing a dark charcoal wool coat, no jewelry. "
            "Cold blue-grey interior light from a rain-streaked window. "
            "Half-body portrait, expression quiet and inward. "
            "Photorealistic, cinematic 16:9 film still, natural skin texture."
        ),
    },
    "marcus_2000": {
        "file": "marcus_2000.png",
        "prompt": (
            "Portrait of a 26-year-old man named Marcus. Dark curly hair, warm hazel eyes, "
            "light stubble, charismatic and open smile. "
            "Wearing an open-collar linen button shirt in pale blue, early 2000s casual style. "
            "Slightly tanned, healthy, full of warmth and confidence. "
            "Soft warm café light. Half-body portrait, relaxed posture, looking slightly off-camera. "
            "Photorealistic, cinematic 16:9 film still, natural skin texture."
        ),
    },
    "marcus_2025": {
        "file": "marcus_2025.png",
        "prompt": (
            "Portrait of a 51-year-old man named Marcus. The same man as in his twenties — "
            "same face structure, same hazel eyes — but 25 years have passed. "
            "Salt-and-pepper hair, neatly kept. Light stubble, now greying. "
            "Deeper lines around the eyes, handsome but weathered, contemplative expression. "
            "Wearing a dark grey wool jacket, open collar. "
            "Cold blue-grey window light, rainy atmosphere. "
            "Half-body portrait, looking toward the distance. "
            "Photorealistic, cinematic 16:9 film still, natural skin texture."
        ),
    },
}


def generate_char(char_id, char_data):
    out = OUT_DIR / char_data["file"]
    if out.exists() and out.stat().st_size > 100_000:
        print(f"  [cached] {out.name}")
        return str(out)

    print(f"  Generating {char_id}...")
    result = fal_client.subscribe(MODEL_IMG, arguments={
        "prompt": char_data["prompt"],
        "negative_prompt": NEG,
        "image_size": "landscape_16_9",
        "num_inference_steps": 28,
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
    print(f"  Saved {out.name} ({kb:.0f} KB) — applying film grade...")

    # Apply film grade in-place
    tmp = out.with_suffix(".tmp.png")
    out.rename(tmp)
    r2 = subprocess.run(
        [FFMPEG, "-y", "-i", str(tmp), "-vf", FILM_GRADE, "-q:v", "1", str(out)],
        capture_output=True, timeout=30
    )
    tmp.unlink(missing_ok=True)
    if r2.returncode == 0:
        print(f"  Graded  {out.name} ({out.stat().st_size // 1024} KB)")
    else:
        print(f"  [grade warn] {r2.stderr.decode(errors='replace')[-150:]}")

    return str(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--char", help="Generate only one character by ID")
    parser.add_argument("--force", action="store_true", help="Re-generate even if cached")
    args = parser.parse_args()

    chars_to_run = CHARS
    if args.char:
        if args.char not in CHARS:
            print(f"ERROR: '{args.char}' not found. Options: {list(CHARS.keys())}")
            return
        chars_to_run = {args.char: CHARS[args.char]}

    if args.force:
        for cid, cdata in chars_to_run.items():
            p = OUT_DIR / cdata["file"]
            if p.exists():
                p.unlink()

    cost = len(chars_to_run) * 0.05
    print("=" * 60)
    print("Missing You × Seedance 2.0 — Character Reference Generator")
    print(f"Model  : {MODEL_IMG}")
    print(f"Chars  : {len(chars_to_run)} | Est. ~${cost:.2f} USD")
    print(f"Output : {OUT_DIR}")
    print("=" * 60)

    results = {}
    for char_id, char_data in chars_to_run.items():
        print(f"\n{char_id}")
        try:
            path = generate_char(char_id, char_data)
            results[char_id] = path
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback; traceback.print_exc()

    # Save manifest
    manifest = OUT_DIR / "chars_manifest.json"
    existing = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
    existing.update(results)
    manifest.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    print(f"\nDone: {len(results)}/{len(chars_to_run)} characters")
    print(f"Review: {OUT_DIR}")
    print("\nNext: python mv_generate_scenes.py --refs-only")


if __name__ == "__main__":
    main()
