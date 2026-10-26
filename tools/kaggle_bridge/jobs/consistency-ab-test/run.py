"""OpenMontage character-consistency A/B test kernel (Kaggle T4).

Tests (protocol: tools/kaggle_bridge/jobs/consistency-ab-test/test_protocol.json):
  A - SDXL Base 1.0, 768x768, fp16, vae slicing/tiling, model CPU offload, NO IP-Adapter (control/gate)
  B - A + ip-adapter-plus-face_sdxl_vit-h only
  C - A + ip-adapter-plus_sdxl_vit-h (full-body) only
  D - B + C combined (only if B and C both pass without OOM)

Banned: DreamShaper XL base, IP-Adapter FaceID, PhotoMaker V2, PuLID, Character LoRA training.
OOM policy: record exact operation / resolution / scenario; never mask by lowering quality.
Outputs: /kaggle/working/consistency-ab-test/images/<test>_<seed>_<scenario>.png
         /kaggle/working/consistency-ab-test/results.json
"""

from __future__ import annotations

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
from transformers import CLIPVisionModelWithProjection, CLIPImageProcessor

OUT = Path("/kaggle/working/consistency-ab-test")
IMG_DIR = OUT / "images"
IMG_DIR.mkdir(parents=True, exist_ok=True)

BASE_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"
IP_REPO = "h94/IP-Adapter"
IP_SUB = "sdxl_models"
IP_FACE_WEIGHT = "ip-adapter-plus-face_sdxl_vit-h.safetensors"
IP_PLUS_WEIGHT = "ip-adapter-plus_sdxl_vit-h.safetensors"

W = H = 768
STEPS = 25
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


def add_ip_adapter(pipe, weight_name, scale, apply_cpu_offload_after=True):
    image_encoder = CLIPVisionModelWithProjection.from_pretrained(
        IP_REPO, subfolder=f"{IP_SUB}/image_encoder", torch_dtype=torch.float16
    )
    pipe.image_encoder = image_encoder
    if not hasattr(pipe, "load_ip_adapter"):
        raise RuntimeError("load_ip_adapter not available in this diffusers version")
    pipe.load_ip_adapter(IP_REPO, subfolder=IP_SUB, weight_name=weight_name)
    if hasattr(pipe, "set_ip_adapter_scale"):
        pipe.set_ip_adapter_scale(scale)
    # cpu_offload MUST be applied AFTER IP-Adapter modules are registered so the
    # offload hook captures them too (avoids CPU/CUDA weight mismatch).
    if apply_cpu_offload_after and hasattr(pipe, "enable_model_cpu_offload"):
        pipe.enable_model_cpu_offload()
    return pipe


def compute_ref_embeds(pipe, ref_image):
    """Pre-compute 1280-dim CLIP image_embeds for the reference character.

    h94/IP-Adapter sdxl_models/image_encoder exposes hidden_size=1664
    (last_hidden_state) but projection_dim=1280 (image_embeds). IP-Adapter
    vit-h weights expect 1280-dim input, so we feed pre-computed image_embeds
    via ip_adapter_image_embeds and bypass the pipeline's image-encoder re-run
    (which would otherwise feed the 1664-dim last_hidden_state and shape-error).
    """
    processor = CLIPImageProcessor()
    inputs = processor(images=ref_image, return_tensors="pt")
    pixel_values = inputs.pixel_values.to(device="cuda", dtype=torch.float16)
    with torch.no_grad():
        out = pipe.image_encoder(pixel_values)
    return out.image_embeds  # (1, 1280)


def generate(pipe, prompt, seed, ref_embeds_list=None):
    kwargs = dict(
        prompt=prompt,
        negative_prompt=NEGATIVE,
        width=W,
        height=H,
        num_inference_steps=STEPS,
        guidance_scale=GUIDANCE,
        generator=torch.manual_seed(seed),
    )
    if ref_embeds_list is not None:
        kwargs["ip_adapter_image_embeds"] = ref_embeds_list
    t0 = time.time()
    try:
        image = pipe(**kwargs).images[0]
    except torch.cuda.OutOfMemoryError as exc:
        torch.cuda.empty_cache()
        raise
    return image, round(time.time() - t0, 3)


def run_test(test_name, make_pipe, ref_image=None, scenarios=None, ip_adapter_count=1):
    scenarios = scenarios or SCENARIOS
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

    # Pre-compute reference image_embeds once per pipe; replicate per adapter.
    ref_embeds_list = None
    if ref_image is not None and hasattr(pipe, "image_encoder"):
        ref_embeds = compute_ref_embeds(pipe, ref_image)  # (1, 1280)
        # IP-Adapter on diffusers 0.40 wants a list of 3D/4D tensors:
        # (batch, 1 image, embed_dim) -> (1, 1, 1280).
        ref_embeds = ref_embeds.unsqueeze(1)
        ref_embeds_list = [ref_embeds] * ip_adapter_count
        print(f"[{test_name}] ref image_embeds: {tuple(ref_embeds.shape)} "
              f"x{ip_adapter_count} adapters")

    renders = []
    oom = None
    passed = True
    for scen_key, scen_desc in scenarios:
        prompt = f"{CHARACTER}, {scen_desc}, {STYLE_SUFFIX}"
        for seed in SEEDS:
            fname = f"{test_name}_{seed}_{scen_key}.png"
            fpath = IMG_DIR / fname
            rec = {
                "test": test_name, "seed": seed, "scenario": scen_key,
                "scenario_desc": scen_desc, "file": fname,
            }
            try:
                image, dt = generate(pipe, prompt, seed, ref_embeds_list=ref_embeds_list)
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


def main():
    results = {
        "protocol": "tools/kaggle_bridge/jobs/consistency-ab-test/test_protocol.json",
        "started_utc": now(),
        "environment": env_info(),
        "tests": [],
        "conclusion": {},
    }
    print("ENV:", json.dumps(results["environment"], ensure_ascii=False))

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
                                                       lambda: load_base_pipe(apply_cpu_offload=True))))
    ta = results["tests"][-1]
    print(f"TEST A baseline: passed={ta.get('passed')} peak_vram={ta.get('peak_vram_mb_overall')} MB "
          f"oom={ta.get('oom')} error={ta.get('error')}")
    if not ta.get("passed"):
        results["finished_utc"] = now()
        (OUT / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))
        print("GATE: bare SDXL Base did not pass. Stopping per protocol.")
        return

    # --- Test B: IP-Adapter Plus Face -------------------------------------
    results["tests"].append(_try_test("B_plus_face",
        lambda: run_test("B_plus_face",
                         lambda: add_ip_adapter(load_base_pipe(apply_cpu_offload=False),
                                                IP_FACE_WEIGHT, 0.7),
                         ref_image=ref_image)))
    tb = results["tests"][-1]
    print(f"TEST B plus-face: passed={tb.get('passed')} peak_vram={tb.get('peak_vram_mb_overall')} MB "
          f"oom={tb.get('oom')} error={tb.get('error')}")

    # --- Test C: IP-Adapter Plus full-body --------------------------------
    results["tests"].append(_try_test("C_plus_fullbody",
        lambda: run_test("C_plus_fullbody",
                         lambda: add_ip_adapter(load_base_pipe(apply_cpu_offload=False),
                                                IP_PLUS_WEIGHT, 0.7),
                         ref_image=ref_image)))
    tc = results["tests"][-1]
    print(f"TEST C plus-fullbody: passed={tc.get('passed')} peak_vram={tc.get('peak_vram_mb_overall')} MB "
          f"oom={tc.get('oom')} error={tc.get('error')}")

    # --- Test D: combination ----------------------------------------------
    td = None
    if tb.get("passed") and tc.get("passed"):
        td = run_test(
            "D_plus_plusface_combo",
            lambda: add_ip_adapter(
                add_ip_adapter(load_base_pipe(apply_cpu_offload=False),
                               IP_PLUS_WEIGHT, 0.7, apply_cpu_offload_after=False),
                IP_FACE_WEIGHT, 0.25, apply_cpu_offload_after=True,
            ),
            ref_image=ref_image,
            ip_adapter_count=2,
        )
        results["tests"].append(td)
        print(f"TEST D combo: passed={td.get('passed')} peak_vram={td.get('peak_vram_mb_overall')} MB "
              f"oom={td.get('oom')} error={td.get('error')}")
    else:
        results["tests"].append({
            "test_name": "D_plus_plusface_combo",
            "skipped": True,
            "reason": "Test B or C failed with OOM; combination not attempted per protocol.",
        })
        print("TEST D combo: SKIPPED (B or C failed with OOM)")

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
            "note": "No test passed without OOM.",
        }

    (OUT / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print("RESULTS:", json.dumps(results["conclusion"], ensure_ascii=False))
    print(f"All outputs in {OUT}")


if __name__ == "__main__":
    main()
