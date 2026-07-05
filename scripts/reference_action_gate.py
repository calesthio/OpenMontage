"""Validate a web/client UI action before exposing its command for execution."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.reference_project_snapshot import build_snapshot


def _find_action(snapshot: dict[str, Any], action_id: str) -> dict[str, Any]:
    for action in snapshot.get("ui_actions") or []:
        if action.get("id") == action_id:
            return action
    available = ", ".join(
        str(action.get("id"))
        for action in snapshot.get("ui_actions") or []
        if action.get("id")
    )
    suffix = f" Available actions: {available}" if available else ""
    raise ValueError(f"Unknown action: {action_id}.{suffix}")


def _validate_confirmation(action: dict[str, Any], confirmation_phrase: str | None) -> None:
    expected = action.get("confirmation_phrase")
    if not action.get("requires_confirmation"):
        return
    if confirmation_phrase != expected:
        raise ValueError(
            f"Action {action.get('id')} requires confirmation phrase: {expected}"
        )


def prepare_action(
    project_dir: str | Path,
    action_id: str,
    *,
    confirmation_phrase: str | None = None,
) -> dict[str, Any]:
    """Return a validated action command without executing it."""

    snapshot = build_snapshot(project_dir)
    action = _find_action(snapshot, action_id)
    if action.get("enabled") is False:
        raise ValueError(f"Action is disabled: {action_id}")
    _validate_confirmation(action, confirmation_phrase)
    return {
        "version": "1.0",
        "status": "ready_to_execute",
        "project_dir": snapshot["project_dir"],
        "phase": snapshot["phase"],
        "action_id": action["id"],
        "label": action["label"],
        "script": action.get("script"),
        "command": action.get("command"),
        "risk": action.get("risk"),
        "paid_generation": bool(action.get("paid_generation")),
        "requires_confirmation": bool(action.get("requires_confirmation")),
        "confirmation_checked": bool(action.get("requires_confirmation")),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", help="Reference-video project directory")
    parser.add_argument("action_id", help="UI action id from reference_project_snapshot.py")
    parser.add_argument(
        "--confirmation-phrase",
        help="Exact phrase required by paid or final delivery actions.",
    )
    args = parser.parse_args(argv)
    try:
        payload = prepare_action(
            args.project_dir,
            args.action_id,
            confirmation_phrase=args.confirmation_phrase,
        )
        exit_code = 0
    except ValueError as error:
        payload = {
            "version": "1.0",
            "status": "blocked",
            "project_dir": str(Path(args.project_dir).expanduser().resolve()),
            "action_id": args.action_id,
            "error": str(error),
        }
        exit_code = 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
