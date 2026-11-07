#!/usr/bin/env python3
"""TDD tests for tools/kaggle_bridge/s1_z_image_turbo_run.py (S1-1).

stdlib only. Does not touch torch/diffusers (not installed locally). Covers:
- the runner compiles,
- build_manifest emits the required manifest structure (job_id, model,
  model_revision, dtype float16, bitsandbytes False, cpu_fallback False,
  images[] with file/sha256/bytes/prompt/seed/seconds),
- manifest enforces the S1-1 fp16/no-bitsandbytes/no-CPU-fallback contract.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

RUN_PATH = REPO / "tools" / "kaggle_bridge" / "s1_z_image_turbo_run.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("s1_z_image_turbo_run", RUN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runner_compiles():
    import py_compile
    py_compile.compile(str(RUN_PATH), doraise=True)


def test_build_manifest_structure():
    mod = _load_module()
    job = {
        "job_id": "s1-z-image-turbo-1",
        "model": "Tongyi-MAI/Z-Image-Turbo",
        "model_revision": "main",
        "width": 1024,
        "height": 1024,
        "steps": 9,
        "guidance_scale": 0.0,
    }
    images = [
        {
            "file": "s1_zit_4000.png",
            "sha256": "a" * 64,
            "bytes": 12345,
            "prompt": "a creature silhouette",
            "seed": 4000,
            "width": 1024,
            "height": 1024,
            "seconds": 12.5,
        }
    ]
    manifest = mod.build_manifest(job, images, load_seconds=120.0,
                                  gpu_minutes=25.5, peak_vram_mb=10240.0,
                                  versions={"diffusers": "0.43.0.dev0",
                                            "diffusers_commit": "abc1234",
                                            "transformers": "5.1.0",
                                            "huggingface_hub": "1.16.0",
                                            "torch": "2.6.0"})
    assert manifest["job_id"] == "s1-z-image-turbo-1"
    assert manifest["model"] == "Tongyi-MAI/Z-Image-Turbo"
    assert manifest["model_revision"] == "main"
    assert manifest["dtype"] == "float16"
    assert manifest["bitsandbytes"] is False
    assert manifest["cpu_fallback"] is False
    assert manifest["device"] == "cuda"
    assert manifest["rights_basis"] == "ai_generated_illustration"
    assert manifest["generator"] == "AI"
    assert manifest["load_seconds"] == 120.0
    assert manifest["gpu_minutes"] == 25.5
    assert manifest["peak_vram_mb"] == 10240.0
    assert len(manifest["images"]) == 1
    ent = manifest["images"][0]
    for key in ("file", "sha256", "bytes", "prompt", "seed", "seconds"):
        assert key in ent, key


def test_build_manifest_records_seeds_and_params():
    mod = _load_module()
    job = {
        "job_id": "s1-z-image-turbo-1",
        "model": "Tongyi-MAI/Z-Image-Turbo",
        "model_revision": "main",
        "width": 1024,
        "height": 1024,
        "steps": 9,
        "guidance_scale": 0.0,
    }
    seeds = [4000, 4001, 4002]
    images = [
        {"file": f"s1_zit_{s:05d}.png", "sha256": "x" * 64, "bytes": 1,
         "prompt": f"p{s}", "seed": s, "width": 1024, "height": 1024,
         "seconds": 1.0}
        for s in seeds
    ]
    manifest = mod.build_manifest(job, images, 0.0, 0.0, None,
                                  versions={"diffusers": "0.43.0.dev0",
                                            "diffusers_commit": "abc1234",
                                            "transformers": "5.1.0",
                                            "huggingface_hub": "1.16.0",
                                            "torch": "2.6.0"})
    got = [ent["seed"] for ent in manifest["images"]]
    assert got == seeds
    assert manifest["steps"] == 9
    assert manifest["guidance_scale"] == 0.0
