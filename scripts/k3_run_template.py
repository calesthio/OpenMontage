"""OpenMontage K3 — FLUX.2-klein-4B pilot frame generation (Kaggle T4).

One kernel per section-group (weights downloaded once per kernel).
Shots are embedded inline (SHOTS) — no repo path dependency.

Per shot:
  - prompt = bit's scene description + VISUAL_STYLE_GUIDE technique
  - 1280x720, 4 steps, guidance_scale=1.0 (CFG off), bfloat16 -> float16 fallback
  - NaN/black frame detection via min/max pixels
  - log time, peak VRAM, selected dtype per shot

Outputs: /kaggle/working/k3-klein-frames/
         frames/B001.png ... B078.png
         results.json
         kernel.log
"""

from __future__ import annotations

import importlib.metadata as md
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import torch
from PIL import Image

# --- Пин версий (diffusers 0.37.0 уже содержит Flux2KleinPipeline) ---
PINNED_VERSIONS = ["diffusers==0.37.0", "transformers==4.57.6", "huggingface_hub==0.36.2"]


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

# --- LOAD SHOTS ---
SHOTS = []
# --- END LOAD SHOTS ---

OUT = Path("/kaggle/working/k3-klein-frames")
FRAME_DIR = OUT / "frames"
FRAME_DIR.mkdir(parents=True, exist_ok=True)

W, H = 1280, 720
STEPS = 4
GUIDANCE = 1.0


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def reset_peak():
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()


def peak_mb():
    if torch.cuda.is_available():
        return round(torch.cuda.max_memory_allocated() / 1024 / 1024, 1)
    return 0


def is_black_or_nan(image: Image.Image) -> bool:
    import numpy as np
    arr = np.asarray(image)
    if arr.dtype.kind == "f":
        if np.isnan(arr).any():
            return True
    gray = arr.mean(axis=2) if arr.ndim == 3 else arr
    return float(gray.max()) < 5.0  # essentially black


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


def main():
    print(f"SHOTS TO RENDER: {len(SHOTS)}")
    print("ENV:", json.dumps(env_info(), ensure_ascii=False))
    print("SIGNATURE:", str(inspect.signature(Flux2KleinPipeline.__call__)))

    results = {
        "started_utc": now(),
        "model": "black-forest-labs/FLUX.2-klein-4B",
        "resolution": f"{W}x{H}",
        "steps": STEPS,
        "guidance_scale": GUIDANCE,
        "environment": env_info(),
        "signature": str(inspect.signature(Flux2KleinPipeline.__call__)),
        "shots": [],
        "selected_dtype": None,
    }
    print("ENV:", json.dumps(results["environment"], ensure_ascii=False))

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
                "black-forest-labs/FLUX.2-klein-4B",
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
    results["load_seconds"] = load_s
    results["peak_vram_mb_after_load"] = peak_mb()
    results["selected_dtype"] = selected_dtype
    print(f"Loaded in {load_s}s, peak VRAM after load: {peak_mb()} MB, dtype={selected_dtype}")

    # --- Generate shots ---
    for idx, shot in enumerate(SHOTS, start=1):
        bid = shot["bit_id"]
        print(f"[{idx}/{len(SHOTS)}] {bid} section={shot['section']} "
              f"t={shot['start']}-{shot['end']}s ...")
        t0 = time.time()
        dtype = torch.bfloat16 if selected_dtype == "bfloat16" else torch.float16
        image = None
        gen_s = 0
        status = "ok"
        try:
            out = pipe(
                prompt=shot["prompt_klein"],
                width=W,
                height=H,
                num_inference_steps=STEPS,
                guidance_scale=GUIDANCE,
                generator=torch.manual_seed(hash(bid) % (2**32)),
                output_type="pil",
            )
            image = out.images[0]
            gen_s = round(time.time() - t0, 2)
            bad = is_black_or_nan(image)
            if bad:
                status = "bad_frame"
                # fallback to float16 if bf16 bad
                if selected_dtype == "bfloat16":
                    print(f"  {bid} bf16 bad frame, retry float16 ...")
                    out = pipe(
                        prompt=shot["prompt_klein"],
                        width=W,
                        height=H,
                        num_inference_steps=STEPS,
                        guidance_scale=GUIDANCE,
                        generator=torch.manual_seed(hash(bid) % (2**32)),
                        output_type="pil",
                    )
                    image = out.images[0]
                    gen_s = round(time.time() - t0, 2)
                    bad = is_black_or_nan(image)
                    status = "ok" if not bad else "bad_frame"
                    if not bad:
                        print(f"  {bid} float16 OK")
        except Exception as exc:
            gen_s = round(time.time() - t0, 2)
            status = f"exception: {exc}"
            image = None
            print(f"  {bid} EXCEPTION: {exc}")

        if image is not None and status == "ok":
            fpath = FRAME_DIR / f"s{shot['section']:02d}_{bid}.png"
            image.save(fpath)
            print(f"  {bid} OK -> {fpath.name} ({gen_s}s)")
            results["shots"].append({
                "bit_id": bid,
                "section": shot["section"],
                "start": shot["start"],
                "end": shot["end"],
                "text": shot["text"],
                "prompt_klein": shot["prompt_klein"],
                "host_in_frame": shot.get("host_in_frame", False),
                "file": str(fpath),
                "status": "ok",
                "gen_seconds": gen_s,
                "seed": hash(bid) % (2**32),
            })
        else:
            print(f"  {bid} FAILED: {status}")
            results["shots"].append({
                "bit_id": bid,
                "section": shot["section"],
                "start": shot["start"],
                "end": shot["end"],
                "text": shot["text"],
                "prompt_klein": shot["prompt_klein"],
                "host_in_frame": shot.get("host_in_frame", False),
                "file": None,
                "status": "failed",
                "reason": status,
                "gen_seconds": gen_s if image is None else None,
            })

    peak_gen = peak_mb()
    results["peak_vram_mb_overall"] = max(results["peak_vram_mb_after_load"], peak_gen)
    results["peak_vram_gb_overall"] = round(
        results["peak_vram_mb_overall"] / 1024, 2
    )
    results["total_vram_gb"] = env_info().get("total_vram_gb", 0)
    results["finished_utc"] = now()
    ok_count = sum(1 for s in results["shots"] if s["status"] == "ok")
    results["status"] = "completed"
    results["shots_ok"] = ok_count
    results["shots_total"] = len(results["shots"])
    print(f"RESULT: {ok_count}/{len(results['shots'])} OK, "
          f"peak VRAM {results['peak_vram_gb_overall']} GB, dtype={selected_dtype}")
    (OUT / "results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False)
    )
    print(f"All outputs in {OUT}")


if __name__ == "__main__":
    main()
