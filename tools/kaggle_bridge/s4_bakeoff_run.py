#!/usr/bin/env python3
"""S4 bakeoff Kaggle-side runner: generates images for ONE model from pre-rendered prompts.

Rules (S4-2):
- fp16 only (torch.float16); NO bitsandbytes; NO CPU fallback (require CUDA).
- non-zero exit if images < prompts.
- full tracebacks saved to output on error.
- versions pinned and written into the manifest (diffusers commit, transformers,
  huggingface_hub, torch).
- one model per kernel run; images named by neutral render_id (blind).

Inputs (JOB_EMBEDDED, embedded by the push script):
  job_id, model, model_id, pipeline_class, dtype, revision,
  images[]: [{render_id, prompt, negative_prompt, guidance_scale, steps, seed}]
Outputs: /kaggle/working/<model>/ manifest.json + images + status.txt
         (+ traceback_*.txt on error).
"""
from __future__ import annotations

import hashlib
import importlib.metadata as md
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

OUT_DIR_NAME = os.environ.get("S4_OUT_DIR", "s4_bakeoff")
OUT = Path("/kaggle/working") / OUT_DIR_NAME
IMAGES_DIR = OUT / "images"

# Filled in by the push script at push time so the runner is self-contained
# (Kaggle copies only run.py -> /kaggle/src/script.py, not the job config).
JOB_EMBEDDED = None


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _fail(msg: str, code: int = 1) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "status.txt").write_text(f"FAILED: {msg}\n", encoding="utf-8")
    print(msg, file=sys.stderr)
    sys.exit(code)


def installed_versions(use_git_diffusers: bool) -> Dict[str, str]:
    """Exact pinned stack versions (recorded in the manifest)."""
    out: Dict[str, str] = {}
    for pkg in ("diffusers", "transformers", "huggingface_hub", "torch"):
        try:
            out[pkg] = md.version(pkg)
        except Exception:
            out[pkg] = None
    if use_git_diffusers:
        try:
            res = subprocess.run(
                ["git", "ls-remote", "https://github.com/huggingface/diffusers.git", "HEAD"],
                capture_output=True, text=True, timeout=60,
            )
            line = (res.stdout or "").strip().splitlines()[0] if res.stdout else ""
            if line:
                out["diffusers_commit"] = line.split()[0]
        except Exception:
            out["diffusers_commit"] = None
    else:
        out["diffusers_commit"] = None
    return out


def install_stack(use_git_diffusers: bool, timeout: int = 1200) -> None:
    """Install a mutually-compatible pinned stack.

    - Z-Image (ZImagePipeline): diffusers from git main (not in releases).
    - SDXL / klein (released pipelines): released diffusers, which does not pull
      the torchao FqnToConfig that conflicts with the kernel's pre-installed
      torchao. --force-reinstall clears stale kernel copies.
    fp16 only; no bitsandbytes; no CPU fallback.
    """
    pkgs = ["huggingface-hub>=1.32.0,<2.0.0", "transformers>=5.0.0,<6.0.0"]
    if use_git_diffusers:
        pkgs.append("git+https://github.com/huggingface/diffusers")
    else:
        pkgs.append("diffusers>=0.34.0,<0.36.0")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "--force-reinstall",
             *pkgs],
            check=True, timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001 - fail closed
        _fail(f"stack install failed: {exc}")


def build_manifest(job: Dict[str, Any], images: List[Dict[str, Any]],
                   load_seconds: float, gpu_minutes: float,
                   peak_vram_mb: Any, versions: Dict[str, str]) -> Dict[str, Any]:
    return {
        "job_id": job.get("job_id"),
        "model": job.get("model"),
        "model_id": job.get("model_id"),
        "pipeline_class": job.get("pipeline_class"),
        "dtype": "float16",
        "bitsandbytes": False,
        "cpu_fallback": False,
        "generator": "AI",
        "rights_basis": "ai_generated_illustration",
        "revision": job.get("revision", "main"),
        "vae_model_id": job.get("vae_model_id"),
        "width": job.get("width", 1280),
        "height": job.get("height", 720),
        "load_seconds": round(load_seconds, 4),
        "gpu_minutes": round(gpu_minutes, 4),
        "peak_vram_mb": peak_vram_mb,
        "device": "cuda",
        "created_utc": now_utc(),
        "diffusers": versions.get("diffusers"),
        "diffusers_commit": versions.get("diffusers_commit"),
        "transformers": versions.get("transformers"),
        "huggingface_hub": versions.get("huggingface_hub"),
        "torch": versions.get("torch"),
        "images": images,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    # Kaggle copies only script.py (no job.json), so the push script embeds the
    # job config as JOB_EMBEDDED.
    job = globals().get("JOB_EMBEDDED")
    if not isinstance(job, dict):
        _fail("JOB_EMBEDDED not set; runner cannot run")

    model: str = job.get("model", "unknown")
    model_id: str = job.get("model_id")
    pipeline_class: str = job.get("pipeline_class")
    revision: str = job.get("revision", "main")
    width: int = int(job.get("width", 1280))
    height: int = int(job.get("height", 720))
    render_jobs: List[Dict[str, Any]] = job.get("images", [])

    if not render_jobs:
        _fail("no render jobs in JOB_EMBEDDED")

    use_git_diffusers = pipeline_class == "ZImagePipeline"
    install_stack(use_git_diffusers=use_git_diffusers)

    import torch  # noqa: E402 - installed above
    from diffusers import (  # noqa: E402 - installed above
        AutoencoderKL,
        ZImagePipeline,
        StableDiffusionXLPipeline,
        FluxPipeline,
    )

    # NO CPU fallback: require CUDA.
    if not torch.cuda.is_available():
        _fail("CUDA not available on kernel; NO CPU fallback permitted (S4-2 rule)")

    PIPELINE_CLASSES = {
        "ZImagePipeline": ZImagePipeline,
        "StableDiffusionXLPipeline": StableDiffusionXLPipeline,
        "FluxPipeline": FluxPipeline,
    }
    pipe_cls = PIPELINE_CLASSES.get(pipeline_class)
    if pipe_cls is None:
        _fail(f"unknown pipeline_class: {pipeline_class!r}")

    torch.cuda.reset_peak_memory_stats()
    t_load0 = time.perf_counter()
    try:
        kwargs = {"revision": revision} if revision else {}
        vae_model_id = job.get("vae_model_id")
        if vae_model_id:
            kwargs["vae"] = AutoencoderKL.from_pretrained(
                vae_model_id, torch_dtype=torch.float16, revision=revision
            )
        pipe = pipe_cls.from_pretrained(model_id, torch_dtype=torch.float16, **kwargs)
        pipe.to("cuda")
    except Exception:
        tb = traceback.format_exc()
        (OUT / "traceback_load.txt").write_text(tb, encoding="utf-8")
        print(tb, file=sys.stderr)
        sys.exit(1)

    t_load1 = time.perf_counter()
    load_seconds = t_load1 - t_load0

    images: List[Dict[str, Any]] = []
    t_total0 = time.perf_counter()
    generated = 0

    for rj in render_jobs:
        render_id: str = rj.get("render_id", f"img_{generated}")
        prompt: str = rj.get("prompt", "")
        negative_prompt = rj.get("negative_prompt")
        guidance_scale = rj.get("guidance_scale")
        steps: int = int(rj.get("steps", 4))
        seed: int = int(rj.get("seed", 4000))
        t0 = time.perf_counter()
        try:
            call_kwargs = dict(
                prompt=prompt,
                height=height,
                width=width,
                num_inference_steps=steps,
                generator=torch.Generator("cuda").manual_seed(seed),
            )
            if negative_prompt is not None:
                call_kwargs["negative_prompt"] = negative_prompt
            if guidance_scale is not None:
                call_kwargs["guidance_scale"] = float(guidance_scale)
            image = pipe(**call_kwargs).images[0]
        except Exception:
            tb = traceback.format_exc()
            (OUT / f"traceback_{render_id}.txt").write_text(tb, encoding="utf-8")
            print(tb, file=sys.stderr)
            images.append({
                "render_id": render_id,
                "file": None,
                "seed": seed,
                "seconds": round(time.perf_counter() - t0, 4),
                "error": "generation_exception",
            })
            continue
        secs = time.perf_counter() - t0
        fname = f"{render_id}.png"
        fpath = IMAGES_DIR / fname
        image.save(fpath, optimize=True)
        data = fpath.read_bytes()
        generated += 1
        images.append({
            "render_id": render_id,
            "file": fname,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "guidance_scale": guidance_scale,
            "steps": steps,
            "seed": seed,
            "width": width,
            "height": height,
            "seconds": round(secs, 4),
        })

    t_total1 = time.perf_counter()
    gpu_minutes = (t_total1 - t_total0) / 60.0
    try:
        peak_vram_mb = round(torch.cuda.max_memory_allocated() / (1024 * 1024), 2)
    except Exception:  # noqa: BLE001
        peak_vram_mb = None

    if generated < len(render_jobs):
        _fail(f"images generated ({generated}) < prompts ({len(render_jobs)})")

    versions = installed_versions(use_git_diffusers=use_git_diffusers)
    manifest = build_manifest(job, images, load_seconds, gpu_minutes,
                              peak_vram_mb, versions)
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (OUT / "status.txt").write_text("COMPLETE\n", encoding="utf-8")
    print(f"s4 {model} done: {generated} images, {gpu_minutes:.2f} GPU min, "
          f"peak VRAM {peak_vram_mb} MB")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001 - full traceback saved to output
        tb = traceback.format_exc()
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "traceback_fatal.txt").write_text(tb, encoding="utf-8")
        print(tb, file=sys.stderr)
        sys.exit(1)
