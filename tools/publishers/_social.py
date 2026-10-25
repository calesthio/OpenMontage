"""Shared helpers for networked social publishers (YouTube, TikTok).

Metadata reaching these tools may originate from web research or feeds, so it is
treated as untrusted: control characters are stripped and platform limits are
enforced here rather than trusting the caller.
"""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Vertical short-form limits shared by YouTube Shorts and TikTok uploads.
MAX_VIDEO_BYTES = 1024 * 1024 * 1024  # 1 GB hard ceiling for this tool family


def clean_text(text: Optional[str], limit: int, *, strip_angle_brackets: bool = True) -> str:
    text = _CONTROL.sub("", text or "")
    if strip_angle_brackets:  # YouTube rejects < and > in titles/descriptions
        text = text.replace("<", "").replace(">", "")
    text = text.strip()
    if len(text.encode("utf-8")) <= limit:
        return text
    encoded = text.encode("utf-8")[:limit]
    return encoded.decode("utf-8", errors="ignore").rstrip()


def clean_tags(tags: Optional[list[str]], total_limit: int = 450) -> list[str]:
    out: list[str] = []
    used = 0
    for tag in tags or []:
        tag = " ".join(clean_text(str(tag), 60).lstrip("#").replace(",", " ").split())
        if not tag or tag.lower() in (t.lower() for t in out):
            continue
        if used + len(tag) + 1 > total_limit:
            break
        out.append(tag)
        used += len(tag) + 1
    return out


def probe_video(path: Path) -> dict[str, Any]:
    """Return duration/width/height via ffprobe; empty dict if ffprobe is unavailable."""
    try:
        res = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height:format=duration",
             "-of", "default=nw=1", str(path)],
            capture_output=True, text=True, timeout=60,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {}
    info: dict[str, Any] = {}
    for line in res.stdout.splitlines():
        if "=" in line:
            key, val = line.split("=", 1)
            try:
                info[key] = float(val) if key == "duration" else int(val)
            except ValueError:
                pass
    return info


def validate_video(path: Path) -> Optional[str]:
    """Return an error string if the file can't be published, else None."""
    if not path.is_file():
        return f"video_path not found: {path}"
    size = path.stat().st_size
    if size == 0:
        return f"video file is empty: {path}"
    if size > MAX_VIDEO_BYTES:
        return f"video file too large ({size} bytes > {MAX_VIDEO_BYTES})"
    return None


def log_entry(platform: str, status: str, *, metadata: dict[str, Any], visibility: Optional[str] = None,
              url: Optional[str] = None, video_id: Optional[str] = None, error: Optional[str] = None,
              timestamp: Optional[str] = None) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "platform": platform,
        "status": status,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "metadata_used": {
            "title": metadata.get("title", ""),
            "description": metadata.get("description", ""),
            "hashtags": metadata.get("hashtags", []),
            "chapters": metadata.get("chapters", []),
        },
    }
    if visibility:
        entry["visibility"] = visibility
    if url:
        entry["url"] = url
    if video_id:
        entry["video_id"] = video_id
    if error:
        entry["error"] = error[:2000]
    return entry


def publish_log(entry: dict[str, Any]) -> dict[str, Any]:
    log = {"version": "1.0", "entries": [entry]}
    from schemas.artifacts import validate_artifact

    validate_artifact("publish_log", log)
    return log
