#!/usr/bin/env python3
"""OpenMontage K3-v3 — FLUX.2-klein-4B host identity variations (Kaggle T4).

Uses the anchor reference image (candidate #6 from v2 sheet) as the `image=`
parameter in Flux2KleinPipeline — native multi-reference Klein, NOT text-from-scratch.

Generates 4-6 variations of ONE character (the anchor):
- different poses: frontal, profile, 3/4, close-up face
- same neutral background, same hair/skin/clothes as the anchor
- 1280x720, 4 steps, guidance_scale=1.0 (CFG off, distillation mode)

Single kernel (weights downloaded once):
  1. Prints real Flux2KleinPipeline.__call__ signature (confirms `image=` param).
  2. Tries torch.bfloat16; on exception/NaN/black frame falls back to torch.float16.
  3. Logs load time, generation time, peak VRAM, selected dtype per variation.
  4. Builds contact_sheet_master_v3.jpg (up to 6 variations, numbered).
  5. WAITING_OWNER: show result; if identity still drifts, discuss SVG-rig fallback.

Outputs: /kaggle/working/k3-v3-host-variations/
         frames/v3_var_01.png ... v3_var_06.png
         contact_sheet_master_v3.jpg
         results.json
"""

from __future__ import annotations

import importlib.metadata as md
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import torch
from PIL import Image, ImageDraw, ImageFont

# --- Пин версий (diffusers 0.37.0 уже содержит Flux2KleinPipeline) ---
PINNED_VERSIONS = [
    "diffusers==0.37.0",
    "transformers==4.57.6",
    "huggingface_hub==0.36.2",
]


def _ensure_pinned_versions():
    for pkg in PINNED_VERSIONS:
        name = pkg.split("==")[0]
        try:
            if md.version(name) == pkg.split("==")[1]:
                continue
        except Exception:
            pass
        print(f"Installing {pkg} ...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", pkg],
            check=True,
        )


_ensure_pinned_versions()

import inspect  # noqa: E402
from diffusers import Flux2KleinPipeline  # noqa: E402

OUT = Path("/kaggle/working/k3-v3-host-variations")
FRAME_DIR = OUT / "frames"
FRAME_DIR.mkdir(parents=True, exist_ok=True)

MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
W, H = 1280, 720
STEPS = 4
GUIDANCE = 1.0

# Anchor reference image path (candidate #6 from v2 sheet)
ANCHOR_PATH = "/kaggle/working/master_v3_anchor.png"
ANCHOR_URL = "https://raw.githubusercontent.com/sora73636-stack/OpenMontage/kilo/mega-100/tools/kaggle_bridge/jobs/pilot-render/ref/master_v3_anchor.png"


def _ensure_anchor():
    """Download anchor reference from GitHub if not present locally."""
    if os.path.exists(ANCHOR_PATH):
        print(f"Anchor already present: {ANCHOR_PATH}")
        return
    print(f"Downloading anchor from {ANCHOR_URL} ...")
    subprocess.run(
        ["curl", "-fsSL", "-o", ANCHOR_PATH, ANCHOR_URL],
        check=True,
    )
    print(f"Anchor downloaded: {ANCHOR_PATH} ({os.path.getsize(ANCHOR_PATH)} bytes)")

TECHNIQUE = (
    "thick crisp black outer contours, controlled interior linework, "
    "large flat matte color fills with light wear texture (dirt, scratches, "
    "signs of use) on clothing fabric only, not on skin/face/background, "
    "clean two-tone cel shading, restrained palette, no gradients, "
    "chibi proportions head larger than body roughly 1:2 short limbs, "
    "large round expressive eyes with visible highlight, "
    "simple readable facial expression not dots"
)

# 5 variations — different poses, SAME anchor image as reference
VARIATIONS = [
    ("v3_var_01", "frontal pose, facing directly forward, neutral expression",
     "neutral host character, short spiky dark gray/black buzz-cut hair, light skin tone, gray t-shirt with light wear texture on fabric only, neutral light gray background without details, frontal pose facing directly forward, " + TECHNIQUE),
    ("v3_var_02", "profile pose, facing left, side view",
     "neutral host character, short spiky dark gray/black buzz-cut hair, light skin tone, gray t-shirt with light wear texture on fabric only, neutral light gray background without details, profile pose facing left side view, " + TECHNIQUE),
    ("v3_var_03", "three-quarter pose, slight turn, looking at viewer",
     "neutral host character, short spiky dark gray/black buzz-cut hair, light skin tone, gray t-shirt with light wear texture on fabric only, neutral light gray background without details, three-quarter pose slight turn looking at viewer, " + TECHNIQUE),
    ("v3_var_04", "close-up face, head and shoulders only",
     "neutral host character, short spiky dark gray/black buzz-cut hair, light skin tone, gray t-shirt with light wear texture on fabric only, neutral light gray background without details, close-up face head and shoulders only, " + TECHNIQUE),
    ("v3_var_05", "frontal pose, hands gently open presenting gesture",
     "neutral host character, short spiky dark gray/black buzz-cut hair, light skin tone, gray t-shirt with light wear texture on fabric only, neutral light gray background without details, frontal pose hands gently open presenting gesture, " + TECHNIQUE),
    ("v3_var_06", "profile pose, facing right, calm demeanor",
     "neutral host character, short spiky dark gray/black buzz-cut hair, light skin tone, gray t-shirt with light wear texture on fabric only, neutral light gray background without details, profile pose facing right calm demeanor, " + TECHNIQUE),
]

SEEDS = [1001, 2027, 777, 42, 2026, 9001]


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def reset_peak():
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()


def peak_mb():
    if torch.cuda.is_available():
        return round(torch.cuda.max_memory_allocated() / 1024 / 1024, 1)
    return 0


def env_info():
    info = {
        "torch": torch.__version__,
        "cuda_available": bool(torch.cuda.is_available()),
        "diffusers": md.version("diffusers"),
        "transformers": md.version("transformers"),
        "huggingface_hub": md.version("huggingface_hub"),
    }
    if torch.cuda.is_available():
        info["device"] = torch.cuda.get_device_name(0)
        info["total_vram_gb"] = round(
            torch.cuda.get_device_properties(0).total_memory / 1024**3, 2
        )
    return info


def is_black_or_nan(image: Image.Image) -> bool:
    import numpy as np
    arr = np.asarray(image)
    if arr.dtype.kind == "f":
        if np.isnan(arr).any():
            return True
    gray = arr.mean(axis=2) if arr.ndim == 3 else arr
    return float(gray.max()) < 5.0


def try_generate(pipe, prompt, seed, anchor_image, dtype_name, dtype):
    generator = torch.manual_seed(seed)
    t0 = time.time()
    try:
        result = pipe(
            image=anchor_image,
            prompt=prompt,
            width=W,
            height=H,
            num_inference_steps=STEPS,
            guidance_scale=GUIDANCE,
            generator=generator,
            output_type="pil",
        )
        image = result.images[0]
        gen_s = round(time.time() - t0, 2)
        if is_black_or_nan(image):
            return None, False, f"black_or_nan_frame, {gen_s}s"
        return image, True, f"ok, {gen_s}s"
    except Exception as exc:
        gen_s = round(time.time() - t0, 2)
        return None, False, f"exception: {exc}, {gen_s}s"


def main():
    results = {
        "started_utc": now(),
        "model": MODEL_ID,
        "resolution": f"{W}x{H}",
        "steps": STEPS,
        "guidance_scale": GUIDANCE,
        "environment": env_info(),
        "signature": str(inspect.signature(Flux2KleinPipeline.__call__)),
        "variations": [],
        "selected_dtype": None,
        "anchor_image": ANCHOR_PATH,
    }
    print("ENV:", json.dumps(results["environment"], ensure_ascii=False))
    print("SIGNATURE:", results["signature"])

    reset_peak()
    t_load0 = time.time()
    pipe = None
    selected_dtype = None
    load_error = None

    for dtype_name, dtype in [("bfloat16", torch.bfloat16), ("float16", torch.float16)]:
        try:
            print(f"Attempting load with {dtype_name} ...")
            pipe = Flux2KleinPipeline.from_pretrained(
                MODEL_ID,
                torch_dtype=dtype,
            )
            pipe.enable_model_cpu_offload()
            selected_dtype = dtype_name
            print(f"Model loaded with {dtype_name}")
            break
        except Exception as exc:
            load_error = str(exc)
            print(f"Load failed with {dtype_name}: {load_error}")
            pipe = None

    if pipe is None:
        results["status"] = "failed"
        results["stage"] = "load"
        results["load_error"] = load_error
        (OUT / "results.json").write_text(
            json.dumps(results, indent=2, ensure_ascii=False)
        )
        return

    load_s = round(time.time() - t_load0, 2)
    peak_after_load = peak_mb()
    results["load_seconds"] = load_s
    results["peak_vram_mb_after_load"] = peak_after_load
    results["selected_dtype"] = selected_dtype
    print(f"Loaded in {load_s}s, peak VRAM after load: {peak_after_load} MB, dtype={selected_dtype}")

    # Ensure anchor reference image is available (download from GitHub if needed)
    _ensure_anchor()

    # Load anchor reference image once
    anchor_image = Image.open(ANCHOR_PATH).convert("RGB")
    print(f"Loaded anchor reference: {ANCHOR_PATH} ({anchor_image.size})")

    # Generate variations    for var_id, pose_desc, prompt in VARIATIONS:
        seed = SEEDS[len(results["variations"])]
        print(f"Generating {var_id} ({pose_desc}, seed={seed}, dtype={selected_dtype}) ...")
        dtype = torch.bfloat16 if selected_dtype == "bfloat16" else torch.float16
        image, ok, reason = try_generate(pipe, prompt, seed, anchor_image, selected_dtype, dtype)

        if not ok and selected_dtype == "bfloat16":
            print(f"  bf16 failed ({reason}), retrying with float16 ...")
            image, ok, reason = try_generate(pipe, prompt, seed, anchor_image, "float16", torch.float16)
            if ok:
                print(f"  float16 succeeded")

        if not ok:
            print(f"  {var_id} FAILED: {reason}")
            results["variations"].append({
                "var_id": var_id,
                "pose": pose_desc,
                "seed": seed,
                "status": "failed",
                "reason": reason,
                "prompt": prompt,
            })
            continue

        out_path = FRAME_DIR / f"{var_id}.png"
        image.save(out_path)
        print(f"  {var_id} OK -> {out_path} ({reason})")

        results["variations"].append({
            "var_id": var_id,
            "pose": pose_desc,
            "seed": seed,
            "status": "ok",
            "file": str(out_path),
            "prompt": prompt,
            "note": reason,
        })

    peak_gen = peak_mb()
    results["peak_vram_mb_overall"] = max(peak_after_load, peak_gen)
    results["peak_vram_gb_overall"] = round(
        results["peak_vram_mb_overall"] / 1024, 2
    )
    results["total_vram_gb"] = env_info().get("total_vram_gb", 0)

    ok_vars = [v for v in results["variations"] if v["status"] == "ok"]
    if ok_vars:
        sheet = build_contact_sheet(ok_vars)
        sheet_path = OUT / "contact_sheet_master_v3.jpg"
        sheet.save(sheet_path, quality=85, optimize=True)
        sheet_size = sheet_path.stat().st_size
        results["contact_sheet"] = {
            "file": str(sheet_path),
            "size_bytes": sheet_size,
            "size_mb": round(sheet_size / 1024 / 1024, 2),
            "layout": "2x3",
            "numbered": True,
            "version": 3,
            "anchor_image": ANCHOR_PATH,
        }
        print(f"Contact sheet v3: {sheet_path} ({sheet_size} bytes)")

    results["finished_utc"] = now()
    ok_count = sum(1 for v in results["variations"] if v["status"] == "ok")
    results["status"] = "completed"
    results["variations_ok"] = ok_count
    results["variations_total"] = len(results["variations"])
    print(f"RESULT: {ok_count}/{len(results['variations'])} OK, "
          f"peak VRAM {results['peak_vram_gb_overall']} GB, dtype={selected_dtype}")
    print("WAITING_OWNER: show contact_sheet_master_v3.jpg; if identity still drifts, discuss SVG-rig fallback")
    (OUT / "results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False)
    )
    print(f"All outputs in {OUT}")


def build_contact_sheet(variations):
    """Build a 2x3 numbered contact sheet from variation results."""
    cols, rows = 3, 2
    cell_w, cell_h = 320, 180
    sheet_w = cols * cell_w
    sheet_h = rows * cell_h
    sheet = Image.new("RGB", (sheet_w, sheet_h), "white")
    draw = ImageDraw.Draw(sheet)

    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 24)
    except Exception:
        font = ImageFont.load_default()

    for i, v in enumerate(variations[: cols * rows]):
        img_path = v["file"]
        img = Image.open(img_path).convert("RGB")
        img = img.resize((cell_w, cell_h))

        r, col = divmod(i, cols)
        x0, y0 = col * cell_w, r * cell_h
        sheet.paste(img, (x0, y0))

        label = str(i + 1)
        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        badge_x = x0 + cell_w - tw - 10
        badge_y = y0 + 10
        draw.rectangle([badge_x - 4, badge_y - 4, badge_x + tw + 4, badge_y + th + 4], fill="white")
        draw.text((badge_x, badge_y), label, fill="black", font=font)

    return sheet


if __name__ == "__main__":
    main()
