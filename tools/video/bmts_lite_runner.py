"""Small subprocess entry point that invokes the installed BMTS-Lite worker."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--request", required=True)
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    workspace = Path(args.workspace).expanduser().resolve()
    try:
        request = json.loads(Path(args.request).read_text(encoding="utf-8"))
        sys.path[:0] = [str(root), str(root / "engine")]
        from worker import run

        result = run(workspace, request, lambda _message, _percent: None)
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
