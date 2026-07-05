"""Create a local Seedance dry-run preview from an approved reference package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.analysis.reference_production_plan import ReferenceProductionPlan
from tools.video.seedance_batch import SeedanceBatch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replication_package_path", help="Edited and approved replication package JSON")
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Project workspace root, for example projects/my-reference-video",
    )
    parser.add_argument(
        "--duration",
        default="15",
        choices=[str(seconds) for seconds in range(4, 16)],
        help="Seedance clip duration in seconds. Defaults to 15.",
    )
    parser.add_argument(
        "--resolution",
        default="480p",
        choices=["480p", "720p"],
        help="Seedance output resolution. Defaults to 480p.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="Seedance local batch preview size, maximum 5. Defaults to 1.",
    )
    parser.add_argument(
        "--provider",
        choices=["runninghub", "fal", "replicate"],
        default="runninghub",
        help="Seedance provider task shape to preview. Defaults to runninghub.",
    )
    parser.add_argument(
        "--model-variant",
        default="sparkvideo-2.0-mini",
        help="Provider model variant to record in task payloads.",
    )
    parser.add_argument(
        "--aspect-ratio",
        choices=["adaptive", "16:9", "4:3", "1:1", "3:4", "9:16", "21:9"],
        default="9:16",
        help="Aspect ratio to include in each Seedance task. Defaults to 9:16.",
    )
    parser.add_argument(
        "--no-audio",
        action="store_true",
        help="Set generate_audio=false in planned tasks.",
    )
    parser.add_argument("--output-dir", help="Optional artifact output directory")
    args = parser.parse_args(argv)

    project_dir = args.project_dir
    output_dir = args.output_dir
    production_result = ReferenceProductionPlan().execute(
        {
            "project_dir": project_dir,
            "replication_package_path": args.replication_package_path,
            "target_mode": "seedance",
            "duration": args.duration,
            "resolution": args.resolution,
            "batch_size": args.batch_size,
            **({"output_dir": output_dir} if output_dir else {}),
        }
    )
    if not production_result.success:
        print(production_result.error or "Reference production plan failed", file=sys.stderr)
        return 1

    batch_result = SeedanceBatch().execute(
        {
            "project_dir": project_dir,
            "production_plan": production_result.data["production_plan"],
            "provider": args.provider,
            "model_variant": args.model_variant,
            "aspect_ratio": args.aspect_ratio,
            "generate_audio": not args.no_audio,
            "dry_run": True,
            "allow_paid_generation": False,
            **({"output_dir": output_dir} if output_dir else {}),
        }
    )
    if not batch_result.success:
        print(batch_result.error or "Seedance dry-run preview failed", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "dry_run": True,
                "paid_generation_started": False,
                "production_plan_path": production_result.data["json_path"],
                "seedance_batch_path": batch_result.data["json_path"],
                "production_plan": production_result.data["production_plan"],
                "seedance_batch": batch_result.data["seedance_batch"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
