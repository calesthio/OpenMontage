#!/usr/bin/env python3
"""STICK4 fixed: IP-Adapter Plus SDXL on T4.

Uses diffusers' built-in `load_ip_adapter()` (the supported path) instead of
the manual IPAdapterXL class. Fixes the `ip_adapter_image_embeds` 2D->3D
tensor bug that blocked STICK4 v2/v3.

h94/IP-Adapter, ip-adapter-plus_sdxl_vit-h.safetensors (Apache-2.0, 848MB).
ViT-H image encoder computes the reference embedding ONCE, then is offloaded
from GPU before generation (no resident encoder during generation).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn.functional as F
from diffusers import StableDiffusionXLPipeline
from transformers import CLIPImageProcessor, CLIPVisionModelWithProjection
from PIL import Image
import numpy as np

OUT = Path("/kaggle/working")
JOB_EMBEDDED = {"job_id": "stick4-ipadapter-fixed-2", "model_id": "Lykon/dreamshaper-xl-1-0", "width": 1024, "height": 1024, "scale": 0.5, "renders": [{"render_id": "scene_pointing", "scene_id": "s01", "prompt": "vent grazer grazing bacterial mats on a vent chimney, side silhouette, pointing at vent chimney, comic ink style, bold black outlines, flat hatching, limited color palette, deep teal, bioluminescent lime, basalt charcoal, pale bone, high contrast, graphic novel illustration, vector art, clean line work", "negative_prompt": "photorealistic, 3d, realistic, blurry, low quality, watermark, text, letters, numbers", "guidance_scale": 1.0, "steps": 25, "seed": 2222, "reference_render_id": "ref_face"}, {"render_id": "scene_confused", "scene_id": "s03", "prompt": "vent grazer, confused expression, three-quarter view, floating in mid-water, comic ink style, bold outlines, hatching, deep teal, bioluminescent lime, basalt charcoal, pale bone", "negative_prompt": "photorealistic, 3d, realistic, blurry, low quality, watermark, text, letters, numbers", "guidance_scale": 1.0, "steps": 25, "seed": 3333, "reference_render_id": "ref_face"}, {"render_id": "scene_talking", "scene_id": "s05", "prompt": "vent grazer talking, mouth open, wide establishing shot, low angle, comic ink style, bold contours, clean line work, deep teal, bioluminescent lime, basalt charcoal, pale bone", "negative_prompt": "photorealistic, 3d, realistic, blurry, low quality, watermark, text, letters, numbers", "guidance_scale": 1.0, "steps": 25, "seed": 4444, "reference_render_id": "ref_face"}]}

IP_ADAPTER_REPO = "h94/IP-Adapter"
IP_ADAPTER_SUBFOLDER = "sdxl_models"
IP_ADAPTER_WEIGHT = "ip-adapter-plus_sdxl_vit-h.safetensors"


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
    payload: Dict[str, Any] = {
        "status": "error", "n_images": None, "n_black": None,
        "seconds_total": None, "errors": list(errors or []),
    }
    try:
        man_path = OUT / "manifest.json"
        if man_path.exists():
            man = json.loads(man_path.read_text(encoding="utf-8"))
            payload["n_images"] = man.get("generated")
            payload["n_black"] = man.get("black_count")
            payload["seconds_total"] = man.get("gpu_seconds")
    except Exception as exc:
        payload["errors"].append(f"done.json could not read manifest: {exc}")
    try:
        (Path("/kaggle/working") / "DONE.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        pass


def _black_or_nan(img) -> Tuple[bool, bool]:
    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    nonfinite = bool((~np.isfinite(arr)).any())
    black = bool(arr.max() < 8.0)
    return black, nonfinite


def _shape_fix_embeds(embeds: torch.Tensor) -> torch.Tensor:
    """Fix: reshape ip_adapter_image_embeds from 2D -> 3D for diffusers."""
    if embeds.dim() == 1:
        embeds = embeds.unsqueeze(0).unsqueeze(0)
    elif embeds.dim() == 2:
        embeds = embeds.unsqueeze(0)
    return embeds


def _clip_image_similarity(img1: Image.Image, img2: Image.Image,
                           processor, model, device: str) -> float:
    # model is offloaded to CPU before generation; keep inputs on CPU to match
    inputs1 = processor(images=img1.convert("RGB"), return_tensors="pt")
    inputs2 = processor(images=img2.convert("RGB"), return_tensors="pt")
    with torch.no_grad():
        e1 = model(**inputs1).image_embeds
        e2 = model(**inputs2).image_embeds
        e1 = F.normalize(e1, dim=-1)
        e2 = F.normalize(e2, dim=-1)
        sim = float((e1 * e2).sum(dim=-1).item())
    return sim


def main() -> None:
    global OUT
    job = JOB_EMBEDDED
    if isinstance(job, str):
        job = json.loads(job)
    if not isinstance(job, dict):
        _blocked("JOB_EMBEDDED not set; runner cannot run", code=1)

    model_id: str = job["model_id"]
    width = int(job.get("width", 1024))
    height = int(job.get("height", 1024))
    renders: List[Dict[str, Any]] = job.get("renders") or []
    if not renders:
        _blocked("no renders in JOB_EMBEDDED", code=1)

    OUT = Path("/kaggle/working") / f"stick4_ipadapter_fixed_{job.get('job_id', 'run')}"
    images_dir = OUT / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    versions: Dict[str, Optional[str]] = {}
    for pkg in ("diffusers", "transformers", "torch", "accelerate", "safetensors",
                "numpy", "pillow"):
        try:
            import importlib.metadata as md
            versions[pkg] = md.version(pkg)
        except Exception:
            versions[pkg] = None

    import torch
    versions["torch_cuda"] = getattr(torch.version, "cuda", None)
    versions["gpu"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None

    if not torch.cuda.is_available():
        _blocked("CUDA not available; NO CPU fallback permitted")

    device = "cuda"
    torch.cuda.reset_peak_memory_stats()

    # --- load DreamShaper XL base pipeline ---
    t0 = time.perf_counter()
    try:
        pipe = StableDiffusionXLPipeline.from_pretrained(
            model_id, torch_dtype=torch.float16, add_watermarker=False)
        pipe.to(device)
        pipe.set_progress_bar_config(disable=True)
    except Exception:
        tb = traceback.format_exc()
        (OUT / "traceback_load.txt").write_text(tb, encoding="utf-8")
        _blocked(f"base pipeline load failed: {tb.strip().splitlines()[-1]}", code=2)
    load_seconds = time.perf_counter() - t0

    # --- generate reference image BEFORE loading IP-Adapter weights ---
    # (IP-Adapter loaded UNet requires image_embeds for all forward passes)
    ref_prompt = "a person's face, comic ink style, bold black outlines, flat hatching, limited color palette, high contrast, graphic novel illustration, clean line work"
    try:
        ref_img = pipe(
            prompt=ref_prompt,
            height=height,
            width=width,
            num_inference_steps=25,
            generator=torch.Generator("cuda").manual_seed(1111),
        ).images[0]
    except Exception:
        tb = traceback.format_exc()
        (OUT / "traceback_refgen.txt").write_text(tb, encoding="utf-8")
        _blocked(f"reference image generation failed: {tb.strip().splitlines()[-1]}", code=2)
    ref_image = ref_img

    # --- load IP-Adapter Plus via diffusers load_ip_adapter ---
    try:
        pipe.load_ip_adapter(
            IP_ADAPTER_REPO,
            subfolder=IP_ADAPTER_SUBFOLDER,
            weight_name=IP_ADAPTER_WEIGHT,
        )
    except Exception:
        tb = traceback.format_exc()
        (OUT / "traceback_ipadapter.txt").write_text(tb, encoding="utf-8")
        _blocked(f"IP-Adapter Plus load failed: {tb.strip().splitlines()[-1]}", code=2)

    # --- load ViT-H image encoder + compute reference embedding ONCE ---
    try:
        image_encoder = CLIPVisionModelWithProjection.from_pretrained(
            IP_ADAPTER_REPO,
            subfolder="models/image_encoder",
            torch_dtype=torch.float16,
        ).to(device)
        image_encoder.eval()
        clip_processor = CLIPImageProcessor.from_pretrained(
            "openai/clip-vit-large-patch14")
    except Exception:
        tb = traceback.format_exc()
        (OUT / "traceback_encoder.txt").write_text(tb, encoding="utf-8")
        _blocked(f"image encoder load failed: {tb.strip().splitlines()[-1]}", code=2)

    ref_inputs = clip_processor(images=ref_image, return_tensors="pt").to(device)
    with torch.no_grad():
        ref_embed = image_encoder(**ref_inputs).image_embeds  # (1, 768) pooled
    ref_embed = ref_embed.detach().clone().unsqueeze(0)  # (1, 1, 768) 3D

    # OFFLOAD encoder before generation
    image_encoder.to("cpu")
    torch.cuda.empty_cache()
    encoder_offloaded = True

    # --- generate 3 scenes ---
    images: List[Dict[str, Any]] = []
    oom_count = black_count = nan_count = 0
    t_total0 = time.perf_counter()

    for rj in renders:
        rid = rj["render_id"]
        call = dict(
            prompt=rj["prompt"],
            height=height,
            width=width,
            num_inference_steps=int(rj.get("steps") or 25),
            generator=torch.Generator("cuda").manual_seed(int(rj["seed"])),
            ip_adapter_image_embeds=[ref_embed],  # single (1,1,768) tensor in list
            scale=float(rj.get("scale", 0.5)),
        )
        if rj.get("negative_prompt") is not None:
            call["negative_prompt"] = rj["negative_prompt"]
        if rj.get("guidance_scale") is not None:
            call["guidance_scale"] = float(rj["guidance_scale"])
        # CFG disabled for single-embedding IP-Adapter call
        call["guidance_scale"] = 1.0

        t_start = time.perf_counter()
        try:
            img = pipe(**call).images[0]
        except torch.cuda.OutOfMemoryError:
            oom_count += 1
            torch.cuda.empty_cache()
            tb = traceback.format_exc()
            (OUT / f"traceback_{rid}.txt").write_text(tb, encoding="utf-8")
            images.append({"render_id": rid, "file": None, "seed": rj["seed"],
                           "error": "oom"})
            continue
        except Exception:
            tb = traceback.format_exc()
            (OUT / f"traceback_{rid}.txt").write_text(tb, encoding="utf-8")
            print(tb, file=sys.stderr)
            images.append({"render_id": rid, "file": None, "seed": rj["seed"],
                           "error": "generation_exception"})
            continue

        secs = time.perf_counter() - t_start
        black, nonfinite = _black_or_nan(img)
        black_count += int(black)
        nan_count += int(nonfinite)

        fname = f"{rid}.png"
        fpath = images_dir / fname
        img.save(fpath, optimize=True)
        data = fpath.read_bytes()

        sim = _clip_image_similarity(ref_image, img, clip_processor,
                                     image_encoder, device)

        images.append({
            "render_id": rid,
            "scene_id": rj.get("scene_id"),
            "variant": rj.get("variant"),
            "file": fname,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "width": img.size[0],
            "height": img.size[1],
            "seed": int(rj["seed"]),
            "steps": int(rj.get("steps") or 0),
            "guidance_scale": call.get("guidance_scale"),
            "seconds": round(secs, 4),
            "black": black,
            "nonfinite": nonfinite,
            "clip_similarity": sim,
        })

    gpu_seconds = time.perf_counter() - t_total0
    try:
        peak_vram_mb = round(torch.cuda.max_memory_allocated() / (1024 * 1024), 2)
        peak_vram_reserved_mb = round(torch.cuda.max_memory_reserved() / (1024 * 1024), 2)
    except Exception:
        peak_vram_mb = None
        peak_vram_reserved_mb = None

    sims = [i["clip_similarity"] for i in images if i.get("file")]
    n_comparisons = len(sims)
    mean_sim = round(sum(sims) / len(sims), 4) if sims else None
    min_sim = round(min(sims), 4) if sims else None
    max_sim = round(max(sims), 4) if sims else None

    times = [i["seconds"] for i in images if i.get("file")]
    steady = round(sum(times[1:]) / len(times[1:]), 3) if len(times) > 1 else (
        round(times[0], 3) if times else None)

    manifest = {
        "job_id": job.get("job_id"),
        "model": "ip_adapter_plus_sdxl",
        "model_id": model_id,
        "ip_adapter_repo": IP_ADAPTER_REPO,
        "ip_adapter_weight": f"{IP_ADAPTER_SUBFOLDER}/{IP_ADAPTER_WEIGHT}",
        "license": "Apache-2.0 (h94/IP-Adapter)",
        "pipeline_class": "StableDiffusionXLPipeline",
        "dtype": "float16",
        "bitsandbytes": False,
        "cpu_fallback": False,
        "image_encoder_offloaded_before_gen": encoder_offloaded,
        "tensor_shape_fix": "2D->3D reshape applied before pipeline call",
        "width": width,
        "height": height,
        "requested": len(renders),
        "generated": len(times),
        "load_seconds": round(load_seconds, 3),
        "steady_state_sec_per_image": steady,
        "mean_sec_per_image": round(sum(times) / len(times), 3) if times else None,
        "gpu_seconds": round(gpu_seconds, 2),
        "peak_vram_mb": peak_vram_mb,
        "peak_vram_reserved_mb": peak_vram_reserved_mb,
        "oom_count": oom_count,
        "black_count": black_count,
        "nan_count": nan_count,
        "consistency": {
            "candidate": "ip_adapter_plus_sdxl",
            "n_comparisons": n_comparisons,
            "mean_clip_similarity": mean_sim,
            "min_clip_similarity": min_sim,
            "max_clip_similarity": max_sim,
            "note": "cosine similarity of CLIP ViT-H image embedding vs reference (1.0 = identical)",
        },
        "versions": versions,
        "created_utc": now_utc(),
        "images": images,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if len(times) < len(renders):
        _status(f"PARTIAL: generated {len(times)}/{len(renders)}; see manifest.json")
        print(f"stick4 ipadapter PARTIAL: {len(times)}/{len(renders)}", file=sys.stderr)
        sys.exit(1)

    _status("COMPLETE")
    print(f"stick4 ipadapter done: {len(times)} images, {steady} s/img, "
          f"peak VRAM {peak_vram_mb} MB, mean_sim={mean_sim}")


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
