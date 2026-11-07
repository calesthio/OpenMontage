#!/usr/bin/env python3
"""S1-1 Kaggle-side runner: Z-Image-Turbo image generation (fp16 only).

Runs on the Kaggle kernel. Rules (S1-1):
- fp16 only (torch.float16); NO bitsandbytes; NO CPU fallback.
- ONE model per kernel run (Z-Image-Turbo only).
- 12 fixed prompts with fixed seeds (read from job.json).
- non-zero exit if images < prompts.
- full tracebacks saved to output on error.
- records seconds/image, peak VRAM, GPU minutes, seeds, params, model revision.
- writes manifest.json with images[] (file, sha256, bytes, prompt, seed, ...).

Inputs (job.json): job_id, model, model_revision, width, height, steps,
guidance_scale, prompts[{prompt, seed}].
Outputs: /kaggle/working/s1_z_image_turbo/manifest.json + images + status.txt
(+ traceback_*.txt on error).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

JOB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "job.json")
OUT_DIR_NAME = "s1_z_image_turbo"
OUT = Path("/kaggle/working") / OUT_DIR_NAME
IMAGES_DIR = OUT / "images"

# Filled in by the push script at push time so the runner is self-contained
# (Kaggle copies only run.py -> /kaggle/src/script.py, not job.json).
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


def _installed_versions() -> Dict[str, str]:
    """Exact versions of the pinned stack (recorded in the manifest)."""
    import importlib.metadata as md

    out: Dict[str, str] = {}
    for pkg in ("diffusers", "transformers", "huggingface_hub", "torch"):
        try:
            out[pkg] = md.version(pkg)
        except Exception:
            out[pkg] = None
    # Best-effort commit hash for the diffusers git install.
    try:
        res = subprocess.run(
            ["git", "ls-remote", "https://github.com/huggingface/diffusers.git",
             "HEAD"],
            capture_output=True, text=True, timeout=60,
        )
        line = (res.stdout or "").strip().splitlines()[0] if res.stdout else ""
        if line:
            out["diffusers_commit"] = line.split()[0]
    except Exception:
        pass
    return out


def install_diffusers_from_source(timeout: int = 1200) -> None:
    """ZImagePipeline is not in released diffusers; install from source.

    Installs a mutually-compatible pinned stack so the kernel's pre-installed
    (often stale) huggingface-hub/transformers do not conflict:
    huggingface-hub 1.x (>=1.32 for diffusers main) + transformers 5.x
    (needs hub in [1.5, 2.0), satisfied by hub 1.x) + diffusers from git main
    (has ZImagePipeline). --force-reinstall clears stale pre-installed copies.
    fp16 only; no bitsandbytes; no CPU fallback.
    """
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet",
             "--force-reinstall",
             "huggingface-hub>=1.32.0,<2.0.0",
             "transformers>=5.0.0,<6.0.0",
             "git+https://github.com/huggingface/diffusers"],
            check=True, timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001 - fail closed
        _fail(f"diffusers compatible install failed: {exc}")


def build_manifest(job: Dict[str, Any], images: List[Dict[str, Any]],
                   load_seconds: float, gpu_minutes: float,
                   peak_vram_mb: Any, versions: Dict[str, str]) -> Dict[str, Any]:
    return {
        "job_id": job.get("job_id"),
        "model": job.get("model", "Tongyi-MAI/Z-Image-Turbo"),
        "model_revision": job.get("model_revision", "main"),
        "base_model": "Tongyi-MAI/Z-Image-Turbo",
        "dtype": "float16",
        "bitsandbytes": False,
        "cpu_fallback": False,
        "generator": "AI",
        "rights_basis": "ai_generated_illustration",
        "width": job.get("width", 1024),
        "height": job.get("height", 1024),
        "steps": job.get("steps", 9),
        "guidance_scale": job.get("guidance_scale", 0.0),
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

    try:
        with open(JOB_PATH) as f:
            job = json.load(f)
    except FileNotFoundError:
        # Kaggle copies only run.py -> /kaggle/src/script.py (not job.json), so the
        # push script embeds the job JSON into this module as JOB_EMBEDDED.
        job = JOB_EMBEDDED
        if job is None:
            _fail("job.json missing and JOB_EMBEDDED not set; runner cannot run")

    prompts: List[Dict[str, Any]] = job.get("prompts", [])
    model: str = job.get("model", "Tongyi-MAI/Z-Image-Turbo")
    revision: str = job.get("model_revision", "main")
    width: int = int(job.get("width", 1024))
    height: int = int(job.get("height", 1024))
    steps: int = int(job.get("steps", 9))
    guidance: float = float(job.get("guidance_scale", 0.0))

    if not prompts:
        _fail("no prompts in job.json")

    install_diffusers_from_source()

    import torch  # noqa: E402 - installed above
    from diffusers import ZImagePipeline  # noqa: E402

    # Record exact pinned stack versions (owner requirement: diffusers commit
    # hash, transformers, huggingface_hub) for the manifest.
    versions = _installed_versions()

    # NO CPU fallback: require CUDA.
    if not torch.cuda.is_available():
        _fail("CUDA not available on kernel; NO CPU fallback permitted (S1-1 rule)")

    torch.cuda.reset_peak_memory_stats()
    t_load0 = time.perf_counter()

    try:
        pipe = ZImagePipeline.from_pretrained(
            model, revision=revision, torch_dtype=torch.float16,
        )
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

    for i, p in enumerate(prompts):
        seed: int = int(p.get("seed", 4000 + i))
        prompt_text: str = p.get("prompt", "")
        t0 = time.perf_counter()
        try:
            image = pipe(
                prompt=prompt_text,
                height=height,
                width=width,
                num_inference_steps=steps,
                guidance_scale=guidance,
                generator=torch.Generator("cuda").manual_seed(seed),
            ).images[0]
        except Exception:
            tb = traceback.format_exc()
            (OUT / f"traceback_img_{i}.txt").write_text(tb, encoding="utf-8")
            print(tb, file=sys.stderr)
            images.append({
                "file": None,
                "seed": seed,
                "prompt": prompt_text,
                "seconds": round(time.perf_counter() - t0, 4),
                "error": "generation_exception",
            })
            continue
        secs = time.perf_counter() - t0
        fname = f"s1_zit_{seed:05d}.png"
        fpath = IMAGES_DIR / fname
        image.save(fpath, optimize=True)
        data = fpath.read_bytes()
        generated += 1
        images.append({
            "file": fname,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "prompt": prompt_text,
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

    if generated < len(prompts):
        _fail(f"images generated ({generated}) < prompts ({len(prompts)})")

    manifest = build_manifest(job, images, load_seconds, gpu_minutes,
                              peak_vram_mb, versions)
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (OUT / "status.txt").write_text("COMPLETE\n", encoding="utf-8")
    print(f"s1 z-image-turbo done: {generated} images, {gpu_minutes:.2f} GPU min, "
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
