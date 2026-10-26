#!/usr/bin/env python3
"""S15: push the DreamShaper XL 1.0 style-lock test to ONE fresh Kaggle T4 kernel.

36 images (6 scenes x 3 styles x 2 seeds @ 1024x1024) + 6 wide images
(1344x768, best-objective-flags style, seed 1001) = 42 images, single kernel.

Recipe: Lykon/dreamshaper-xl-1-0 @ revision 41e66447..., StableDiffusionXLPipeline,
fp16, DEISMultistepScheduler, 25 steps, CFG 5.5, stock VAE, cuda (no offload),
NO bf16, NO bitsandbytes.

Usage:
  python scripts/s15_push_style_lock.py
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

KERNEL_SLUG = "forts845/of-bridge-runner"
JOBS_DIR = Path("/tmp/kilo/s15_jobs")
WIDTH = 1024
HEIGHT = 1024
SEEDS = [1001, 2027]
STEPS = 25
CFG = 5.5

MODEL_ID = "Lykon/dreamshaper-xl-1-0"
REVISION = "41e6644752a8c9aa63930e6043c4fd83c7708420"
OUTPUT_DIR = "s15_style_lock_dreamshaper-xl-1-0"

TAIL = ("stylized, non-photorealistic, empty low-detail lower fifth for captions, "
        "no text")
NEGATIVE = ("photorealistic, photo, glossy 3D render, mirror reflections, "
            "text, letters, watermark, signature, logo, extra limbs, fused "
            "anatomy, duplicated creature, cluttered bottom edge")

STYLES: Dict[str, str] = {
    "paper-cut": ("layered hand-cut paper shapes, matte paper fiber, clean cut "
                  "edges, separate foreground midground background, broad "
                  "directional light, soft cutout shadows, deep navy, mineral "
                  "teal, sea-glass, shell ivory, one coral accent"),
    "field-guide": ("naturalist field-guide illustration, clean ink outline with "
                    "thicker outer contour, opaque gouache colour masses, "
                    "restrained watercolor texture, warm paper, graphite, "
                    "sea-ink, kelp green, mineral blue, one rust-coral accent"),
    "graphic-novel-ink": ("bold graphic-novel ink illustration, thick outer "
                          "contour, sparse hatching, large flat shadow masses, "
                          "limited halftone, night ink, deep sea, electric "
                          "teal, pale bone, one coral accent"),
}

ANATOMY_CREATURE = "exactly six separate tendrils, two pairs of fins"

# Scenes verbatim from docs/openmontage/image_gen/S10_TEST_SET.json scene_specs.
# Anatomy lines follow S10 `spec.anatomy` exactly:
#   s01 grazer    limb_count 6  -> ANATOMY_CREATURE verbatim
#   s03 drifter   limb_count 0  -> limbless wording (a six-tendril sentence on a
#                                  limbless creature would be wrong by S10 and
#                                  would bias the owner's anatomy score)
#   s10 plate     limb_count 6  -> ANATOMY_CREATURE for the grazer, drifter limbless
SCENES: List[Dict[str, Any]] = [
    {
        "scene_id": "s01",
        "kind": "creature",
        "subject": "vent grazer grazing bacterial mats on a vent chimney",
        "anatomy": ("The vent grazer has exactly six separate tendrils, "
                    "two pairs of fins."),
        "environment": "hydrothermal vent chimney field, bacterial mats on basalt",
        "light": "bioluminescent vent glow, deep teal water, faint lime bioluminescence",
        "camera": "side silhouette, rule-of-thirds, copy space",
    },
    {
        "scene_id": "s03",
        "kind": "creature",
        "subject": "filter drifter sieving suspended microbes",
        "anatomy": ("The filter drifter is limbless: no legs, no arms, one "
                    "continuous undulating fin, wide filter mouth."),
        "environment": "open water column of the frozen alien ocean, drifting particles and faint light shafts",
        "light": "diffuse bioluminescent glow, neutral buoyancy",
        "camera": "three-quarter view, floating in mid-water",
    },
    {
        "scene_id": "s05",
        "kind": "habitat",
        "anatomy": "",
        "subject": "vent chimney field with black smokers",
        "environment": "field of hydrothermal vent chimneys on the ocean floor, black smoker plumes and mineral crusts",
        "light": "vent glow illuminating black smoker plumes",
        "camera": "wide establishing shot, low angle",
    },
    {
        "scene_id": "s06",
        "kind": "habitat",
        "anatomy": "",
        "subject": "under-ice cavern ceiling with melt pools",
        "environment": "cavern beneath the frozen ice shell, melt pools and ice columns",
        "light": "faint light filtering through ice, bioluminescent patches",
        "camera": "looking up at the ice ceiling",
    },
    {
        "scene_id": "s10",
        "kind": "creature",
        "anatomy": ("The vent grazer has exactly six separate tendrils, two "
                    "pairs of fins, and the filter drifter is limbless."),
        "subject": "food-web plate: chemosynthetic bacteria, vent grazer, filter drifter",
        "environment": "vent field with bacterial mat base of the food web",
        "light": "vent glow, bioluminescent lime bacteria",
        "camera": "wide plate with copy space for labels",
    },
    {
        "scene_id": "s12",
        "kind": "wide_scene",
        "anatomy": "",
        "subject": "frozen planet surface with vent plumes breaking through ice",
        "environment": "ice crust surface of the frozen ocean world, plume fractures and drifting frost",
        "light": "dim surface light, plume glow from below",
        "camera": "planet-surface wide, high angle",
    },
]


def build_prompt(scene: Dict[str, Any], style_key: str, style_text: str) -> str:
    parts: List[str] = []
    if scene.get("anatomy"):
        parts.append(scene["anatomy"])
    parts.append(f"{scene['subject']}.")
    parts.append(f"It is shown {scene['environment']}, {scene['light']},")
    parts.append(f"{style_text}.")
    parts.append(f"{scene['camera']}; {TAIL}")
    return " ".join(parts)


def build_job(attempt: int = 1) -> Dict[str, Any]:
    renders: List[Dict[str, Any]] = []
    rid = 0
    for scene in SCENES:
        for style_key, style_text in STYLES.items():
            for seed in SEEDS:
                rid += 1
                renders.append({
                    "render_id": f"s15_{style_key}_{scene['scene_id']}_{seed}",
                    "scene_id": scene["scene_id"],
                    "style": style_key,
                    "prompt": build_prompt(scene, style_key, style_text),
                    "negative_prompt": NEGATIVE,
                    "steps": STEPS,
                    "guidance_scale": CFG,
                    "seed": int(seed),
                    "width": WIDTH,
                    "height": HEIGHT,
                })
    wide_scenes = [s["scene_id"] for s in SCENES]
    job: Dict[str, Any] = {
        "job_id": f"s15-style-lock-{attempt}",
        "attempt": attempt,
        "model": "dreamshaper-xl-1-0",
        "model_id": MODEL_ID,
        "revision": REVISION,
        "output_dir": OUTPUT_DIR,
        "width": WIDTH,
        "height": HEIGHT,
        "dtype": "float16",
        "bf16": False,
        "bitsandbytes": False,
        "cpu_offload": False,
        "steps": STEPS,
        "guidance": CFG,
        "scheduler": {"class": "DEISMultistepScheduler", "kwargs": {}},
        "max_wall_seconds": 5400,
        "changed_from_previous": (f"attempt {attempt}: S15 style-lock test, "
                                  f"{len(renders)} renders @1024 + "
                                  f"{len(wide_scenes)} wide @1344x768"),
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "kind": "style_lock_s15",
        "renders": renders,
        "wide_scenes": wide_scenes,
        "model_config": {
            "pipeline_candidates": ["StableDiffusionXLPipeline", "AutoPipelineForText2Image"],
            "load_config": {
                "offload": False,
                "low_cpu_mem_usage": None,
                "extra_kwargs": {},
                "guidance_override": CFG,
                "scheduler": {"class": "DEISMultistepScheduler", "kwargs": {}},
            },
            "install_ladder": ["released_037_x4", "released_037_x5",
                               "released_041_x5_ao", "git_main_x4"],
        },
        "styles": list(STYLES),
        "seeds": list(SEEDS),
        "styles_note": ("paper-cut / field-guide / graphic-novel-ink, each "
                        "identical across all scenes; palettes translated to colour words"),
    }
    if len(renders) != 36:
        raise SystemExit(f"BLOCKED: {len(renders)} 1024 renders, expected 36")
    return job


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--attempt", type=int, default=1)
    ap.add_argument("--timeout", type=int, default=3600)
    args = ap.parse_args(argv)

    job = build_job(args.attempt)
    work = JOBS_DIR / job["job_id"]
    work.mkdir(parents=True, exist_ok=True)

    # prompt audit trail (repo-side; the kernel never sees style names in files)
    audit = {
        "job_id": job["job_id"],
        "created_utc": job["created_utc"],
        "model_id": MODEL_ID,
        "revision": REVISION,
        "tail": TAIL,
        "negative_prompt": NEGATIVE,
        "styles": STYLES,
        "anatomy_rule": {
            "s01": "ANATOMY_CREATURE verbatim (S10 limb_count 6)",
            "s03": "limbless wording (S10 limb_count 0)",
            "s10": "ANATOMY_CREATURE for the grazer + limbless drifter",
            "habitats": "no anatomy line",
        },
        "renders": [{"render_id": r["render_id"], "scene_id": r["scene_id"],
                     "style": r["style"], "seed": r["seed"],
                     "prompt": r["prompt"]} for r in job["renders"]],
    }
    for r in job["renders"]:
        if not r["prompt"].endswith(TAIL):
            raise SystemExit(f"BLOCKED: prompt for {r['render_id']} does not "
                             f"end with the required tail")
    audit_path = REPO / "docs/openmontage/image_gen/s15_prompts.json"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(f"prompts: {audit_path}")

    engine_py = REPO / "tools/kaggle_bridge/s15_style_lock_run.py"
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
        "revision": job["revision"],
        "kernel_slug": KERNEL_SLUG,
        "num_renders_1024": len(job["renders"]),
        "num_wide": len(job["wide_scenes"]),
        "total": len(job["renders"]) + len(job["wide_scenes"]),
        "steps": STEPS,
        "cfg": CFG,
        "scheduler": "DEISMultistepScheduler",
        "dtype": "float16",
        "push": ps.data.get("push"),
        "submitted_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (work / "submitted.json").write_text(
        json.dumps(submitted, indent=2), encoding="utf-8")
    print(json.dumps(submitted, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
