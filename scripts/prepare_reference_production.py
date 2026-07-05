"""Prepare a production handoff plan from an approved reference package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.analysis.reference_production_plan import ReferenceProductionPlan
from tools.analysis.reference_target_modes import SUPPORTED_REFERENCE_TARGET_MODES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replication_package_path", help="Edited replication package JSON")
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Output project directory, for example projects/my-reference-video",
    )
    parser.add_argument(
        "--target-mode",
        choices=list(SUPPORTED_REFERENCE_TARGET_MODES),
        default="seedance",
        help="Downstream production path to prepare. Reference-video v1 supports Seedance only.",
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
        help="Seedance local batch planner size, maximum 5. Defaults to 1.",
    )
    parser.add_argument("--output-dir", help="Optional artifact output directory")
    args = parser.parse_args(argv)

    result = ReferenceProductionPlan().execute(
        {
            "project_dir": args.project_dir,
            "replication_package_path": args.replication_package_path,
            "target_mode": args.target_mode,
            "duration": args.duration,
            "resolution": args.resolution,
            "batch_size": args.batch_size,
            **({"output_dir": args.output_dir} if args.output_dir else {}),
        }
    )

    if not result.success:
        print(result.error or "Reference production plan failed", file=sys.stderr)
        return 1

    print(json.dumps(result.data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
