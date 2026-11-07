"""OpenMontage character-consistency A/B test kernel (Kaggle T4).

Tests (protocol: tools/kaggle_bridge/jobs/consistency-ab-test/test_protocol.json):
  A - SDXL Base 1.0, 768x768, fp16, vae slicing/tiling, model CPU offload, NO IP-Adapter (control/gate)
  B - A + ip-adapter-plus-face_sdxl_vit-h via OFFICIAL diffusers API
        (pipe.load_ip_adapter + pipe.set_ip_adapter_scale + ip_adapter_image=PIL.Image)

Banned: DreamShaper XL base, IP-Adapter FaceID, PhotoMaker V2, PuLID, Character LoRA training,
manual ip_adapter_image_embeds construction.
OOM policy: record exact operation / resolution / scenario; never mask by lowering quality.
Outputs: /kaggle/working/consistency-ab-test/images/<test>_<seed>_<scenario>.png
         /kaggle/working/consistency-ab-test/results.json

Default run = QUICK test (1 seed x 1 scenario) to confirm the official IP-Adapter path works.
Pass --full-matrix to run the full 5-seed x 9-scenario matrix for tests A and B.
"""

from __future__ import annotations

import argparse
import importlib.metadata as md
import json
import os
import subprocess
import sys
import time
import traceback
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
from PIL import Image
from diffusers import StableDiffusionXLPipeline

OUT = Path("/kaggle/working/consistency-ab-test")
IMG_DIR = OUT / "images"
IMG_DIR.mkdir(parents=True, exist_ok=True)

BASE_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"
IP_REPO = "h94/IP-Adapter"
IP_SUB = "sdxl_models"
IP_FACE_WEIGHT = "ip-adapter-plus-face_sdxl_vit-h.safetensors"
IP_PLUS_WEIGHT = "ip-adapter-plus_sdxl_vit-h.safetensors"

W = H = 768
STEPS = 30
GUIDANCE = 7.5
SEEDS = [42, 123, 777, 2026, 9001]

SCENARIOS = [
    ("crowd_portrait_close_up", "crowd portrait close-up, surrounded by blurred people"),
    ("side_profile", "side profile view, looking to the left"),
    ("full_body_standing", "full body standing, head to toe"),
    ("dynamic_action_pose", "dynamic action pose, leaping mid-air"),
    ("different_lighting", "dramatic chiaroscuro lighting, strong shadows"),
    ("different_emotion", "joyful emotion, laughing, big smile"),
    ("different_outfit_detail", "blue denim jacket with embroidered patch detail visible"),
    ("different_background", "standing in an autumn forest with colorful leaves"),
    ("group_scene_other_character", "group scene with other character, standing next to a second person"),
]

CHARACTER = (
    "young woman with short curly auburn hair and freckles, "
    "wearing a blue denim jacket and a silver chain necklace"
)
NEGATIVE = (
    "photorealistic, 3d, realistic, blurry, low quality, watermark, "
    "text, letters, numbers, distorted, ugly, deformed, extra limbs, extra fingers"
)
STYLE_SUFFIX = "comic line-art style, bold black outlines, clean line work, flat color"

REF_PROMPT = (
    f"portrait of {CHARACTER}, clean light gray background, soft studio lighting, "
    "highly detailed, 8k"
)

QUICK_SEEDS = [42]
QUICK_SCENARIOS = [SCENARIOS[0]]


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def slug(s):
    return "".join(c if c.isalnum() else "_" for c in s.lower()).strip("_")


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
        info["total_vram_gb"] = round(torch.cuda.get_device_properties(0).total_memory / 1024 ** 3, 2)
    return info


def _apply_vae_opts(pipe):
    for m in ("enable_vae_slicing", "enable_vae_tiling"):
        if hasattr(pipe, m):
            getattr(pipe, m)()


def load_base_pipe(apply_cpu_offload=True):
    """SDXL Base 1.0 with fp16 + memory optimisations. No IP-Adapter."""
    pipe = StableDiffusionXLPipeline.from_pretrained(
        BASE_MODEL, torch_dtype=torch.float16, use_safetensors=True
    )
    _apply_vae_opts(pipe)
    if apply_cpu_offload:
        pipe.enable_model_cpu_offload()
    return pipe


def add_ip_adapter(pipe, weight_name, scale=0.6, apply_cpu_offload_after=True):
    """Load one IP-Adapter weight via OFFICIAL diffusers API."""
    pipe.load_ip_adapter(IP_REPO, subfolder=IP_SUB, weight_name=weight_name)
    pipe.set_ip_adapter_scale(scale)
    if apply_cpu_offload_after and hasattr(pipe, "enable_model_cpu_offload"):
        pipe.enable_model_cpu_offload()
    return pipe


def add_ip_adapter_plus_face(pipe, scale=0.6, apply_cpu_offload_after=True):
    """IP-Adapter Plus Face via OFFICIAL diffusers API."""
    return add_ip_adapter(pipe, IP_FACE_WEIGHT, scale=scale,
                          apply_cpu_offload_after=apply_cpu_offload_after)


def add_ip_adapter_plus(pipe, scale=0.6, apply_cpu_offload_after=True):
    """IP-Adapter Plus (full-body) via OFFICIAL diffusers API."""
    return add_ip_adapter(pipe, IP_PLUS_WEIGHT, scale=scale,
                          apply_cpu_offload_after=apply_cpu_offload_after)


def generate(pipe, prompt, seed, ip_adapter_image=None):
    kwargs = dict(
        prompt=prompt,
        negative_prompt=NEGATIVE,
        width=W,
        height=H,
        num_inference_steps=STEPS,
        guidance_scale=GUIDANCE,
        generator=torch.manual_seed(seed),
    )
    if ip_adapter_image is not None:
        kwargs["ip_adapter_image"] = ip_adapter_image
    t0 = time.time()
    try:
        image = pipe(**kwargs).images[0]
    except torch.cuda.OutOfMemoryError as exc:
        torch.cuda.empty_cache()
        raise
    return image, round(time.time() - t0, 3)


def run_test(test_name, make_pipe, ref_image=None, scenarios=None, seeds=None, ip_adapter_image=None):
    scenarios = scenarios or SCENARIOS
    seeds = seeds or SEEDS
    reset_peak()
    t_load = time.time()
    try:
        pipe = make_pipe()
    except Exception as exc:  # noqa: BLE001 - adapter/setup failure must not kill the kernel
        torch.cuda.empty_cache()
        return {
            "test_name": test_name,
            "load_seconds": None,
            "peak_vram_mb_after_load": None,
            "peak_vram_mb_overall": None,
            "oom": None,
            "passed": False,
            "error": f"pipe_setup_failed: {str(exc)[:200]}",
            "renders": [],
        }
    load_s = round(time.time() - t_load, 2)
    peak_after_load = peak_mb()
    reset_peak()

    renders = []
    oom = None
    passed = True
    for scen_key, scen_desc in scenarios:
        prompt = f"{CHARACTER}, {scen_desc}, {STYLE_SUFFIX}"
        for seed in seeds:
            fname = f"{test_name}_{seed}_{scen_key}.png"
            fpath = IMG_DIR / fname
            rec = {
                "test": test_name, "seed": seed, "scenario": scen_key,
                "scenario_desc": scen_desc, "file": fname,
            }
            try:
                image, dt = generate(pipe, prompt, seed, ip_adapter_image=ip_adapter_image)
                image.save(fpath)
                rec.update({
                    "status": "ok", "seconds": dt,
                    "peak_vram_mb": peak_mb(),
                })
            except torch.cuda.OutOfMemoryError as exc:
                passed = False
                oom = {
                    "operation": "generate",
                    "resolution": f"{W}x{H}",
                    "test": test_name,
                    "scenario": scen_key,
                    "seed": seed,
                    "error": str(exc)[:200],
                }
                rec.update({"status": "OOM", "error": str(exc)[:200]})
                renders.append(rec)
                break
            except Exception as exc:  # noqa: BLE001
                passed = False
                rec.update({"status": "error", "error": str(exc)[:200]})
            renders.append(rec)
            if oom:
                break
        if oom:
            break

    del pipe
    torch.cuda.empty_cache()

    return {
        "test_name": test_name,
        "load_seconds": load_s,
        "peak_vram_mb_after_load": peak_after_load,
        "peak_vram_mb_overall": peak_mb(),
        "oom": oom,
        "passed": passed and oom is None,
        "renders": renders,
    }


def main(full_matrix=False):
    seeds = SEEDS if full_matrix else QUICK_SEEDS
    scenarios = SCENARIOS if full_matrix else QUICK_SCENARIOS
    results = {
        "protocol": "tools/kaggle_bridge/jobs/consistency-ab-test/test_protocol.json",
        "mode": "full-matrix" if full_matrix else "quick",
        "started_utc": now(),
        "environment": env_info(),
        "tests": [],
        "conclusion": {},
    }
    print("ENV:", json.dumps(results["environment"], ensure_ascii=False))
    print(f"MODE: {'full-matrix' if full_matrix else 'quick'} "
          f"({len(seeds)} seed(s) x {len(scenarios)} scenario(s))")

    # --- reference character image (clean background) ---------------------
    ref_image = None
    try:
        ref_pipe = load_base_pipe()
        reset_peak()
        t0 = time.time()
        ref_image = ref_pipe(prompt=REF_PROMPT, negative_prompt=NEGATIVE,
                             width=W, height=H, num_inference_steps=STEPS,
                             guidance_scale=GUIDANCE,
                             generator=torch.manual_seed(42)).images[0]
        ref_path = IMG_DIR / "ref_character.png"
        ref_image.save(ref_path)
        print(f"Reference character saved: {ref_path} ({round(time.time()-t0,2)}s, "
              f"peak VRAM {peak_mb()} MB)")
        del ref_pipe
        torch.cuda.empty_cache()
    except Exception as exc:  # noqa: BLE001
        print(f"REFERENCE GENERATION FAILED: {exc}")
        traceback.print_exc()

    def _try_test(name, fn):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - never let one test kill the kernel
            torch.cuda.empty_cache()
            rec = {"test_name": name, "passed": False,
                   "error": f"test_crashed: {str(exc)[:200]}",
                   "renders": [], "oom": None,
                   "load_seconds": None, "peak_vram_mb_after_load": None,
                   "peak_vram_mb_overall": None}
            print(f"TEST {name}: CRASHED {rec['error']}")
            return rec

    # --- Test A: baseline, no adapter -------------------------------------
    results["tests"].append(_try_test("A_baseline",
                                      lambda: run_test("A_baseline",
                                                       lambda: load_base_pipe(apply_cpu_offload=True),
                                                       ref_image=None,
                                                       scenarios=scenarios, seeds=seeds)))
    ta = results["tests"][-1]
    print(f"TEST A baseline: passed={ta.get('passed')} peak_vram={ta.get('peak_vram_mb_overall')} MB "
          f"oom={ta.get('oom')} error={ta.get('error')}")
    if not ta.get("passed"):
        results["finished_utc"] = now()
        (OUT / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))
        print("GATE: bare SDXL Base did not pass. Stopping per protocol.")
        return

    # --- Test B: IP-Adapter Plus Face (OFFICIAL API) ----------------------
    results["tests"].append(_try_test("B_plus_face_official",
        lambda: run_test("B_plus_face_official",
                         lambda: add_ip_adapter_plus_face(load_base_pipe(apply_cpu_offload=False),
                                                          scale=0.6),
                         ref_image=ref_image,
                         scenarios=scenarios, seeds=seeds,
                         ip_adapter_image=ref_image)))
    tb = results["tests"][-1]
    print(f"TEST B plus-face (official): passed={tb.get('passed')} peak_vram={tb.get('peak_vram_mb_overall')} MB "
          f"oom={tb.get('oom')} error={tb.get('error')}")

    # --- Test C: IP-Adapter Plus full-body (OFFICIAL API) -----------------
    results["tests"].append(_try_test("C_plus_fullbody_official",
        lambda: run_test("C_plus_fullbody_official",
                         lambda: add_ip_adapter_plus(load_base_pipe(apply_cpu_offload=False),
                                                     scale=0.6),
                         ref_image=ref_image,
                         scenarios=scenarios, seeds=seeds,
                         ip_adapter_image=ref_image)))
    tc = results["tests"][-1]
    print(f"TEST C plus-fullbody (official): passed={tc.get('passed')} peak_vram={tc.get('peak_vram_mb_overall')} MB "
          f"oom={tc.get('oom')} error={tc.get('error')}")

    # --- Test D: combination ----------------------------------------------
    td = None
    if tb.get("passed") and tc.get("passed"):
        td = run_test(
            "D_plus_plusface_combo_official",
            lambda: add_ip_adapter_plus_face(
                add_ip_adapter_plus(load_base_pipe(apply_cpu_offload=False),
                                    scale=0.6, apply_cpu_offload_after=False),
                scale=0.6, apply_cpu_offload_after=True,
            ),
            ref_image=ref_image,
            scenarios=scenarios, seeds=seeds,
            ip_adapter_image=ref_image,
        )
        results["tests"].append(td)
        print(f"TEST D combo (official): passed={td.get('passed')} peak_vram={td.get('peak_vram_mb_overall')} MB "
              f"oom={td.get('oom')} error={td.get('error')}")
    else:
        results["tests"].append({
            "test_name": "D_plus_plusface_combo_official",
            "skipped": True,
            "reason": "Test B or C failed with OOM/error; combination not attempted per protocol.",
        })
        print("TEST D combo: SKIPPED (B or C failed)")

    # --- conclusion -------------------------------------------------------
    passing = [t for t in results["tests"] if t.get("passed")]
    results["finished_utc"] = now()
    if passing:
        best = min(passing, key=lambda t: t["peak_vram_mb_overall"])
        results["conclusion"] = {
            "best_test": best["test_name"],
            "best_peak_vram_mb": best["peak_vram_mb_overall"],
            "passed_tests": [t["test_name"] for t in passing],
            "failed_tests": [t["test_name"] for t in results["tests"]
                             if not t.get("passed")],
            "note": "Human visual scoring (6 categories x 5 scenarios, 1-5) pending on saved images.",
        }
    else:
        results["conclusion"] = {
            "best_test": None,
            "note": "No test passed without OOM/error.",
        }

    (OUT / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print("RESULTS:", json.dumps(results["conclusion"], ensure_ascii=False))
    print(f"All outputs in {OUT}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-matrix", action="store_true",
                        help="Run full 5-seed x 9-scenario matrix (default: quick 1x1 test)")
    args = parser.parse_args()
    main(full_matrix=args.full_matrix)
