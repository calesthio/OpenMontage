"""Import local assets and bind them to scenes in a reference package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.analysis.reference_asset_binding import ReferenceAssetBinding


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replication_package_path", help="Pending replication package JSON")
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Project workspace root, for example projects/my-reference-video",
    )
    parser.add_argument(
        "--asset",
        nargs=4,
        action="append",
        metavar=("PATH", "SCENE_ID", "ROLE", "ASSET_ID"),
        required=True,
        help="Asset binding tuple. Repeat for multiple assets.",
    )
    parser.add_argument(
        "--authorized",
        action="store_true",
        help="Mark all provided assets as team-authorized for this binding.",
    )
    parser.add_argument("--output-dir", help="Optional artifact output directory")
    args = parser.parse_args(argv)

    assets = [
        {
            "path": path,
            "scene_id": scene_id,
            "role": role,
            "id": asset_id,
            "authorized": args.authorized,
        }
        for path, scene_id, role, asset_id in args.asset
    ]

    result = ReferenceAssetBinding().execute(
        {
            "project_dir": args.project_dir,
            "replication_package_path": args.replication_package_path,
            "assets": assets,
            **({"output_dir": args.output_dir} if args.output_dir else {}),
        }
    )

    if not result.success:
        print(result.error or "Reference asset binding failed", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "replication_package_path": result.data["json_path"],
                "replication_package": result.data["replication_package"],
                "asset_manifest": result.data["asset_manifest"],
                "next_step": "approve_reference_package",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
