"""OpenMontage pilot render kernel — 10 section images (SDXL Base 1.0).

Generates ONE image per pilot section (§1–§10) using the FINAL character
consistency method from docs/openmontage/image_gen/EPISODE_IMAGE_PIPELINE.md:

  Model: SDXL Base 1.0 (stabilityai/stable-diffusion-xl-base-1.0), fp16,
         vae_slicing + vae_tiling + model_cpu_offload, 768×768, 25 steps,
         CFG 7.5, fixed seed 42.
  Consistency: fixed text-prompt per frame — NO IP-Adapter (tested, 0 usable
               frames on h94/IP-Adapter + diffusers 0.37.0, embedding dim
               mismatch 1664 vs 1280).
  Style prefix (injected verbatim, from script.md image recipe):
    "bold graphic-novel ink illustration, thick outer contour, sparse hatching,
     large flat shadow masses, limited halftone, night ink, deep sea,
     electric teal, pale bone, one coral accent"
  Style tail (injected verbatim):
    "stylized, non-photorealistic, empty low-detail lower fifth for captions,
     no text"
  Negative prompt:
    "photorealistic, photo, glossy 3D render, mirror reflections, text, letters,
     watermark, signature, logo, extra limbs, fused anatomy, duplicated creature,
     cluttered bottom edge"

Section prompts are taken from docs/openmontage/pilot/script.md (first beat of
each section), with the fixed style prefix/tail applied.

Outputs: /kaggle/working/pilot-render/images/section_01.png ... section_10.png
         /kaggle/working/pilot-render/results.json
"""

from __future__ import annotations

import importlib.metadata as md
import json
import subprocess
import sys
import time
from pathlib import Path

import torch
from diffusers import StableDiffusionXLPipeline

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

MODEL_ID = "stabilityai/stable-diffusion-xl-base-1.0"
OUT = Path("/kaggle/working/pilot-render")
IMG_DIR = OUT / "images"
IMG_DIR.mkdir(parents=True, exist_ok=True)

W = H = 768
STEPS = 25
GUIDANCE = 7.5
SEED = 42

STYLE_PREFIX = (
    "bold graphic-novel ink illustration, thick outer contour, sparse hatching, "
    "large flat shadow masses, limited halftone, night ink, deep sea, "
    "electric teal, pale bone, one coral accent"
)
STYLE_TAIL = (
    "stylized, non-photorealistic, empty low-detail lower fifth for captions, "
    "no text"
)
NEGATIVE = (
    "photorealistic, photo, glossy 3D render, mirror reflections, text, letters, "
    "watermark, signature, logo, extra limbs, fused anatomy, duplicated creature, "
    "cluttered bottom edge"
)

# One representative visual prompt per section (first beat of each section,
# from docs/openmontage/pilot/script.md).
SECTIONS = [
    ("section_01", "Hook and the question",
     "extreme wide establishing plate, black ice ceiling filling the top third, "
     "still dark water below, single pale-bone glint at the horizon line, "
     "night ink and deep sea teal, no subject"),
    ("section_02", "The world: an ocean with no shores",
     "wide context, curved horizon of ice meeting dark water with no land "
     "anywhere, pale bone above, deep teal below, distant and empty"),
    ("section_03", "Energy: no sunlight, two answers",
     "wide plate, pale-bone ice lid, single light shaft stopping at the surface, "
     "darkness below, extreme minimal"),
    ("section_04", "Life near the ice: mats and filter-feeders",
     "wide plate, empty drafting field in deep sea teal, single pale-bone outline "
     "of a rectangle, one coral accent corner mark, no text"),
    ("section_05", "Predators, and the logic of an arms race",
     "wide plate, empty night ink field with a single pale-bone question-shaped "
     "gap of light, no subject, flat fills"),
    ("section_06", "The deep, the vents, and the animals that stay",
     "wide context, descending water column from pale-bone ice to basalt floor, "
     "faint gradient, no subject"),
    ("section_07", "Chance and law: would this world repeat?",
     "wide plate, pale-bone outline shape at left, empty black space at right, "
     "hard flat seam between"),
    ("section_08", "What blocks technology without land or fire",
     "wide plate, empty black field with a single pale-bone vertical seam of "
     "light, no subject"),
    ("section_09", "What is science, and what is a guess",
     "wide plate, pale-bone field divided into two flat blocks, one textured, "
     "one empty, hard seam"),
    ("section_10", "Closing and a question for you",
     "wide context, pale-bone ice-covered moon lit from one edge, black space, "
     "distant and schematic"),
]


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def reset_peak():
    torch.cuda.reset_peak_memory_stats()


def peak_mb():
    return round(torch.cuda.max_memory_allocated() / 1024 / 1024, 1)


def env_info():
    info = {"torch": torch.__version__, "cuda_available": bool(torch.cuda.is_available())}
    try:
        import importlib.metadata as md
        info["diffusers"] = md.version("diffusers")
    except Exception:
        info["diffusers"] = None
    if torch.cuda.is_available():
        info["device"] = torch.cuda.get_device_name(0)
        info["total_vram_gb"] = round(torch.cuda.get_device_properties(0).total_memory / 1024 ** 3, 2)
    return info


def build_prompt(scene_text):
    return f"{STYLE_PREFIX}. {scene_text}. {STYLE_TAIL}"


def main():
    results = {
        "protocol": "tools/kaggle_bridge/jobs/pilot-render/job.json",
        "started_utc": now(),
        "environment": env_info(),
        "model": MODEL_ID,
        "method": "SDXL Base 1.0 + fixed text-prompt consistency (no IP-Adapter)",
        "note": "klein 4B blocked on diffusers 0.37.0; using SDXL Base 1.0 per EPISODE_IMAGE_PIPELINE.md",
        "width": W, "height": H, "steps": STEPS, "guidance_scale": GUIDANCE, "seed": SEED,
        "sections": [],
    }
    print("ENV:", json.dumps(results["environment"], ensure_ascii=False))

    # --- Load model ---------------------------------------------------------
    reset_peak()
    t0 = time.time()
    try:
        pipe = StableDiffusionXLPipeline.from_pretrained(
            MODEL_ID, torch_dtype=torch.float16, use_safetensors=True
        )
        for m in ("enable_vae_slicing", "enable_vae_tiling"):
            if hasattr(pipe, m):
                getattr(pipe, m)()
        pipe.enable_model_cpu_offload()
        load_s = round(time.time() - t0, 2)
        peak_after_load = peak_mb()
        print(f"Model loaded: {load_s}s, peak VRAM after load: {peak_after_load} MB")
    except Exception as exc:  # noqa: BLE001
        print(f"MODEL LOAD FAILED: {exc}")
        results["model_load"] = {"status": "failed", "error": str(exc)[:500]}
        (OUT / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))
        return

    results["model_load"] = {
        "status": "ok", "load_seconds": load_s,
        "peak_vram_mb_after_load": peak_after_load,
    }

    # --- Generate one image per section ------------------------------------
    reset_peak()
    for section_id, section_title, scene_text in SECTIONS:
        prompt = build_prompt(scene_text)
        fname = f"{section_id}.png"
        fpath = IMG_DIR / fname
        rec = {
            "section_id": section_id,
            "section_title": section_title,
            "file": fname,
            "prompt": prompt,
            "negative_prompt": NEGATIVE,
        }
        try:
            t_gen = time.time()
            image = pipe(
                prompt=prompt,
                negative_prompt=NEGATIVE,
                width=W,
                height=H,
                num_inference_steps=STEPS,
                guidance_scale=GUIDANCE,
                generator=torch.manual_seed(SEED),
            ).images[0]
            gen_s = round(time.time() - t_gen, 3)
            image.save(fpath)
            rec.update({
                "status": "ok",
                "generate_seconds": gen_s,
                "peak_vram_mb": peak_mb(),
                "file_path": str(fpath),
            })
            print(f"{section_id}: OK ({gen_s}s, peak VRAM {peak_mb()} MB)")
        except Exception as exc:  # noqa: BLE001
            rec.update({"status": "failed", "error": str(exc)[:500]})
            print(f"{section_id}: FAILED {exc}")
        results["sections"].append(rec)

    peak_overall = peak_mb()
    results["peak_vram_mb_overall"] = peak_overall
    results["finished_utc"] = now()
    ok_count = sum(1 for s in results["sections"] if s.get("status") == "ok")
    results["summary"] = {
        "total_sections": len(SECTIONS),
        "ok": ok_count,
        "failed": len(SECTIONS) - ok_count,
    }
    print(f"SUMMARY: {ok_count}/{len(SECTIONS)} sections rendered, peak VRAM {peak_overall} MB")

    (OUT / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"All outputs in {OUT}")


if __name__ == "__main__":
    main()
