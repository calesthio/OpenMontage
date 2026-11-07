#!/usr/bin/env python3
"""tools/packaging/package_builder.py — build the upload package from artifacts.

Inputs (episode dir): script.md, artifacts/claim_ids.json,
artifacts/rights_records.json, artifacts/credits.txt (optional).

Outputs (out dir): metadata.json, credits.txt, DISCLOSURE.md, shorts_plan.json,
SHORTS_PLAN.md, package_manifest.json.

Rules: titles are taken from the script (never invented), credits are derived
from rights records (never pasted by hand), every Shorts beat carries a
claim_id, AI content is disclosed, and the status is always
DRAFT_NOT_PUBLISHABLE — an agent cannot publish.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List

from tools.packaging.packaging import build_metadata_block, disclosure_checklist

WORDS_PER_SECOND = 2.5
_MAX_TAGS = 20


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


CLAIM_MARKER = re.compile(r"\s*\[([^\]]*)\]\s*$")


def parse_script(path: Path) -> Dict[str, Any]:
    """Extract titles, chapters and bullet sentences from a pilot script."""
    titles: List[str] = []
    chapters: List[Dict[str, str]] = []
    sentences: List[Dict[str, str]] = []
    in_titles = False
    current_chapter = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            heading = stripped[3:].strip()
            in_titles = "title" in heading.lower()
            if heading.lower().startswith("chapter"):
                current_chapter = heading
                chapters.append({"heading": heading,
                                 "title": heading.split("—", 1)[-1].strip()})
            continue
        if in_titles:
            m = re.match(r"^\d+\.\s+(.*\S)$", stripped)
            if m:
                titles.append(m.group(1).strip())
            continue
        if stripped.startswith("- "):
            raw = stripped[2:].strip()
            ids = ", ".join(re.findall(r"\[([^\]]*)\]", raw)).strip()
            text = CLAIM_MARKER.sub("", raw).strip()
            if text:
                sentences.append({"sentence": text, "claim_id": ids,
                                  "chapter": current_chapter})
    return {"titles": titles, "chapters": chapters, "sentences": sentences}


def _claim_index(claim_ids: Any) -> Dict[str, str]:
    index: Dict[str, str] = {}
    if isinstance(claim_ids, list):
        for row in claim_ids:
            if not isinstance(row, dict):
                continue
            text = str(row.get("text") or "").strip().lower()
            cid = str(row.get("claim_id") or "").strip()
            if text and cid:
                index[text] = cid
    return index


def _credits_from_rights(records: Any) -> List[str]:
    lines: List[str] = []
    seen = set()
    if not isinstance(records, list):
        return lines
    for rec in records:
        if not isinstance(rec, dict):
            continue
        credit = str(rec.get("credit") or rec.get("center") or "").strip()
        license_text = str(rec.get("license") or rec.get("license_text") or "").strip()
        line = f"{credit} — {license_text}" if license_text else credit
        line = line.strip(" —")
        if line and line not in seen:
            seen.add(line)
            lines.append(line)
    return lines


def _estimate_seconds(text: str) -> float:
    words = len([w for w in text.split() if w.strip()])
    return max(2.0, round(words / WORDS_PER_SECOND + 0.3, 2))


def build_shorts_plan(sentences: List[Dict[str, str]],
                      max_seconds: float = 45.0) -> Dict[str, Any]:
    """First sentences (claim_id required) that fit the Shorts budget."""
    beats: List[Dict[str, Any]] = []
    total = 0.0
    for row in sentences:
        cid = str(row.get("claim_id") or "").strip()
        if not cid:
            continue
        dur = _estimate_seconds(row["sentence"])
        if total + dur > max_seconds and beats:
            break
        beats.append({"index": len(beats), "sentence": row["sentence"],
                      "claim_id": cid, "est_seconds": dur})
        total = round(total + dur, 2)
    return {"max_seconds": max_seconds, "total_seconds": total, "beats": beats}


def _description(title: str, chapters: List[Dict[str, str]], credits: List[str],
                 ai_illustration: bool) -> str:
    parts = [title, ""]
    if chapters:
        parts.append("## Chapters")
        for i, ch in enumerate(chapters, 1):
            parts.append(f"{i}. {ch['title']}")
        parts.append("")
    if ai_illustration:
        parts.append("This video uses AI-generated illustrations. They are labelled "
                     "on screen as \"Speculative illustration\" and are not real "
                     "footage or observed events.")
        parts.append("")
    if credits:
        parts.append("## Credits")
        parts.extend(credits)
    return "\n".join(parts).strip()


def build_package(episode_dir: str | Path, out_dir: str | Path, *,
                  ai_illustration: bool = False,
                  shorts_max_seconds: float = 45.0,
                  tags: List[str] | None = None) -> Dict[str, Any]:
    ep = Path(episode_dir)
    out = Path(out_dir)
    script = ep / "script.md"
    if not script.is_file():
        return {"ok": False, "error": f"no script.md in {ep}", "outputs": {}}

    parsed = parse_script(script)
    if not parsed["sentences"]:
        return {"ok": False, "error": "script has no claim-tagged sentences",
                "outputs": {}}
    titles = parsed["titles"] or ["Untitled episode"]
    title = titles[0]

    art = ep / "artifacts"
    claim_ids = _read_json(art / "claim_ids.json")
    index = _claim_index(claim_ids)
    sentences = []
    for row in parsed["sentences"]:
        cid = row["claim_id"] or index.get(row["sentence"].strip().lower(), "")
        sentences.append({**row, "claim_id": cid})

    rights = _read_json(art / "rights_records.json")
    credits = _credits_from_rights(rights)
    if not credits and (art / "credits.txt").is_file():
        credits = [ln.strip() for ln in
                   (art / "credits.txt").read_text(encoding="utf-8").splitlines()
                   if ln.strip()]

    tag_list = tags or []
    if not tag_list:
        words = [w.strip(",:;.!?").lower() for w in title.split()]
        tag_list = [w for w in words if len(w) > 3][:_MAX_TAGS]
    if ai_illustration and "ai illustration" not in tag_list:
        tag_list.append("ai illustration")

    meta = build_metadata_block(
        title=title,
        description=_description(title, parsed["chapters"], credits, ai_illustration),
        tags=tag_list[:_MAX_TAGS],
        credits={"credits": "\n".join(credits)} if credits else {},
        ai_disclosure=ai_illustration,
    )
    shorts = build_shorts_plan(sentences, shorts_max_seconds)
    checklist = disclosure_checklist(ai_illustration=ai_illustration)

    out.mkdir(parents=True, exist_ok=True)
    (out / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (out / "credits.txt").write_text("\n".join(credits) + ("\n" if credits else ""),
                                     encoding="utf-8")
    (out / "shorts_plan.json").write_text(json.dumps(shorts, indent=2), encoding="utf-8")
    (out / "SHORTS_PLAN.md").write_text(
        "# Shorts plan (<= %.0f s)\n\n" % shorts_max_seconds
        + "\n".join(f"{b['index'] + 1}. [{b['claim_id']}] {b['sentence']} "
                    f"({b['est_seconds']:.1f}s)" for b in shorts["beats"])
        + "\n", encoding="utf-8")
    (out / "DISCLOSURE.md").write_text(
        "# Disclosure checklist (owner confirms)\n\n"
        + "\n".join(f"- [{'x' if item['satisfied'] else ' '}] {item['topic']} — "
                    f"{item['url']}" for item in checklist)
        + "\n", encoding="utf-8")

    manifest = {
        "status": "DRAFT_NOT_PUBLISHABLE",
        "episode_dir": str(ep),
        "package_dir": str(out),
        "title": title,
        "titles_considered": titles,
        "chapters": len(parsed["chapters"]),
        "sentences": len(sentences),
        "credits_lines": len(credits),
        "shorts_beats": len(shorts["beats"]),
        "ai_illustration": ai_illustration,
        "inputs": {p.name: _sha256(p) for p in
                   [script, art / "claim_ids.json", art / "rights_records.json"]
                   if p.is_file()},
        "created_utc": _now(),
    }
    (out / "package_manifest.json").write_text(json.dumps(manifest, indent=2),
                                               encoding="utf-8")
    return {"ok": True, "status": manifest["status"],
            "outputs": {k: str(out / k) for k in
                        ("metadata.json", "credits.txt", "DISCLOSURE.md",
                         "shorts_plan.json", "SHORTS_PLAN.md",
                         "package_manifest.json")},
            "manifest": manifest}
