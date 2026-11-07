#!/usr/bin/env python3
"""S14 smoke-test Kaggle-side runner: ONE model per kernel run.

Rules (S14):
- fp16 only (torch.float16); NO bitsandbytes; NO CPU fallback (CUDA required,
  the job is BLOCKED instead).
- GPU precheck: must be T4 (compute capability 7.5); fp16 supported, bf16 NOT
  supported. Anything else -> BLOCKED.
- ONE model per kernel run (never stack dependency sets in one kernel).
- 3 fixed seeds x 512x512, one simple prompt, checkpoint's own default
  scheduler/steps.
- Saves the model license file + revision SHA next to the results.
- Per-image: load_time, warm sec/image (first excluded), peak VRAM
  allocated/reserved, black_or_nan flag, output file, error text.
- If a model fails to import/load/run in fp16 -> HARDWARE FAIL with exact
  error, one retry max, then move on.
- Writes /kaggle/working/DONE.json (waiting rule).

Inputs: JOB_EMBEDDED:
  job_id, model, model_id, license_id, pipeline_candidates[], width, height,
  seeds[], prompt, max_wall_seconds
Outputs: /kaggle/working/s14_smoke_<model>/manifest.json, images/<seed>.png,
         license.txt, revision.txt, status.txt (+ traceback_*.txt on error),
         install_log.json, DONE.json
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

MAX_WALL_SECONDS = 3600

PROMPT = ("flat vector illustration of an alien deep-sea creature, exactly six "
          "separate tendrils, two pairs of fins, plain light background, "
          "empty lower fifth, no text")
WIDTH = 512
HEIGHT = 512
SEEDS = [101, 202, 303]


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _status(text: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "status.txt").write_text(text.strip() + "\n", encoding="utf-8")


def _write_traceback(exc: Exception, tag: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"traceback_{tag}.txt").write_text(
        traceback.format_exc(), encoding="utf-8")


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
            payload["seconds_total"] = man.get("seconds_total")
            ok = man.get("generated") == man.get("requested")
            payload["status"] = "ok" if ok else "error"
            if not ok:
                payload["errors"].append(
                    f"partial: {man.get('generated')}/{man.get('requested')}")
        else:
            payload["errors"].append("manifest.json missing")
    except Exception as exc:  # noqa: BLE001
        payload["errors"].append(f"done.json could not read manifest: {exc}")
    try:
        (OUT / "DONE.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def _versions() -> Dict[str, Optional[str]]:
    out: Dict[str, Optional[str]] = {}
    for pkg in ("diffusers", "transformers", "huggingface_hub", "torch",
                "accelerate", "safetensors", "numpy", "Pillow"):
        try:
            out[pkg] = md.version(pkg)
        except Exception:  # noqa: BLE001
            out[pkg] = None
    try:
        import torch  # noqa: F401
        out["torch_cuda"] = getattr(torch.version, "cuda", None)
        out["gpu"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        out["cc_major"], out["cc_minor"] = (None, None)
        if torch.cuda.is_available():
            cap = torch.cuda.get_device_capability(0)
            out["cc_major"], out["cc_minor"] = cap
    except Exception:  # noqa: BLE001
        out["torch_cuda"] = None
        out["gpu"] = None
        out["cc_major"] = None
        out["cc_minor"] = None
    out["python"] = platform.python_version()
    return out


def _pip(args: List[str], timeout: int = 1500) -> Tuple[bool, str]:
    try:
        p = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "--no-cache-dir",
             *args],
            check=False, timeout=timeout, capture_output=True, text=True)
        return p.returncode == 0, (p.stderr or "")[-2000:]
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _probe_classes(classes: List[str]) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    code = (
        "import importlib.metadata as md, json\n"
        "try:\n    import diffusers\n"
        "except Exception as e:\n    print('PROBE_FAIL ' + type(e).__name__ + ': ' + str(e)); raise SystemExit(2)\n"
        "names = " + repr(list(classes)) + "\n"
        "found = None\n"
        "for n in names:\n    if hasattr(diffusers, n): found = n; break\n"
        "vers = {}\n"
        "for p in ('diffusers','transformers','huggingface_hub','accelerate','torch'):\n"
        "    try: vers[p] = md.version(p)\n    except Exception: vers[p] = None\n"
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


def _model_revision(model_id: Optional[str]) -> Optional[str]:
    if not model_id:
        return None
    try:
        from huggingface_hub import HfApi
        return HfApi().model_info(model_id).sha
    except Exception:  # noqa: BLE001 - revision is provenance, never fatal
        return None


def _model_license(model_id: Optional[str]) -> Optional[str]:
    if not model_id:
        return None
    try:
        from huggingface_hub import HfApi
        info = HfApi().model_info(model_id)
        return info.license
    except Exception:  # noqa: BLE001
        return None


def _black_or_nan(img) -> Tuple[bool, bool]:
    import numpy as np
    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    nonfinite = bool((~np.isfinite(arr)).any())
    black = bool(arr.max() < 8.0)
    return black, nonfinite


def _precheck_gpu() -> Tuple[bool, str, Dict[str, Any]]:
    """Return (ok, reason, info). Must be T4, cc 7.5, fp16, no bf16."""
    import torch  # noqa: F401
    info: Dict[str, Any] = {}
    if not torch.cuda.is_available():
        return False, "CUDA not available", info
    name = torch.cuda.get_device_name(0)
    cap = torch.cuda.get_device_capability(0)
    cc = f"{cap[0]}.{cap[1]}"
    info["gpu_name"] = name
    info["compute_capability"] = cc
    # fp16 check via tensor creation (works on all torch versions;
    # torch.cuda.is_fp16_supported() does not exist in torch 2.11).
    try:
        _ = torch.zeros(1, device="cuda", dtype=torch.float16)
        info["fp16_supported"] = True
    except Exception:  # noqa: BLE001
        info["fp16_supported"] = False
    # bf16 requires compute capability >= 8.0 (Ampere); T4 is cc 7.5 (Turing)
    # and has no native bf16 regardless of what torch.cuda.is_bf16_supported()
    # reports on some CUDA/driver versions. Base the decision on cc.
    info["bf16_supported"] = bool(cap >= (8, 0) and torch.cuda.is_bf16_supported())
    try:
        import bitsandbytes  # noqa: F401
        info["bitsandbytes"] = "present"
    except Exception:  # noqa: BLE001
        info["bitsandbytes"] = "absent"
    if cap != (7, 5):
        return False, f"GPU is {name} cc {cc}, expected T4 cc 7.5", info
    if not info["fp16_supported"]:
        return False, "fp16 not supported", info
    if info["bf16_supported"] is True:
        return False, "bf16 supported (expected fp16-only T4)", info
    return True, "T4 cc 7.5 fp16-only precheck passed", info


def _load_pipeline(model_id: str, pipe_cls, revision: Optional[str],
                   extra_kwargs: Dict[str, Any],
                   ) -> Tuple[Any, Dict[str, Any]]:
    import torch  # noqa: F401
    import diffusers  # noqa: F401
    kwargs: Dict[str, Any] = {"torch_dtype": torch.float16}
    kwargs.update(extra_kwargs or {})
    if revision:
        kwargs["revision"] = revision
    notes: Dict[str, Any] = {}
    pipe = pipe_cls.from_pretrained(model_id, **kwargs)
    # fp16 only: never pipe.to("cuda") before offload; use enable_model_cpu_offload
    # (compute stays on GPU). No bitsandbytes.
    pipe.enable_model_cpu_offload()
    notes["model_cpu_offload"] = True
    pipe.set_progress_bar_config(disable=True)
    return pipe, notes


def _generate(pipe, prompt: str, seed: int, width: int, height: int,
              num_inference_steps: Optional[int] = None,
              guidance_scale: Optional[float] = None
              ) -> Tuple[Any, float, Dict[str, Any]]:
    import torch  # noqa: F401
    t0 = time.time()
    generator = torch.Generator(device="cuda").manual_seed(seed)
    call: Dict[str, Any] = dict(prompt=prompt, height=height, width=width,
                                generator=generator)
    if num_inference_steps is not None:
        call["num_inference_steps"] = int(num_inference_steps)
    if guidance_scale is not None:
        call["guidance_scale"] = float(guidance_scale)
    image = pipe(**call).images[0]
    secs = time.time() - t0
    notes = {"seed": seed,
             "num_inference_steps": call.get("num_inference_steps"),
             "guidance_scale": call.get("guidance_scale")}
    return image, secs, notes


def main() -> None:
    global OUT
    job = JOB_EMBEDDED
    if isinstance(job, str):
        job = json.loads(job)
    if not isinstance(job, dict):
        _status("BLOCKED: JOB_EMBEDDED not set; runner cannot run")
        _write_done(["JOB_EMBEDDED not set"])
        sys.exit(1)

    model: str = job["model"]
    model_id: str = job["model_id"]
    license_id: str = job.get("license_id") or model_id
    OUT = Path("/kaggle/working") / f"s14_smoke_{model}"
    images_dir = OUT / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    errors: List[str] = []
    versions = _versions()
    (OUT / "versions.json").write_text(json.dumps(versions, indent=2), encoding="utf-8")

    # --- GPU precheck ------------------------------------------------------
    gpu_ok, gpu_reason, gpu_info = _precheck_gpu()
    (OUT / "gpu_precheck.json").write_text(
        json.dumps({"ok": gpu_ok, "reason": gpu_reason, "info": gpu_info},
                   indent=2), encoding="utf-8")
    if not gpu_ok:
        _status(f"BLOCKED: {gpu_reason}")
        _write_done([f"GPU precheck failed: {gpu_reason}"])
        sys.exit(3)

    # bitsandbytes must not be imported/required
    try:
        import bitsandbytes  # noqa: F401
        errors.append("bitsandbytes is importable (S14 forbids it)")
    except Exception:  # noqa: BLE001
        pass  # good

    # --- install + probe pipeline class ------------------------------------
    candidates: List[str] = list(job.get("pipeline_candidates") or [])
    if not candidates:
        _status("BLOCKED: no pipeline_candidates in job")
        _write_done(["no pipeline_candidates"])
        sys.exit(1)
    log: Dict[str, Any] = {"rungs": []}
    # S14 smoke test: single released diffusers stack; no ladder stacking.
    ok_pip, pip_err = _pip(["diffusers==0.37.0", "transformers==4.57.6",
                            "huggingface-hub>=0.34,<1.0", "accelerate>=1.10",
                            "safetensors>=0.4"])
    found, probe_err, vers = (None, "pip failed: " + pip_err, {}) if not ok_pip else \
        _probe_classes(candidates)
    log["rungs"].append({
        "rung": 1, "stack": "released_037_x4",
        "pip_ok": ok_pip, "pip_error": pip_err,
        "import_found": found, "import_error": probe_err,
        "versions_after": vers,
    })
    (OUT / "install_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    if not found:
        msg = (f"HARDWARE FAIL: no importable pipeline class for {model!r}; "
               f"error: {probe_err}; versions: {json.dumps(vers)}")
        _status(msg)
        _write_traceback(RuntimeError(msg), "import")
        errors.append(msg)
        _write_done(errors)
        sys.exit(1)

    import diffusers  # noqa: E402
    pipe_cls = getattr(diffusers, found)

    # --- provenance: license + revision SHA --------------------------------
    license_val = _model_license(license_id)
    revision = _model_revision(model_id)
    (OUT / "license.txt").write_text(
        str(license_val or "unknown"), encoding="utf-8")
    (OUT / "revision.txt").write_text(
        str(revision or "unknown"), encoding="utf-8")

    # --- load pipeline ------------------------------------------------------
    try:
        pipe, load_notes = _load_pipeline(model_id, pipe_cls, revision, {})
    except Exception as exc:  # noqa: BLE001
        msg = f"HARDWARE FAIL: pipeline load failed for {model!r}: {exc}"
        _status(msg)
        _write_traceback(exc, "load")
        errors.append(msg)
        _write_done(errors)
        sys.exit(1)

    import torch  # noqa: E402
    load_t0 = time.time()
    # trigger a tiny warm allocation to measure load time realistically
    _ = torch.cuda.memory_allocated()
    load_seconds = time.time() - load_t0

    # --- generate 3 seeds ---------------------------------------------------
    manifest_images: List[Dict[str, Any]] = []
    warm_times: List[float] = []
    peak_alloc_mb = None
    peak_reserved_mb = None
    black_count = 0
    nan_count = 0

    for i, seed in enumerate(SEEDS):
        rec: Dict[str, Any] = {
            "seed": seed, "output_file": f"{seed}.png",
            "error": None, "black_or_nan": False,
            "warm_sec_per_image": None,
        }
        try:
            img, secs, gnotes = _generate(pipe, PROMPT, seed, WIDTH, HEIGHT,
                                          job.get("steps"), job.get("guidance_scale"))
            if i == 0:
                # first image is warm-up; exclude from warm average
                rec["warm_sec_per_image"] = None
            else:
                rec["warm_sec_per_image"] = round(secs, 4)
                warm_times.append(secs)
            # black/NaN check
            black, nonfinite = _black_or_nan(img)
            rec["black_or_nan"] = bool(black or nonfinite)
            if black:
                black_count += 1
            if nonfinite:
                nan_count += 1
            # save image
            img.save(images_dir / f"{seed}.png")
            data = (images_dir / f"{seed}.png").read_bytes()
            rec["sha256"] = sha256_file(images_dir / f"{seed}.png")
            rec["bytes"] = len(data)
            rec["seconds"] = round(secs, 4)
            print(f"[{model}] seed {seed}: {secs:.2f}s black={black} nan={nonfinite}")
        except Exception as exc:  # noqa: BLE001
            rec["error"] = str(exc)
            rec["black_or_nan"] = False
            errors.append(f"seed {seed} failed: {exc}")
            _write_traceback(exc, f"seed_{seed}")
            print(f"[{model}] seed {seed} FAILED: {exc}", file=sys.stderr)
        manifest_images.append(rec)

    try:
        peak_alloc_mb = round(torch.cuda.max_memory_allocated() / (1024 * 1024), 2)
        peak_reserved_mb = round(torch.cuda.max_memory_reserved() / (1024 * 1024), 2)
    except Exception:  # noqa: BLE001
        pass

    n_ok = sum(1 for r in manifest_images if not r["error"] and not r["black_or_nan"])
    manifest = {
        "job_id": job.get("job_id"), "model": model, "model_id": model_id,
        "license": license_val, "revision": revision,
        "prompt": PROMPT, "width": WIDTH, "height": HEIGHT,
        "steps": job.get("steps"), "guidance_scale": job.get("guidance_scale"),
        "seeds": SEEDS, "requested": len(SEEDS), "generated": len(manifest_images),
        "n_ok": n_ok, "black_count": black_count, "nan_count": nan_count,
        "load_seconds": round(load_seconds, 4),
        "warm_sec_per_image": (round(statistics.mean(warm_times), 4)
                               if warm_times else None),
        "peak_vram_allocated_mb": peak_alloc_mb,
        "peak_vram_reserved_mb": peak_reserved_mb,
        "versions": versions,
        "pipeline_class": found,
        "install_log": log,
        "gpu_precheck": {"ok": gpu_ok, "reason": gpu_reason, "info": gpu_info},
        "images": manifest_images,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _status(f"COMPLETE: {n_ok}/{len(SEEDS)} ok, load {load_seconds:.1f}s, "
            f"peak VRAM {peak_alloc_mb} MB")
    _write_done()
    print(f"S14 {model}: {n_ok}/{len(SEEDS)} images ok")


if __name__ == "__main__":
    main()
