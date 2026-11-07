"""OpenMontage FLUX.2 Klein 4B baseline VRAM test kernel (Kaggle T4).

Test: model load + single generation 768x768 fp16 batch=1 with model_cpu_offload.
Measure peak VRAM. If > 14.0 GB, flag as "не влезает на одной T4".

Outputs: /kaggle/working/flux2-klein-test/results.json
"""

from __future__ import annotations

import importlib.metadata as md
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# --- Пин версий (должно совпадать с requirements-pinned.txt в codespace) ---
PINNED_VERSIONS = [
    "diffusers==0.37.0",
    "transformers==4.57.6",
    "huggingface_hub==0.36.2",
]


def _ensure_pinned_versions():
    """Установить закреплённые версии перед импортом diffusers/transformers."""
    for pkg in PINNED_VERSIONS:
        name = pkg.split("==")[0]
        try:
            installed = md.version(name)
            if installed == pkg.split("==")[1]:
                continue
        except Exception:
            pass
        print(f"Installing {pkg} ...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", pkg],
            check=True,
        )


_ensure_pinned_versions()

import torch
from diffusers import FluxPipeline

OUT = Path("/kaggle/working/flux2-klein-test")
OUT.mkdir(parents=True, exist_ok=True)

MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
W = H = 768
STEPS = 4
GUIDANCE = 1.0
SEED = 42


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def reset_peak():
    torch.cuda.reset_peak_memory_stats()


def peak_mb():
    return round(torch.cuda.max_memory_allocated() / 1024 / 1024, 1)


def env_info():
    info = {
        "torch": torch.__version__,
        "cuda_available": bool(torch.cuda.is_available()),
    }
    try:
        info["diffusers"] = md.version("diffusers")
    except Exception:
        info["diffusers"] = None
    if torch.cuda.is_available():
        info["device"] = torch.cuda.get_device_name(0)
        info["total_vram_gb"] = round(
            torch.cuda.get_device_properties(0).total_memory / 1024**3, 2
        )
    return info


def main():
    results = {
        "protocol": "tools/kaggle_bridge/jobs/flux2-klein-test/test_protocol.json",
        "started_utc": now(),
        "environment": env_info(),
        "test": {},
    }
    print("ENV:", json.dumps(results["environment"], ensure_ascii=False))

    # --- Load model ---------------------------------------------------------
    reset_peak()
    t0 = time.time()
    try:
        pipe = FluxPipeline.from_pretrained(
            MODEL_ID,
            torch_dtype=torch.float16,
        )
        pipe.enable_model_cpu_offload()
        load_s = round(time.time() - t0, 2)
        peak_after_load = peak_mb()
        print(f"Model loaded: {load_s}s, peak VRAM after load: {peak_after_load} MB")
    except Exception as exc:
        print(f"MODEL LOAD FAILED: {exc}")
        results["test"] = {
            "status": "failed",
            "stage": "load",
            "error": str(exc)[:500],
        }
        (OUT / "results.json").write_text(
            json.dumps(results, indent=2, ensure_ascii=False)
        )
        return

    # --- Single generation --------------------------------------------------
    reset_peak()
    try:
        image = pipe(
            prompt="A young woman with short curly auburn hair and freckles, wearing a blue denim jacket, comic line-art style, bold black outlines",
            width=W,
            height=H,
            num_inference_steps=STEPS,
            guidance_scale=GUIDANCE,
            generator=torch.manual_seed(SEED),
        ).images[0]
        gen_s = round(time.time() - t0 - load_s, 2)
        peak_gen = peak_mb()
        image.save(OUT / "flux2_klein_baseline_768x768.png")
        print(f"Generation done: {gen_s}s, peak VRAM: {peak_gen} MB")
    except Exception as exc:
        print(f"GENERATION FAILED: {exc}")
        results["test"] = {
            "status": "failed",
            "stage": "generate",
            "error": str(exc)[:500],
            "peak_vram_mb_after_load": peak_after_load,
        }
        (OUT / "results.json").write_text(
            json.dumps(results, indent=2, ensure_ascii=False)
        )
        return

    # --- Conclusion ---------------------------------------------------------
    total_vram_gb = results["environment"].get("total_vram_gb", 0)
    peak_overall_mb = max(peak_after_load, peak_gen)
    peak_overall_gb = round(peak_overall_mb / 1024, 2)
    fits_t4 = peak_overall_mb < 14000  # 14.0 GB warning threshold

    results["test"] = {
        "status": "completed",
        "model": MODEL_ID,
        "resolution": f"{W}x{H}",
        "batch_size": 1,
        "steps": STEPS,
        "guidance_scale": GUIDANCE,
        "load_seconds": load_s,
        "generate_seconds": gen_s,
        "peak_vram_mb_after_load": peak_after_load,
        "peak_vram_mb_overall": peak_overall_mb,
        "peak_vram_gb_overall": peak_overall_gb,
        "total_vram_gb": total_vram_gb,
        "fits_on_single_t4": fits_t4,
        "note": "Если пик VRAM > 14.0 ГБ — модель не влезает на одной T4.",
    }
    print("TEST RESULT:", json.dumps(results["test"], ensure_ascii=False))

    (OUT / "results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False)
    )
    print(f"All outputs in {OUT}")


if __name__ == "__main__":
    main()