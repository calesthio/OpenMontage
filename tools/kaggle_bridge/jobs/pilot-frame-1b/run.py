"""Generate 1 pilot frame (Step 4a) — baseline SDXL Base 1.0 + detailed text prompt.

Fallback consistency method (PROJECT_PLAN §4.7): no IP-Adapter; character/scene
held constant by a fixed detailed text prompt. First section of the pilot
script (§1 "Hook and the question"), first beat S001, with the locked graphic-novel
ink style prefix/tail injected as prompt text.
"""

from __future__ import annotations

import importlib.metadata as md
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
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", pkg], check=True)


_ensure_pinned_versions()

BASE_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"
OUT = Path("/kaggle/working/pilot-frame-1")
OUT.mkdir(parents=True, exist_ok=True)

W = H = 768
STEPS = 30
GUIDANCE = 7.5
SEED = 42

PREFIX = (
    "bold graphic-novel ink illustration, thick outer contour, sparse hatching, "
    "large flat shadow masses, limited halftone, night ink, deep sea, "
    "electric teal, pale bone, one coral accent"
)
TAIL = "stylized, non-photorealistic, empty low-detail lower fifth for captions, no text"
NEGATIVE = (
    "photorealistic, photo, glossy 3D render, mirror reflections, text, letters, "
    "watermark, signature, logo, extra limbs, fused anatomy, duplicated creature, "
    "cluttered bottom edge"
)

SCENE = (
    "extreme wide establishing plate, black ice ceiling filling the top third, "
    "still dark water below, single pale-bone glint at the horizon line, "
    "night ink and deep sea teal, no subject"
)
PROMPT = f"{PREFIX}. {SCENE}. {TAIL}"


def _apply_vae_opts(pipe):
    for m in ("enable_vae_slicing", "enable_vae_tiling"):
        if hasattr(pipe, m):
            getattr(pipe, m)()


def main():
    print("Loading SDXL Base 1.0 ...")
    pipe = StableDiffusionXLPipeline.from_pretrained(
        BASE_MODEL, torch_dtype=torch.float16, use_safetensors=True
    )
    _apply_vae_opts(pipe)
    pipe.enable_model_cpu_offload()
    print("Model loaded.")

    t0 = time.time()
    image = pipe(
        prompt=PROMPT,
        negative_prompt=NEGATIVE,
        width=W,
        height=H,
        num_inference_steps=STEPS,
        guidance_scale=GUIDANCE,
        generator=torch.manual_seed(SEED),
    ).images[0]
    dt = time.time() - t0

    out = OUT / "frame_001.png"
    image.save(out)
    peak = round(torch.cuda.max_memory_allocated() / 1024 / 1024, 1)
    print(f"Saved {out} ({dt:.1f}s, peak VRAM {peak} MB)")


if __name__ == "__main__":
    main()

