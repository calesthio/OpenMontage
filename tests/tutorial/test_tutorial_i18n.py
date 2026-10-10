from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from lib import tutorial as T  # noqa: E402
from lib import tutorial_i18n as I  # noqa: E402

SRC = [{"index": 0, "narration": "Open the Sales area."},
       {"index": 1, "narration": "Pick an auction."}]
DOC = {"lang": "de", "source_lang": "en",
       "recipe": {"title": "Circuit Auction Backoffice", "intro_subtitle": "Eine kurze Tour"},
       "steps": [{"index": 0, "source": "Open the Sales area.", "narration": "Öffnen Sie den Bereich Verkäufe."},
                 {"index": 1, "source": "Pick an auction.", "narration": "Wählen Sie eine Auktion."}]}


def test_validate_lang():
    assert I.validate_lang("de") == "de" and I.validate_lang("pt-BR") == "pt-BR"
    for bad in ("German", "DE", "../x", "", "d"):
        with pytest.raises(ValueError):
            I.validate_lang(bad)


def test_paths(tmp_path):
    spec = tmp_path / "sales-tour.tutorial.cy.js"
    assert I.timings_path(spec, "sales-tour", "en", "en") == tmp_path / "sales-tour.timings.json"
    assert I.timings_path(spec, "sales-tour", "de", "en") == tmp_path / "sales-tour.timings.de.json"
    assert I.i18n_path(spec, "sales-tour", "de") == tmp_path / "sales-tour.i18n.de.json"


def test_build_template_lists_steps_and_recipe_keys():
    tpl = I.build_template(source_lang="en", lang="de",
                           recipe={"title": "T", "intro_text": "I", "music_track": "x"},
                           source_steps=SRC)
    assert tpl["lang"] == "de" and tpl["source_lang"] == "en"
    assert tpl["recipe"] == {"title": "T", "intro_text": "I"}  # only translatable keys, source text as placeholder
    assert tpl["steps"] == [{"index": 0, "source": "Open the Sales area.", "narration": "", "stale": False},
                            {"index": 1, "source": "Pick an auction.", "narration": "", "stale": False}]


def test_build_template_merges_existing_and_flags_stale():
    existing = {**DOC, "steps": [{"index": 0, "source": "OLD", "narration": "Alt."},
                                 DOC["steps"][1]]}
    tpl = I.build_template(source_lang="en", lang="de", recipe={"title": "T"},
                           source_steps=SRC, existing=existing)
    assert tpl["steps"][0] == {"index": 0, "source": "Open the Sales area.", "narration": "Alt.", "stale": True}
    assert tpl["steps"][1]["narration"] == "Wählen Sie eine Auktion." and tpl["steps"][1]["stale"] is False
    assert tpl["recipe"]["title"] == "Circuit Auction Backoffice"


def test_validate_translation_ok():
    assert I.validate_translation(DOC, lang="de", source_steps=SRC) == []


def test_validate_translation_rejects_empty_lines():
    bad = json.loads(json.dumps(DOC))
    bad["steps"][1]["narration"] = "   "
    errs = I.validate_translation(bad, lang="de", source_steps=SRC)
    assert any("step 1" in e and "empty" in e for e in errs)
    bad["steps"][0]["narration"] = 42
    errs = I.validate_translation(bad, lang="de", source_steps=SRC)
    assert any("step 0" in e for e in errs)
    errs = I.validate_translation({**DOC, "lang": "fr"}, lang="de", source_steps=SRC)
    assert any("lang" in e for e in errs)
    missing = {**DOC, "steps": DOC["steps"][:1]}
    errs = I.validate_translation(missing, lang="de", source_steps=SRC)
    assert any("missing" in e and "1" in e for e in errs)


def test_apply_translation_replaces_narration():
    steps = [T.Step(index=0, narration="Open the Sales area."), T.Step(index=1, narration="Pick an auction.")]
    warnings = I.apply_translation(steps, DOC)
    assert warnings == []
    assert [s.narration for s in steps] == ["Öffnen Sie den Bereich Verkäufe.", "Wählen Sie eine Auktion."]


def test_apply_translation_warns_on_stale_source():
    steps = [T.Step(index=0, narration="Open the SALES area now."), T.Step(index=1, narration="Pick an auction.")]
    warnings = I.apply_translation(steps, DOC)
    assert len(warnings) == 1 and "stale" in warnings[0] and "step 0" in warnings[0]
    assert steps[0].narration == "Öffnen Sie den Bereich Verkäufe."  # still applied


def test_apply_translation_missing_and_extra_steps():
    steps = [T.Step(index=0, narration="Open the Sales area."), T.Step(index=2, narration="New step.")]
    warnings = I.apply_translation(steps, DOC)
    assert steps[1].narration == "New step."  # kept source text
    assert any("step 2" in w and "missing" in w for w in warnings)
    assert any("step 1" in w and "extra" in w for w in warnings)


def test_localized_recipe():
    rec = I.localized_recipe({"lang": "en", "title": "T", "intro_subtitle": "S", "music_track": "m"}, DOC)
    assert rec["lang"] == "de" and rec["title"] == "Circuit Auction Backoffice"
    assert rec["intro_subtitle"] == "Eine kurze Tour" and rec["music_track"] == "m"


def test_load_sidecar_errors(tmp_path):
    with pytest.raises(FileNotFoundError):
        I.load_sidecar(tmp_path / "nope.json")
    p = tmp_path / "x.json"
    p.write_text("{not json")
    with pytest.raises(ValueError):
        I.load_sidecar(p)
