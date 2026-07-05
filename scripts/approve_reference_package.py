"""Approve an edited reference replication package for downstream planning."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.analysis.reference_review_approval import (
    APPROVAL_PHRASE,
    ReferenceReviewApproval,
)
from tools.analysis.reference_target_modes import SUPPORTED_REFERENCE_TARGET_MODES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replication_package_path", help="Edited replication package JSON")
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Project workspace root, for example projects/my-reference-video",
    )
    parser.add_argument(
        "--target-mode",
        choices=list(SUPPORTED_REFERENCE_TARGET_MODES),
        default="seedance",
        help="Approved downstream target mode. Reference-video v1 supports Seedance only.",
    )
    parser.add_argument("--reviewer", required=True, help="Human reviewer name or team role")
    parser.add_argument("--review-notes", default="", help="Optional human review notes")
    parser.add_argument(
        "--approval-phrase",
        required=True,
        help=f"Must exactly equal {APPROVAL_PHRASE!r}.",
    )
    parser.add_argument("--output-dir", help="Optional artifact output directory")
    args = parser.parse_args(argv)

    result = ReferenceReviewApproval().execute(
        {
            "project_dir": args.project_dir,
            "replication_package_path": args.replication_package_path,
            "target_mode": args.target_mode,
            "reviewer": args.reviewer,
            "review_notes": args.review_notes,
            "approval_phrase": args.approval_phrase,
            **({"output_dir": args.output_dir} if args.output_dir else {}),
        }
    )

    if not result.success:
        print(result.error or "Reference review approval failed", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "approved_package_path": result.data["json_path"],
                "approved_package": result.data["approved_package"],
                "paid_generation_started": False,
                "next_step": "preview_reference_seedance",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
