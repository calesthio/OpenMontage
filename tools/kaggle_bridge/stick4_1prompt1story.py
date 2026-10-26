#!/usr/bin/env python3
"""STICK4 parallel: 1Prompt1Story on DreamShaper XL (pinned versions).

1Prompt1Story uses prompt-concatenation on the base pipeline — no adapter
checkpoints, no extra weights, no CLIP encoder needed for generation.
Pins diffusers==0.37.0, transformers==4.57.6, huggingface_hub==0.36.2.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

OUT = Path("/kaggle/working")
JOB_EMBEDDED = None

MODEL_ID = "Lykon/dreamshaper-xl-1-0"
PINNED = ["diffusers==0.37.0", "transformers==4.57.6", "huggingface_hub==0.36.2"]

STYLE_PREFIX = (
    "comic ink style, bold black outlines, flat hatching, limited color palette, "
    "deep teal, bioluminescent lime, basalt charcoal, pale bone, high contrast, "
    "graphic novel illustration, vector art, clean line work, "
)

REF_PROMPT = ("a person's face, comic ink style, bold black outlines, flat hatching, "
              "limited color palette, high contrast, graphic novel illustration, clean line work")

SCENES = [
    {"render_id": "scene_pointing", "scene_id": "s01",
     "prompt": "vent grazer grazing bacterial mats on a vent chimney, side silhouette, pointing at vent chimney",
     "negative_prompt": "photorealistic, 3d, realistic, blurry, low quality, watermark, text, letters, numbers",
     "guidance_scale": 7.5, "steps": 25, "seed": 2222},
    {"render_id": "scene_confused", "scene_id": "s03",
     "prompt": "vent grazer, confused expression, three-quarter view, floating in mid-water",
     "negative_prompt": "photorealistic, 3d, realistic, blurry, low quality, watermark, text, letters, numbers",
     "guidance_scale": 7.5, "steps": 25, "seed": 3333},
    {"render_id": "scene_talking", "scene_id": "s05",
     "prompt": "vent grazer talking, mouth open, wide establishing shot, low angle",
     "negative_prompt": "photorealistic, 3d, realistic, blurry, low quality, watermark, text, letters, numbers",
     "guidance_scale": 7.5, "steps": 25, "seed": 4444},
]


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _status(text: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "status.txt").write_text(text.strip() + "\n", encoding="utf-8")


def _blocked(msg: str, code: int = 3) -> None:
    _status(f"BLOCKED: {msg}")
    print(f"BLOCKED: {msg}", file=sys.stderr)
    sys.exit(code)


def _write_done(errors: Optional[List[str]] = None) -> None:
    payload: Dict[str, Any] = {"status": "error", "n_images": None, "n_black": None,
                               "seconds_total": None, "errors": list(errors or [])}
    try:
        man_path = OUT / "manifest.json"
        if man_path.exists():
            man = json.loads(man_path.read_text(encoding="utf-8"))
            payload["n_images"] = man.get("generated")
            payload["n_black"] = man.get("black_count")
            payload["seconds_total"] = man.get("gpu_seconds")
            ok = man.get("generated") == man.get("requested")
            payload["status"] = "ok" if ok else "error"
    except Exception:
        pass
    try:
        (Path("/kaggle/working") / "DONE.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        pass


def _black_or_nan(img) -> tuple[bool, bool]:
    import numpy as np
    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    nonfinite = bool((~np.isfinite(arr)).any())
    black = bool(arr.max() < 8.0)
    return black, nonfinite


def _pixel_diff(img1, img2) -> float:
    """Mean absolute pixel difference between two images (0-255 scale)."""
    import numpy as np
    a = np.asarray(img1.convert("RGB").resize((1024, 1024)), dtype=np.float32)
    b = np.asarray(img2.convert("RGB").resize((1024, 1024)), dtype=np.float32)
    return float(np.abs(a - b).mean())


def main() -> None:
    # --- pin versions BEFORE importing diffusers/transformers ---
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", "--no-cache-dir", *PINNED],
        check=True, timeout=1500,
    )

    import torch
    from diffusers import StableDiffusionXLPipeline
    from PIL import Image
    import numpy as np

    if not torch.cuda.is_available():
        _blocked("CUDA not available; NO CPU fallback permitted")

    device = "cuda"
    torch.cuda.reset_peak_memory_stats()

    # --- load DreamShaper XL base pipeline (no adapter, no extra weights) ---
    t0 = time.perf_counter()
    try:
        pipe = StableDiffusionXLPipeline.from_pretrained(
            MODEL_ID, torch_dtype=torch.float16, add_watermarker=False)
        pipe.to(device)
        pipe.set_progress_bar_config(disable=True)
    except Exception:
        tb = traceback.format_exc()
        (OUT / "traceback_load.txt").write_text(tb, encoding="utf-8")
        _blocked(f"base pipeline load failed: {tb.strip().splitlines()[-1]}", code=2)
    load_seconds = time.perf_counter() - t0

    # --- generate reference image (bare) ---
    try:
        ref_img = pipe(
            prompt=REF_PROMPT,
            height=1024, width=1024,
            num_inference_steps=25,
            generator=torch.Generator("cuda").manual_seed(1111),
        ).images[0]
    except Exception:
        tb = traceback.format_exc()
        (OUT / "traceback_refgen.txt").write_text(tb, encoding="utf-8")
        _blocked(f"reference image generation failed: {tb.strip().splitlines()[-1]}", code=2)

    images_dir = OUT / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    ref_img.save(images_dir / "ref_face.png", optimize=True)

    # --- generate 3 scenes with 1Prompt1Story prompt-concatenation ---
    images: List[Dict[str, Any]] = []
    oom_count = black_count = nan_count = 0
    t_total0 = time.perf_counter()

    for rj in SCENES:
        rid = rj["render_id"]
        story_prompt = STYLE_PREFIX + rj["prompt"]

        call = dict(
            prompt=story_prompt,
            height=1024, width=1024,
            num_inference_steps=int(rj.get("steps") or 25),
            generator=torch.Generator("cuda").manual_seed(int(rj["seed"])),
        )
        if rj.get("negative_prompt") is not None:
            call["negative_prompt"] = rj["negative_prompt"]
        if rj.get("guidance_scale") is not None:
            call["guidance_scale"] = float(rj["guidance_scale"])

        t_start = time.perf_counter()
        try:
            img = pipe(**call).images[0]
        except torch.cuda.OutOfMemoryError:
            oom_count += 1
            torch.cuda.empty_cache()
            tb = traceback.format_exc()
            (OUT / f"traceback_{rid}.txt").write_text(tb, encoding="utf-8")
            images.append({"render_id": rid, "file": None, "seed": rj["seed"], "error": "oom"})
            continue
        except Exception:
            tb = traceback.format_exc()
            (OUT / f"traceback_{rid}.txt").write_text(tb, encoding="utf-8")
            images.append({"render_id": rid, "file": None, "seed": rj["seed"], "error": "generation_exception"})
            continue

        secs = time.perf_counter() - t_start
        black, nonfinite = _black_or_nan(img)
        black_count += int(black)
        nan_count += int(nonfinite)

        fname = f"{rid}.png"
        fpath = images_dir / fname
        img.save(fpath, optimize=True)
        data = fpath.read_bytes()

        pdiff = _pixel_diff(ref_img, img)

        images.append({
            "render_id": rid, "scene_id": rj["scene_id"],
            "file": fname, "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data), "width": img.size[0], "height": img.size[1],
            "seed": int(rj["seed"]), "steps": int(rj.get("steps") or 0),
            "guidance_scale": call.get("guidance_scale"),
            "seconds": round(secs, 4), "black": black, "nonfinite": nonfinite,
            "pixel_diff_vs_ref": round(pdiff, 4),
            "prompt_used": story_prompt,
        })

    gpu_seconds = time.perf_counter() - t_total0
    try:
        peak_vram_mb = round(torch.cuda.max_memory_allocated() / (1024 * 1024), 2)
    except Exception:
        peak_vram_mb = None

    pdiffs = [i["pixel_diff_vs_ref"] for i in images if i.get("file")]
    n_comp = len(pdiffs)
    mean_pd = round(sum(pdiffs) / len(pdiffs), 4) if pdiffs else None
    min_pd = round(min(pdiffs), 4) if pdiffs else None
    max_pd = round(max(pdiffs), 4) if pdiffs else None

    versions: Dict[str, Optional[str]] = {}
    for pkg in ("diffusers", "transformers", "huggingface_hub", "torch", "accelerate",
                "safetensors", "numpy", "pillow"):
        try:
            import importlib.metadata as md
            versions[pkg] = md.version(pkg)
        except Exception:
            versions[pkg] = None

    manifest = {
        "job_id": "stick4-1prompt1story-pinned",
        "model": "1prompt1story_sdxl",
        "model_id": MODEL_ID,
        "technique": "prompt-concatenation (zero extra weights)",
        "pipeline_class": "StableDiffusionXLPipeline",
        "dtype": "float16",
        "width": 1024, "height": 1024,
        "requested": len(SCENES),
        "generated": len([i for i in images if i.get("file")]),
        "load_seconds": round(load_seconds, 3),
        "gpu_seconds": round(gpu_seconds, 2),
        "peak_vram_mb": peak_vram_mb,
        "oom_count": oom_count, "black_count": black_count, "nan_count": nan_count,
        "consistency": {
            "candidate": "1prompt1story_sdxl",
            "metric": "mean_abs_pixel_diff_vs_reference (0-255, lower=more consistent)",
            "n_comparisons": n_comp,
            "mean_pixel_diff": mean_pd,
            "min_pixel_diff": min_pd,
            "max_pixel_diff": max_pd,
        },
        "versions": versions,
        "created_utc": now_utc(),
        "images": images,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    generated = len([i for i in images if i.get("file")])
    if generated < len(SCENES):
        _status(f"PARTIAL: generated {generated}/{len(SCENES)}")
        sys.exit(1)

    _status("COMPLETE")
    print(f"stick4 1prompt1story done: {n_comp} images, mean_pixel_diff={mean_pd}, "
          f"peak VRAM {peak_vram_mb} MB")


if __name__ == "__main__":
    _done_errors: List[str] = []
    try:
        main()
    except SystemExit as exc:
        if exc.code not in (0, None):
            _done_errors.append(f"exit code {exc.code}")
        raise
    except Exception:
        tb = traceback.format_exc()
        _done_errors.append(tb.strip().splitlines()[-1] if tb.strip() else "exception")
        try:
            OUT.mkdir(parents=True, exist_ok=True)
            (OUT / "traceback_fatal.txt").write_text(tb, encoding="utf-8")
            _status(f"FAILED: {tb.strip().splitlines()[-1]}")
        except Exception:
            pass
        print(tb, file=sys.stderr)
        sys.exit(1)
    finally:
        _write_done(_done_errors)
