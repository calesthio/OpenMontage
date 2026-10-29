"""Character-consistency benchmark on Kaggle Tesla T4.

Tests (native reference conditioning only — no IP-Adapter / PhotoMaker / PuLID /
InstantID / FaceID / InsightFace / ArcFace, no non-commercial models):

  Model 1: black-forest-labs/FLUX.2-klein-4B (Apache-2.0, commercial OK)
  Model 2: Qwen/Qwen-Image-Edit-2511 (Apache-2.0) — ONLY if a quantized T4-compatible
           fp16 variant is confirmed; full 57.7 GB BF16 weights are NOT downloaded.

Pipeline per model:
  1. One clean source character image (neutral pose, simple background), 512x512, fp16.
  2. Three image-edits using the source as reference (img2img):
     A. Character sits at a desk with an open book, scratching head.
     B. Same character explains a simple biological diagram, pointing at it.
     C. Same character looks surprised at a small object in hand.
  Each edit changes ONLY pose/action/surroundings; face, head shape, eye spacing,
  eyebrow asymmetry, body proportions, scarf, colors and line thickness must be kept.

Outputs: /kaggle/working/character_benchmark/
  images/         — source + 3 edits per model
  contact_sheet.png
  benchmark.csv
  report.md
"""

from __future__ import annotations

import csv
import io
import json
import os
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import torch
from PIL import Image, ImageDraw

try:
    import psutil  # system RAM
    _HAS_PSUTIL = True
except Exception:  # noqa: BLE001
    _HAS_PSUTIL = False
    import resource

from diffusers import Flux2KleinPipeline

OUT = Path("/kaggle/working/character_benchmark")
IMG_DIR = OUT / "images"
IMG_DIR.mkdir(parents=True, exist_ok=True)

MODEL_FLUX = "black-forest-labs/FLUX.2-klein-4B"
MODEL_QWEN = "Qwen/Qwen-Image-Edit-2511"

W = H = 512
STEPS = 4
GUIDANCE = 1.0
STRENGTH = 0.75
SEED_SOURCE = 42
DTYPE = torch.float16  # T4 has no bf16 hardware support


def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def peak_vram_mb():
    return round(torch.cuda.max_memory_allocated() / 1024 / 1024, 1)


def system_ram_mb():
    if _HAS_PSUTIL:
        return round(psutil.Process().memory_info().rss / 1024 / 1024, 1)
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)


def env_info():
    info = {
        "torch": torch.__version__,
        "cuda_available": bool(torch.cuda.is_available()),
        "ram_mb": system_ram_mb(),
    }
    if torch.cuda.is_available():
        info["device"] = torch.cuda.get_device_name(0)
        info["total_vram_gb"] = round(
            torch.cuda.get_device_properties(0).total_memory / 1024 ** 3, 2
        )
    return info


def reset_peak():
    torch.cuda.reset_peak_memory_stats()


def apply_memory_opts(pipe):
    for m in ("enable_vae_slicing", "enable_vae_tiling", "enable_model_cpu_offload"):
        if hasattr(pipe, m):
            getattr(pipe, m)()


def slug(s):
    return "".join(c if c.isalnum() else "_" for c in s.lower()).strip("_")


CHARACTER_PROMPT = (
    "Simple white round head character mascot, thick black drawn outline, "
    "two small black oval eyes, one slightly raised eyebrow, simple mouth, "
    "thin black arms legs and torso, small dark teal scarf with tiny coral tip accent, "
    "friendly expressive slightly comical expression, clean 2D ink sticker art, "
    "flat fill, minimal gray shadow, warm white background"
)
NEGATIVE = (
    "photorealistic, 3d, realistic, blurry, low quality, watermark, "
    "text, letters, numbers, gradient, gray shadow, extra characters, logo, "
    "detailed shading, realistic skin"
)

EDIT_PROMPTS = {
    "A_scratch_head": (
        "same character sitting at a desk with an open book, scratching head with one hand, "
        "thick black outline, dark teal scarf with coral tip, clean 2D ink sticker art, "
        "flat fill, warm white background"
    ),
    "B_explain_diagram": (
        "same character explaining a simple biological diagram, pointing at it with one hand, "
        "thick black outline, dark teal scarf with coral tip, clean 2D ink sticker art, "
        "flat fill, warm white background"
    ),
    "C_surprised_object": (
        "same character looking surprised at a small object held in hand, "
        "thick black outline, dark teal scarf with coral tip, clean 2D ink sticker art, "
        "flat fill, warm white background"
    ),
}


def save_image(image, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def generate_text_to_image(pipe, prompt, seed, out_path):
    reset_peak()
    t0 = time.time()
    image = pipe(
        prompt=prompt,
        height=H,
        width=W,
        num_inference_steps=STEPS,
        guidance_scale=GUIDANCE,
        generator=torch.Generator("cuda").manual_seed(seed),
    ).images[0]
    secs = round(time.time() - t0, 3)
    save_image(image, out_path)
    return image, secs, peak_vram_mb()


def generate_image_to_image(pipe, prompt, source_image, seed, out_path):
    reset_peak()
    t0 = time.time()
    image = pipe(
        prompt=prompt,
        image=source_image,
        height=H,
        width=W,
        num_inference_steps=STEPS,
        guidance_scale=GUIDANCE,
        generator=torch.Generator("cuda").manual_seed(seed),
    ).images[0]
    secs = round(time.time() - t0, 3)
    save_image(image, out_path)
    return image, secs, peak_vram_mb()


def unload(pipe):
    try:
        del pipe
    except Exception:
        pass
    torch.cuda.empty_cache()


def build_contact_sheet(image_paths, out_path):
    """Grid of images with labels for visual comparison."""
    imgs = [Image.open(p).convert("RGB") for p in image_paths]
    cols = 2
    rows = (len(imgs) + cols - 1) // cols
    cell = 520
    sheet = Image.new("RGB", (cols * cell, rows * cell), "white")
    draw = ImageDraw.Draw(sheet)
    for i, im in enumerate(imgs):
        r, c = divmod(i, cols)
        box = (c * cell, r * cell, (c + 1) * cell, (r + 1) * cell)
        thumb = im.copy()
        thumb.thumbnail((cell - 40, cell - 80))
        tw, th = thumb.size
        sheet.paste(thumb, (box[0] + (cell - tw) // 2, box[1] + 20))
        label = Path(image_paths[i]).stem.replace("_", " ")
        draw.text((box[0] + 10, box[1] + cell - 22), label, fill="black")
    sheet.save(out_path)
    return out_path


def run_model(model_id, is_edit_pipeline):
    """Run full benchmark for one model. Returns a results dict."""
    result = {
        "model_id": model_id,
        "status": "started",
        "download_seconds": None,
        "load_seconds": None,
        "peak_vram_after_load_mb": None,
        "source": None,
        "edits": {},
        "error": None,
        "oom": None,
    }
    try:
        t_dl0 = time.time()
        pipe = Flux2KleinPipeline.from_pretrained(
            model_id, torch_dtype=DTYPE, use_safetensors=True
        )
        t_dl1 = time.time()
        result["download_seconds"] = round(t_dl1 - t_dl0, 3)

        apply_memory_opts(pipe)
        result["load_seconds"] = round(time.time() - t_dl1, 3)
        result["peak_vram_after_load_mb"] = peak_vram_mb()

        # 1. source character image
        src_path = IMG_DIR / f"{slug(model_id)}_source.png"
        image, gen_secs, gen_peak = generate_text_to_image(
            pipe, CHARACTER_PROMPT, SEED_SOURCE, src_path
        )
        result["source"] = {
            "file": src_path.name,
            "seconds": gen_secs,
            "peak_vram_mb": gen_peak,
            "resolution": f"{W}x{H}",
            "steps": STEPS,
            "guidance_scale": GUIDANCE,
            "seed": SEED_SOURCE,
            "status": "ok",
        }

        # 2. three edits using source as reference
        for key, prompt in EDIT_PROMPTS.items():
            out_path = IMG_DIR / f"{slug(model_id)}_{key}.png"
            try:
                edit_image, e_secs, e_peak = generate_image_to_image(
                    pipe, prompt, image, SEED_SOURCE + 1, out_path
                )
                result["edits"][key] = {
                    "file": out_path.name,
                    "seconds": e_secs,
                    "peak_vram_mb": e_peak,
                    "strength": STRENGTH,
                    "seed": SEED_SOURCE + 1,
                    "status": "ok",
                }
            except torch.cuda.OutOfMemoryError as exc:
                torch.cuda.empty_cache()
                result["edits"][key] = {
                    "file": out_path.name,
                    "status": "OOM",
                    "error": str(exc)[:200],
                }
                result["oom"] = key
                break
            except Exception as exc:  # noqa: BLE001
                result["edits"][key] = {
                    "file": out_path.name,
                    "status": "error",
                    "error": str(exc)[:200],
                }

        result["status"] = "completed"
        unload(pipe)
    except torch.cuda.OutOfMemoryError as exc:
        torch.cuda.empty_cache()
        result["status"] = "OOM"
        result["oom"] = "load_or_generate"
        result["error"] = str(exc)[:300]
    except Exception as exc:  # noqa: BLE001
        result["status"] = "failed"
        result["error"] = str(exc)[:300]
        traceback.print_exc()
        try:
            unload(pipe)
        except Exception:
            pass
    return result


def main():
    (OUT / "images").mkdir(parents=True, exist_ok=True)
    report = {
        "started_utc": now_utc(),
        "finished_utc": None,
        "environment": env_info(),
        "protocol_notes": (
            "T4 has no bf16 hardware support; fp16 used throughout even though model "
            "cards show bf16. No IP-Adapter / PhotoMaker / PuLID / InstantID / FaceID / "
            "InsightFace / ArcFace. No non-commercial models. Full Qwen 57.7 GB weights "
            "not downloaded."
        ),
        "models": [],
    }
    print("ENV:", json.dumps(report["environment"], ensure_ascii=False))

    results = []
    for model_id in (MODEL_FLUX,):
        print(f"=== MODEL {model_id} ===")
        res = run_model(model_id, is_edit_pipeline=True)
        results.append(res)
        print(
            f"  status={res['status']} load_s={res['load_seconds']} "
            f"peak_load_vram={res['peak_vram_after_load_mb']} MB "
            f"source_ok={res['source'] is not None and res['source'].get('status')=='ok'} "
            f"oom={res.get('oom')} err={res.get('error')}"
        )

    # Qwen-Image-Edit-2511: blocked on T4 (bf16-only card, no bf16 on T4,
    # full weights ~57.7 GB exceed 14.56 GB VRAM). Record as not tested.
    qwen_blocked = {
        "model_id": MODEL_QWEN,
        "status": "not_tested",
        "error": (
            "T4 has no bf16 hardware support; model card requires torch.bfloat16. "
            "Full BF16 weights (~57.7 GB) exceed T4 14.56 GB VRAM. No confirmed "
            "quantized fp16 variant compatible with a single T4. Not downloaded."
        ),
        "download_seconds": None,
        "load_seconds": None,
        "peak_vram_after_load_mb": None,
        "source": None,
        "edits": {},
        "oom": None,
    }
    results.append(qwen_blocked)
    print("=== MODEL Qwen-Image-Edit-2511: NOT_TESTED (bf16/T4 incompatibility) ===")

    # Build CSV
    csv_path = OUT / "benchmark.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "model_id", "stage", "file", "status", "seconds",
                "peak_vram_mb", "resolution", "steps", "guidance_scale",
                "strength", "seed", "error",
            ]
        )
        for res in results:
            mid = res["model_id"]
            if res.get("source"):
                s = res["source"]
                w.writerow(
                    [mid, "source", s["file"], s["status"], s["seconds"],
                     s["peak_vram_mb"], s["resolution"], s["steps"],
                     s["guidance_scale"], "", s["seed"], s.get("error", "")]
                )
            for key, e in res.get("edits", {}).items():
                w.writerow(
                    [mid, key, e.get("file", ""), e["status"], e.get("seconds"),
                     e.get("peak_vram_mb"), f"{W}x{H}", STEPS, GUIDANCE,
                     e.get("strength", ""), e.get("seed", ""), e.get("error", "")]
                )
            if res.get("error") and not res.get("source"):
                w.writerow([mid, "load", "", res["status"], None, None, "", "", "", "", "", res["error"]])

    report["models"] = results
    report["finished_utc"] = now_utc()
    sheet_path = OUT / "contact_sheet.png"
    try:
        all_images = sorted(IMG_DIR.glob("*.png"))
        if all_images:
            build_contact_sheet(all_images, sheet_path)
    except Exception as exc:  # noqa: BLE001 - contact sheet must not lose the report
        print(f"contact_sheet failed: {exc}")
        sheet_path = None
    report["artifacts"] = {
        "images_dir": str(IMG_DIR),
        "contact_sheet": str(sheet_path) if sheet_path else None,
        "benchmark_csv": str(csv_path),
    }
    (OUT / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print("REPORT:", json.dumps(report, ensure_ascii=False)[:800])
    print(f"All artifacts in {OUT}")


if __name__ == "__main__":
    main()
