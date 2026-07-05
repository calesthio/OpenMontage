"""Backlot event stream — append-only tool-event log per project.

Written by the BaseTool instrumentation layer (tools/base_tool.py) whenever a
tool executes against a project directory; consumed by the Backlot board's
watcher to power live activity and per-scene generating states.

Design rules:
- Observability must never break production: every public function swallows
  its own errors. A failed event write is silently dropped.
- Zero agent burden: project attribution is inferred from the tool's inputs
  (explicit ``project_dir`` or any path argument under ``projects/``).
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from lib.paths import PROJECTS_DIR, REPO_ROOT  # single source of truth

EVENTS_FILENAME = "events.jsonl"

# Thread-level serialization only. Cross-PROCESS appends are unsynchronized
# by design: single-line O_APPEND writes rarely tear, and read_events skips
# malformed lines, so a torn line degrades to one missing activity entry.
_write_lock = threading.Lock()

# Input keys checked (in order) when inferring the project a tool call
# belongs to. Explicit project keys win over path inference.
_EXPLICIT_PROJECT_KEYS = ("project_dir", "project_path")
_PATH_HINT_KEYS = (
    "output_path",
    "output_dir",
    "output_file",
    "input_path",
    "video_path",
    "audio_path",
    "image_path",
    "file_path",
)


def infer_project_dir(inputs: Any) -> Optional[Path]:
    """Best-effort: which project directory does this tool call belong to?

    Returns None when the call can't be attributed — the event is then
    simply not emitted (principle: never guess loudly, never fail).
    """
    if not isinstance(inputs, dict):
        return None
    try:
        # Only paths under the canonical projects root are attributable —
        # an explicit project_dir pointing elsewhere (HyperFrames workspace,
        # arbitrary user dir) must not receive an events.jsonl. Explicit
        # values are normalized to the project ROOT the same way hints are,
        # so project_dir="projects/x/renders/build" attributes to projects/x.
        projects_root = PROJECTS_DIR.resolve()
        for key in _EXPLICIT_PROJECT_KEYS + _PATH_HINT_KEYS:
            value = inputs.get(key)
            if not isinstance(value, (str, Path)) or not str(value):
                continue
            try:
                resolved = Path(value).resolve()
                rel = resolved.relative_to(projects_root)
            except (ValueError, OSError):
                continue
            if rel.parts:
                return PROJECTS_DIR / rel.parts[0]
    except Exception:
        return None
    return None


def emit_event(project_dir: Path | str, payload: dict[str, Any]) -> None:
    """Append one event to the project's events.jsonl. Never raises.

    Writes only into an EXISTING project directory — a typo'd path must not
    spawn a ghost project on the board.
    """
    try:
        project_dir = Path(project_dir)
        if not project_dir.is_dir():
            return
        entry = {"ts": datetime.now(timezone.utc).isoformat()}
        entry.update({k: v for k, v in payload.items() if v is not None})
        path = project_dir / EVENTS_FILENAME
        line = json.dumps(entry, default=str)
        with _write_lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception:
        pass


def read_events(project_dir: Path | str, limit: Optional[int] = None) -> list[dict[str, Any]]:
    """Read events for a project (oldest first). Tolerates malformed lines."""
    path = Path(project_dir) / EVENTS_FILENAME
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    if limit is not None:
        return events[-limit:]
    return events
