#!/usr/bin/env python3
"""S5-1: build the FIXED 10-scene test set for the S5 bake-off.

Source: docs/openmontage/image_gen/prompt_test_matrix.json (12 scenes, v1.1).
Rules (S5-1):
  - 10 scenes: the 12 minus the 2 easiest (s02 duplicate silhouette, s07 empty
    flat plate -> no anatomy to test).
  - 1 seed per scene, the scene's FIRST seed in the matrix; the SAME seed is
    used for every model (seed-controlled comparison).
  - 1024x1024 output.
  - ONE prompt variant per model, the best per docs/.../PROMPTING_FACTS.md:
      sdxl   -> variant A  (structured keyword phrases) + short negative prompt
      zimage -> variant B  (prose, style stated first) + NO negative prompt
      klein  -> variant C  (prose, anatomy first)      + NO negative prompt
  - Optional fairness check: 3 scenes rendered with ONE identical neutral text
    for all three models (variant "N"), if --with-neutral is passed.

Prompts are rendered by tools/prompting.builder (OpenCode-owned: read only).

Outputs (committed, no media):
  docs/openmontage/image_gen/S5_TEST_SET.json          run matrix (what the runner reads)
  docs/openmontage/image_gen/S5_TEST_SET_MAPPING.json  render_id -> scene/model/variant/seed
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
OUT_SET = REPO / "docs/openmontage/image_gen/S5_TEST_SET.json"
OUT_MAP = REPO / "docs/openmontage/image_gen/S5_TEST_SET_MAPPING.json"

DROP_SCENES = {"s02", "s07"}  # 2 easiest (see docstring)
VARIANT_BY_MODEL = {"sdxl": "A", "zimage": "B", "klein": "C"}
MODELS = ["sdxl", "zimage", "klein"]
RESOLUTION = [1024, 1024]
NEUTRAL_SCENES = ["s01", "s08", "s10"]  # fairness check: 3 scenes


def neutral_text(spec: Dict[str, Any]) -> str:
    """One plain descriptive prompt, byte-identical for all three models.

    Deliberately model-agnostic: no per-model ordering tricks, no negative
    prompt. Used only to check whether prompt-format gains survive when every
    model gets the same words.
    """
    anatomy = spec.get("anatomy", {}) or {}
    counts = (
        f"{anatomy.get('limb_count', 0)} limbs, {anatomy.get('eye_count', 0)} eyes, "
        f"{anatomy.get('horn_count', 0)} horns"
    )
    feats = ", ".join(anatomy.get("dominant_features", []) or [])
    palette = ", ".join(f"{k} {v}" for k, v in (spec.get("palette") or {}).items())
    bits = [
        f"{spec.get('style', 'flat-vector field-guide plate')} plate",
        f"{spec.get('subject', '')}",
        counts,
    ]
    if feats:
        bits.append(feats)
    bits += [
        spec.get("environment", ""),
        spec.get("light", ""),
        palette,
        spec.get("camera", ""),
        "clean image without text, no letters, no numerals, no watermark",
        "no people, no logos, not photorealistic",
    ]
    return ". ".join(b.strip() for b in bits if b and b.strip()) + "."


def build(with_neutral: bool) -> tuple[Dict[str, Any], Dict[str, Any]]:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    first_spec: Dict[str, Dict[str, Any]] = {}
    first_seed: Dict[str, int] = {}
    for job in matrix["jobs"]:
        sid = job["scene_id"]
        if sid in DROP_SCENES:
            continue
        first_spec.setdefault(sid, job["spec"])
        first_seed.setdefault(sid, int(job["seed"]))

    scene_ids = sorted(first_spec)  # s01, s03..s12
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

    if with_neutral:
        for sid in NEUTRAL_SCENES:
            text = neutral_text(first_spec[sid])
            for model in MODELS:
                n += 1
                rid = f"r{n:04d}"
                settings = builder.build(target=model, variant="A",
                                         spec=CreatureSpec.from_mapping(first_spec[sid]))
                # identical prompt text for every model; only runtime settings differ
                renders.append({
                    "render_id": rid,
                    "scene_id": sid,
                    "model": model,
                    "variant": "N",
                    "seed": first_seed[sid],
                    "prompt": text,
                    "negative_prompt": None,
                    "guidance_scale": settings["guidance_scale"],
                    "steps": settings["steps"],
                })
                mapping[rid] = {
                    "scene_id": sid,
                    "scene_seed": first_seed[sid],
                    "model": model,
                    "variant": "N",
                    "neutral": True,
                    "prompt_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                }

    test_set = {
        "schema_version": "1.0",
        "milestone": "S5",
        "niche": matrix.get("niche", "speculative_evolution"),
        "pilot": matrix.get("pilot", ""),
        "source_matrix": str(MATRIX.relative_to(REPO)),
        "dropped_scenes": sorted(DROP_SCENES),
        "drop_reason": "the 2 easiest: s02 (duplicate vent-grazer silhouette of s01) "
                       "and s07 (empty flat abyssal plate, no anatomy)",
        "total_scenes": 10,
        "models": MODELS,
        "variant_by_model": VARIANT_BY_MODEL,
        "variant_rationale": {
            "sdxl": "structured keyword phrases + short negative prompt",
            "zimage": "prose, style first, no negative prompt",
            "klein": "prose, anatomy first, no negative prompt",
        },
        "resolution": RESOLUTION,
        "seeds": {sid: first_seed[sid] for sid in scene_ids},
        "seed_mode": "1 seed per scene, identical across the 3 models",
        "neutral_check": {
            "enabled": bool(with_neutral),
            "scenes": NEUTRAL_SCENES,
            "rule": "identical prompt text for all 3 models; only steps/guidance differ",
        },
        "renders": renders,
    }
    return test_set, {"mapping": mapping, "scenes": scene_ids}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-neutral", action="store_true",
                    help="also add the 3-scene identical-text fairness check")
    args = ap.parse_args()
    test_set, map_doc = build(args.with_neutral)
    OUT_SET.write_text(json.dumps(test_set, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    OUT_MAP.write_text(json.dumps({
        "schema_version": "1.0",
        "milestone": "S5",
        "note": "blind mapping for the S5 test set; never shown to the owner's "
                "phone review sheets",
        "scene_order": map_doc["scenes"],
        "mapping": map_doc["mapping"],
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    per_model = {m: sum(1 for r in test_set["renders"] if r["model"] == m)
                 for m in MODELS}
    print(f"scenes: {len(map_doc['scenes'])} {map_doc['scenes']}")
    print(f"renders per model: {per_model}")
    print(f"resolution: {RESOLUTION[0]}x{RESOLUTION[1]}")
    print(f"wrote {OUT_SET.relative_to(REPO)} and {OUT_MAP.relative_to(REPO)}")


if __name__ == "__main__":
    main()
