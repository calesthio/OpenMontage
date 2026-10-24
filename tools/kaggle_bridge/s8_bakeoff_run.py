#!/usr/bin/env python3
"""S8 additions to the bake-off engine (appended to s7_bakeoff_run.py).

This file is NOT a standalone runner in the Kaggle kernel: the push script
concatenates it after the S7 engine (which is the generic install/probe/
measure/manifest machine) and then appends the `__main__` guard, so the kernel
receives one self-contained run.py.

Three S8 models are registered:

  sdxl-lightning     ByteDance/SDXL-Lightning 8-step UNet on the SDXL Base
                     pipeline (vendor-card recipe), OpenRAIL++
  dreamshaper-xl     Lykon/dreamshaper-xl-lightning (SDXL family), OpenRAIL++
  sana-sprint-1.6b   Efficient-Large-Model/Sana_Sprint_1.6B_1024px_diffusers
                     (SanaSprintPipeline), Apache-2.0

The two loading tricks the vendor cards need:
  * `unet_checkpoint` - swap the UNet of a base pipeline for a distilled
    checkpoint (SDXL-Lightning's card recipe: build the UNet from the base
    config, then load the distilled state dict into it);
  * `scheduler` - replace the pipeline scheduler after loading
    (SDXL-Lightning: EulerDiscreteScheduler with trailing timesteps;
     DreamShaper XL Lightning: DPMSolverMultistepScheduler).

S8 rules: fp16 only, no bitsandbytes, no CPU fallback (offload allowed),
released library versions pinned in the manifest, NO git main, 90 min wall cap.
"""
# NOTE: no `from __future__ import annotations` here - this file is APPENDED to
# the S8 engine source, and a future import must be the first statement of a
# file. The typing aliases below are runtime-safe on their own.
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

# The engine module: when this file is appended to the engine source, this is
# the __main__ module itself; when it is imported locally, it is the engine.
_ENGINE = sys.modules.get(__name__)
if _ENGINE is None or not hasattr(_ENGINE, "install_and_probe"):
    # Standalone use (local imports/tests): load the engine module. When this
    # file is APPENDED to the engine source the engine's own globals are
    # already here, so the import is skipped (the engine does not exist as a
    # separate file inside the Kaggle kernel).
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import s7_bakeoff_run as _ENGINE  # type: ignore[no-redef]

# --- S8 model registry -----------------------------------------------------
_ENGINE.PIPELINE_CANDIDATES.update({
    "sdxl-lightning": ["StableDiffusionXLPipeline"],
    "dreamshaper-xl": ["StableDiffusionXLPipeline"],
    "sana-sprint-1.6b": ["SanaSprintPipeline", "SanaPipeline"],
})

_ENGINE.LOAD_CONFIG.update({
    "sdxl-lightning": {
        # vendor card: base pipeline + fp16 UNet checkpoint + Euler/trailing
        "offload": False,
        "low_cpu_mem_usage": None,
        "extra_kwargs": {"variant": "fp16"},
        "guidance_override": 0.0,
        "scheduler": {"class": "EulerDiscreteScheduler",
                      "kwargs": {"timestep_spacing": "trailing"}},
    },
    "dreamshaper-xl": {
        # vendor card: fp16 variant, DPMSolverMultistep, 4 steps, guidance 2
        "offload": False,
        "low_cpu_mem_usage": None,
        "extra_kwargs": {"variant": "fp16"},
        "guidance_override": 2.0,
        "scheduler": {"class": "DPMSolverMultistepScheduler", "kwargs": {}},
    },
    "sana-sprint-1.6b": {
        # card: bfloat16 official; S8 mandates fp16; 1.6B -> fits the T4
        "offload": True,
        "low_cpu_mem_usage": None,
        "extra_kwargs": {},
        "guidance_override": 4.5,  # diffusers SanaSprintPipeline default
    },
})

# Released stacks only (S8: no git main). diffusers 0.37.0 ships
# StableDiffusionXLPipeline and SanaSprintPipeline.
S8_LADDER = ["released_037_x4", "released_037_x5", "released_036_x4"]
_ENGINE.DEFAULT_LADDERS.update({
    "sdxl-lightning": list(S8_LADDER),
    "dreamshaper-xl": list(S8_LADDER),
    "sana-sprint-1.6b": list(S8_LADDER),
})


def _load_pipeline(job: Dict[str, Any], model: str, pipe_cls,
                   cfg: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
    """S8 loader: base loader + distilled-UNet swap + scheduler override."""
    import torch

    notes: Dict[str, Any] = {}
    kwargs: Dict[str, Any] = {"torch_dtype": torch.float16}
    if cfg.get("low_cpu_mem_usage") is not None:
        kwargs["low_cpu_mem_usage"] = bool(cfg["low_cpu_mem_usage"])
    for k, v in (cfg.get("extra_kwargs") or {}).items():
        kwargs[k] = v
    if job.get("revision"):
        kwargs["revision"] = job["revision"]
    if job.get("vae_model_id"):
        from diffusers import AutoencoderKL
        kwargs["vae"] = AutoencoderKL.from_pretrained(
            job["vae_model_id"], torch_dtype=torch.float16)
        notes["vae"] = job["vae_model_id"]

    unet_ckpt = job.get("unet_checkpoint")
    if unet_ckpt:
        # Vendor-card recipe (SDXL-Lightning): build the UNet from the base
        # config, then load the distilled checkpoint's state dict into it.
        from diffusers import UNet2DConditionModel
        from huggingface_hub import hf_hub_download
        from safetensors.torch import load_file
        base_model = job["model_id"]
        unet = UNet2DConditionModel.from_config(base_model, subfolder="unet")
        unet = unet.to(torch.float16)
        state = load_file(hf_hub_download(unet_ckpt["repo"],
                                          unet_ckpt["file"]), device="cpu")
        missing, unexpected = unet.load_state_dict(state, strict=False)
        if missing:
            raise RuntimeError(
                f"distilled UNet checkpoint is missing {len(missing)} keys "
                f"(first: {missing[0]}); the base architecture does not match")
        notes["unet_checkpoint"] = f"{unet_ckpt['repo']}/{unet_ckpt['file']}"
        notes["unet_missing_keys"] = len(missing)
        notes["unet_unexpected_keys"] = len(unexpected)
        kwargs["unet"] = unet

    pipe = pipe_cls.from_pretrained(job["model_id"], **kwargs)

    if cfg.get("force_upcast_vae"):
        vae = getattr(pipe, "vae", None)
        if vae is not None and hasattr(vae, "config"):
            vae.config.force_upcast = True
            notes["vae_force_upcast"] = True
    if cfg.get("vae_fp32"):
        vae = getattr(pipe, "vae", None)
        if vae is not None:
            vae.to(dtype=torch.float32)
            notes["vae_fp32"] = True
    if cfg.get("text_encoder_fp32"):
        # fp16 overflow in a large text encoder (Gemma2) produces NaN
        # embeddings -> NaN latents -> black frames. The encoder is small
        # enough to run in fp32 without leaving the T4's VRAM budget; the
        # DiT and the VAE stay fp16 (the S8 brief).
        te = getattr(pipe, "text_encoder", None)
        if te is not None:
            te.to(dtype=torch.float32)
            notes["text_encoder_fp32"] = True
        else:
            notes["text_encoder_fp32"] = "no text_encoder on this pipeline"

    sched = cfg.get("scheduler")
    if sched:
        import diffusers
        cls = getattr(diffusers, sched["class"], None)
        if cls is None:
            raise RuntimeError(
                f"scheduler class {sched['class']!r} missing from diffusers")
        pipe.scheduler = cls.from_config(pipe.scheduler.config,
                                         **(sched.get("kwargs") or {}))
        notes["scheduler"] = sched["class"]
        notes["scheduler_kwargs"] = sched.get("kwargs") or {}

    if cfg.get("offload"):
        pipe.enable_model_cpu_offload()
        notes["model_cpu_offload"] = True
    else:
        pipe.to("cuda")
        notes["model_cpu_offload"] = False
    pipe.set_progress_bar_config(disable=True)
    return pipe, notes


_ENGINE._load_pipeline = _load_pipeline  # the engine calls the module global

# The engine's own main() must be captured BEFORE the function below is
# defined: when this file is appended to the engine source, both live in the
# same module namespace, so `def main` would shadow the engine's main and
# `_ENGINE.main()` would call itself forever (RecursionError, S8 attempt 1).
_ENGINE_MAIN = _ENGINE.main


def main() -> int:
    raw = os.environ.get("S8_JOB_JSON")
    if raw:
        _ENGINE.JOB_EMBEDDED = json.loads(raw)
    elif not getattr(_ENGINE, "JOB_EMBEDDED", None):
        job_path = Path("/kaggle/working/s8_job.json")
        if not job_path.is_file():
            print("BLOCKED: no embedded S8 job and no /kaggle/working/"
                  "s8_job.json", file=sys.stderr)
            return 1
        _ENGINE.JOB_EMBEDDED = json.loads(job_path.read_text(encoding="utf-8"))
    return _ENGINE_MAIN()


if __name__ == "__main__":
    sys.exit(main())
