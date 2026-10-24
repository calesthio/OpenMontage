#!/usr/bin/env python3
"""S8-2a: build the S8 test set for the THREE new models.

Same 10 scenes, same seeds and the same prompt variants as S7 (so the S7
frames for SDXL Base and FLUX.2-klein-4B stay comparable and are REUSED, not
re-rendered). Only the three new models are rendered here.

Per-model prompt variant and sampling settings (all from the official model
cards, see docs/openmontage/image_gen/CANDIDATES_S8.md):

  sdxl-lightning    target sdxl / variant A (structured + short negative)
                    8 steps, guidance 0, EulerDiscreteScheduler with
                    timestep_spacing="trailing"  (SDXL-Lightning card)
  dreamshaper-xl    target sdxl / variant A (structured + short negative)
                    4 steps, guidance 2, DPMSolverMultistepScheduler
                    (dreamshaper-xl-lightning card)
  sana-sprint-1.6b  target klein / variant C (prose, anatomy first, no negative
                    prompt - SanaSprintPipeline has no negative_prompt arg)
                    2 steps, guidance 4.5 (card snippet + diffusers default)

Outputs (committed, no media):
  docs/openmontage/image_gen/S8_TEST_SET.json          renders for the new models
  docs/openmontage/image_gen/S8_TEST_SET_MAPPING.json  render_id -> scene/model
  docs/openmontage/image_gen/S8_REUSE.json             the S7 runs we reuse
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tools.prompting.builder import CreatureSpec, PromptBuilder  # noqa: E402

MATRIX = REPO / "docs/openmontage/image_gen/prompt_test_matrix.json"
OUT_SET = REPO / "docs/openmontage/image_gen/S8_TEST_SET.json"
OUT_MAP = REPO / "docs/openmontage/image_gen/S8_TEST_SET_MAPPING.json"
OUT_REUSE = REPO / "docs/openmontage/image_gen/S8_REUSE.json"
LOG_DIR = REPO / "docs/openmontage/image_gen/logs"

DROP_SCENES = {"s02", "s07"}
RESOLUTION = [1024, 1024]

# The three new models. `steps`/`guidance_scale` come from the vendor card;
# `target`/`variant` come from PROMPTING_FACTS.md (best variant per family).
MODEL_SPEC: Dict[str, Dict[str, Any]] = {
    "sdxl-lightning": {
        "target": "sdxl",
        "variant": "A",
        "steps": 8,
        "guidance_scale": 0.0,
        "negative_prompt": True,
        "model_id": "stabilityai/stable-diffusion-xl-base-1.0",
        "pipeline_class": "StableDiffusionXLPipeline",
        "vae_model_id": "madebyollin/sdxl-vae-fp16-fix",
        "unet_checkpoint": {
            "repo": "ByteDance/SDXL-Lightning",
            "file": "sdxl_lightning_8step_unet.safetensors",
        },
        "card": "https://huggingface.co/ByteDance/SDXL-Lightning (2026-10-22)",
    },
    "dreamshaper-xl": {
        "target": "sdxl",
        "variant": "A",
        "steps": 4,
        "guidance_scale": 2.0,
        "negative_prompt": True,
        "model_id": "Lykon/dreamshaper-xl-lightning",
        "pipeline_class": "StableDiffusionXLPipeline",
        "vae_model_id": None,
        "unet_checkpoint": None,
        "card": "https://huggingface.co/Lykon/dreamshaper-xl-lightning (2026-10-22)",
    },
    "sana-sprint-1.6b": {
        "target": "klein",
        "variant": "C",
        "steps": 2,
        "guidance_scale": 4.5,
        # SanaSprintPipeline.__call__ has no negative_prompt argument
        "negative_prompt": False,
        "model_id": "Efficient-Large-Model/Sana_Sprint_1.6B_1024px_diffusers",
        "pipeline_class": "SanaSprintPipeline",
        "vae_model_id": None,
        "unet_checkpoint": None,
        "card": "https://huggingface.co/Efficient-Large-Model/"
                "Sana_Sprint_1.6B_1024px_diffusers (2026-10-22)",
    },
}

# S7 runs that S8 reuses (no re-render). The sha256 list is the proof that the
# reused frames are the ones the S7 kernel produced.
REUSE = {
    "sdxl": {"job_id": "s7-sdxl-1", "manifest": "logs/s7-sdxl-1/manifest.json"},
    "klein": {"job_id": "s7-klein-1", "manifest": "logs/s7-klein-1/manifest.json"},
}

RENDER_PREFIX = {
    "sdxl-lightning": "r1",
    "dreamshaper-xl": "r2",
    "sana-sprint-1.6b": "r3",
}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def reuse_records() -> List[Dict[str, Any]]:
    """Load the S7 manifests and record every reused image sha256."""
    out: List[Dict[str, Any]] = []
    for model, ref in REUSE.items():
        man_path = LOG_DIR.parent / ref["manifest"]
        man = json.loads(man_path.read_text(encoding="utf-8"))
        cache = REPO / "output/s7_cache" / model
        for entry in man.get("images", []):
            img = cache / entry["file"]
            if not img.is_file():
                raise SystemExit(
                    f"BLOCKED: reused image missing from the cache: {img}")
            digest = sha256_of(img)
            if digest != entry.get("sha256"):
                raise SystemExit(
                    f"BLOCKED: cached {model}/{entry['file']} sha256 "
                    f"{digest} != S7 manifest {entry.get('sha256')}")
            out.append({
                "model": model,
                "job_id": man.get("job_id"),
                "render_id": entry.get("render_id"),
                "scene_id": entry.get("scene_id"),
                "file": entry.get("file"),
                "sha256": digest,
                "bytes": entry.get("bytes"),
                "cached": str(img.relative_to(REPO)),
            })
    return out


def build() -> Dict[str, Any]:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    first_spec: Dict[str, Dict[str, Any]] = {}
    first_seed: Dict[str, int] = {}
    for job in matrix["jobs"]:
        sid = job["scene_id"]
        if sid in DROP_SCENES:
            continue
        first_spec.setdefault(sid, job["spec"])
        first_seed.setdefault(sid, int(job["seed"]))

    scene_ids = sorted(first_spec)
    if len(scene_ids) != 10:
        raise SystemExit(f"expected 10 scenes, got {len(scene_ids)}: {scene_ids}")

    builder = PromptBuilder()
    renders: List[Dict[str, Any]] = []
    mapping: Dict[str, Any] = {}
    for model, spec in MODEL_SPEC.items():
        prefix = RENDER_PREFIX[model]
        for i, sid in enumerate(scene_ids, start=1):
            built = builder.build(spec["target"], spec["variant"],
                                  CreatureSpec.from_mapping(first_spec[sid]))
            negative = built["negative_prompt"] if spec["negative_prompt"] else None
            render = {
                "render_id": f"{prefix}{i:03d}",
                "scene_id": sid,
                "model": model,
                "target": spec["target"],
                "variant": spec["variant"],
                "prompt": built["prompt"],
                "negative_prompt": negative,
                "guidance_scale": spec["guidance_scale"],
                "steps": spec["steps"],
                "seed": first_seed[sid],
            }
            renders.append(render)
            mapping[render["render_id"]] = {
                "scene_id": sid, "model": model, "variant": spec["variant"],
                "seed": first_seed[sid], "steps": spec["steps"],
                "guidance_scale": spec["guidance_scale"],
            }

    reuse = reuse_records()
    return {
        "schema_version": "1.0",
        "milestone": "S8-2",
        "resolution": RESOLUTION,
        "scenes": scene_ids,
        "seeds": first_seed,
        "models": list(MODEL_SPEC),
        "model_spec": MODEL_SPEC,
        "renders": renders,
        "reuse": reuse,
        "notes": "S8 renders the 3 new models only; SDXL Base and "
                 "FLUX.2-klein-4B are reused from S7 (sha256 verified). "
                 "Z-Image-Turbo is not submitted in S8.",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()
    doc = build()
    OUT_SET.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    OUT_MAP.write_text(json.dumps({
        "schema_version": "1.0",
        "milestone": "S8-2",
        "renders": doc["renders"],
    }, indent=2) + "\n", encoding="utf-8")
    OUT_REUSE.write_text(json.dumps({
        "schema_version": "1.0",
        "milestone": "S8-2",
        "reused_models": list(REUSE),
        "images": doc["reuse"],
    }, indent=2) + "\n", encoding="utf-8")
    print(f"scenes: {len(doc['scenes'])}  new renders: {len(doc['renders'])}  "
          f"reused S7 frames: {len(doc['reuse'])}")
    for m in doc["models"]:
        n = sum(1 for r in doc["renders"] if r["model"] == m)
        print(f"  {m}: {n} renders")
    return 0


if __name__ == "__main__":
    sys.exit(main())
