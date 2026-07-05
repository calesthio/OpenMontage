"""Create a dry-run Seedance task list or approved single-sample run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.video.seedance_batch import SeedanceBatch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("production_plan_path", help="Production plan JSON path")
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Project workspace root, for example projects/my-reference-video",
    )
    parser.add_argument(
        "--provider",
        choices=["runninghub", "fal", "replicate"],
        default="runninghub",
        help="Seedance provider task shape to prepare. Defaults to runninghub.",
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
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Request paid execution instead of dry-run. Currently blocked unless the tool supports it and explicit approval is supplied.",
    )
    parser.add_argument(
        "--allow-paid-generation",
        action="store_true",
        help="Explicit paid-generation approval flag required with --execute.",
    )
    parser.add_argument(
        "--approval-phrase",
        help='Required confirmation phrase for paid sample execution: "RUN SEEDANCE SAMPLE".',
    )
    parser.add_argument("--output-dir", help="Optional artifact output directory")
    args = parser.parse_args(argv)

    result = SeedanceBatch().execute(
        {
            "project_dir": args.project_dir,
            "production_plan_path": args.production_plan_path,
            "provider": args.provider,
            "model_variant": args.model_variant,
            "aspect_ratio": args.aspect_ratio,
            "generate_audio": not args.no_audio,
            "dry_run": not args.execute,
            "allow_paid_generation": args.allow_paid_generation,
            "sample_only": True,
            **({"approval_phrase": args.approval_phrase} if args.approval_phrase else {}),
            **({"output_dir": args.output_dir} if args.output_dir else {}),
        }
    )

    if not result.success:
        print(result.error or "Seedance batch planning failed", file=sys.stderr)
        return 1

    print(json.dumps(result.data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
