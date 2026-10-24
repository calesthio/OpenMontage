#!/usr/bin/env python3
"""S7-1: build the FIXED 10-scene test set for the S7 model bake-off.

Same 10 scenes, same seeds and same per-model prompt variants as S5-1 (the S5
test set was never rendered -- the S5 SDXL and klein kernel runs both died),
so the S5 files stay the historical record and S7 owns its own copy.

Rules (S7):
  - 10 scenes: s01, s03..s12 (s02 duplicate silhouette + s07 empty flat plate
    dropped in S5-1: no anatomy to test).
  - 1 seed per scene, the SAME seed for every model (seed-controlled).
  - 1024x1024.
  - ONE prompt variant per model, the best per PROMPTING_FACTS.md:
      sdxl   -> variant A  (structured keyword phrases) + short negative prompt
      zimage -> variant B  (prose, style stated first)  + NO negative prompt
      klein  -> variant C  (prose, anatomy first)       + NO negative prompt
  - 30 renders total (10 scenes x 3 models) -- no neutral fairness check.

Prompts are rendered by tools/prompting.builder (OpenCode-owned: read only).

Outputs (committed, no media):
  docs/openmontage/image_gen/S7_TEST_SET.json          run matrix (what the runner reads)
  docs/openmontage/image_gen/S7_TEST_SET_MAPPING.json  render_id -> scene/model/variant/seed
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
OUT_SET = REPO / "docs/openmontage/image_gen/S7_TEST_SET.json"
OUT_MAP = REPO / "docs/openmontage/image_gen/S7_TEST_SET_MAPPING.json"

DROP_SCENES = {"s02", "s07"}
VARIANT_BY_MODEL = {"sdxl": "A", "zimage": "B", "klein": "C"}
# Run order for S7 (one model per kernel run): SDXL, klein, Z-Image.
MODELS = ["sdxl", "klein", "zimage"]
RESOLUTION = [1024, 1024]


def build() -> tuple[Dict[str, Any], Dict[str, Any]]:
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
    n = 0
    for sid in scene_ids:
        spec = CreatureSpec.from_mapping(first_spec[sid])
        for model in MODELS:
            n += 1
            rid = f"r{n:04d}"
            variant = VARIANT_BY_MODEL[model]
            r = builder.build(target=model, variant=variant, spec=spec,
                              negation_style=False)
            renders.append({
                "render_id": rid,
                "scene_id": sid,
                "model": model,
                "variant": variant,
                "seed": first_seed[sid],
                "prompt": r["prompt"],
                "negative_prompt": r["negative_prompt"],
                "guidance_scale": r["guidance_scale"],
                "steps": r["steps"],
            })
            mapping[rid] = {
                "scene_id": sid,
                "scene_seed": first_seed[sid],
                "model": model,
                "variant": variant,
                "prompt_sha256": hashlib.sha256(
                    r["prompt"].encode("utf-8")).hexdigest(),
            }

    test_set = {
        "schema_version": "1.0",
        "milestone": "S7",
        "niche": matrix.get("niche", "speculative_evolution"),
        "pilot": matrix.get("pilot", ""),
        "source_matrix": str(MATRIX.relative_to(REPO)),
        "dropped_scenes": sorted(DROP_SCENES),
        "drop_reason": "the 2 easiest: s02 (duplicate vent-grazer silhouette of s01) "
                       "and s07 (empty flat abyssal plate, no anatomy)",
        "total_scenes": 10,
        "models": MODELS,
        "run_order": MODELS,
        "variant_by_model": VARIANT_BY_MODEL,
        "variant_rationale": {
            "sdxl": "structured keyword phrases + short negative prompt",
            "zimage": "prose, style first, no negative prompt",
            "klein": "prose, anatomy first, no negative prompt",
        },
        "resolution": RESOLUTION,
        "seeds": {sid: first_seed[sid] for sid in scene_ids},
        "seed_mode": "1 seed per scene, identical across the 3 models",
        "total_renders": len(renders),
        "renders": renders,
    }
    return test_set, {"mapping": mapping, "scenes": scene_ids}


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    test_set, map_doc = build()
    OUT_SET.write_text(json.dumps(test_set, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    OUT_MAP.write_text(json.dumps({
        "schema_version": "1.0",
        "milestone": "S7",
        "note": "blind mapping for the S7 test set; never shown to the owner's "
                "phone review sheets",
        "scene_order": map_doc["scenes"],
        "mapping": map_doc["mapping"],
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    per_model = {m: sum(1 for r in test_set["renders"] if r["model"] == m)
                 for m in MODELS}
    print(f"scenes: {len(map_doc['scenes'])} {map_doc['scenes']}")
    print(f"renders per model: {per_model}  total: {len(test_set['renders'])}")
    print(f"resolution: {RESOLUTION[0]}x{RESOLUTION[1]}")
    print(f"wrote {OUT_SET.relative_to(REPO)} and {OUT_MAP.relative_to(REPO)}")


if __name__ == "__main__":
    main()
