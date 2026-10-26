#!/usr/bin/env python3
"""S15 style-lock Kaggle-side runner: DreamShaper XL 1.0, ONE model per kernel.

Recipe (frozen in docs/openmontage/image_gen/recipe_dreamshaper_xl_1_0.json):
  model Lykon/dreamshaper-xl-1-0 @ revision 41e6644752a8c9aa63930e6043c4fd83c7708420
  StableDiffusionXLPipeline, torch.float16, DEISMultistepScheduler, 25 steps,
  CFG 5.5, stock VAE (no madebyollin fallback unless NaN/black), cuda (no offload).
  fp16 only; NO bf16; NO bitsandbytes.

42 renders:
  6 scenes x 3 styles x 2 seeds (1001, 2027) = 36 images @ 1024x1024
  6 images @ 1344x768 (16:9) with the best-objective-flags style, seed 1001

Styles (kept identical across scenes; palettes translated to colour words):
  A paper-cut
  B field-guide
  C graphic-novel ink

Every prompt ends: "stylized, non-photorealistic, empty low-detail lower fifth
for captions, no text"
Common negative: "photorealistic, photo, glossy 3D render, mirror reflections,
text, letters, watermark, signature, logo, extra limbs, fused anatomy,
duplicated creature, cluttered bottom edge"

Creature scenes (s01, s03, s10) carry the anatomy sentence verbatim:
  "exactly six separate tendrils, two pairs of fins"

Inputs: JOB_EMBEDDED (embedded by scripts/s15_push_style_lock.py):
  job_id, model, model_id, revision, width/height defaults, renders[]:
    [{render_id, scene_id, style, seed, width, height, prompt,
      negative_prompt, guidance_scale, steps}],
  max_wall_seconds (optional)

Outputs: /kaggle/working/s15_style_lock_dreamshaper-xl-1-0/manifest.json,
         images/<render_id>.png, status.txt, traceback_*.txt on error,
         install_log.json, /kaggle/working/DONE.json (waiting rule).
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

# Per-model wall-clock cap (S15: 90 minutes per kernel).
MAX_WALL_SECONDS = 5400

# --- install ladders (identical to S7/S12; released diffusers first) ---
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
                "(ships StableDiffusionXLPipeline)",
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

PIPELINE_CANDIDATES = {
    "sdxl": ["StableDiffusionXLPipeline", "AutoPipelineForText2Image"],
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
        except Exception:  # noqa: BLE001
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


def install_and_probe(model: str, ladder: List[str],
                      candidates: Optional[List[str]] = None
                      ) -> Tuple[bool, Dict[str, Any]]:
    log: Dict[str, Any] = {"ladder": [], "rungs": []}
    names = list(candidates or PIPELINE_CANDIDATES.get(model) or [])
    if not names:
        log["error"] = f"no pipeline candidates for model {model!r}"
        return False, log
    for i, rung_name in enumerate(ladder, start=1):
        stack = RELEASED_STACKS[rung_name]
        ok, err = _pip(list(stack["pip_args"]))
        found, probe_err, vers = (None, "pip failed: " + err, {}) if not ok else \
            _probe_classes(names)
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


def _model_revision(model_id: Optional[str]) -> Optional[str]:
    if not model_id:
        return None
    try:
        from huggingface_hub import HfApi
        return HfApi().model_info(model_id).sha
    except Exception:  # noqa: BLE001 - provenance, never fatal
        return None


def _write_done(errors: Optional[List[str]] = None) -> None:
    """Write /kaggle/working/DONE.json (waiting rule: every kernel, always)."""
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
            want = man.get("total_requested") or man.get("requested")
            ok = man.get("generated") == want
            payload["status"] = "ok" if ok else "error"
            if not ok:
                payload["errors"].append(
                    f"partial: {man.get('generated')}/{want}")
        else:
            payload["errors"].append("manifest.json missing")
    except Exception as exc:  # noqa: BLE001
        payload["errors"].append(f"done.json could not read manifest: {exc}")
    try:
        (Path("/kaggle/working") / "DONE.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def _black_or_nan(img) -> Tuple[bool, bool]:
    import numpy as np
    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    nonfinite = bool((~np.isfinite(arr)).any())
    black = bool(arr.max() < 8.0)
    return black, nonfinite


# Caption-band + blur proxies, mirrored from scripts/s10_checks.py so the wide
# image picks the style with the best OBJECTIVE flags (no aesthetic judgement).
CAPTION_BAND_FRACTION = 0.28
CAPTION_DARK_LEVEL = 128
CAPTION_MIN_DARK = 0.35
BLUR_ABS_FLOOR = 15.0


def _objective_flags(img) -> Dict[str, Any]:
    import numpy as np
    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    gray = arr @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    gy, gx = np.gradient(gray)
    lap = float((np.abs(gx) + np.abs(gy)).var()) if gray.size else 0.0
    h = arr.shape[0]
    band = gray[h - max(1, int(round(h * CAPTION_BAND_FRACTION))):, :]
    yb, xb = np.gradient(band)
    edges = np.abs(xb) + np.abs(yb)
    busy = float((edges > max(1.0, float(edges.max()) * 0.25)).mean()) \
        if edges.max() > 0 else 0.0
    dark = float((band < CAPTION_DARK_LEVEL).mean())
    return {
        "laplacian_var": round(lap, 3),
        "blur_flag": bool(lap < BLUR_ABS_FLOOR),
        "caption_dark_fraction": round(dark, 3),
        "caption_busy_fraction": round(busy, 3),
        "caption_readable": bool(dark >= CAPTION_MIN_DARK and busy <= 0.35),
    }


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
    # S15: stock VAE only - no vae_model_id override unless NaN/black appears.
    pipe = pipe_cls.from_pretrained(job["model_id"], **kwargs)
    sched = cfg.get("scheduler")
    if sched and sched.get("class"):
        import diffusers as _diffusers
        cls = getattr(_diffusers, str(sched["class"]), None)
        if cls is None:
            raise RuntimeError(
                f"scheduler class {sched['class']!r} missing from diffusers")
        pipe.scheduler = cls.from_config(pipe.scheduler.config,
                                         **(sched.get("kwargs") or {}))
        notes["scheduler"] = str(sched["class"])
        notes["scheduler_kwargs"] = sched.get("kwargs") or {}
    pipe.to("cuda")
    notes["model_cpu_offload"] = False
    notes["device"] = "cuda"
    pipe.set_progress_bar_config(disable=True)
    return pipe, notes


def resolve_model_plan(job: Dict[str, Any]) -> Dict[str, Any]:
    model = str(job["model"])
    model_cfg: Dict[str, Any] = job.get("model_config") or {}
    candidates: List[str] = list(model_cfg.get("pipeline_candidates")
                                 or PIPELINE_CANDIDATES.get(model) or [])
    ladder: List[str] = list(job.get("install_ladder")
                             or model_cfg.get("install_ladder")
                             or ["released_037_x4", "released_037_x5",
                                 "released_041_x5_ao", "git_main_x4"])
    cfg: Dict[str, Any] = dict(model_cfg.get("load_config") or {})
    cfg.update(job.get("load_config") or {})
    return {"model": model, "candidates": candidates,
            "ladder": ladder, "cfg": cfg}


def build_generation_call(rj: Dict[str, Any], cfg: Dict[str, Any],
                          width: int, height: int) -> Dict[str, Any]:
    call: Dict[str, Any] = dict(
        prompt=rj["prompt"],
        height=height,
        width=width,
        num_inference_steps=int(rj.get("steps") or 25),
    )
    if rj.get("negative_prompt") is not None:
        call["negative_prompt"] = rj["negative_prompt"]
    guidance = cfg.get("guidance_override")
    if guidance is None:
        guidance = rj.get("guidance_scale")
    if guidance is not None:
        call["guidance_scale"] = float(guidance)
    return call


def main() -> None:
    global OUT
    job = JOB_EMBEDDED
    if isinstance(job, str):
        job = json.loads(job)
    if not isinstance(job, dict):
        _blocked("JOB_EMBEDDED not set; runner cannot run", code=1)

    model: str = job["model"]
    OUT = Path("/kaggle/working") / (job.get("output_dir")
                                     or "s15_style_lock_dreamshaper-xl-1-0")
    images_dir = OUT / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    plan = resolve_model_plan(job)
    ladder: List[str] = plan["ladder"]
    candidates: List[str] = plan["candidates"]
    cfg: Dict[str, Any] = plan["cfg"]
    max_wall = int(job.get("max_wall_seconds") or MAX_WALL_SECONDS)
    if not ladder:
        _blocked(f"no install ladder for model {model!r}")
    if not candidates:
        _blocked(f"no pipeline candidates for model {model!r}")

    # --- install + verify the pipeline class BEFORE generating --------------
    ok, log = install_and_probe(model, ladder, candidates)
    (OUT / "install_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    if not ok:
        last = log["rungs"][-1] if log["rungs"] else {}
        _blocked("no install rung gave an importable pipeline class; "
                 f"last error: {last.get('import_error')}; "
                 f"versions: {json.dumps(log['rungs'][-1]['versions_after'] if log['rungs'] else {})}")

    import torch  # noqa: E402 - installed above
    import diffusers  # noqa: E402

    if not torch.cuda.is_available():
        _blocked("CUDA not available; NO CPU fallback permitted (S15 rule)")

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

    images: List[Dict[str, Any]] = []
    oom_count = black_count = nan_count = 0
    vram_alloc_max = 0.0
    vram_reserved_max = 0.0
    t_total0 = time.perf_counter()
    wall_cap_hit = False

    for rj in renders:
        if time.perf_counter() - t_total0 > max_wall:
            wall_cap_hit = True
            print(f"wall-clock cap {max_wall}s reached before {rj['render_id']}",
                  file=sys.stderr)
            break
        rid = rj["render_id"]
        call = build_generation_call(rj, cfg, int(rj.get("width", width)),
                                     int(rj.get("height", height)))
        call["generator"] = torch.Generator("cuda").manual_seed(int(rj["seed"]))

        torch.cuda.reset_peak_memory_stats()  # per-image VRAM, not cumulative
        t_start = time.perf_counter()
        try:
            img = pipe(**call).images[0]
        except torch.cuda.OutOfMemoryError:
            oom_count += 1
            torch.cuda.empty_cache()
            tb = traceback.format_exc()
            (OUT / f"traceback_{rid}.txt").write_text(tb, encoding="utf-8")
            images.append({"render_id": rid, "file": None, "seed": rj["seed"],
                           "scene_id": rj["scene_id"], "style": rj["style"],
                           "error": "oom", "width": int(rj.get("width", width)),
                           "height": int(rj.get("height", height)),
                           "steps": int(rj.get("steps") or 25),
                           "guidance_scale": float(call.get("guidance_scale", 0.0)),
                           "black": False, "nonfinite": False})
            continue
        except Exception:  # noqa: BLE001
            tb = traceback.format_exc()
            (OUT / f"traceback_{rid}.txt").write_text(tb, encoding="utf-8")
            print(tb, file=sys.stderr)
            images.append({"render_id": rid, "file": None, "seed": rj["seed"],
                           "scene_id": rj["scene_id"], "style": rj["style"],
                           "error": "generation_exception",
                           "width": int(rj.get("width", width)),
                           "height": int(rj.get("height", height)),
                           "steps": int(rj.get("steps") or 25),
                           "guidance_scale": float(call.get("guidance_scale", 0.0)),
                           "black": False, "nonfinite": False})
            continue
        secs = time.perf_counter() - t_start

        black, nonfinite = _black_or_nan(img)
        black_count += int(black)
        nan_count += int(nonfinite)
        flags = _objective_flags(img)

        fname = f"{rid}.png"
        fpath = images_dir / fname
        img.save(fpath, optimize=True)
        data = fpath.read_bytes()
        try:
            peak_alloc = round(torch.cuda.max_memory_allocated() / (1024 * 1024), 2)
            peak_reserved = round(torch.cuda.max_memory_reserved() / (1024 * 1024), 2)
        except Exception:  # noqa: BLE001
            peak_alloc = None
            peak_reserved = None
        vram_alloc_max = max(vram_alloc_max, peak_alloc or 0.0)
        vram_reserved_max = max(vram_reserved_max, peak_reserved or 0.0)
        images.append({
            "render_id": rid,
            "scene_id": rj["scene_id"],
            "style": rj["style"],
            "file": fname,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "width": int(rj.get("width", width)),
            "height": int(rj.get("height", height)),
            "seed": int(rj["seed"]),
            "steps": int(rj.get("steps") or 25),
            "guidance_scale": float(call.get("guidance_scale", 0.0)),
            "prompt": rj["prompt"],
            "negative_prompt": rj.get("negative_prompt"),
            "seconds": round(secs, 4),
            "black": black,
            "nonfinite": nonfinite,
            "peak_vram_allocated_mb": peak_alloc,
            "peak_vram_reserved_mb": peak_reserved,
            **flags,
        })

    # --- wide images: 6 x best-objective-flags style @ 1344x768, seed 1001 ---
    wide_scenes = job.get("wide_scenes") or []
    if wide_scenes:
        # best style = fewest objective flags among the 36 (black/nonfinite
        # dominate, then unreadable caption band, then blur); deterministic
        # tie-break on style order. No aesthetic judgement.
        style_order = ["paper-cut", "field-guide", "graphic-novel-ink"]
        style_stats: Dict[str, Dict[str, Any]] = {}
        for s in style_order:
            items = [im for im in images
                     if im.get("file") and im.get("style") == s]
            if not items:
                style_stats[s] = {"images": 0, "bad": 10 ** 6}
                continue
            hard = sum(1 for im in items if im.get("black") or im.get("nonfinite"))
            cap = sum(1 for im in items if im.get("caption_readable") is False)
            blur = sum(1 for im in items if im.get("blur_flag"))
            dark = sum(float(im.get("caption_dark_fraction") or 0.0)
                       for im in items) / len(items)
            style_stats[s] = {
                "images": len(items),
                "black_or_nan": hard,
                "caption_unreadable": cap,
                "blur_flagged": blur,
                "mean_caption_dark_fraction": round(dark, 4),
                "bad": hard * 1000 + cap * 10 + blur,
            }
        best_style = min(style_order,
                         key=lambda s: (style_stats[s]["bad"],
                                        -style_stats[s].get(
                                            "mean_caption_dark_fraction", 0.0),
                                        style_order.index(s)))
        (OUT / "wide_style.json").write_text(
            json.dumps({"best_style": best_style, "style_stats": style_stats,
                        "rule": "min(bad) where bad = 1000*black_or_nan + "
                                "10*caption_unreadable + blur_flagged; "
                                "tie-break mean caption dark fraction, then "
                                "declared style order"},
                       indent=2), encoding="utf-8")
        print(f"wide style chosen: {best_style} (stats={style_stats})",
              file=sys.stderr)

        wide_warm = True  # first wide image is warm-up for the 1344x768 bucket
        for scene in wide_scenes:
            rid = f"s15_wide_{best_style}_{scene}_1001"
            # the prompt MUST be the best style's prompt for that scene
            base = next((r for r in renders
                         if r["scene_id"] == scene and r["style"] == best_style),
                        None)
            if base is None:
                print(f"wide: no base render for scene {scene}, skipping",
                      file=sys.stderr)
                continue
            torch.cuda.reset_peak_memory_stats()
            call = build_generation_call(base, cfg, 1344, 768)
            call["guidance_scale"] = 5.5
            call["generator"] = torch.Generator("cuda").manual_seed(1001)
            t_start = time.perf_counter()
            try:
                img = pipe(**call).images[0]
            except torch.cuda.OutOfMemoryError:
                oom_count += 1
                torch.cuda.empty_cache()
                tb = traceback.format_exc()
                (OUT / f"traceback_{rid}.txt").write_text(tb, encoding="utf-8")
                images.append({"render_id": rid, "file": None, "seed": 1001,
                               "scene_id": scene, "style": best_style,
                               "error": "oom", "width": 1344, "height": 768,
                               "steps": 25, "guidance_scale": 5.5,
                               "black": False, "nonfinite": False})
                continue
            except Exception:  # noqa: BLE001
                tb = traceback.format_exc()
                (OUT / f"traceback_{rid}.txt").write_text(tb, encoding="utf-8")
                print(tb, file=sys.stderr)
                images.append({"render_id": rid, "file": None, "seed": 1001,
                               "scene_id": scene, "style": best_style,
                               "error": "generation_exception", "width": 1344,
                               "height": 768, "steps": 25, "guidance_scale": 5.5,
                               "black": False, "nonfinite": False})
                continue
            secs = time.perf_counter() - t_start
            black, nonfinite = _black_or_nan(img)
            black_count += int(black)
            nan_count += int(nonfinite)
            flags = _objective_flags(img)
            fname = f"{rid}.png"
            fpath = images_dir / fname
            img.save(fpath, optimize=True)
            data = fpath.read_bytes()
            try:
                peak_alloc = round(torch.cuda.max_memory_allocated() / (1024 * 1024), 2)
                peak_reserved = round(torch.cuda.max_memory_reserved() / (1024 * 1024), 2)
            except Exception:  # noqa: BLE001
                peak_alloc = None
                peak_reserved = None
            vram_alloc_max = max(vram_alloc_max, peak_alloc or 0.0)
            vram_reserved_max = max(vram_reserved_max, peak_reserved or 0.0)
            images.append({
                "render_id": rid,
                "scene_id": scene,
                "style": best_style,
                "file": fname,
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "width": 1344,
                "height": 768,
                "seed": 1001,
                "steps": 25,
                "guidance_scale": 5.5,
                "prompt": base["prompt"],
                "negative_prompt": base.get("negative_prompt"),
                "seconds": round(secs, 4),
                "black": black,
                "nonfinite": nonfinite,
                "peak_vram_allocated_mb": peak_alloc,
                "peak_vram_reserved_mb": peak_reserved,
                "warm_image": wide_warm,
                **flags,
            })
            wide_warm = False

    gpu_seconds = time.perf_counter() - t_total0
    times = [i["seconds"] for i in images if i.get("file")]
    warmup_excluded = times[1:] if len(times) > 1 else times
    steady = round(statistics.mean(warmup_excluded), 3) if warmup_excluded else None
    usable_per_min = (round(len(times) / (gpu_seconds / 60.0), 2)
                      if times and gpu_seconds > 0 else None)

    versions = _versions()
    resolved_revision = job.get("revision") or _model_revision(job.get("model_id"))
    expected_total = len(renders) + len(wide_scenes)
    manifest = {
        "job_id": job.get("job_id"),
        "model": model,
        "model_id": job.get("model_id"),
        "model_revision": resolved_revision,
        "pipeline_class": declared,
        "dtype": "float16",
        "bf16": False,
        "bitsandbytes": False,
        "cpu_offload": False,
        "device": "cuda",
        "width": width,
        "height": height,
        "requested": len(renders),
        "wide_requested": len(wide_scenes),
        "total_requested": expected_total,
        "generated": len(times),
        "load_seconds": round(load_seconds, 3),
        "steady_state_sec_per_image": steady,
        "mean_sec_per_image": round(statistics.mean(times), 3) if times else None,
        "usable_images_per_minute": usable_per_min,
        "gpu_seconds": round(gpu_seconds, 2),
        "peak_vram_mb": round(vram_alloc_max, 2),
        "peak_vram_reserved_mb": round(vram_reserved_max, 2),
        "peak_vram_note": "max of per-image torch.cuda.max_memory_allocated() "
                          "(peak memory is reset before every render)",
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

    if len(times) < expected_total:
        reason = "wall-clock cap reached" if wall_cap_hit else "some images failed"
        _status(f"PARTIAL: generated {len(times)}/{expected_total} ({reason}); "
                f"see manifest.json")
        print(f"s15 {model} PARTIAL: {len(times)}/{expected_total} ({reason})",
              file=sys.stderr)
        sys.exit(1)

    _status("COMPLETE")
    print(f"s15 {model} done: {len(times)} images, {steady} s/img steady, "
          f"peak VRAM {manifest['peak_vram_mb']} MB, load {load_seconds:.1f}s")


if __name__ == "__main__":
    _done_errors: List[str] = []
    try:
        main()
    except SystemExit as exc:
        if exc.code not in (0, None):
            _done_errors.append(f"exit code {exc.code}")
        raise
    except Exception:  # noqa: BLE001 - full traceback saved to kernel output
        tb = traceback.format_exc()
        _done_errors.append(tb.strip().splitlines()[-1] if tb.strip() else "exception")
        try:
            OUT.mkdir(parents=True, exist_ok=True)
            (OUT / "traceback_fatal.txt").write_text(tb, encoding="utf-8")
            _status(f"FAILED: {tb.strip().splitlines()[-1]}")
        except Exception:  # noqa: BLE001
            pass
        print(tb, file=sys.stderr)
        sys.exit(1)
    finally:
        _write_done(_done_errors)
