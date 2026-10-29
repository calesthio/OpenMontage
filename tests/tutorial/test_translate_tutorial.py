from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import render_tutorial as RT  # noqa: E402
import translate_tutorial as TT  # noqa: E402


def _client(tmp_path: Path) -> Path:
    d = tmp_path / "cypress" / "e2e-tutorials" / "sales"
    d.mkdir(parents=True)
    (d / "sales-tour.tutorial.cy.js").write_text("describe('x', () => {});")
    (d / "sales-tour.tutorial.json").write_text(json.dumps({"title": "Sales", "lang": "en", "intro_text": "Hi"}))
    (d / "sales-tour.timings.json").write_text(json.dumps({
        "spec": "cypress/e2e-tutorials/sales/sales-tour.tutorial.cy.js", "lang": "en",
        "steps": [{"index": 0, "narration": "Open Sales.", "duration_ms": 1000},
                  {"index": 1, "narration": "Pick one.", "duration_ms": 900}]}))
    return tmp_path


def test_resolve_tutorial_per_lang_paths(tmp_path):
    client = _client(tmp_path)
    en = RT.resolve_tutorial(client, "sales-tour")
    assert en["lang"] == "en" and en["source_lang"] == "en" and en["i18n_path"] is None
    assert en["timings_path"].name == "sales-tour.timings.json" and en["timings"]["steps"]
    de = RT.resolve_tutorial(client, "sales-tour", lang="de")
    assert de["timings_path"].name == "sales-tour.timings.de.json" and de["timings"] == {}
    assert de["i18n_path"].name == "sales-tour.i18n.de.json" and de["i18n"] is None
    assert de["source_timings"]["steps"][1]["narration"] == "Pick one."


def test_template_and_write_sidecar(tmp_path):
    client = _client(tmp_path)
    tut = RT.resolve_tutorial(client, "sales-tour", lang="de")
    tpl = TT.template_for(tut)
    assert [s["source"] for s in tpl["steps"]] == ["Open Sales.", "Pick one."]
    assert tpl["recipe"] == {"title": "Sales", "intro_text": "Hi"}
    doc = {**tpl, "recipe": {"title": "Verkauf", "intro_text": "Hallo"}}
    doc["steps"][0]["narration"] = "Verkauf öffnen."
    doc["steps"][1]["narration"] = "Eine auswählen."
    out = TT.write_sidecar(tut, doc)
    assert out == tut["i18n_path"]
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["steps"][0] == {"index": 0, "source": "Open Sales.", "narration": "Verkauf öffnen."}
    assert "stale" not in saved["steps"][0]
    # Re-resolving now loads it.
    assert RT.resolve_tutorial(client, "sales-tour", lang="de")["i18n"]["lang"] == "de"


def test_write_sidecar_rejects_incomplete(tmp_path):
    client = _client(tmp_path)
    tut = RT.resolve_tutorial(client, "sales-tour", lang="de")
    doc = TT.template_for(tut)  # narration lines still empty
    with pytest.raises(ValueError, match="step 0"):
        TT.write_sidecar(tut, doc)
    assert not tut["i18n_path"].exists()


def test_template_requires_source_timings(tmp_path):
    client = _client(tmp_path)
    (client / "cypress" / "e2e-tutorials" / "sales" / "sales-tour.timings.json").unlink()
    tut = RT.resolve_tutorial(client, "sales-tour", lang="de")
    with pytest.raises(FileNotFoundError, match="author_tutorial"):
        TT.template_for(tut)


def test_write_sidecar_refuses_symlink_target(tmp_path):
    client = _client(tmp_path)
    tut = RT.resolve_tutorial(client, "sales-tour", lang="de")
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    tut["i18n_path"].symlink_to(outside)
    doc = TT.template_for(tut)
    for s in doc["steps"]:
        s["narration"] = "ok"
    with pytest.raises(ValueError, match="symlink"):
        TT.write_sidecar(tut, doc)
    assert outside.read_text() == "{}"
