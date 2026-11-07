#!/usr/bin/env python3
"""STICK4 bare: DreamShaper XL bare generation test (no adapter), pinned versions.

Pins diffusers==0.37.0, transformers==4.57.6, huggingface_hub==0.36.2
(the last known-working combo from STYLE1's manifest).
Generates one bare DreamShaper XL image and confirms it is valid.
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
from typing import Any, Dict, List, Optional

OUT = Path("/kaggle/working")
JOB_EMBEDDED = None

MODEL_ID = "Lykon/dreamshaper-xl-1-0"
PINNED = ["diffusers==0.37.0", "transformers==4.57.6", "huggingface_hub==0.36.2"]

REF_PROMPT = ("a person's face, comic ink style, bold black outlines, flat hatching, "
              "limited color palette, high contrast, graphic novel illustration, clean line work")


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

    # --- bare generation: one test image, no adapter ---
    try:
        img = pipe(
            prompt=REF_PROMPT,
            height=1024,
            width=1024,
            num_inference_steps=25,
            generator=torch.Generator("cuda").manual_seed(1111),
        ).images[0]
    except Exception:
        tb = traceback.format_exc()
        (OUT / "traceback_gen.txt").write_text(tb, encoding="utf-8")
        _blocked(f"bare generation failed: {tb.strip().splitlines()[-1]}", code=2)

    black, nonfinite = _black_or_nan(img)
    valid = not black and not nonfinite

    images_dir = OUT / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    fname = "ref_face.png"
    fpath = images_dir / fname
    img.save(fpath, optimize=True)
    data = fpath.read_bytes()

    gpu_seconds = time.perf_counter() - t0
    try:
        peak_vram_mb = round(torch.cuda.max_memory_allocated() / (1024 * 1024), 2)
    except Exception:
        peak_vram_mb = None

    versions: Dict[str, Optional[str]] = {}
    for pkg in ("diffusers", "transformers", "huggingface_hub", "torch", "accelerate",
                "safetensors", "numpy", "pillow"):
        try:
            import importlib.metadata as md
            versions[pkg] = md.version(pkg)
        except Exception:
            versions[pkg] = None

    manifest = {
        "job_id": "stick4-bare-dreamshaper",
        "model": "dreamshaper-xl-1-0-bare",
        "model_id": MODEL_ID,
        "pipeline_class": "StableDiffusionXLPipeline",
        "dtype": "float16",
        "ip_adapter": None,
        "width": 1024,
        "height": 1024,
        "requested": 1,
        "generated": 1 if valid else 0,
        "load_seconds": round(load_seconds, 3),
        "gpu_seconds": round(gpu_seconds, 2),
        "peak_vram_mb": peak_vram_mb,
        "black_count": int(black),
        "nan_count": int(nonfinite),
        "bare_valid": bool(valid),
        "versions": versions,
        "created_utc": now_utc(),
        "images": [{
            "render_id": "ref_face",
            "file": fname,
            "seed": 1111,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "width": img.size[0],
            "height": img.size[1],
            "black": black,
            "nonfinite": nonfinite,
            "valid": valid,
        }],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    _status("COMPLETE" if valid else "FAILED: invalid image")
    print(f"stick4 bare done: valid={valid}, black={black}, nan={nonfinite}, "
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
