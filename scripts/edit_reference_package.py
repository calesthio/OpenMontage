"""Edit copy and Seedance prompts in a pending reference package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.analysis.reference_text_edit import ReferenceTextEdit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replication_package_path", help="Pending replication package JSON")
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Project workspace root, for example projects/my-reference-video",
    )
    parser.add_argument("--rewrite-text", help="Updated global rewrite draft text")
    parser.add_argument(
        "--scene-edit",
        nargs=3,
        action="append",
        metavar=("SCENE_ID", "SCRIPT_TEXT", "SEEDANCE_PROMPT"),
        help="Scene text tuple. Repeat for multiple scenes.",
    )
    parser.add_argument("--output-dir", help="Optional artifact output directory")
    args = parser.parse_args(argv)

    scene_edits = [
        {
            "scene_id": scene_id,
            "script_text": script_text,
            "seedance_prompt": seedance_prompt,
        }
        for scene_id, script_text, seedance_prompt in (args.scene_edit or [])
    ]

    result = ReferenceTextEdit().execute(
        {
            "project_dir": args.project_dir,
            "replication_package_path": args.replication_package_path,
            **({"rewrite_text": args.rewrite_text} if args.rewrite_text else {}),
            **({"scene_edits": scene_edits} if scene_edits else {}),
            **({"output_dir": args.output_dir} if args.output_dir else {}),
        }
    )

    if not result.success:
        print(result.error or "Reference text edit failed", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "replication_package_path": result.data["json_path"],
                "replication_package": result.data["replication_package"],
                "next_step": "bind_reference_assets_or_approve",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
