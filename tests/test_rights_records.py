"""Rights records + credits derived from the EDL (fail closed)."""
from __future__ import annotations

import json

import pytest

from tools.packaging.rights_records import (
    build_rights_records,
    credits_lines,
    write_rights_records,
)
from tools.qa.qc import rights_record_problems

SHA = "c" * 64


def _edl():
    return {"cuts": [
        {"cut_id": 1, "asset_id": "card_00_card_01", "kind": "graphics",
         "role": "graphics_card", "source": "/cards/card_01.png"},
        {"cut_id": 2, "asset_id": "ill_scene_ill_01", "kind": "ai_illustration",
         "role": "illustration", "source": "/img/ill_01.png",
         "label": "Speculative illustration", "source_sha256": SHA},
    ]}


def _manifest():
    return {"images": [{"file": "/img/ill_01.png", "sha256": SHA,
                        "scene_id": "vent_grazer"}]}


def test_every_cut_gets_a_record_that_passes_qc_rights_checks():
    records = build_rights_records(_edl(), _manifest(), model="klein")
    assert [r["asset_id"] for r in records] == ["card_00_card_01", "ill_scene_ill_01"]
    for rec in records:
        assert rights_record_problems(rec) == [], rec


def test_illustration_record_carries_model_licence_and_sha():
    rec = build_rights_records(_edl(), _manifest())[1]
    assert rec["rights_basis"] == "ai_generated_illustration"
    assert rec["sha256"] == SHA
    assert rec["model"].startswith("black-forest-labs/FLUX.2-klein")
    assert rec["license"] == "Apache-2.0"
    assert rec["source_url"].startswith("https://huggingface.co/")


def test_unknown_model_is_rejected():
    with pytest.raises(ValueError):
        build_rights_records(_edl(), _manifest(), model="mystery")


def test_illustration_without_sha_fails_closed(tmp_path):
    edl = {"cuts": [{"asset_id": "ill_x", "kind": "ai_illustration",
                     "source": str(tmp_path / "missing.png")}]}
    with pytest.raises(ValueError):
        build_rights_records(edl, {"images": []})


def test_unknown_cut_kind_fails_closed():
    with pytest.raises(ValueError):
        build_rights_records({"cuts": [{"asset_id": "a", "kind": "footage",
                                        "source": "x.mp4"}]}, {"images": []})


def test_credits_are_deduplicated_and_cite_the_licence(tmp_path):
    records = build_rights_records(_edl(), _manifest())
    lines = credits_lines(records)
    assert len(lines) == 2  # own graphics + AI model, each once
    assert any("Apache-2.0" in line for line in lines)
    assert any("own work" in line.lower() for line in lines)
    out = write_rights_records(tmp_path / "rights_records.json", records)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data["assets"]) == 2
