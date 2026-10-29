#!/usr/bin/env python3
"""tools/illustration/review_queue.py - the REVIEW queue for the owner.

Builds a queue of the episode's images sorted by **objective** flags only:

  * text_like      - lettering or text-like artifacts detected,
  * blur_low       - below the configured sharpness floor,
  * size_mismatch  - the frame is not the target frame,
  * palette_drift  - the style palette does not show up in the image,
  * duplicate      - a near-duplicate of another image in the episode.

Anatomy, composition and beauty are **not** judged here: they stay
owner-judged, and the queue says so.

The queue is written as JSON and as CSV (the owner works through the CSV).
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from tools.illustration.illustration_qc import (
    duplicate_report,
    qc_image,
)

#: Flag -> priority weight (higher = more urgent for the owner).
FLAG_WEIGHTS: Dict[str, int] = {
    "text_like": 60,
    "size_mismatch": 40,
    "palette_drift": 25,
    "blur_low": 20,
    "duplicate": 15,
}

#: The flags a human must look at, in the order they are explained.
FLAG_ORDER = ("text_like", "size_mismatch", "palette_drift", "blur_low",
              "duplicate")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def build_review_queue(paths: Sequence[str], target_w: int, target_h: int,
                       palette: Optional[Dict[str, str]] = None,
                       out_dir: Optional[str | Path] = None,
                       episode: str = "") -> Dict[str, Any]:
    """Build the review queue for a set of images."""
    files = list(paths)
    results = [qc_image(path, target_w, target_h, palette or {}) for path in files]
    duplicates = duplicate_report(files)["duplicates"]
    duplicate_files: Dict[str, List[str]] = {}
    for pair in duplicates:
        duplicate_files.setdefault(pair["file_i"], []).append(pair["file_j"])
        duplicate_files.setdefault(pair["file_j"], []).append(pair["file_i"])

    items: List[Dict[str, Any]] = []
    for path, result in zip(files, results):
        flags: List[str] = []
        if result["text_like"]:
            flags.append("text_like")
        if not result["size_ok"] or not result["aspect_ok"]:
            flags.append("size_mismatch")
        if result.get("palette", {}).get("drift"):
            flags.append("palette_drift")
        if not result["blur_ok"]:
            flags.append("blur_low")
        if path in duplicate_files:
            flags.append("duplicate")
        if not flags:
            continue
        priority = sum(FLAG_WEIGHTS.get(flag, 10) for flag in flags)
        items.append({
            "file": path,
            "name": Path(path).name,
            "flags": flags,
            "priority": priority,
            "detail": {
                "text_like": result["text_like"],
                "text_evidence": result.get("text_evidence", {}),
                "blur_variance": result["blur_variance"],
                "blur_ok": result["blur_ok"],
                "size_ok": result["size_ok"],
                "aspect_ok": result["aspect_ok"],
                "dimensions": result["dimensions"],
                "palette": result.get("palette", {}),
                "duplicates": duplicate_files.get(path, []),
            },
        })

    items.sort(key=lambda item: (-item["priority"], item["name"]))
    for position, item in enumerate(items, start=1):
        item["rank"] = position

    queue = {
        "schema_version": 1,
        "episode": episode,
        "total": len(files),
        "queued": len(items),
        "flags": {
            flag: sum(1 for item in items if flag in item["flags"])
            for flag in FLAG_ORDER
        },
        "note": ("objective flags only - anatomy, composition and beauty stay "
                 "owner-judged"),
        "built_utc": _now(),
        "items": items,
    }

    if out_dir:
        directory = Path(out_dir)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "review_queue.json").write_text(
            json.dumps(queue, indent=2), encoding="utf-8")
        with (directory / "review_queue.csv").open("w", encoding="utf-8",
                                                   newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["rank", "file", "flags", "priority", "text_like",
                             "blur_variance", "size_ok", "palette_coverage"])
            for item in items:
                detail = item["detail"]
                writer.writerow([
                    item["rank"], item["file"], "|".join(item["flags"]),
                    item["priority"], detail["text_like"],
                    detail["blur_variance"], detail["size_ok"],
                    detail["palette"].get("coverage", ""),
                ])
    return queue
