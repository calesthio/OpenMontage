"""Run the opt-in paid Atlas Cloud media smoke suite through OpenMontage selectors."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.graphics.image_selector import ImageSelector
from tools.video.video_selector import VideoSelector


IMAGE_CASES: tuple[dict[str, Any], ...] = (
    {
        "id": "seedream_campaign_key_visual",
        "skill": "campaign-key-visual",
        "model": "bytedance/seedream-v5.0-pro/text-to-image",
        "prompt": (
            "Create a premium vertical 3:4 campaign key visual for the fictional fragrance LUMA VALE. "
            "One faceted cobalt-glass bottle stands on pale travertine, surrounded by three translucent "
            "mineral ribbons and a single hard-edged pool of amber light. Reserve a calm upper-left field "
            "for exactly the headline LUMA VALE and the smaller line MINERAL LIGHT. Editorial art direction, "
            "precise readable typography, tactile glass, stone pores, controlled shadows, deep cobalt, warm "
            "amber and bone palette, 85mm product lens. No extra copy, duplicate bottle, fake certification, "
            "watermark, illegible letters, clutter, or generic luxury-ad styling. Fictional brand concept."
        ),
        "width": 1530,
        "height": 2040,
        "output_format": "png",
    },
    {
        "id": "gpt_image_impossible_material_portrait",
        "skill": "impossible-material-fashion-portrait",
        "model": "openai/gpt-image-2/text-to-image",
        "prompt": (
            "Create a 3:4 editorial fashion portrait of one fictional adult model from the waist up, wearing "
            "a sculptural coat made from translucent smoked quartz that bends like tailored wool while retaining "
            "crystalline fracture planes. The face remains natural and unobstructed; the coat has one high collar, "
            "two sleeves, plausible seams and gravity. Charcoal cyclorama, narrow cool rim light, soft frontal fill, "
            "medium-format 100mm look, realistic skin texture, restrained slate and silver palette. No real-person "
            "likeness, extra limbs, fused hands, jewelry, text, logo, watermark, plastic CGI sheen, or broken anatomy."
        ),
        "width": 1536,
        "height": 2048,
        "quality": "high",
        "output_format": "png",
    },
    {
        "id": "nano_banana_bottled_world",
        "skill": "bottled-miniature-world",
        "model": "google/nano-banana-2/text-to-image",
        "prompt": (
            "Create a vertical 3:4 cinematic illustration of one complete clear apothecary bottle on an old walnut "
            "desk, sealed with one rough cork. Inside is one coherent fictional 1:500 moonlit canal village: exactly "
            "one stone observatory, one arched bridge, three cottage clusters, one connected path, dark pines and "
            "warm lanterns, with no people or animals. Prove containment with a visible base, rounded shoulders, neck, "
            "thick rim, wall thickness, curved Fresnel highlights, edge refraction, caustics and tabletop contact. "
            "100mm macro, cool moonlight and warm windows. No duplicated landmark, floating architecture, scale drift, "
            "broken glass, cloudy walls, impossible refraction, label, logo, text, or watermark."
        ),
        "width": 1536,
        "height": 2048,
        "resolution": "2k",
        "thinking_level": "high",
        "output_format": "png",
    },
)


VIDEO_CASES: tuple[dict[str, Any], ...] = (
    {
        "id": "seedance25_architectural_reveal",
        "skill": "architectural-sketch-to-space-reveal",
        "model": "bytedance/seedance-2.5/text-to-video",
        "prompt": (
            "One continuous ten-second architectural transformation. Begin inches above an architect's graphite "
            "section drawing on cream paper; the camera glides forward as drawn contour lines rise into warm limestone "
            "walls, pencil hatching becomes slatted oak, and a blue wash becomes a shallow reflecting pool. Without a "
            "cut, pass through the drawn doorway into the completed sunlit courtyard while construction lines remain "
            "faintly visible in the finished surfaces. End in a stable wide reveal beneath a circular oculus. Precise "
            "geometry, believable material transition, restrained museum atmosphere, synchronized pencil-scratch and "
            "room-tone audio. No people, captions, logos, teleporting objects, melting walls, jump cuts, or watermark."
        ),
        "operation": "text_to_video",
        "duration": 10,
        "resolution": "720p",
        "aspect_ratio": "16:9",
        "generate_audio": True,
    },
    {
        "id": "seedance20_food_fantasy",
        "skill": "food-sensory-fantasy-film",
        "model": "bytedance/seedance-2.0/text-to-video",
        "prompt": (
            "A ten-second macro food fantasy in one fluid shot: an immaculate dark-chocolate sphere rests on black "
            "stone; a ribbon of hot espresso pours from above, the shell cracks cleanly and opens like petals, releasing "
            "a miniature saffron cloud and dozens of bright ruby pomegranate seeds that bounce with believable weight. "
            "The camera makes a slow 120-degree orbit and settles on the glossy molten center. High-speed detail, real "
            "fluid viscosity, crisp crumbs, appetizing steam, warm copper highlights, synchronized pour/crack/bounce audio. "
            "No hands, utensils, text, brand, duplicate fruit, dirty surface, implausible splash, jump cut, or watermark."
        ),
        "operation": "text_to_video",
        "duration": 10,
        "resolution": "720p",
        "aspect_ratio": "16:9",
        "generate_audio": True,
    },
    {
        "id": "gemini_omni_greenhouse_take",
        "skill": "generated-continuous-take",
        "model": "google/gemini-omni-flash/text-to-video",
        "prompt": (
            "One unbroken ten-second Steadicam journey through a vast night greenhouse during a gentle storm. Start "
            "tight on rain sliding down one glass pane, pull backward through hanging vines, descend beside a narrow "
            "irrigation channel, then curve around a gardener's empty brass cart as hundreds of bioluminescent blue "
            "flowers open in a timed wave toward the lens. Finish at a wide symmetrical view of the glowing conservatory. "
            "Continuous geography and lighting, foreground occlusion motivates the move, realistic wet leaves and glass, "
            "subtle rain and metal resonance. No people, hidden cuts, camera collision, duplicated cart, text, or watermark."
        ),
        "operation": "text_to_video",
        "duration": 10,
        "resolution": "720p",
        "aspect_ratio": "16:9",
        "thinking_level": "high",
    },
    {
        "id": "minimax_h3_creature_encounter",
        "skill": "creature-encounter-film",
        "model": "minimax/h3/text-to-video",
        "prompt": (
            "A ten-second cinematic wildlife encounter on a wind-scoured volcanic plateau at dawn. A small six-legged "
            "fictional basalt creature sprints beside the low tracking camera; each footfall kicks loose pumice with "
            "convincing mass. At second four it leaps across a narrow fissure, folds its stone plates midair, lands hard, "
            "slides, and braces while a sheet of dust overtakes the lens. The camera eases to a stop as the creature turns "
            "one luminous amber eye toward us. One continuous shot, consistent anatomy and scale, strong contact shadows, "
            "real inertia and debris physics. No attack, gore, extra creature, morphing limbs, text, logo, cut, or watermark."
        ),
        "operation": "text_to_video",
        "duration": 10,
        "resolution": "2K",
        "aspect_ratio": "16:9",
    },
)


def _result_record(case: dict[str, Any], result: Any) -> dict[str, Any]:
    return {
        "id": case["id"],
        "skill": case["skill"],
        "model": case["model"],
        "success": result.success,
        "error": result.error,
        "artifacts": result.artifacts,
        "cost_usd": result.cost_usd,
        "data": result.data,
    }


def run(project_dir: Path, *, images: bool, videos: bool, allow_paid: bool) -> int:
    if not allow_paid:
        raise SystemExit("Refusing paid Atlas calls without --allow-paid")

    project_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = project_dir / "smoke_manifest.json"
    records: list[dict[str, Any]] = []
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        records = [record for record in previous.get("records", []) if record.get("success")]

    def checkpoint() -> None:
        manifest = {
            "provider": "atlascloud",
            "endpoint_policy": "OpenMontage selectors -> Atlas Cloud tools -> Atlas Cloud HTTP API",
            "estimated_batch_cost_usd": 4.844,
            "records": records,
            "success": len({record["id"] for record in records if record["success"]}) == len(IMAGE_CASES) + len(VIDEO_CASES),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    completed_ids = {record["id"] for record in records}
    if images:
        selector = ImageSelector()
        for case in IMAGE_CASES:
            if case["id"] in completed_ids:
                continue
            inputs = {
                **case,
                "preferred_provider": "atlascloud",
                "allowed_providers": ["atlascloud"],
                "generation_mode": "generate",
                "output_path": str(project_dir / "images" / f"{case['id']}.png"),
            }
            inputs.pop("id")
            inputs.pop("skill")
            result = selector.execute(inputs)
            records.append(_result_record(case, result))
            checkpoint()
            if not result.success:
                break

    if videos and all(record["success"] for record in records):
        selector = VideoSelector()
        for case in VIDEO_CASES:
            if case["id"] in completed_ids:
                continue
            inputs = {
                **case,
                "preferred_provider": "atlascloud",
                "allowed_providers": ["atlascloud"],
                "output_path": str(project_dir / "videos" / f"{case['id']}.mp4"),
            }
            inputs.pop("id")
            inputs.pop("skill")
            result = selector.execute(inputs)
            records.append(_result_record(case, result))
            checkpoint()
            if not result.success:
                break

    checkpoint()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    print(json.dumps({
        "success": manifest["success"],
        "manifest": str(manifest_path),
        "results": [{"id": item["id"], "success": item["success"], "error": item["error"]} for item in records],
    }, indent=2))
    return 0 if manifest["success"] else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--images-only", action="store_true")
    parser.add_argument("--videos-only", action="store_true")
    parser.add_argument("--allow-paid", action="store_true")
    args = parser.parse_args()
    return run(
        args.project_dir,
        images=not args.videos_only,
        videos=not args.images_only,
        allow_paid=args.allow_paid,
    )


if __name__ == "__main__":
    raise SystemExit(main())
