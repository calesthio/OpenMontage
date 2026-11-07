#!/usr/bin/env python3
"""S12: push ONE bake-off model to a fresh Kaggle kernel run.

One model per kernel, never several dependency stacks in one kernel.
3 models x 6 S10 scenes x 3 seeds = 54 images, flat-vector field-guide
(S-A) style — the owner has not picked an S10 winner yet, so S-A is used
and that is stated in the report.

Usage:
  python scripts/s12_push_bakeoff.py --model klein
  python scripts/s12_push_bakeoff.py --model dreamshaper-xl-1-0 --retry-with-vae
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tools.kaggle_bridge.kaggle_bridge import KaggleBridgeTool  # noqa: E402

KERNEL_SLUG = "forts845/openmontage-runner"
JOBS_DIR = Path("/tmp/kilo/s12_jobs")
WIDTH = 1024
HEIGHT = 1024
SEEDS = [1001, 2027, 4409]
STYLE = "S-A"

SCENES: List[Dict[str, Any]] = [
    {
        "scene_id": "s01",
        "subject": "vent grazer grazing bacterial mats on a vent chimney",
        "anatomy": "6 limbs, 2 eyes, 0 horns",
        "features": ["long neck", "spade-like forelimbs"],
        "environment": "hydrothermal vent chimney field, bacterial mats on basalt",
        "light": "bioluminescent vent glow, deep teal water, faint lime bioluminescence",
        "palette": "deep_teal #14455C, bioluminescent_lime #A8E06F, basalt_charcoal #3B444B, pale_bone #EDE7D8",
        "camera": "side silhouette, rule-of-thirds, copy space",
    },
    {
        "scene_id": "s03",
        "subject": "filter drifter sieving suspended microbes",
        "anatomy": "0 limbs, 0 eyes, 0 horns",
        "features": ["undulating fin", "wide filter mouth"],
        "environment": "open water column of the frozen alien ocean, drifting particles and faint light shafts",
        "light": "diffuse bioluminescent glow, neutral buoyancy",
        "palette": "midnight_indigo #1C2A5E, ice_aqua #6FD3D8, glacier_blue #2E6E8E, pale_bone #EDE7D8",
        "camera": "three-quarter view, floating in mid-water",
    },
    {
        "scene_id": "s05",
        "subject": "vent chimney field with black smokers",
        "anatomy": "0 limbs, 0 eyes, 0 horns",
        "features": [],
        "environment": "field of hydrothermal vent chimneys on the ocean floor, black smoker plumes and mineral crusts",
        "light": "vent glow illuminating black smoker plumes",
        "palette": "abyss_black #1A1B1E, sulphur_amber #E8A33D, smoker_grey #5A5F66, vent_lime #A8E06F",
        "camera": "wide establishing shot, low angle",
    },
    {
        "scene_id": "s06",
        "subject": "under-ice cavern ceiling with melt pools",
        "anatomy": "0 limbs, 0 eyes, 0 horns",
        "features": [],
        "environment": "cavern beneath the frozen ice shell, melt pools and ice columns",
        "light": "faint light filtering through ice, bioluminescent patches",
        "palette": "glacier_blue #2E6E8E, ice_white #DCE9EF, cavern_indigo #22304F, bioluminescent_lime #A8E06F",
        "camera": "looking up at the ice ceiling",
    },
    {
        "scene_id": "s10",
        "subject": "food-web plate: chemosynthetic bacteria, vent grazer, filter drifter",
        "anatomy": "6 limbs, 2 eyes, 0 horns",
        "features": [],
        "environment": "vent field with bacterial mat base of the food web",
        "light": "vent glow, bioluminescent lime bacteria",
        "palette": "plate_teal #0F3B4A, mat_lime #B7E86A, basalt_charcoal #3B444B, pale_bone #EDE7D8",
        "camera": "wide plate with copy space for labels",
    },
    {
        "scene_id": "s12",
        "subject": "frozen planet surface with vent plumes breaking through ice",
        "anatomy": "0 limbs, 0 eyes, 0 horns",
        "features": [],
        "environment": "ice crust surface of the frozen ocean world, plume fractures and drifting frost",
        "light": "dim surface light, plume glow from below",
        "palette": "ice_violet #5B5A8C, frost_white #E6EAF2, plume_teal #2E7D8A, dim_surface_grey #3A3F4A",
        "camera": "planet-surface wide, high angle",
    },
]

MODELS: Dict[str, Dict[str, Any]] = {
    "klein": {
        "model_id": "black-forest-labs/FLUX.2-klein-4B",
        "pipeline_class": "Flux2KleinPipeline",
        "steps": 4,
        "guidance": 1.0,
        "scheduler": None,
        "cpu_offload": True,
        "extra_kwargs": {},
        "install_ladder": ["released_037_x4", "released_037_x5",
                           "released_041_x5_ao", "git_main_x5_ao"],
        "prompt_target": "klein",
        "prompt_variant": "C",
    },
    "dreamshaper-xl-lightning": {
        "model_id": "Lykon/dreamshaper-xl-lightning",
        "pipeline_class": "StableDiffusionXLPipeline",
        "steps": 4,
        "guidance": 2.0,
        "scheduler": "DPMSolverMultistepScheduler",
        "cpu_offload": False,
        "extra_kwargs": {"variant": "fp16"},
        "install_ladder": ["released_037_x4", "released_037_x5",
                           "released_041_x5_ao", "git_main_x4"],
        "prompt_target": "sdxl",
        "prompt_variant": "A",
    },
    "dreamshaper-xl-1-0": {
        "model_id": "Lykon/dreamshaper-xl-1-0",
        "pipeline_class": "StableDiffusionXLPipeline",
        "steps": 25,
        "guidance": 5.5,
        "scheduler": "DEISMultistepScheduler",
        "cpu_offload": False,
        "extra_kwargs": {},
        "install_ladder": ["released_037_x4", "released_037_x5",
                           "released_041_x5_ao", "git_main_x4"],
        "prompt_target": "sdxl",
        "prompt_variant": "A",
    },
}

RENDER_FIELDS = ("render_id", "scene_id", "variant", "prompt",
                 "negative_prompt", "steps", "guidance_scale", "seed")


def build_prompt(scene: Dict[str, Any]) -> str:
    parts: List[str] = [f"{scene['anatomy']}."]
    if scene["features"]:
        parts.append(f"{', '.join(scene['features'])}.")
    parts.append(f"{scene['subject']} has {scene['anatomy']}.")
    parts.append(f"It is shown {scene['environment']}, {scene['light']},")
    parts.append("in a flat vector illustration with saturated colour, bold contours, "
                 "smooth gradients, a rich coloured background, readable shapes "
                 "and no texture noise,")
    parts.append(f"{scene['palette']}.")
    parts.append(f"{scene['camera']}; clean image without text, text-free, "
                 "no letters, no numerals, no watermark, not photorealistic, "
                 "no people, no logos.")
    return " ".join(parts)


def build_job(model_key: str, attempt: int = 1,
              retry_with_vae: bool = False) -> Dict[str, Any]:
    if model_key not in MODELS:
        raise SystemExit(f"BLOCKED: unknown model {model_key!r}; "
                         f"registered: {sorted(MODELS)}")
    m = MODELS[model_key]
    renders: List[Dict[str, Any]] = []
    for scene in SCENES:
        for seed in SEEDS:
            renders.append({
                "render_id": f"s12-{model_key}-{scene['scene_id']}-{seed}",
                "scene_id": scene["scene_id"],
                "variant": STYLE,
                "prompt": build_prompt(scene),
                "negative_prompt": None,
                "steps": int(m["steps"]),
                "guidance_scale": float(m["guidance"]),
                "seed": int(seed),
            })
    if len(renders) != 18:
        raise SystemExit(f"BLOCKED: {len(renders)} renders, expected 18")
    model_config: Dict[str, Any] = {
        "pipeline_candidates": [m["pipeline_class"]],
        "load_config": {
            "offload": bool(m["cpu_offload"]),
            "low_cpu_mem_usage": None,
            "extra_kwargs": dict(m["extra_kwargs"]),
            "guidance_override": float(m["guidance"]),
            "scheduler": {"class": m["scheduler"], "kwargs": {}
                          } if m["scheduler"] else {"class": None, "kwargs": {}},
        },
        "install_ladder": list(m["install_ladder"]),
        "dtype": "float16",
        "prompt_target": m["prompt_target"],
        "prompt_variant": m["prompt_variant"],
        "steps": int(m["steps"]),
        "guidance": float(m["guidance"]),
        "scheduler": {"class": m["scheduler"], "kwargs": {}
                      } if m["scheduler"] else {},
        "versions": {},
    }
    job: Dict[str, Any] = {
        "job_id": f"s12-{model_key}-{attempt}",
        "attempt": attempt,
        "model": model_key,
        "model_id": m["model_id"],
        "output_dir": f"s12_bakeoff_{model_key}",
        "width": WIDTH,
        "height": HEIGHT,
        "dtype": "float16",
        "bitsandbytes": False,
        "cpu_fallback": False,
        "install_ladder": list(m["install_ladder"]),
        "model_config": model_config,
        "renders": renders,
        "max_wall_seconds": 5400,
        "changed_from_previous": (f"attempt {attempt}: S12 model bake-off, "
                                  f"18 renders, style {STYLE}"),
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "kind": "model_bakeoff_s12",
        "styles": [STYLE],
    }
    if retry_with_vae:
        job["vae_model_id"] = "madebyollin/sdxl-vae-fp16-fix"
    return job


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True, choices=sorted(MODELS))
    ap.add_argument("--attempt", type=int, default=1)
    ap.add_argument("--retry-with-vae", action="store_true",
                    help="load madebyollin/sdxl-vae-fp16-fix as the VAE "
                         "(dreamshaper-xl-1-0 fallback only)")
    ap.add_argument("--timeout", type=int, default=3600)
    args = ap.parse_args(argv)

    if args.retry_with_vae and args.model != "dreamshaper-xl-1-0":
        raise SystemExit("BLOCKED: --retry-with-vae only applies to "
                         "dreamshaper-xl-1-0")

    job = build_job(args.model, args.attempt, args.retry_with_vae)
    work = JOBS_DIR / job["job_id"]
    work.mkdir(parents=True, exist_ok=True)

    engine_py = REPO / "tools/kaggle_bridge/s7_bakeoff_run.py"
    engine_text = engine_py.read_text(encoding="utf-8")
    marker = "JOB_EMBEDDED = None"
    if marker not in engine_text:
        raise SystemExit("BLOCKED: JOB_EMBEDDED marker missing in the runner")
    literal = json.dumps(json.dumps(job, ensure_ascii=False))
    run_text = engine_text.replace(marker,
                                   f"JOB_EMBEDDED = json.loads({literal})\n", 1)
    if run_text.count('if __name__ == "__main__":') != 1:
        raise SystemExit("BLOCKED: the composed runner must keep exactly one "
                         "__main__ guard")
    (work / "run.py").write_text(run_text, encoding="utf-8")

    bridge = KaggleBridgeTool()
    bj = bridge.execute({
        "command": "build_job_folder",
        "job_folder": str(work),
        "job_id": job["job_id"],
        "kernel_slug": KERNEL_SLUG,
        "job": job,
        "run_py": run_text,
        "enable_gpu": True,
        "enable_internet": True,
        "kaggle_cmd": "kaggle",
    })
    if not bj.success:
        raise SystemExit(f"BUILD FAILED: {bj.error}")

    ps = bridge.execute({
        "command": "push",
        "job_folder": str(work),
        "kernel_slug": KERNEL_SLUG,
        "timeout": int(args.timeout),
        "accelerator": "gpu",
        "max_retries": 1,
        "kaggle_cmd": "kaggle",
    })
    if not ps.success:
        raise SystemExit(f"PUSH FAILED: {ps.error}")

    submitted = {
        "job_id": job["job_id"],
        "model": job["model"],
        "model_id": job["model_id"],
        "kernel_slug": KERNEL_SLUG,
        "num_renders": len(job["renders"]),
        "install_ladder": job["install_ladder"],
        "push": ps.data.get("push"),
        "submitted_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "vae_model_id": job.get("vae_model_id"),
    }
    (work / "submitted.json").write_text(
        json.dumps(submitted, indent=2), encoding="utf-8")
    print(json.dumps(submitted, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
