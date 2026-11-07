"""OpenMontage K1+K2 — FLUX.2-klein-4B host candidate generation (Kaggle T4).

Single kernel (weights downloaded once):
  1. Prints real Flux2KleinPipeline.__call__ signature.
  2. Tries torch.bfloat16; on exception/NaN/black frame falls back to torch.float16.
  3. Logs load time, generation time, peak VRAM, selected dtype.
  4. Generates 8 host candidates (1280x720, 4 steps, guidance_scale=1.0),
     different seeds, light neutral background, narrative prompt with explicit
     cel-shading technique.
  5. Builds contact_sheet_master.jpg 2x4 with numbers (<= 2 MB).
  6. WAITING_OWNER: owner names number -> copy becomes pilot-render/ref/master.png.

Outputs: /kaggle/working/k1k2-host-candidates/
         images/candidate_01.png ... candidate_08.png
         contact_sheet_master.jpg
         results.json
"""

from __future__ import annotations

import importlib.metadata as md
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import torch
from PIL import Image, ImageDraw, ImageFont

# --- Пин версий (не менять: diffusers 0.37.0 уже содержит Flux2KleinPipeline) ---
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

OUT = Path("/kaggle/working/k1k2-host-candidates")
IMG_DIR = OUT / "images"
IMG_DIR.mkdir(parents=True, exist_ok=True)

MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
W, H = 1280, 720
STEPS = 4
GUIDANCE = 1.0
NUM_CANDIDATES = 8

TECHNIQUE = (
    "thick crisp black outer contours, controlled interior linework, "
    "large flat matte color fills, clean two-tone cel shading, "
    "restrained palette, no gradients"
)
HOST_DESC = (
    "neutral host character presenter, short neutral hair, simple neutral "
    "clothing without logos or text, light neutral background, "
    "graphic-novel ink illustration, bold flat cel-shaded style"
)

# 8 narrative prompts — different seed, same host, light neutral background
PROMPTS = [
    f"{HOST_DESC}, medium close-up, calm explanatory expression, {TECHNIQUE}, night ink and pale bone accents, soft neutral studio lighting",
    f"{HOST_DESC}, medium shot, slight smile, hands gently open, {TECHNIQUE}, deep sea teal and pale bone palette, even neutral background",
    f"{HOST_DESC}, waist-up shot, looking directly at viewer, {TECHNIQUE}, electric teal accent line, flat matte fills, neutral light grey background",
    f"{HOST_DESC}, medium close-up, thoughtful expression, {TECHNIQUE}, coral accent detail, restrained palette, no gradients, beige neutral background",
    f"{HOST_DESC}, medium shot, presenting gesture, {TECHNIQUE}, two-tone cel shading, night ink contour, pale bone face, neutral backdrop",
    f"{HOST_DESC}, close-up, friendly neutral expression, {TECHNIQUE}, sharp black outer contour, flat matte color, light neutral background",
    f"{HOST_DESC}, medium shot, calm demeanor, {TECHNIQUE}, deep sea teal and electric teal accents, large flat color fills, no gradients",
    f"{HOST_DESC}, waist-up, neutral pose, {TECHNIQUE}, coral accent ring, pale bone and night ink, restrained palette, neutral off-white background",
]

SEEDS = [1001, 2027, 777, 42, 2026, 9001, 123, 555]


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
    """Return True if frame is black (all pixels ~0) or contains NaN."""
    import numpy as np

    arr = np.asarray(image)
    if arr.dtype.kind == "f":
        if np.isnan(arr).any():
            return True
    if arr.ndim == 3:
        # Convert to grayscale luminance for black check
        gray = arr.mean(axis=2)
    else:
        gray = arr
    return float(gray.max()) < 5.0  # essentially black


def try_generate(pipe, prompt, seed, dtype_name, dtype):
    """Generate one image. Returns (image, ok, reason)."""
    generator = torch.manual_seed(seed)
    t0 = time.time()
    try:
        result = pipe(
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
            return None, False, f"black_or_nan_frame (max pixel too low), {gen_s}s"
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
        "candidates": [],
        "selected_dtype": None,
    }
    print("ENV:", json.dumps(results["environment"], ensure_ascii=False))
    print("SIGNATURE:", results["signature"])

    # --- Load model, try bf16 first, fall back to float16 ---
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

    # --- Generate candidates ---
    for idx, (prompt, seed) in enumerate(zip(PROMPTS, SEEDS), start=1):
        cand_name = f"candidate_{idx:02d}"
        print(f"Generating {cand_name} (seed={seed}, dtype={selected_dtype}) ...")

        dtype = torch.bfloat16 if selected_dtype == "bfloat16" else torch.float16
        image, ok, reason = try_generate(pipe, prompt, seed, selected_dtype, dtype)

        # Fallback to float16 if bf16 produced bad frame
        if not ok and selected_dtype == "bfloat16":
            print(f"  bf16 failed ({reason}), retrying with float16 ...")
            image, ok, reason = try_generate(pipe, prompt, seed, "float16", torch.float16)
            if ok:
                print(f"  float16 succeeded")

        if not ok:
            print(f"  {cand_name} FAILED: {reason}")
            results["candidates"].append({
                "index": idx,
                "name": cand_name,
                "seed": seed,
                "status": "failed",
                "reason": reason,
                "prompt": prompt,
            })
            continue

        out_path = IMG_DIR / f"{cand_name}.png"
        image.save(out_path)
        print(f"  {cand_name} OK -> {out_path} ({reason})")

        results["candidates"].append({
            "index": idx,
            "name": cand_name,
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

    # --- Build contact sheet 2x4 with numbers ---
    ok_images = [c for c in results["candidates"] if c["status"] == "ok"]
    if ok_images:
        sheet = build_contact_sheet(ok_images)
        sheet_path = OUT / "contact_sheet_master.jpg"
        sheet.save(sheet_path, quality=85, optimize=True)
        sheet_size = sheet_path.stat().st_size
        results["contact_sheet"] = {
            "file": str(sheet_path),
            "size_bytes": sheet_size,
            "size_mb": round(sheet_size / 1024 / 1024, 2),
            "layout": "2x4",
            "numbered": True,
        }
        print(f"Contact sheet: {sheet_path} ({sheet_size} bytes)")

    results["finished_utc"] = now()
    results["status"] = "completed"
    print("RESULT:", json.dumps(results, ensure_ascii=False)[:2000])
    (OUT / "results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False)
    )
    print(f"All outputs in {OUT}")
    print("WAITING_OWNER: name the candidate number (1-8) to copy as pilot-render/ref/master.png")


def build_contact_sheet(candidates):
    """Build a 2x4 numbered contact sheet from candidate results."""
    cols, rows = 4, 2
    cell_w, cell_h = 320, 180  # 1280x720 scaled down
    sheet_w = cols * cell_w
    sheet_h = rows * cell_h
    sheet = Image.new("RGB", (sheet_w, sheet_h), "white")
    draw = ImageDraw.Draw(sheet)

    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 24)
    except Exception:
        font = ImageFont.load_default()

    for i, c in enumerate(candidates[: cols * rows]):
        img_path = c["file"]
        img = Image.open(img_path).convert("RGB")
        img = img.resize((cell_w, cell_h))

        r = i // cols
        col = i % cols
        x0 = col * cell_w
        y0 = r * cell_h
        sheet.paste(img, (x0, y0))

        # Number badge
        label = str(i + 1)
        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        # White badge background with black text
        badge_x = x0 + cell_w - tw - 10
        badge_y = y0 + 10
        draw.rectangle([badge_x - 4, badge_y - 4, badge_x + tw + 4, badge_y + th + 4], fill="white")
        draw.text((badge_x, badge_y), label, fill="black", font=font)

    return sheet


if __name__ == "__main__":
    main()
