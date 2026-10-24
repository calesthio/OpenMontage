"""Run the opt-in paid ModelRunner media smoke suite through OpenMontage selectors.

One case per capability (plus the budget video tier), routed through the
capability selectors where one exists so the smoke also proves discovery and
routing. Estimated batch cost: about $0.69. Requires MODELRUNNER_KEY and an
explicit --allow-paid.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.audio.modelrunner_music import ModelRunnerMusic
from tools.audio.tts_selector import TTSSelector
from tools.graphics.image_selector import ImageSelector
from tools.video.video_selector import VideoSelector

ESTIMATED_BATCH_COST_USD = 0.69

CASES: tuple[dict[str, Any], ...] = (
    {
        "id": "kokoro_tts_narration",
        "capability": "tts",
        "model": "hexgrad/kokoro-82m",
        "inputs": {
            "text": (
                "ModelRunner smoke test. One key, one queue contract, and four media "
                "capabilities, verified end to end."
            ),
            "preferred_provider": "modelrunner",
            "model_id": "kokoro",
            "voice_id": "af_bella",
        },
        "output_name": "tts/kokoro_narration.wav",
    },
    {
        "id": "seedream_lite_still",
        "capability": "image",
        "model": "bytedance/seedream-v5/text-to-image",
        "inputs": {
            "prompt": (
                "A minimalist product photograph of a matte ceramic hourglass on pale "
                "sandstone, single warm key light from the left, soft shadow, editorial "
                "styling, no text, no watermark."
            ),
            "model": "bytedance/seedream-v5/text-to-image",
            "preferred_provider": "modelrunner",
            "allowed_providers": ["modelrunner"],
            "generation_mode": "generate",
        },
        "output_name": "images/seedream_lite_still.jpeg",
    },
    {
        "id": "lyria3_music_bed",
        "capability": "music",
        "model": "google/lyria-3/clip",
        "inputs": {
            "prompt": (
                "Instrumental only, no vocals: sparse hang drum and detuned kalimba "
                "trading phrases over a slow tape-warbled sub pulse, distant rain on "
                "a tin roof, unresolved and curious."
            ),
            "model": "google/lyria-3/clip",
        },
        "output_name": "music/lyria3_bed.mp3",
    },
    {
        "id": "seedance_mini_budget_clip",
        "capability": "video",
        "model": "bytedance/seedance-v2-mini/text-to-video",
        "inputs": {
            "prompt": (
                "A paper sailboat drifts across a rain puddle on dark asphalt, gentle "
                "ripples, reflected neon, light rain ambience."
            ),
            "model": "bytedance/seedance-v2-mini/text-to-video",
            "preferred_provider": "modelrunner",
            "allowed_providers": ["modelrunner"],
            "operation": "text_to_video",
            "duration": 4,
            "resolution": "480p",
            "aspect_ratio": "16:9",
        },
        "output_name": "videos/seedance_mini_budget_clip.mp4",
    },
    {
        "id": "wan27_flagship_clip",
        "capability": "video",
        "model": "wan-video/wan/v2.7/text-to-video",
        "inputs": {
            "prompt": (
                "Slow dolly toward a lighthouse at dusk as its beam sweeps across calm "
                "water, gulls in the distance, waves and wind ambience."
            ),
            "model": "wan-video/wan/v2.7/text-to-video",
            "preferred_provider": "modelrunner",
            "allowed_providers": ["modelrunner"],
            "operation": "text_to_video",
            "duration": 4,
            "resolution": "720P",
            "aspect_ratio": "16:9",
        },
        "output_name": "videos/wan27_flagship_clip.mp4",
    },
)

_SELECTORS = {
    "tts": TTSSelector,
    "image": ImageSelector,
    "video": VideoSelector,
    "music": ModelRunnerMusic,  # music has no capability selector; call the tool
}


def _probe(path_text: str) -> dict[str, Any]:
    path = Path(path_text)
    if not path.is_file():
        return {}
    from tools.video._shared import probe_output

    return probe_output(path)


def _result_record(case: dict[str, Any], result: Any) -> dict[str, Any]:
    data = dict(result.data or {})
    return {
        "id": case["id"],
        "capability": case["capability"],
        "model": case["model"],
        "success": result.success,
        "error": result.error,
        "request_id": data.get("request_id"),
        "artifacts": result.artifacts,
        "estimated_cost_usd": result.cost_usd,
        "probe": _probe(result.artifacts[0]) if result.artifacts else {},
        "data": data,
    }


def run(project_dir: Path, *, allow_paid: bool) -> int:
    if not allow_paid:
        raise SystemExit("Refusing paid ModelRunner calls without --allow-paid")

    project_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = project_dir / "smoke_manifest.json"
    records: list[dict[str, Any]] = []
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        records = [record for record in previous.get("records", []) if record.get("success")]

    def checkpoint() -> None:
        manifest = {
            "provider": "modelrunner",
            "endpoint_policy": "OpenMontage selectors -> ModelRunner tools -> ModelRunner queue API",
            "estimated_batch_cost_usd": ESTIMATED_BATCH_COST_USD,
            "records": records,
            "success": len({r["id"] for r in records if r["success"]}) == len(CASES),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    completed_ids = {record["id"] for record in records}
    for case in CASES:
        if case["id"] in completed_ids:
            continue
        runner = _SELECTORS[case["capability"]]()
        inputs = {**case["inputs"], "output_path": str(project_dir / case["output_name"])}
        result = runner.execute(inputs)
        records.append(_result_record(case, result))
        checkpoint()
        if not result.success:
            break

    checkpoint()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    print(json.dumps({
        "success": manifest["success"],
        "manifest": str(manifest_path),
        "results": [
            {
                "id": item["id"],
                "success": item["success"],
                "request_id": item.get("request_id"),
                "estimated_cost_usd": item.get("estimated_cost_usd"),
                "error": item["error"],
            }
            for item in records
        ],
    }, indent=2))
    return 0 if manifest["success"] else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--allow-paid", action="store_true")
    args = parser.parse_args()
    return run(args.project_dir, allow_paid=args.allow_paid)


if __name__ == "__main__":
    raise SystemExit(main())
