#!/usr/bin/env python3
"""S4-3 prompt-rule experiment verification.

Uses tools/prompting.builder (OpenCode-owned, READ ONLY — do not edit) to render
the controlled prompt variants for 6 scenes and confirm the experiment conditions
produce the intended prompt differences. Objective image measurement (text-like
artifacts via QC detector, image-hash duplicates, blur score) requires the
generated images from S4-2 Kaggle jobs; this script verifies prompt construction
only (no GPU, no media).

Experiment design (6 scenes, same seeds):
  (a) Z-Image: with vs without negative_prompt argument → builder sets
      negative_prompt=None for zimage (vendor guidance: Turbo guidance=0 so
      negative_prompt is ignored). Negation phrasing vs positive phrasing.
      Style-first (zimage default) vs style-last.
  (b) klein: anatomy-first (variant C) vs anatomy-last (variant B).
      guidance 1.0 (no CFG) vs recommended 3.5 (diffusers FluxPipeline default).
  (c) SDXL: with vs without the short negative prompt.

Outputs: prompt variant table + assertions that each condition differs as
expected. No images generated here; no media committed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.prompting import (  # noqa: E402 - OpenCode-owned, read only
    AnatomySpec,
    CreatureSpec,
    PromptBuilder,
)

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "openmontage" / "image_gen" / "S4_PROMPT_EXPERIMENT_VARIANTS.json"


def _spec(subject, limb_count, features):
    return CreatureSpec(
        subject=subject,
        anatomy=AnatomySpec(limb_count=limb_count, eye_count=2, horn_count=0,
                            dominant_features=features),
        environment="hydrothermal vent chimney field, bacterial mats on basalt",
        light="bioluminescent vent glow, deep teal water, faint lime",
        style="flat-vector field-guide plate",
        palette={"deep teal": "#14455C", "bioluminescent lime": "#A8E06F",
                 "basalt charcoal": "#3B444B", "pale bone": "#EDE7D8"},
        camera="side silhouette, rule-of-thirds, copy space",
        constraints={"no_text": True, "no_people": True, "no_logos": True,
                     "not_photorealistic": True, "silhouette_first": True},
    )


# 6 scenes (mirrors S1-1 breakdown): 3 silhouettes, 2 habitat, 1 anatomy crop
SCENES = [
    ("s01", _spec("vent grazer grazing bacterial mats", 6, ["long neck", "spade-like forelimbs"])),
    ("s02", _spec("vent grazer full-body silhouette", 6, ["long neck", "spade-like forelimbs"])),
    ("s03", _spec("filter drifter in open water", 0, ["undulating fin", "wide filter mouth"])),
    ("s04", _spec("ice burrower in sediment", 0, ["tapered head", "segmented body"])),
    ("s05", _spec("vent chimney field habitat", 6, ["long neck", "spade-like forelimbs"])),
    ("s08", _spec("vent grazer forelimb anatomy crop", 6, ["spade-like forelimbs", "joint detail"])),
]


def render_experiment(scene_id, spec, model, variant, negation_style=False):
    builder = PromptBuilder(seed=4000)
    return builder.build(model, variant, spec, negation_style=negation_style)


def main() -> None:
    results = {"scenes": [], "assertions": []}

    for scene_id, spec in SCENES:
        scene = {"scene_id": scene_id, "subject": spec.subject, "variants": {}}
        for model in ("zimage", "klein", "sdxl"):
            entry = {
                "A_tags": render_experiment(scene_id, spec, model, "A", False),
                "B_prose": render_experiment(scene_id, spec, model, "B", False),
                "C_anatomy_first": render_experiment(scene_id, spec, model, "C", False),
                "B_negation": render_experiment(scene_id, spec, model, "B", True),
                "B_positive": render_experiment(scene_id, spec, model, "B", False),
            }
            scene["variants"][model] = entry
        results["scenes"].append(scene)

    # ---- Assertions: each experiment condition produces intended difference ----
    a = results["assertions"]

    # (a) Z-Image: negative_prompt always None (ignored when guidance=0)
    zimg = render_experiment("s01", SCENES[0][1], "zimage", "B", False)
    a.append(("zimage negative_prompt is None", zimg["negative_prompt"] is None))
    a.append(("zimage guidance_scale is 0.0", zimg["guidance_scale"] == 0.0))
    # negation vs positive phrasing differ in prompt text
    z_neg = render_experiment("s01", SCENES[0][1], "zimage", "B", True)
    z_pos = render_experiment("s01", SCENES[0][1], "zimage", "B", False)
    a.append(("zimage negation != positive prompt text",
              z_neg["prompt"] != z_pos["prompt"]))
    # style-first: zimage B prompt starts with style phrase
    a.append(("zimage style stated first",
              z_pos["prompt"].startswith("A flat-vector field-guide plate")))

    # (b) klein: anatomy-first (C) vs anatomy-last (B) differ
    klein_b = render_experiment("s01", SCENES[0][1], "klein", "B", False)
    klein_c = render_experiment("s01", SCENES[0][1], "klein", "C", False)
    a.append(("klein C != B (anatomy-first vs last)", klein_c["prompt"] != klein_b["prompt"]))
    a.append(("klein negative_prompt is None", klein_b["negative_prompt"] is None))
    a.append(("klein steps == 4", klein_b["steps"] == 4))
    # guidance 1.0 (no CFG) vs recommended 3.5 — builder sets None (project uses diffusers default)
    a.append(("klein guidance_scale None (uses diffusers default 3.5)",
              klein_b["guidance_scale"] is None))

    # (c) SDXL: with vs without negative prompt
    sdxl_with = render_experiment("s01", SCENES[0][1], "sdxl", "A", False)
    a.append(("sdxl negative_prompt present", sdxl_with["negative_prompt"] is not None))
    a.append(("sdxl guidance_scale 7.5", sdxl_with["guidance_scale"] == 7.5))
    a.append(("sdxl steps 50", sdxl_with["steps"] == 50))

    # determinism
    a.append(("determinism same inputs same output",
              render_experiment("s01", SCENES[0][1], "sdxl", "A", False)
              == render_experiment("s01", SCENES[0][1], "sdxl", "A", False)))

    results["assertions"] = [{"check": k, "passed": v} for k, v in a]
    results["all_passed"] = all(v for _, v in a)

    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    failed = [k for k, v in a if not v]
    print(f"S4-3 experiment variants: {len(a)} assertions, {len(failed)} failed")
    if failed:
        print("FAILED:", failed)
        sys.exit(1)
    print("All S4-3 prompt-rule experiment assertions passed.")


if __name__ == "__main__":
    main()
