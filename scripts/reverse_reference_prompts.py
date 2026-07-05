"""Reverse-engineer Seedance prompts from reference-video keyframes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.analysis.reference_prompt_reverse import ReferencePromptReverse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replication_package_path", help="Pending replication package JSON")
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Project workspace root, for example projects/my-reference-video",
    )
    parser.add_argument(
        "--provider",
        choices=["doubao"],
        default="doubao",
        help="Vision provider for prompt reverse. Defaults to doubao.",
    )
    parser.add_argument("--model", help="Optional provider model or endpoint id")
    parser.add_argument(
        "--max-keyframes-per-scene",
        type=int,
        default=3,
        help="Maximum keyframes sent to the vision model per scene.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=4096,
        help="Maximum output tokens requested from the vision model.",
    )
    parser.add_argument("--output-dir", help="Optional artifact output directory")
    args = parser.parse_args(argv)

    result = ReferencePromptReverse().execute(
        {
            "project_dir": args.project_dir,
            "replication_package_path": args.replication_package_path,
            "provider": args.provider,
            "max_keyframes_per_scene": args.max_keyframes_per_scene,
            "max_tokens": args.max_tokens,
            **({"model": args.model} if args.model else {}),
            **({"output_dir": args.output_dir} if args.output_dir else {}),
        }
    )

    if not result.success:
        print(result.error or "Reference prompt reverse failed", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "replication_package_path": result.data["json_path"],
                "replication_package": result.data["replication_package"],
                "scene_results": result.data.get("scene_results", []),
                "next_step": "edit_reference_package_or_bind_assets",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
