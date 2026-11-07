#!/usr/bin/env python3
"""S10-1: build the frozen visual-style test set (54 renders).

Same six scenes as the S7/S8 bake-off (2 creatures, 2 habitats, 1 food-web
plate, 1 wide scene), each drawn in THREE candidate styles with the SAME three
seeds per scene:

    S-A  flat vector illustration (saturated colour, bold contours, gradients,
         rich coloured background, readable shapes, no texture noise)
    S-B  natural-history gouache field-guide plate (warm paper texture, visible
         brush strokes, detailed anatomy, muted-but-varied palette)
    S-C  layered paper-cut diorama (foreground/midground/background layers,
         soft drop shadows, depth)

6 scenes x 3 styles x 3 seeds = 54 renders at 1024x1024.

Rules carried into the set:
  * the model is the CONFIG-LOCKED one (`config/image_engine.json` -> model);
    the prompt target/variant comes from the same config entry, and the prompt
    is rendered by `tools/prompting/builder.py` (OpenCode-owned, read only),
  * every creature prompt carries the written anatomy counts,
  * style text is positive phrasing, never "plain background", never a named
    artist / channel / franchise,
  * every scene has its own background wording and its own palette (varied
    colour), and all three styles of a scene share the scene's palette so the
    comparison isolates the style,
  * seeds come from the reserved illustration range 3000-3999 and are never
    reused across scenes.

Output (committed, no media): docs/openmontage/image_gen/S10_TEST_SET.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tools.prompting.builder import CreatureSpec, PromptBuilder  # noqa: E402

MATRIX = REPO / "docs/openmontage/image_gen/prompt_test_matrix.json"
OUT_SET = REPO / "docs/openmontage/image_gen/S10_TEST_SET.json"
CONFIG = REPO / "config/image_engine.json"

RESOLUTION = [1024, 1024]

# The six scenes of the milestone, with the reason each one is in the test.
SCENE_PLAN: Dict[str, Dict[str, Any]] = {
    "s01": {
        "kind": "creature",
        "role": "vent grazer (limbed creature)",
        "caption": "The vent grazer crops bacterial mats at the chimney rim.",
        "palette": {"deep_teal": "#14455C", "bioluminescent_lime": "#A8E06F",
                    "basalt_charcoal": "#3B444B", "pale_bone": "#EDE7D8"},
        "seeds": [3100, 3101, 3102],
    },
    "s03": {
        "kind": "creature",
        "role": "filter drifter (limbless creature)",
        "caption": "Filter drifters sieve microbes from the open water column.",
        "palette": {"midnight_indigo": "#1C2A5E", "ice_aqua": "#6FD3D8",
                    "glacier_blue": "#2E6E8E", "pale_bone": "#EDE7D8"},
        "environment": "open water column of the frozen alien ocean, drifting "
                       "particles and faint light shafts",
        "seeds": [3110, 3111, 3112],
    },
    "s05": {
        "kind": "habitat",
        "role": "vent chimney field (habitat)",
        "caption": "Chimney fields vent mineral-rich water onto the sea floor.",
        "palette": {"abyss_black": "#1A1B1E", "sulphur_amber": "#E8A33D",
                    "smoker_grey": "#5A5F66", "vent_lime": "#A8E06F"},
        "environment": "field of hydrothermal vent chimneys on the ocean floor, "
                       "black smoker plumes and mineral crusts",
        "seeds": [3120, 3121, 3122],
    },
    "s06": {
        "kind": "habitat",
        "role": "under-ice cavern (habitat)",
        "caption": "Melt pools glow beneath the frozen ice shell.",
        "palette": {"glacier_blue": "#2E6E8E", "ice_white": "#DCE9EF",
                    "cavern_indigo": "#22304F",
                    "bioluminescent_lime": "#A8E06F"},
        "environment": "cavern beneath the frozen ice shell, melt pools and "
                       "ice columns",
        "seeds": [3130, 3131, 3132],
    },
    "s10": {
        "kind": "food_web_plate",
        "role": "food-web plate (bacteria -> grazer -> drifter)",
        "caption": "Chemosynthetic bacteria feed the whole vent food web.",
        "palette": {"plate_teal": "#0F3B4A", "mat_lime": "#B7E86A",
                    "basalt_charcoal": "#3B444B", "pale_bone": "#EDE7D8"},
        "seeds": [3140, 3141, 3142],
    },
    "s12": {
        "kind": "wide_scene",
        "role": "frozen surface wide scene",
        "caption": "Plumes break through the ice crust of the frozen ocean world.",
        "palette": {"ice_violet": "#5B5A8C", "frost_white": "#E6EAF2",
                    "plume_teal": "#2E7D8A", "dim_surface_grey": "#3A3F4A"},
        "environment": "ice crust surface of the frozen ocean world, plume "
                       "fractures and drifting frost",
        "seeds": [3150, 3151, 3152],
    },
}

# The three candidate styles. `prompt` is the phrase handed to the read-only
# builder as the spec's style; `tokens` are asserted to be in every rendered
# prompt (so a prompt can never silently lose its style block).
STYLES: Dict[str, Dict[str, Any]] = {
    "S-A": {
        "name": "flat vector illustration",
        "prompt": (
            "flat vector illustration with saturated colour, bold contours, "
            "smooth gradients, a rich coloured background, readable shapes "
            "and no texture noise"
        ),
        "tokens": ["flat vector illustration", "saturated colour",
                   "bold contours", "smooth gradients",
                   "rich coloured background", "readable shapes",
                   "no texture noise"],
        "creature_detail_phrase": "readable shapes",
    },
    "S-B": {
        "name": "natural-history gouache field-guide plate",
        "prompt": (
            "natural-history gouache field-guide plate with warm paper "
            "texture, visible brush strokes, detailed anatomy and a muted "
            "but varied palette"
        ),
        "tokens": ["natural-history gouache field-guide plate",
                   "warm paper texture", "visible brush strokes",
                   "detailed anatomy", "muted but varied palette"],
        "creature_detail_phrase": "detailed anatomy",
    },
    "S-C": {
        "name": "layered paper-cut diorama",
        "prompt": (
            "layered paper-cut diorama with separate foreground, midground "
            "and background layers, soft drop shadows and clear depth"
        ),
        "tokens": ["layered paper-cut diorama", "foreground", "midground",
                   "background layers", "soft drop shadows", "clear depth"],
        "creature_detail_phrase": "separate foreground, midground and "
                                  "background layers",
    },
}


def load_config_lock() -> Dict[str, Any]:
    """The active adapter from config/image_engine.json, fail-closed."""
    from tools.illustration.model_registry import active_adapter, load_engine
    engine = load_engine(CONFIG)
    adapter = active_adapter(engine)
    if adapter.dtype != "float16":
        raise SystemExit(f"BLOCKED: locked model dtype is {adapter.dtype!r}; "
                         "S10 runs fp16 only")
    if adapter.prompt_target not in {"sdxl", "zimage", "klein"}:
        raise SystemExit(f"BLOCKED: unknown prompt target {adapter.prompt_target!r}")
    return {
        "engine_status": engine.status,
        "model": adapter.key,
        "display_name": adapter.display_name,
        "model_id": adapter.model_id,
        "prompt_target": adapter.prompt_target,
        "prompt_variant": adapter.prompt_variant,
        "steps": adapter.steps,
        "guidance": adapter.guidance,
        "scheduler": dict(adapter.scheduler),
        "dtype": adapter.dtype,
        "install_ladder": list(adapter.install_ladder),
        "versions": dict(adapter.versions),
    }


def scene_specs() -> Dict[str, Any]:
    """The six base specs from the S7 matrix, with S10 palette/background."""
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    base: Dict[str, Any] = {}
    for job in matrix["jobs"]:
        sid = job["scene_id"]
        if sid in SCENE_PLAN and sid not in base:
            base[sid] = job["spec"]
    missing = sorted(set(SCENE_PLAN) - set(base))
    if missing:
        raise SystemExit(f"BLOCKED: scenes missing from the matrix: {missing}")
    out: Dict[str, Any] = {}
    for sid, plan in SCENE_PLAN.items():
        spec = deepcopy(base[sid])
        spec["palette"] = dict(plan["palette"])
        if plan.get("environment"):
            spec["environment"] = plan["environment"]
        out[sid] = spec
    return out


def build() -> Dict[str, Any]:
    lock = load_config_lock()
    specs = scene_specs()
    builder = PromptBuilder()
    renders: List[Dict[str, Any]] = []
    n = 0
    for sid in sorted(SCENE_PLAN):
        plan = SCENE_PLAN[sid]
        base = specs[sid]
        anatomy = base.get("anatomy") or {}
        for style_key in ("S-A", "S-B", "S-C"):
            spec = deepcopy(base)
            spec["style"] = STYLES[style_key]["prompt"]
            for seed in plan["seeds"]:
                n += 1
                built = builder.build(lock["prompt_target"],
                                      lock["prompt_variant"],
                                      CreatureSpec.from_mapping(spec))
                prompt = built["prompt"]
                for token in STYLES[style_key]["tokens"]:
                    if token not in prompt:
                        raise SystemExit(
                            f"BLOCKED: style token {token!r} missing from "
                            f"{sid}/{style_key}: {prompt}")
                for token in ("plain background", "white background"):
                    if token in prompt.lower():
                        raise SystemExit(
                            f"BLOCKED: banned phrase {token!r} in {sid}/{style_key}")
                renders.append({
                    # neutral render id: the kernel output carries no style name
                    "render_id": f"p{n:03d}",
                    "scene_id": sid,
                    "style": style_key,
                    "seed": seed,
                    "kind": plan["kind"],
                    "prompt": prompt,
                    "negative_prompt": built["negative_prompt"],
                    "steps": lock["steps"],
                    "guidance_scale": lock["guidance"],
                    "dtype": lock["dtype"],
                    "anatomy_counts": {
                        "limbs": int(anatomy.get("limb_count", 0)),
                        "eyes": int(anatomy.get("eye_count", 0)),
                        "horns": int(anatomy.get("horn_count", 0)),
                        "features": list(anatomy.get("dominant_features") or []),
                    },
                })
    if len(renders) != 54:
        raise SystemExit(f"BLOCKED: expected 54 renders, built {len(renders)}")

    return {
        "schema_version": "1.0",
        "milestone": "S10-1",
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "purpose": "visual-style test: 3 styles x 6 scenes x 3 seeds, blind "
                   "owner pack, objective flags only",
        "resolution": RESOLUTION,
        "model": lock["model"],
        "model_source": "config/image_engine.json -> model (LOCKED)",
        "model_display_name": lock["display_name"],
        "model_id": lock["model_id"],
        "engine_status": lock["engine_status"],
        "prompt_target": lock["prompt_target"],
        "prompt_variant": lock["prompt_variant"],
        "steps": lock["steps"],
        "guidance": lock["guidance"],
        "scheduler": lock["scheduler"],
        "dtype": lock["dtype"],
        "bitsandbytes": False,
        "install_ladder": lock["install_ladder"],
        "versions_reference": lock["versions"],
        "prompt_source": "tools/prompting/builder.py (OpenCode-owned, read only)",
        "scenes": sorted(SCENE_PLAN),
        "scene_specs": [
            {"scene_id": sid, "kind": SCENE_PLAN[sid]["kind"],
             "role": SCENE_PLAN[sid]["role"],
             "caption": SCENE_PLAN[sid]["caption"],
             "seeds": list(SCENE_PLAN[sid]["seeds"]),
             "spec": specs[sid]}
            for sid in sorted(SCENE_PLAN)
        ],
        "styles": ["S-A", "S-B", "S-C"],
        "style_specs": {
            key: {"name": val["name"], "prompt": val["prompt"],
                  "prompt_tokens": val["tokens"],
                  "creature_detail_phrase": val["creature_detail_phrase"]}
            for key, val in STYLES.items()
        },
        "notes": [
            "Scenes s01/s03/s05/s06/s10/s12 are the S7/S8 scenes, so the style "
            "test is comparable with the model bake-off; the palette and some "
            "background wording are re-authored per scene for S10.",
            "The 2 habitat scenes and the wide scene carry a zero anatomy "
            "count (0 limbs / 0 eyes / 0 horns) because the read-only builder "
            "always renders the counts line; that is identical across the three "
            "styles, so the comparison is unaffected.",
        ],
        "renders": renders,
    }


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.parse_args(argv)
    doc = build()
    OUT_SET.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    per_style: Dict[str, int] = {}
    for r in doc["renders"]:
        per_style[r["style"]] = per_style.get(r["style"], 0) + 1
    print(f"model: {doc['model']} ({doc['prompt_target']}/{doc['prompt_variant']}, "
          f"{doc['steps']} steps, {doc['dtype']})")
    print(f"scenes: {len(doc['scenes'])}  renders: {len(doc['renders'])}  "
          f"per style: {per_style}")
    print(f"wrote {OUT_SET.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
