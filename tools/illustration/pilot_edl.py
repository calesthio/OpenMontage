#!/usr/bin/env python3
"""tools/illustration/pilot_edl.py — EDL for an all-illustration episode.

Maps every labelled AI still to exactly one cut, spreads cuts across the
script's sentences in proportion to their length, assigns each cut the
sentence's claim_ids, and rotates motion (move/easing/direction) so no two
consecutive cuts repeat a move.

Deterministic: same inputs -> same EDL. No network, no media I/O.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

SPECULATIVE_LABEL = "Speculative illustration"

# (move, easing, direction) — zoompan-expressible moves only.
MOTION_CYCLE = [
    ("pan", "easeinout", "left"),
    ("zoom", "easein", "in"),
    ("detail_crop", "easeout", "right"),
    ("parallax", "easeinout", "up"),
    ("pan", "easeout", "right"),
    ("zoom", "easeinout", "out"),
    ("detail_crop", "easein", "left"),
    ("parallax", "easeout", "down"),
]


def _as_list(value: Any) -> List[Any]:
    return list(value or [])


def _split_ids(raw: Any) -> List[str]:
    text = str(raw or "").replace(";", ",")
    return [p.strip() for p in text.split(",") if p.strip()]


def _assign_images(sentences: Sequence[Dict[str, Any]], n_images: int) -> List[int]:
    """How many images each sentence gets (base + one for the first `extra`)."""
    n = len(sentences)
    base, extra = divmod(n_images, n)
    counts = [base + (1 if i < extra else 0) for i in range(n)]
    if any(c == 0 for c in counts):
        # Fewer images than sentences: give one image to the longest sentences.
        order = sorted(range(n), key=lambda i: -len(str(sentences[i]["sentence"])))
        counts = [0] * n
        for i in order[:n_images]:
            counts[i] = 1
    return counts


def build_illustration_edl(
    images: Iterable[Dict[str, Any]],
    sentences: Iterable[Dict[str, Any]] | None,
    *,
    total_duration: float,
    topic: str,
    episode: str,
    motion_cycle: Sequence[Sequence[str]] | None = None,
    out_path: str | Path | None = None,
    sections: Sequence[Dict[str, Any]] | None = None,
    card_paths: Sequence[str] | None = None,
    card_duration: float = 3.0,
) -> Dict[str, Any]:
    """Build an all-illustration EDL, optionally opening each section with
    an own-graphics card (spec L6: chapter cards are original graphics)."""
    imgs = _as_list(images)
    if sections is None:
        rows = [r for r in _as_list(sentences) if str(r.get("sentence", "")).strip()]
        if not rows:
            raise ValueError("no sentences for the EDL")
        groups = [{"title": "", "rows": rows}]
    else:
        groups = []
        for sec in sections:
            srows = [r for r in _as_list(sec.get("sentences"))
                     if str(r.get("sentence", "")).strip()]
            if srows:
                groups.append({"title": str(sec.get("title") or ""), "rows": srows})
        if not groups:
            raise ValueError("no sentences for the EDL")
        if card_paths is not None and len(card_paths) != len(groups):
            raise ValueError(
                f"card_paths ({len(card_paths)}) must match sections ({len(groups)})")
    if not imgs:
        raise ValueError("no images for the EDL")
    total = float(total_duration)
    if total <= 0:
        raise ValueError("total_duration must be > 0")
    if card_duration < 0:
        raise ValueError("card_duration must be >= 0")

    cycle = [tuple(m) for m in (motion_cycle or MOTION_CYCLE)]
    rows = [r for g in groups for r in g["rows"]]
    counts = _assign_images(rows, len(imgs))

    # Section and sentence durations are proportional to spoken length.
    section_weights = [sum(max(1, len(str(r["sentence"]))) for r in g["rows"])
                       for g in groups]
    swsum = sum(section_weights)
    section_durs = [total * w / swsum for w in section_weights]
    section_durs[-1] = total - sum(section_durs[:-1])

    cuts: List[Dict[str, Any]] = []
    motion_segments: List[Dict[str, Any]] = []
    cursor = 0.0
    img_idx = 0
    row_base = 0
    for gi, group in enumerate(groups):
        section_start = cursor
        section_dur = section_durs[gi]
        has_card = bool(card_paths) and gi < len(card_paths) and card_paths[gi]
        if has_card:
            card_dur = min(float(card_duration), max(0.0, section_dur - 0.5))
            card_end = round(section_start + card_dur, 3)
            cuts.append({
                "cut_id": len(cuts) + 1,
                "start": round(section_start, 3),
                "end": card_end,
                "duration": round(card_end - section_start, 3),
                "asset_id": f"card_{gi:02d}_{Path(str(card_paths[gi])).stem}",
                "source": str(card_paths[gi]),
                "source_sha256": "",
                "role": "graphics_card",
                "kind": "graphics",
                "generator": "original",
                "static_by_design": True,
                "label": "",
                "description": f"Chapter card: {group['title']}",
                "rationale": ("Own-graphics chapter card drawn by the factory "
                              "(no third-party material), static by design."),
                "claim_ids": "",
                "rights_basis": "explicit_license",
                "credit": "Original graphics by the channel owner (own work)",
                "license": ("Own work, all rights held by the channel owner; "
                            "used with permission in this episode."),
                "scene_id": "",
            })
            cursor = card_end
            section_dur = section_start + section_dur - cursor
            section_dur = max(0.0, section_dur)
        sent_weights = [max(1, len(str(r["sentence"]))) for r in group["rows"]]
        sw = sum(sent_weights)
        sent_durs = [section_dur * w / sw for w in sent_weights]
        for ri, (row, dur) in enumerate(zip(group["rows"], sent_durs)):
            count = counts[row_base + ri]
            if count == 0:
                continue
            ids = _split_ids(row.get("claim_id"))
            per = dur / count
            sentence_start = cursor
            for k in range(count):
                img = imgs[img_idx]
                move, easing, direction = cycle[img_idx % len(cycle)]
                cut_dur = round(per, 3)
                start = round(cursor, 3)
                end = (round(start + cut_dur, 3) if k < count - 1
                       else round(sentence_start + dur, 3))
                if end - start <= 0:
                    raise ValueError(
                        f"non-positive cut duration at cut {len(cuts) + 1}: "
                        f"{start}->{end}")
                cut = {
                    "cut_id": len(cuts) + 1,
                    "start": start,
                    "end": end,
                    "duration": round(end - start, 3),
                    "asset_id": f"ill_{img.get('scene_id', 'scene')}_{Path(str(img['file'])).stem}",
                    "source": str(img["file"]),
                    "source_sha256": str(img.get("sha256", "")),
                    "role": "illustration",
                    "kind": "ai_illustration",
                    "generator": "AI",
                    "label": SPECULATIVE_LABEL,
                    "description": f"Speculative illustration for: {row['sentence'].strip()}",
                    "rationale": (
                        f"AI illustration ({img.get('scene_id', 'scene')}) illustrating "
                        f"the narration sentence; invented design, labelled on screen."
                    ),
                    "claim_ids": ", ".join(ids),
                    "rights_basis": "ai_generated_illustration",
                    "move": move,
                    "easing": easing,
                    "direction": direction,
                    "scene_id": img.get("scene_id", ""),
                }
                cuts.append(cut)
                motion_segments.append({
                    "start": start, "end": end, "move": move, "easing": easing,
                    "direction": direction, "cut_id": cut["cut_id"],
                })
                cursor = end
                img_idx += 1
        row_base += len(group["rows"])

    # Absorb rounding into the final cut so the timeline equals the narration.
    drift = round(total - cursor, 3)
    if cuts and abs(drift) > 0:
        cuts[-1]["end"] = round(cuts[-1]["end"] + drift, 3)
        cuts[-1]["duration"] = round(cuts[-1]["end"] - cuts[-1]["start"], 3)
        if motion_segments:
            motion_segments[-1]["end"] = cuts[-1]["end"]

    edl = {
        "version": 1,
        "episode_id": episode,
        "topic_id": topic,
        "total_duration_s": round(total, 3),
        "resolution": "1280x720",
        "fps": 30,
        "codec": "h264",
        "audio_codec": "aac",
        "source": "illustration manifest + script sentences",
        "cuts": cuts,
        "motion_segments": motion_segments,
    }
    if out_path:
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(edl, indent=2), encoding="utf-8")
    return edl


def sentence_rows(script_path: str | Path) -> List[Dict[str, str]]:
    """Parse a bullet/table script into {sentence, claim_id} rows."""
    import re

    text = Path(script_path).read_text(encoding="utf-8")
    marker = re.compile(r"\s*\[([^\]]*)\]\s*$")
    rows: List[Dict[str, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            raw = stripped[2:].strip()
            ids = ", ".join(re.findall(r"\[([^\]]*)\]", raw))
            sentence = marker.sub("", raw).strip()
            if sentence:
                rows.append({"sentence": sentence, "claim_id": ids})
        elif stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) >= 3 and re.match(r"^B\d+(?:-\d+)?$", cells[0]) and cells[1]:
                rows.append({"sentence": cells[1], "claim_id": cells[2]})
    return rows


def images_from_manifest(manifest_path: str | Path) -> List[Dict[str, Any]]:
    """Read the labelled illustration manifest into EDL image records."""
    data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    out = []
    for ent in data.get("images", []):
        out.append({
            "file": ent["file"],
            "sha256": ent.get("sha256", ""),
            "scene_id": ent.get("scene_id", ""),
        })
    return out


def script_sections(script_path: str | Path) -> List[Dict[str, Any]]:
    """Parse a bullet script into `[{title, sentences:[{sentence, claim_id}]}]`.

    A `## ` heading with no bullet sentences (e.g. the titles block) is
    dropped so it can never become a chapter card or consume runtime.
    """
    import re

    text = Path(script_path).read_text(encoding="utf-8")
    marker = re.compile(r"\s*\[([^\]]*)\]\s*$")
    sections: List[Dict[str, Any]] = []
    title = ""
    rows: List[Dict[str, str]] = []

    def flush():
        if rows:
            sections.append({"title": title.strip(), "sentences": list(rows)})
            rows.clear()

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            flush()
            title = stripped[3:].strip()
            continue
        if stripped.startswith("- "):
            raw = stripped[2:].strip()
            ids = ", ".join(re.findall(r"\[([^\]]*)\]", raw))
            sentence = marker.sub("", raw).strip()
            if sentence:
                rows.append({"sentence": sentence, "claim_id": ids})
    flush()
    return sections
