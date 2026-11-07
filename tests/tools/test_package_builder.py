#!/usr/bin/env python3
"""Red/green tests for tools/packaging/package_builder.py (G10/L8).

Builds the upload package from episode artifacts: metadata block, credits
from rights records, AI disclosure checklist, and a Shorts plan where every
sentence carries a claim_id. Offline; writes only JSON/markdown.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.packaging.package_builder import build_package  # noqa: E402

SCRIPT = """# Pilot

## 3 truthful titles

1. How Could Life Survive Beneath a Frozen Alien Ocean?
2. Europa and Enceladus: Oceans Beneath the Ice

## Hook

- Beneath miles of ice, on a frozen moon, there could be an ocean. [SE-01]
- On Europa, a global saltwater sea lies hidden under a frozen crust. [SE-01, SE-04]
- That ocean holds more than twice as much water as Earth's oceans. [SE-02]

## Chapter 1 — Vents

- Chemosynthetic bacteria turn inorganic chemicals into food. [SE-08]
"""


def _episode(tmp_path):
    ep = tmp_path / "ep"
    art = ep / "artifacts"
    art.mkdir(parents=True)
    (ep / "script.md").write_text(SCRIPT, encoding="utf-8")
    (art / "claim_ids.json").write_text(json.dumps([
        {"text": "Beneath miles of ice, on a frozen moon, there could be an ocean.",
         "claim_id": "SE-01"},
        {"text": "Chemosynthetic bacteria turn inorganic chemicals into food.",
         "claim_id": "SE-08"},
    ]), encoding="utf-8")
    (art / "rights_records.json").write_text(json.dumps([
        {"asset_id": "ill-1", "kind": "ai_illustration",
         "rights_basis": "ai_generated_illustration",
         "credit": "AI-generated illustration (Speculative illustration)",
         "license": "AI-generated, project-owned", "sha256": "a" * 64,
         "source_url": "ai://generated"},
    ]), encoding="utf-8")
    (art / "credits.txt").write_text(
        "Illustrations: AI-generated (Speculative illustration)\n", encoding="utf-8")
    return ep, art


def test_package_has_title_description_and_chapters(tmp_path):
    ep, art = _episode(tmp_path)
    out = tmp_path / "pkg"
    res = build_package(ep, out, ai_illustration=True)
    assert res["ok"] is True, res
    meta = json.loads((out / "metadata.json").read_text())
    assert meta["title"].startswith("How Could Life Survive")
    assert "## Chapters" in meta["description"]
    assert "1. Vents" in meta["description"]
    assert meta["ai_disclosure"] is True
    assert isinstance(meta["tags"], list) and meta["tags"]


def test_credits_are_generated_not_pasted(tmp_path):
    ep, art = _episode(tmp_path)
    out = tmp_path / "pkg"
    build_package(ep, out, ai_illustration=True)
    credits = (out / "credits.txt").read_text()
    assert "AI-generated illustration" in credits
    assert "Creative Commons" not in credits  # no invented third-party credits
    meta = json.loads((out / "metadata.json").read_text())
    assert meta["credits"]


def test_disclosure_checklist_cites_official_page(tmp_path):
    ep, art = _episode(tmp_path)
    out = tmp_path / "pkg"
    build_package(ep, out, ai_illustration=True)
    text = (out / "DISCLOSURE.md").read_text()
    assert "support.google.com/youtube/answer/13643031" in text
    assert "altered or synthetic" in text.lower()


def test_shorts_plan_sentences_all_have_claim_ids(tmp_path):
    ep, art = _episode(tmp_path)
    out = tmp_path / "pkg"
    build_package(ep, out, ai_illustration=True, shorts_max_seconds=45)
    plan = json.loads((out / "shorts_plan.json").read_text())
    assert plan["beats"], plan
    assert plan["total_seconds"] <= 45
    for beat in plan["beats"]:
        assert beat["claim_id"].strip()
        assert beat["sentence"].strip()
    assert (out / "SHORTS_PLAN.md").is_file()


def test_package_fails_closed_without_script(tmp_path):
    ep = tmp_path / "empty"
    ep.mkdir()
    res = build_package(ep, tmp_path / "pkg")
    assert res["ok"] is False
    assert "script" in res["error"].lower()


def test_package_never_claims_publishable(tmp_path):
    ep, art = _episode(tmp_path)
    out = tmp_path / "pkg"
    res = build_package(ep, out, ai_illustration=True)
    manifest = json.loads((out / "package_manifest.json").read_text())
    assert manifest["status"] == "DRAFT_NOT_PUBLISHABLE"
    assert res["status"] == "DRAFT_NOT_PUBLISHABLE"
