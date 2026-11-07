#!/usr/bin/env python3
"""S7 bake-off Kaggle-side runner: ONE model per kernel run.

Rules (S7):
- fp16 only (torch.float16); NO bitsandbytes; NO CPU fallback (CUDA required,
  the job is BLOCKED instead). Model CPU offload is allowed (compute stays on
  the GPU) and is recorded in the manifest.
- Released diffusers first; git-main diffusers only as a later, documented
  rung of the install ladder. transformers is pinned to match.
- The pipeline class is verified with `python -c` BEFORE any generation. The
  job names its candidate classes; the first one that imports is used.
- Per-model install ladder (max 4 rungs). Every rung records the exact
  installed versions, so a failure is diagnosable.
- Wall-clock cap per model (90 min by default): generation stops, a partial
  manifest is written and the status is PARTIAL (never a silent hang).
- Records per model: load_seconds, steady-state s/image (first warm-up
  excluded), usable images per minute, peak VRAM, black/NaN/OOM counts,
  attempts needed, exact package versions.
- Images are named by neutral render_id (blind pack); the mapping lives in
  the repo, never in the kernel output.

Inputs: JOB_EMBEDDED (embedded by scripts/s7_push_bakeoff.py):
  job_id, model, model_id, pipeline_candidates[], vae_model_id, width, height,
  renders[]: [{render_id, scene_id, variant, prompt, negative_prompt,
               guidance_scale, steps, seed}],
  install_ladder[] (optional override), load_config (optional override),
  max_wall_seconds (optional override)
Outputs: /kaggle/working/s7_bakeoff_<model>/manifest.json, images/<render_id>.png,
         status.txt (+ traceback_*.txt on error), install_log.json
"""
from __future__ import annotations

import hashlib
import importlib.metadata as md
import json
import os
import platform
import statistics
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

OUT = Path("/kaggle/working")
JOB_EMBEDDED = None

# Per-model wall-clock cap (S7: 90 minutes per model).
MAX_WALL_SECONDS = 5400

# --- install ladders -------------------------------------------------------
# Each rung is a materially different, pinned stack. Rung 1 is always a
# released diffusers; git-main diffusers only appears as a later rung.
#
# Measured constraints (S7 SDXL run 1 + vendor cards):
#   * diffusers 0.41.0 requires huggingface-hub>=1.32,<2.0, so it can only be
#     paired with transformers 5.x (transformers 4.57.x pins hub<1.0) ->
#     `released_041_x4` is a dead rung (pip ResolutionImpossible).
#   * diffusers 0.41.0 imports `torchao.quantization.FqnToConfig`; the Kaggle
#     kernel's pre-installed torchao is too new and no longer exports it ->
#     torchao==0.15.0 is pinned in the 0.41.0 stacks.
#   * diffusers 0.37.0 requires hub>=0.34,<2.0 and ships BOTH
#     Flux2KleinPipeline and ZImagePipeline -> the primary rung for
#     klein and Z-Image.
RELEASED_STACKS = {
    "released_041_x4": {
        "note": "released diffusers 0.41.0 + transformers 4.x + hub <1.0 "
                "(DEAD: diffusers 0.41 needs hub>=1.32)",
        "pip_args": [
            "diffusers==0.41.0", "transformers==4.57.6",
            "huggingface-hub>=0.34,<1.0", "accelerate>=1.10", "safetensors>=0.4",
        ],
    },
    "released_041_x5": {
        "note": "released diffusers 0.41.0 + transformers 5.x + hub 1.x "
                "(DEAD on this kernel: torchao.quantization.FqnToConfig)",
        "pip_args": [
            "diffusers==0.41.0", "transformers==5.20.2",
            "huggingface-hub>=1.0,<2.0", "accelerate>=1.10", "safetensors>=0.4",
        ],
    },
    "released_041_x5_ao": {
        "note": "released diffusers 0.41.0 + transformers 5.x + torchao 0.15.0 pin",
        "pip_args": [
            "diffusers==0.41.0", "transformers==5.20.2",
            "huggingface-hub>=1.0,<2.0", "torchao==0.15.0",
            "accelerate>=1.10", "safetensors>=0.4",
        ],
    },
    "released_037_x4": {
        "note": "released diffusers 0.37.0 + transformers 4.x + hub <1.0 "
                "(ships Flux2KleinPipeline and ZImagePipeline)",
        "pip_args": [
            "diffusers==0.37.0", "transformers==4.57.6",
            "huggingface-hub>=0.34,<1.0", "accelerate>=1.10", "safetensors>=0.4",
        ],
    },
    "released_037_x5": {
        "note": "released diffusers 0.37.0 + transformers 5.x + hub 1.x",
        "pip_args": [
            "diffusers==0.37.0", "transformers==5.20.2",
            "huggingface-hub>=1.0,<2.0", "accelerate>=1.10", "safetensors>=0.4",
        ],
    },
    "released_036_x4": {
        "note": "older released diffusers 0.36.0 + transformers 4.x",
        "pip_args": [
            "diffusers==0.36.0", "transformers==4.57.6",
            "huggingface-hub>=0.34,<1.0", "accelerate>=1.10", "safetensors>=0.4",
        ],
    },
    "git_main_x4": {
        "note": "git-main diffusers + transformers 4.x (vendor-card path)",
        "pip_args": [
            "git+https://github.com/huggingface/diffusers.git",
            "transformers==4.57.6", "huggingface-hub>=0.34,<1.0",
            "accelerate>=1.10", "safetensors>=0.4",
        ],
    },
    "git_main_x5_ao": {
        "note": "git-main diffusers + transformers 5.x + torchao 0.15.0 pin",
        "pip_args": [
            "git+https://github.com/huggingface/diffusers.git",
            "transformers==5.20.2", "huggingface-hub>=1.0,<2.0",
            "torchao==0.15.0", "accelerate>=1.10", "safetensors>=0.4",
        ],
    },
}

# Pipeline classes per model. The FIRST importable class wins.
PIPELINE_CANDIDATES = {
    "sdxl": ["StableDiffusionXLPipeline"],
    # The FLUX.2-klein-4B card uses Flux2KleinPipeline (the HF model page is
    # tagged Flux2KleinPipeline); Flux2Pipeline is the FLUX.2-dev class and
    # leaves the Qwen3 text encoder on the meta device -> "Cannot copy out of
    # meta tensor" (observed on the S5 klein run).
    "klein": ["Flux2KleinPipeline", "Flux2Pipeline", "FluxPipeline"],
    "zimage": ["ZImagePipeline"],
}

# How each model is loaded and called (vendor-card driven).
LOAD_CONFIG = {
    "sdxl": {
        "offload": False,
        "low_cpu_mem_usage": None,
        "extra_kwargs": {"add_watermarker": False},
        "guidance_override": None,
    },
    "klein": {
        # vendor card: pipe.enable_model_cpu_offload()
        "offload": True,
        "low_cpu_mem_usage": None,
        "extra_kwargs": {},
        "guidance_override": 1.0,
    },
    "zimage": {
        # vendor card: low_cpu_mem_usage=False
        "offload": False,
        "low_cpu_mem_usage": False,
        "extra_kwargs": {},
        "guidance_override": None,
    },
}

DEFAULT_LADDERS = {
    # SDXL already ran: its ladder is kept as the historical record (rung 3,
    # released_036_x4, is the one that worked).
    "sdxl": ["released_036_x4", "released_037_x4", "released_041_x5_ao", "git_main_x4"],
    "klein": ["released_037_x4", "released_037_x5", "released_041_x5_ao", "git_main_x5_ao"],
    "zimage": ["released_037_x4", "released_037_x5", "released_041_x5_ao", "git_main_x5_ao"],
}


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
    for pkg in ("diffusers", "transformers", "huggingface_hub", "torch", "accelerate",
                "safetensors", "numpy", "pillow"):
        try:
            out[pkg] = md.version(pkg)
        except Exception:  # noqa: BLE001 - a missing package is data, not failure
            out[pkg] = None
    try:
        import torch
        out["torch_cuda"] = getattr(torch.version, "cuda", None)
        out["gpu"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except Exception:  # noqa: BLE001
        out["torch_cuda"] = None
        out["gpu"] = None
    out["python"] = platform.python_version()
    return out


def _pip(args: List[str], timeout: int = 1500) -> Tuple[bool, str]:
    try:
        p = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "--no-cache-dir", *args],
            check=False, timeout=timeout, capture_output=True, text=True)
        return p.returncode == 0, (p.stderr or "")[-2000:]
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _probe_classes(classes: List[str]) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    """Import diffusers in a subprocess and return (class_found, error, versions).

    The probe runs in its own interpreter so a broken install cannot poison
    the runner (the S5 lesson: verify the import before generating).
    """
    code = (
        "import importlib.metadata as md, json\n"
        "try:\n"
        "    import diffusers\n"
        "except Exception as e:\n"
        "    print('PROBE_FAIL ' + type(e).__name__ + ': ' + str(e)); raise SystemExit(2)\n"
        "names = " + repr(list(classes)) + "\n"
        "found = None\n"
        "for n in names:\n"
        "    if hasattr(diffusers, n):\n"
        "        found = n; break\n"
        "vers = {}\n"
        "for p in ('diffusers','transformers','huggingface_hub','accelerate','torch'):\n"
        "    try: vers[p] = md.version(p)\n"
        "    except Exception: vers[p] = None\n"
        "print('PROBE_OK ' + (found or 'NONE') + ' ' + json.dumps(vers))\n"
    )
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       timeout=900)
    out = ((p.stdout or "") + (p.stderr or "")).strip().splitlines()
    versions: Dict[str, Any] = {}
    found: Optional[str] = None
    error: Optional[str] = None
    for line in out:
        if line.startswith("PROBE_OK "):
            parts = line.split(" ", 2)
            found = None if parts[1] == "NONE" else parts[1]
            try:
                versions = json.loads(parts[2])
            except Exception:  # noqa: BLE001
                versions = {}
        elif line.startswith("PROBE_FAIL "):
            error = line
    if found is None and error is None:
        error = out[-1] if out else "probe produced no output"
    return found, error, versions


def install_and_probe(model: str, ladder: List[str]) -> Tuple[bool, Dict[str, Any]]:
    """Walk the install ladder until the model's pipeline class imports."""
    log: Dict[str, Any] = {"ladder": [], "rungs": []}
    candidates = PIPELINE_CANDIDATES[model]
    for i, rung_name in enumerate(ladder, start=1):
        stack = RELEASED_STACKS[rung_name]
        ok, err = _pip(list(stack["pip_args"]))
        found, probe_err, vers = (None, "pip failed: " + err, {}) if not ok else \
            _probe_classes(candidates)
        log["rungs"].append({
            "rung": i,
            "stack": rung_name,
            "note": stack["note"],
            "pip_args": stack["pip_args"],
            "pip_ok": ok,
            "import_found": found,
            "import_error": probe_err,
            "versions_after": vers,
        })
        if ok and found:
            log["used_rung"] = i
            log["used_stack"] = rung_name
            log["pipeline_class"] = found
            return True, log
        print(f"[install rung {i} failed: {rung_name}] {probe_err}", file=sys.stderr)
    return False, log


def _black_or_nan(img) -> Tuple[bool, bool]:
    import numpy as np
    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    nonfinite = bool((~np.isfinite(arr)).any())
    black = bool(arr.max() < 8.0)
    return black, nonfinite


def _load_pipeline(job: Dict[str, Any], model: str, pipe_cls, cfg: Dict[str, Any]):
    """Load the pipeline. Returns (pipeline, load_notes)."""
    import torch
    kwargs: Dict[str, Any] = {"torch_dtype": torch.float16}
    if cfg.get("low_cpu_mem_usage") is not None:
        kwargs["low_cpu_mem_usage"] = bool(cfg["low_cpu_mem_usage"])
    for k, v in (cfg.get("extra_kwargs") or {}).items():
        kwargs[k] = v
    if job.get("revision"):
        kwargs["revision"] = job["revision"]
    notes: Dict[str, Any] = {}
    if job.get("vae_model_id"):
        from diffusers import AutoencoderKL
        kwargs["vae"] = AutoencoderKL.from_pretrained(
            job["vae_model_id"], torch_dtype=torch.float16)
        notes["vae"] = job["vae_model_id"]
    pipe = pipe_cls.from_pretrained(job["model_id"], **kwargs)
    if cfg.get("force_upcast_vae"):
        # fp16 VAE decoders overflow to NaN on the 16-channel latents these
        # models use; diffusers' own guidance for the SD3/Flux lineage is
        # `pipe.vae.config.force_upcast = True` (decode in fp32).
        vae = getattr(pipe, "vae", None)
        if vae is not None and hasattr(vae, "config"):
            vae.config.force_upcast = True
            notes["vae_force_upcast"] = True
        else:
            notes["vae_force_upcast"] = "no vae.config on this pipeline"
    if cfg.get("vae_fp32"):
        # The config flag above only helps when the pipeline implements
        # `upcast_vae()`; ZImagePipeline does not, so cast the decoder
        # explicitly (the DiT stays fp16 - the S7 brief mandates fp16).
        # Done BEFORE the offload hooks are installed: moving a module that
        # already carries an offload hook raises inside diffusers.
        vae = getattr(pipe, "vae", None)
        if vae is not None:
            vae.to(dtype=torch.float32)
            notes["vae_fp32"] = True
        else:
            notes["vae_fp32"] = "no vae on this pipeline"
    if cfg.get("offload"):
        pipe.enable_model_cpu_offload()
        notes["model_cpu_offload"] = True
    else:
        pipe.to("cuda")
        notes["model_cpu_offload"] = False
    pipe.set_progress_bar_config(disable=True)
    return pipe, notes


def main() -> None:
    global OUT
    job = JOB_EMBEDDED
    if isinstance(job, str):
        job = json.loads(job)
    if not isinstance(job, dict):
        _blocked("JOB_EMBEDDED not set; runner cannot run", code=1)

    model: str = job["model"]
    OUT = Path("/kaggle/working") / f"s7_bakeoff_{model}"
    images_dir = OUT / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    ladder: List[str] = job.get("install_ladder") or DEFAULT_LADDERS[model]
    max_wall = int(job.get("max_wall_seconds") or MAX_WALL_SECONDS)
    cfg = dict(LOAD_CONFIG[model])
    cfg.update(job.get("load_config") or {})

    # --- install + verify the pipeline class BEFORE generating --------------
    ok, log = install_and_probe(model, ladder)
    (OUT / "install_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    if not ok:
        last = log["rungs"][-1] if log["rungs"] else {}
        _blocked("no install rung gave an importable pipeline class; "
                 f"last error: {last.get('import_error')}; "
                 f"versions: {json.dumps(log['rungs'][-1]['versions_after'] if log['rungs'] else {})}")

    import torch  # noqa: E402 - installed above
    import diffusers  # noqa: E402

    if not torch.cuda.is_available():
        _blocked("CUDA not available; NO CPU fallback permitted (S7 rule)")

    declared = log.get("pipeline_class")
    pipe_cls = getattr(diffusers, declared, None)
    if pipe_cls is None:
        _blocked(f"pipeline class {declared!r} missing from diffusers "
                 f"{md.version('diffusers')}")

    width = int(job.get("width", 1024))
    height = int(job.get("height", 1024))
    renders: List[Dict[str, Any]] = job.get("renders") or []
    if not renders:
        _blocked("no renders in JOB_EMBEDDED", code=1)

    torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    try:
        pipe, load_notes = _load_pipeline(job, model, pipe_cls, cfg)
    except Exception:  # noqa: BLE001
        tb = traceback.format_exc()
        (OUT / "traceback_load.txt").write_text(tb, encoding="utf-8")
        print(tb, file=sys.stderr)
        _blocked(f"model load failed: {tb.strip().splitlines()[-1]}", code=2)
    load_seconds = time.perf_counter() - t0

    offload_used = bool(load_notes.get("model_cpu_offload"))
    images: List[Dict[str, Any]] = []
    oom_count = black_count = nan_count = 0
    t_total0 = time.perf_counter()
    wall_cap_hit = False

    for rj in renders:
        if time.perf_counter() - t_total0 > max_wall:
            wall_cap_hit = True
            print(f"wall-clock cap {max_wall}s reached before {rj['render_id']}",
                  file=sys.stderr)
            break
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
        guidance = cfg.get("guidance_override")
        if guidance is None:
            guidance = rj.get("guidance_scale")
        if guidance is not None:
            call["guidance_scale"] = float(guidance)

        t_start = time.perf_counter()
        try:
            img = pipe(**call).images[0]
        except torch.cuda.OutOfMemoryError:
            oom_count += 1
            torch.cuda.empty_cache()
            if not offload_used:
                try:
                    pipe.enable_model_cpu_offload()
                    offload_used = True
                    load_notes["model_cpu_offload"] = True
                    img = pipe(**call).images[0]
                except Exception:  # noqa: BLE001
                    tb = traceback.format_exc()
                    (OUT / f"traceback_{rid}.txt").write_text(tb, encoding="utf-8")
                    images.append({"render_id": rid, "file": None, "seed": rj["seed"],
                                   "error": "oom_after_offload"})
                    continue
            else:
                tb = traceback.format_exc()
                (OUT / f"traceback_{rid}.txt").write_text(tb, encoding="utf-8")
                images.append({"render_id": rid, "file": None, "seed": rj["seed"],
                               "error": "oom_with_offload"})
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
        fpath = images_dir / fname
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
            "guidance_scale": guidance,
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
    warmup_excluded = times[1:] if len(times) > 1 else times
    steady = round(statistics.mean(warmup_excluded), 3) if warmup_excluded else None
    steady_median = (round(statistics.median(warmup_excluded), 3)
                      if warmup_excluded else None)
    usable_per_min = (round(len(times) / (gpu_seconds / 60.0), 2)
                      if times and gpu_seconds > 0 else None)

    versions = _versions()
    manifest = {
        "job_id": job.get("job_id"),
        "model": model,
        "model_id": job.get("model_id"),
        "pipeline_class": declared,
        "dtype": "float16",
        "bitsandbytes": False,
        "cpu_fallback": False,
        "cpu_offload_used": offload_used,
        "width": width,
        "height": height,
        "requested": len(renders),
        "generated": len(times),
        "load_seconds": round(load_seconds, 3),
        "steady_state_sec_per_image": steady,
        "steady_median_sec_per_image": steady_median,
        "mean_sec_per_image": round(statistics.mean(times), 3) if times else None,
        "usable_images_per_minute": usable_per_min,
        "gpu_seconds": round(gpu_seconds, 2),
        "peak_vram_mb": peak_vram_mb,
        "oom_count": oom_count,
        "black_count": black_count,
        "nan_count": nan_count,
        "wall_cap_seconds": max_wall,
        "wall_cap_hit": wall_cap_hit,
        "load_notes": load_notes,
        "versions": versions,
        "install_log": log,
        "created_utc": now_utc(),
        "images": images,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if len(times) < len(renders):
        reason = "wall-clock cap reached" if wall_cap_hit else "some images failed"
        _status(f"PARTIAL: generated {len(times)}/{len(renders)} ({reason}); "
                f"see manifest.json")
        print(f"s7 {model} PARTIAL: {len(times)}/{len(renders)} ({reason})",
              file=sys.stderr)
        sys.exit(1)

    _status("COMPLETE")
    print(f"s7 {model} done: {len(times)} images, {steady} s/img steady, "
          f"peak VRAM {peak_vram_mb} MB, load {load_seconds:.1f}s")


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
