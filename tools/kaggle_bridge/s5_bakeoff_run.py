#!/usr/bin/env python3
"""S5 bake-off Kaggle-side runner: ONE model per kernel run.

Rules (S5-2):
- fp16 only (torch.float16); NO bitsandbytes; NO CPU fallback (CUDA required).
- released diffusers only (no git main); matching transformers.
- Z-Image: `from diffusers import ZImagePipeline` is verified BEFORE any
  generation. Two install attempts max, then the model is BLOCKED with the
  exact import error (never a silent skip).
- klein: on CUDA OOM, enable_model_cpu_offload() once and retry that image.
- Records per model: load_seconds, steady-state s/image, peak VRAM,
  black/NaN/OOM counts, exact package versions.
- Images are named by neutral render_id (blind pack); the mapping lives in the
  repo, never in the kernel output.

Inputs: JOB_EMBEDDED (embedded by scripts/s5_push_bakeoff.py):
  job_id, model, model_id, pipeline_class, revision, vae_model_id,
  width, height, renders[]: [{render_id, scene_id, variant, prompt,
  negative_prompt, guidance_scale, steps, seed}]
Outputs: /kaggle/working/<job_id>/manifest.json, images/<render_id>.png,
         status.txt (+ traceback_*.txt on error)
"""
from __future__ import annotations

import hashlib
import importlib.metadata as md
import json
import os
import statistics
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

OUT_DIR_NAME = os.environ.get("S5_OUT_DIR", "s5_bakeoff")
OUT = Path("/kaggle/working") / OUT_DIR_NAME
IMAGES_DIR = OUT / "images"

JOB_EMBEDDED = None

# Pipeline classes whose import decides whether the installed release is usable.
PROBE_CLASSES = {
    "sdxl": ["StableDiffusionXLPipeline"],
    "klein": ["Flux2Pipeline"],
    "zimage": ["ZImagePipeline"],
}

# Two install attempts maximum per model (S5 stop rule).
ATTEMPTS_COMMON = [
    {"diffusers": ">=0.36,<0.37", "transformers": ">=4.57,<5"},
    {"diffusers": ">=0.41", "transformers": ">=4.57,<6"},
]
# Z-Image ships in a newer release than SDXL/klein need, so it goes straight to
# the newest release on attempt 1 and only falls back to the older release.
ATTEMPTS_ZIMAGE = [
    {"diffusers": ">=0.41", "transformers": ">=4.57,<6"},
    {"diffusers": ">=0.41", "transformers": ">=4.57,<5"},
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


def _versions() -> Dict[str, Optional[str]]:
    out: Dict[str, Optional[str]] = {}
    for pkg in ("diffusers", "transformers", "huggingface_hub", "torch", "accelerate"):
        try:
            out[pkg] = md.version(pkg)
        except Exception:  # noqa: BLE001 - missing package is data, not failure
            out[pkg] = None
    try:
        import torch
        out["torch_cuda"] = getattr(torch.version, "cuda", None)
        out["gpu"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except Exception:  # noqa: BLE001
        out["torch_cuda"] = None
        out["gpu"] = None
    return out


def _pip(args: List[str], timeout: int = 1500) -> Tuple[bool, str]:  # type: ignore[name-defined]
    try:
        p = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", *args],
                           check=False, timeout=timeout, capture_output=True, text=True)
        return p.returncode == 0, (p.stderr or "")[-2000:]
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _import_probe(module_attr: List[str]) -> Optional[str]:
    """Return None if the attribute imports, else the exact error string."""
    code = (
        "import diffusers, sys\n"
        f"names = {module_attr!r}\n"
        "err = None\n"
        "for n in names:\n"
        "    try:\n"
        "        obj = getattr(diffusers, n)\n"
        "        print('OK', n, obj)\n"
        "        sys.exit(0)\n"
        "    except Exception as e:\n"
        "        err = f'{type(e).__name__}: {e}'\n"
        "print('IMPORT_FAIL', err)\n"
        "sys.exit(1)\n"
    )
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       timeout=600)
    if p.returncode == 0:
        return None
    tail = ((p.stdout or "") + (p.stderr or "")).strip().splitlines()[-1:]
    return tail[0] if tail else "import failed with no output"


def install_and_probe(classes: List[str],
                      attempts: Optional[List[Dict[str, str]]] = None,
                      ) -> Tuple[bool, Dict[str, Any]]:
    """Install the pinned stack (2 attempts max) and verify the pipeline class."""
    log: Dict[str, Any] = {"attempts": []}
    for i, pin in enumerate(attempts or ATTEMPTS_COMMON, start=1):
        pkgs = [f"diffusers{pin['diffusers']}", f"transformers{pin['transformers']}",
                "huggingface-hub>=0.34,<2", "accelerate>=1.0"]
        ok, err = _pip(pkgs)
        probe_err = _import_probe(classes) if ok else f"pip failed: {err}"
        log["attempts"].append({"attempt": i, "pins": pin, "pip_ok": ok,
                                "import_error": probe_err})
        if ok and probe_err is None:
            log["used_attempt"] = i
            return True, log
        print(f"[install attempt {i} failed] {probe_err}", file=sys.stderr)
    return False, log


def _black_or_nan(img) -> Tuple[bool, bool]:
    import numpy as np
    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    nonfinite = bool((~np.isfinite(arr)).any())
    black = bool(arr.max() < 8.0)
    return black, nonfinite


def main() -> None:
    global OUT, IMAGES_DIR
    OUT.mkdir(parents=True, exist_ok=True)
    job = globals().get("JOB_EMBEDDED")
    if not isinstance(job, dict):
        _blocked("JOB_EMBEDDED not set; runner cannot run", code=1)

    model: str = job["model"]
    OUT = Path("/kaggle/working") / f"s5_bakeoff_{model}"
    IMAGES_DIR = OUT / "images"
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    # --- verify the pipeline class BEFORE generating ----------------------
    # Z-Image is strict: no ZImagePipeline -> BLOCKED (no substitute model).
    # klein prefers Flux2Pipeline but may fall back to FluxPipeline if only
    # that class exists; SDXL has a single class.
    probe_classes = PROBE_CLASSES[model]
    attempts = ATTEMPTS_ZIMAGE if model == "zimage" else ATTEMPTS_COMMON
    ok, log = install_and_probe(probe_classes, attempts)
    (OUT / "install_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    if not ok and model == "zimage":
        _blocked("ZImagePipeline import failed after 2 attempts: "
                 f"{log['attempts'][-1]['import_error']}")

    import torch  # noqa: E402 - installed above
    import diffusers  # noqa: E402

    if not torch.cuda.is_available():
        _blocked("CUDA not available; NO CPU fallback permitted (S5-2 rule)")

    # klein: FLUX.2 uses Flux2Pipeline when the release has it, else FluxPipeline.
    pipe_cls = None
    declared = job.get("pipeline_class")
    candidates = [declared] if declared else []
    if model == "klein":
        # vendor class first (S7 finding: Flux2KleinPipeline is the FLUX.2 klein
        # pipeline; Flux2Pipeline/FluxPipeline kept only as ordered fallbacks)
        candidates = ["Flux2KleinPipeline", "Flux2Pipeline", "FluxPipeline"]
    for name in candidates:
        try:
            pipe_cls = getattr(diffusers, name)
            declared = name
            break
        except AttributeError:
            continue
    if pipe_cls is None:
        _blocked(f"none of pipeline classes {candidates} exist in diffusers "
                 f"{md.version('diffusers')}")

    width = int(job.get("width", 1024))
    height = int(job.get("height", 1024))
    renders: List[Dict[str, Any]] = job.get("renders", [])
    if not renders:
        _blocked("no renders in JOB_EMBEDDED", code=1)

    offload_enabled = False
    torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    try:
        kwargs: Dict[str, Any] = {}
        if job.get("revision"):
            kwargs["revision"] = job["revision"]
        if model in {"klein", "zimage"}:
            # vendor card: avoid the meta-tensor path that broke S5's klein run
            kwargs["low_cpu_mem_usage"] = False
        if job.get("vae_model_id"):
            from diffusers import AutoencoderKL
            kwargs["vae"] = AutoencoderKL.from_pretrained(
                job["vae_model_id"], torch_dtype=torch.float16)
        pipe = pipe_cls.from_pretrained(job["model_id"], torch_dtype=torch.float16, **kwargs)
        if model == "klein":
            # weights stream to the GPU per module: compute stays on CUDA, no CPU
            # inference. Avoids `Cannot copy out of meta tensor` on pipe.to().
            pipe.enable_model_cpu_offload()
            offload_enabled = True
        else:
            pipe.to("cuda")
        pipe.set_progress_bar_config(disable=True)
    except Exception:  # noqa: BLE001
        tb = traceback.format_exc()
        (OUT / "traceback_load.txt").write_text(tb, encoding="utf-8")
        print(tb, file=sys.stderr)
        _blocked(f"model load failed: {tb.strip().splitlines()[-1]}", code=2)
    load_seconds = time.perf_counter() - t0

    images: List[Dict[str, Any]] = []
    oom_count = black_count = nan_count = 0
    t_total0 = time.perf_counter()

    for rj in renders:
        rid = rj["render_id"]
        call: Dict[str, Any] = dict(
            prompt=rj["prompt"],
            height=height,
            width=width,
            num_inference_steps=int(rj.get("steps") or 28),
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
            if not offload_enabled:
                # one documented OOM fallback: CPU offload, then retry this image
                pipe.enable_model_cpu_offload()
                offload_enabled = True
            try:
                img = pipe(**call).images[0]
            except Exception:  # noqa: BLE001
                tb = traceback.format_exc()
                (OUT / f"traceback_{rid}.txt").write_text(tb, encoding="utf-8")
                images.append({"render_id": rid, "file": None, "seed": rj["seed"],
                               "error": "oom_after_offload"})
                continue
        except Exception:  # noqa: BLE001
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
        fpath = IMAGES_DIR / fname
        img.save(fpath, optimize=True)
        data = fpath.read_bytes()
        images.append({
            "render_id": rid,
            "scene_id": rj["scene_id"],
            "variant": rj["variant"],
            "file": fname,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "width": img.size[0],
            "height": img.size[1],
            "seed": int(rj["seed"]),
            "steps": int(rj.get("steps") or 0),
            "guidance_scale": rj.get("guidance_scale"),
            "prompt": rj["prompt"],
            "seconds": round(secs, 4),
            "black": black,
            "nonfinite": nonfinite,
        })

    gpu_seconds = time.perf_counter() - t_total0
    try:
        peak_vram_mb = round(torch.cuda.max_memory_allocated() / (1024 * 1024), 2)
    except Exception:  # noqa: BLE001
        peak_vram_mb = None

    times = [i["seconds"] for i in images if i.get("file")]
    steady = round(statistics.median(times[1:]), 3) if len(times) > 1 else (
        round(times[0], 3) if times else None)

    versions = _versions()
    manifest = {
        "job_id": job.get("job_id"),
        "model": model,
        "model_id": job.get("model_id"),
        "pipeline_class": declared,
        "dtype": "float16",
        "bitsandbytes": False,
        "cpu_fallback": False,
        "cpu_offload_used": offload_enabled,
        "width": width,
        "height": height,
        "requested": len(renders),
        "generated": len(times),
        "load_seconds": round(load_seconds, 3),
        "steady_state_sec_per_image": steady,
        "mean_sec_per_image": round(statistics.mean(times), 3) if times else None,
        "gpu_seconds": round(gpu_seconds, 2),
        "peak_vram_mb": peak_vram_mb,
        "oom_count": oom_count,
        "black_count": black_count,
        "nan_count": nan_count,
        "versions": versions,
        "install_log": (json.loads((OUT / "install_log.json").read_text())
                        if (OUT / "install_log.json").is_file() else None),
        "created_utc": now_utc(),
        "images": images,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if len(times) < len(renders):
        _status(f"PARTIAL: generated {len(times)}/{len(renders)}; see manifest.json")
        print(f"s5 {model} PARTIAL: {len(times)}/{len(renders)}", file=sys.stderr)
        sys.exit(1)

    _status("COMPLETE")
    print(f"s5 {model} done: {len(times)} images, "
          f"{steady} s/img steady, peak VRAM {peak_vram_mb} MB, "
          f"load {load_seconds:.1f}s")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001 - full traceback saved to kernel output
        tb = traceback.format_exc()
        try:
            OUT.mkdir(parents=True, exist_ok=True)
            (OUT / "traceback_fatal.txt").write_text(tb, encoding="utf-8")
            _status(f"FAILED: {tb.strip().splitlines()[-1]}")
        except Exception:  # noqa: BLE001
            pass
        print(tb, file=sys.stderr)
        sys.exit(1)
