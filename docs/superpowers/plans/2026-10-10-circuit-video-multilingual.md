# Circuit-video: render a tutorial in another language (German first) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render one tutorial video whose voice-over and burned-in captions (and title cards) are in a chosen language other than the one the Cypress spec is written in — German (`de`) as the first second language — via the circuit-video MCP and the CLIs.

**Architecture:** The spoken lines live inside the Cypress spec (`cy.tutorialStep("English text", …)`), so a translation sidecar `<name>.i18n.<lang>.json` next to the spec supplies the translated narration per step index plus the translated recipe texts (title, intro/outro). Translation is produced by the calling agent (Claude) through two MCP tools — `get_tutorial_text` hands out a template built from the committed English `timings.json`; `save_tutorial_translation` validates and writes the sidecar — or by hand via `translate_tutorial.py`. Because narration duration drives capture pacing, each language gets its own `<name>.timings.<lang>.json` (authored with `author_tutorial.py --lang de`) and its own capture: the Cypress config picks the timings file for `CYPRESS_TUTORIAL_LANG`. At render time `render_tutorial.py --lang de` swaps the step narration and recipe texts before synthesis, caption generation and title cards, so the rest of the pipeline is unchanged. Voices come from `ELEVENLABS_VOICE_IDS` (`de:` entry) through either narration backend.

**Tech Stack:** Python 3 stdlib; the existing Cypress bridge; a small change in the client repo's `cypress.tutorial.config.js` (JavaScript, Node fs); ttsd or ElevenLabs (see the narration plan).

**Spec:** No separate spec. User's words: "enable create of one video with option to have voice and subtitle in other language, start with german a sec language". Interpreted as: one output video per chosen language (German voice + German captions), not a multi-track file. A multi-audio-track MP4 is noted as a possible follow-up, not built here.

**Depends on:** `2026-10-10-circuit-video-elevenlabs-narration.md` (Plan A) being merged first — this plan edits the same functions (`build_arg_parser`, `resolve_narration_choice` call site, `render_argv`, `render_tutorial` tool) and assumes their post-Plan-A shape. The caption plan (Plan B) is independent.

## Design decisions

- **Source language** is `recipe.lang` (default `en`). Rendering with `--lang` equal to the source language behaves exactly as today (same timings file name, no sidecar needed), so nothing changes for existing tutorials.
- **Sidecar format** `<name>.i18n.<lang>.json` (committed in the client repo next to the spec):
  ```json
  {
    "lang": "de",
    "source_lang": "en",
    "recipe": {"title": "…", "subtitle": "…", "intro_text": "…", "intro_subtitle": "…",
               "outro_text": "…", "outro_subtitle": "…"},
    "steps": [{"index": 0, "source": "<English line as of translation time>", "narration": "<German line>"}]
  }
  ```
  `source` lets the render detect a stale translation (the English line in the spec changed) and warn.
- **Per-language timings** `<name>.timings.<lang>.json` (source language keeps the legacy `<name>.timings.json`). The client's Cypress config loads both shapes and exposes the set for `process.env.CYPRESS_TUTORIAL_LANG` (fallback: the source file). This requires a change in `circuitauction-backoffice/client` — called out as its own task, in that repo.
- **Text source for translation** is the committed source-language `timings.json` (it already lists every step's index and narration), so `get_tutorial_text` needs neither Cypress nor the demo app. If it is missing, the tool says to author first.
- **Authoring without Cypress**: `author_tutorial.py --from-timings` takes the step list from the source `timings.json` instead of a collect-only Cypress run. Needed so the MCP can author German timings in one tool call; also faster for the English re-author after a voice change.
- **Captions**: `build_subtitle_segments` splits on whitespace; German works unchanged. Title cards: `make_title_card` uses DejaVu (Pillow) which covers umlauts and ß.
- **Language codes**: `^[a-z]{2}(-[A-Z]{2})?$` (`de`, `pt-BR`). Voices are looked up by the full code first, then the two-letter prefix.

## Global Constraints

- Python 3.10+; stdlib only for the new module; no network in tests.
- The MCP never prints to stdout. Tool inputs that reach a filename or argv are validated (`validate_lang`, `validate_tutorial_name`).
- `tests/mcp/test_circuit_video.py`, `tests/tutorial/*` keep passing after each task.
- A render in a non-source language must refuse to start (exit 2 / `isError`) when the sidecar or the per-language timings are missing — never silently narrate English with a German voice, and never ship German audio over an English-paced capture.
- Commit after each task; messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Changes in the client repo are committed there, separately.

## Review Focus

1. The English spec line changed after translation → render still works but prints `WARN: stale translation for step N` (source mismatch), and `get_tutorial_text` marks that step `"stale": true`. (Pinned in Task 1, `test_apply_translation_warns_on_stale_source`.)
2. Sidecar has a step index the spec no longer has, or lacks one it has → missing index: step keeps the source text and a WARN names it; extra index: ignored with a WARN. (Pinned in Task 1, `test_apply_translation_missing_and_extra_steps`.)
3. `save_tutorial_translation` receives an empty German line or a non-string → rejected with the step index in the message, nothing written. (Pinned in Task 1, `test_validate_translation_rejects_empty_lines`, and Task 6 `test_save_translation_rejects_bad_payload`.)
4. `render_tutorial --lang de` with `de` timings present but `CYPRESS_TUTORIAL_LANG` not reaching Cypress (client config not updated) → the capture would be English-paced. Pinned by the bridge test in Task 3 (`test_run_tutorial_spec_passes_lang`) and by the manual check in Task 4 (manifest `lang` echo).
5. `lang` in a tool call that is not a valid code (`"German"`, `"../x"`) → `ValueError` before anything runs. (Pinned in Task 1, `test_validate_lang`.)

---

### Task 1: `lib/tutorial_i18n.py` — sidecar paths, template, validation, application

**Files:**
- Create: `lib/tutorial_i18n.py`
- Test: `tests/tutorial/test_tutorial_i18n.py`

**Interfaces:**
- Consumes: `lib.tutorial.Step` (dataclass with `index`, `narration`).
- Produces:
  - `LANG_RE`, `validate_lang(lang: str) -> str`
  - `TRANSLATABLE_RECIPE_KEYS = ("title", "subtitle", "intro_text", "intro_subtitle", "outro_text", "outro_subtitle")`
  - `timings_path(spec: Path, name: str, lang: str, source_lang: str) -> Path`
  - `i18n_path(spec: Path, name: str, lang: str) -> Path`
  - `build_template(*, source_lang, lang, recipe, source_steps: list[dict], existing: dict | None = None) -> dict`
  - `validate_translation(doc: dict, *, lang: str, source_steps: list[dict]) -> list[str]` (errors; empty = valid)
  - `apply_translation(steps: list[Step], doc: dict) -> list[str]` (mutates `step.narration`; returns warnings)
  - `localized_recipe(recipe: dict, doc: dict) -> dict`
  - `load_sidecar(path: Path) -> dict`

- [ ] **Step 1: Write the failing tests**

```python
# tests/tutorial/test_tutorial_i18n.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/tutorial/test_tutorial_i18n.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lib.tutorial_i18n'`

- [ ] **Step 3: Implement**

```python
# lib/tutorial_i18n.py
"""Per-language narration sidecars for Cypress tutorials.

The spoken lines live in the spec (cy.tutorialStep("…")). To voice and caption a
tutorial in another language we keep `<name>.i18n.<lang>.json` next to the spec
with one translated line per step index, plus translated recipe texts. Pure
helpers only (no I/O except load_sidecar) so everything is unit-testable.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

LANG_RE = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")
TRANSLATABLE_RECIPE_KEYS = (
    "title", "subtitle", "intro_text", "intro_subtitle", "outro_text", "outro_subtitle",
)


def validate_lang(lang: str) -> str:
    lang = (lang or "").strip()
    if not LANG_RE.match(lang):
        raise ValueError("lang must be a code like de, fr or pt-BR")
    return lang


def timings_path(spec: Path, name: str, lang: str, source_lang: str) -> Path:
    if lang == source_lang:
        return spec.with_name(f"{name}.timings.json")
    return spec.with_name(f"{name}.timings.{lang}.json")


def i18n_path(spec: Path, name: str, lang: str) -> Path:
    return spec.with_name(f"{name}.i18n.{lang}.json")


def load_sidecar(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"translation sidecar not found: {path}")
    try:
        doc = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise ValueError(f"{path}: invalid JSON ({e})") from e
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return doc


def build_template(
    *,
    source_lang: str,
    lang: str,
    recipe: dict,
    source_steps: list[dict],
    existing: Optional[dict] = None,
) -> dict:
    """Skeleton for a translator (human or agent): every step with its current
    source line and the existing translation (if any), flagged stale when the
    source changed since it was translated."""
    prior_steps = {int(s.get("index", -1)): s for s in (existing or {}).get("steps", [])}
    prior_recipe = (existing or {}).get("recipe", {}) or {}
    steps = []
    for s in sorted(source_steps, key=lambda x: int(x.get("index", 0))):
        idx = int(s.get("index", 0))
        src = (s.get("narration") or "").strip()
        prev = prior_steps.get(idx) or {}
        steps.append({
            "index": idx,
            "source": src,
            "narration": (prev.get("narration") or "").strip(),
            "stale": bool(prev) and (prev.get("source") or "").strip() != src,
        })
    rec = {}
    for key in TRANSLATABLE_RECIPE_KEYS:
        if key in recipe and recipe.get(key) not in (None, ""):
            rec[key] = prior_recipe.get(key) or recipe[key]
    return {"lang": lang, "source_lang": source_lang, "recipe": rec, "steps": steps}


def validate_translation(doc: dict, *, lang: str, source_steps: list[dict]) -> list[str]:
    errs: list[str] = []
    if doc.get("lang") != lang:
        errs.append(f"lang mismatch: sidecar says {doc.get('lang')!r}, expected {lang!r}")
    steps = doc.get("steps")
    if not isinstance(steps, list):
        return errs + ["steps must be a list"]
    seen: dict[int, dict] = {}
    for s in steps:
        if not isinstance(s, dict) or "index" not in s:
            errs.append(f"step entry without index: {s!r}")
            continue
        idx = int(s["index"])
        text = s.get("narration")
        if not isinstance(text, str):
            errs.append(f"step {idx}: narration must be a string")
        elif not text.strip():
            errs.append(f"step {idx}: narration is empty")
        seen[idx] = s
    wanted = {int(s.get("index", 0)) for s in source_steps if (s.get("narration") or "").strip()}
    missing = sorted(wanted - set(seen))
    if missing:
        errs.append(f"missing translations for step(s) {', '.join(map(str, missing))}")
    rec = doc.get("recipe", {})
    if rec and not isinstance(rec, dict):
        errs.append("recipe must be an object")
    elif rec:
        for key, val in rec.items():
            if key not in TRANSLATABLE_RECIPE_KEYS:
                errs.append(f"recipe.{key} is not translatable")
            elif not isinstance(val, str):
                errs.append(f"recipe.{key} must be a string")
    return errs


def apply_translation(steps: list[Any], doc: dict) -> list[str]:
    """Replace each Step.narration with the sidecar line for its index."""
    warnings: list[str] = []
    by_idx = {int(s["index"]): s for s in doc.get("steps", []) if isinstance(s, dict) and "index" in s}
    present = set()
    for st in steps:
        present.add(st.index)
        entry = by_idx.get(st.index)
        if not entry or not (entry.get("narration") or "").strip():
            if st.narration:
                warnings.append(f"step {st.index}: missing translation — keeping source text")
            continue
        src = (entry.get("source") or "").strip()
        if src and src != st.narration.strip():
            warnings.append(f"step {st.index}: stale translation (source line changed since it was translated)")
        st.narration = entry["narration"].strip()
    for idx in sorted(set(by_idx) - present):
        warnings.append(f"step {idx}: extra translation (no such step in the spec) — ignored")
    return warnings


def localized_recipe(recipe: dict, doc: dict) -> dict:
    out = dict(recipe)
    for key, val in (doc.get("recipe") or {}).items():
        if key in TRANSLATABLE_RECIPE_KEYS and isinstance(val, str) and val.strip():
            out[key] = val
    out["lang"] = doc.get("lang") or out.get("lang", "en")
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/tutorial/test_tutorial_i18n.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add lib/tutorial_i18n.py tests/tutorial/test_tutorial_i18n.py
git commit -m "feat(tutorial): translation sidecar helpers for multilingual tutorials

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: `translate_tutorial.py` CLI (template out / sidecar in)

**Files:**
- Create: `translate_tutorial.py` (repo root, next to `author_tutorial.py`)
- Modify: `render_tutorial.py` `resolve_tutorial` (lines 61-83) to accept `lang` and expose `source_lang`, `i18n_path`, `timings_path`
- Test: `tests/tutorial/test_translate_tutorial.py`

**Interfaces:**
- Consumes: Task 1 helpers; `render_tutorial.resolve_tutorial`.
- Produces:
  - `render_tutorial.resolve_tutorial(client_dir: Path, name: str, lang: Optional[str] = None) -> dict` now returns additional keys: `"lang"` (requested or source), `"source_lang"`, `"timings_path"` (per-lang), `"timings"` (per-lang content or `{}`), `"source_timings"` (source-language content or `{}`), `"i18n_path"` (or None when lang == source), `"i18n"` (loaded sidecar or None).
  - `translate_tutorial.template_for(tut: dict) -> dict` and `translate_tutorial.write_sidecar(tut: dict, doc: dict) -> Path` (raise `ValueError` listing problems).
  - CLI: `translate_tutorial.py --tutorial X --client-dir C --lang de --template [-o out.json]` prints/writes the template; `--from file.json` validates + writes the sidecar.

- [ ] **Step 1: Write the failing tests**

```python
# tests/tutorial/test_translate_tutorial.py
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
    saved = json.loads(out.read_text())
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/tutorial/test_translate_tutorial.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'translate_tutorial'`

- [ ] **Step 3: Change `resolve_tutorial` in `render_tutorial.py`**

Add `from lib import tutorial_i18n as I18N  # noqa: E402` to the imports, then replace the function body:

```python
def resolve_tutorial(client_dir: Path, name: str, lang: Optional[str] = None) -> dict:
    root = client_dir / "cypress" / "e2e-tutorials"
    specs = list(root.rglob(f"{name}.tutorial.cy.js"))
    if not specs:
        raise FileNotFoundError(f"No tutorial spec {name}.tutorial.cy.js under {root}")
    spec = specs[0]
    recipe_path = spec.with_name(f"{name}.tutorial.json")
    recipe = json.loads(recipe_path.read_text()) if recipe_path.exists() else {}
    if not recipe_path.exists():
        print(f"WARN: no recipe {recipe_path.name} — using defaults (title from name).", file=sys.stderr)
    if not recipe.get("title"):
        recipe["title"] = name.replace("-", " ").replace("_", " ").title()
    source_lang = recipe.get("lang", "en")
    lang = I18N.validate_lang(lang) if lang else source_lang

    def _load(p: Path) -> dict:
        return json.loads(p.read_text()) if p.exists() else {}

    source_timings_path = I18N.timings_path(spec, name, source_lang, source_lang)
    timings_path = I18N.timings_path(spec, name, lang, source_lang)
    i18n_path = I18N.i18n_path(spec, name, lang) if lang != source_lang else None
    i18n = I18N.load_sidecar(i18n_path) if i18n_path and i18n_path.exists() else None
    spec_rel = spec.relative_to(client_dir).as_posix()
    return {
        "name": name,
        "spec": spec,
        "spec_rel": spec_rel,
        "recipe": recipe,
        "lang": lang,
        "source_lang": source_lang,
        "timings": _load(timings_path),
        "timings_path": timings_path,
        "source_timings": _load(source_timings_path),
        "i18n_path": i18n_path,
        "i18n": i18n,
    }
```

- [ ] **Step 4: Create `translate_tutorial.py`**

```python
#!/usr/bin/env python3
"""Create or update a tutorial's translation sidecar (<name>.i18n.<lang>.json).

  # 1) get a template (every step's source line, empty `narration` to fill):
  python translate_tutorial.py --tutorial sales-tour --client-dir ../circuitauction-backoffice/client \
      --lang de --template -o /tmp/sales-tour.de.json
  # 2) fill the `narration` lines and the `recipe` texts (by hand or with an LLM), then:
  python translate_tutorial.py --tutorial sales-tour --client-dir ../circuitauction-backoffice/client \
      --lang de --from /tmp/sales-tour.de.json

The template is built from the committed source-language timings.json, so run
author_tutorial.py for the source language first. Then author the new language:
  python author_tutorial.py --tutorial sales-tour --client-dir … --lang de --from-timings
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from lib import tutorial_i18n as I18N  # noqa: E402
from render_tutorial import resolve_tutorial  # noqa: E402


def template_for(tut: dict) -> dict:
    source_steps = (tut.get("source_timings") or {}).get("steps") or []
    if not source_steps:
        raise FileNotFoundError(
            f"no source-language timings for {tut['name']} "
            f"({I18N.timings_path(tut['spec'], tut['name'], tut['source_lang'], tut['source_lang']).name}); "
            "run author_tutorial.py for the source language first"
        )
    return I18N.build_template(
        source_lang=tut["source_lang"], lang=tut["lang"], recipe=tut["recipe"],
        source_steps=source_steps, existing=tut.get("i18n"),
    )


def write_sidecar(tut: dict, doc: dict) -> Path:
    if tut.get("i18n_path") is None:
        raise ValueError(f"{tut['lang']} is the source language of this tutorial; nothing to translate")
    source_steps = (tut.get("source_timings") or {}).get("steps") or []
    errs = I18N.validate_translation(doc, lang=tut["lang"], source_steps=source_steps)
    if errs:
        raise ValueError("translation not saved:\n  - " + "\n  - ".join(errs))
    src_by_idx = {int(s["index"]): (s.get("narration") or "").strip() for s in source_steps}
    clean = {
        "lang": tut["lang"],
        "source_lang": tut["source_lang"],
        "recipe": {k: v for k, v in (doc.get("recipe") or {}).items()
                   if k in I18N.TRANSLATABLE_RECIPE_KEYS and isinstance(v, str) and v.strip()},
        "steps": [
            {"index": int(s["index"]),
             "source": src_by_idx.get(int(s["index"]), (s.get("source") or "").strip()),
             "narration": s["narration"].strip()}
            for s in sorted(doc["steps"], key=lambda x: int(x["index"]))
        ],
    }
    out: Path = tut["i18n_path"]
    out.write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tutorial", required=True)
    ap.add_argument("--client-dir", required=True)
    ap.add_argument("--lang", required=True, help="target language code, e.g. de")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--template", action="store_true", help="print/write the translation template")
    mode.add_argument("--from", dest="from_file", help="filled template JSON to validate and save")
    ap.add_argument("-o", "--output", default=None, help="with --template: write here instead of stdout")
    args = ap.parse_args()

    try:
        tut = resolve_tutorial(Path(args.client_dir).resolve(), args.tutorial, lang=args.lang)
        if args.template:
            doc = template_for(tut)
            text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
            if args.output:
                Path(args.output).write_text(text)
                print(f"OK wrote template {args.output}")
            else:
                sys.stdout.write(text)
            return 0
        doc = json.loads(Path(args.from_file).read_text())
        out = write_sidecar(tut, doc)
        print(f"OK wrote {out} ({len(doc['steps'])} steps). Next: author_tutorial.py --lang {args.lang} --from-timings")
        return 0
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

Extra step indices are allowed in the file; `apply_translation` warns about them at render time.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/tutorial/test_translate_tutorial.py tests/tutorial/test_render_tutorial_narration.py tests/tutorial/test_tutorial_lib.py -v`
Expected: all PASS (existing callers of `resolve_tutorial` keep working: the new keys are additive).

- [ ] **Step 6: Commit**

```bash
git add translate_tutorial.py render_tutorial.py tests/tutorial/test_translate_tutorial.py
git commit -m "feat(tutorial): translation template/sidecar CLI and per-language resolution

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Cypress bridge passes the language; client config picks per-language timings

**Files:**
- Modify: `tools/capture/cypress_bridge.py` `run_tutorial_spec` (lines 46-109)
- Modify (client repo): `../circuitauction-backoffice/client/cypress.tutorial.config.js` `loadTimingsBySpec` (lines 25-44) and the assignment at line 71
- Test: `tests/tutorial/test_cypress_bridge_lang.py`

**Interfaces:**
- Produces: `run_tutorial_spec(client_dir, spec, base_url=None, collect_only=False, timeout=1800, lang: Optional[str] = None)` — when `lang` is set, the subprocess env has `CYPRESS_TUTORIAL_LANG=<lang>` and `--env` includes `tutorialLang=<lang>`.
- Client: `config.env.tutorialTimingsBySpec` holds the timings for `process.env.CYPRESS_TUTORIAL_LANG` (fallback: the un-suffixed file); `config.env.tutorialLang` echoes the chosen language so the spec's manifest records it.

- [ ] **Step 1: Write the failing test**

```python
# tests/tutorial/test_cypress_bridge_lang.py
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tools.capture import cypress_bridge as bridge  # noqa: E402


def test_run_tutorial_spec_passes_lang(tmp_path, monkeypatch):
    seen = {}

    def fake_run(cmd, cwd=None, env=None, timeout=None):
        seen["cmd"], seen["env"] = cmd, env

    monkeypatch.setattr(bridge, "_run", fake_run)
    monkeypatch.setattr(bridge, "_find_manifest", lambda client, spec: ({"steps": []}, tmp_path / "m.json"))
    monkeypatch.setattr(bridge, "_resolve_browser", lambda: "")
    bridge.run_tutorial_spec(str(tmp_path), "cypress/e2e-tutorials/x.tutorial.cy.js", lang="de")
    assert seen["env"]["CYPRESS_TUTORIAL_LANG"] == "de"
    env_arg = seen["cmd"][seen["cmd"].index("--env") + 1]
    assert "tutorialLang=de" in env_arg.split(",")

    bridge.run_tutorial_spec(str(tmp_path), "cypress/e2e-tutorials/x.tutorial.cy.js")
    assert "CYPRESS_TUTORIAL_LANG" not in seen["env"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/tutorial/test_cypress_bridge_lang.py -v`
Expected: FAIL with `TypeError: run_tutorial_spec() got an unexpected keyword argument 'lang'`

- [ ] **Step 3: Modify the bridge**

Signature: add `lang: Optional[str] = None` after `timeout`. After `if collect_only: env_pairs.append("tutorialCollectOnly=1")` add:

```python
    if lang:
        env_pairs.append(f"tutorialLang={lang}")
```

After `env["CYPRESS_NO_COMMAND_LOG"] = "1"` add:

```python
    if lang:
        env["CYPRESS_TUTORIAL_LANG"] = lang  # cypress.tutorial.config.js picks <name>.timings.<lang>.json
```

- [ ] **Step 4: Modify the client config** (in `circuitauction-backoffice/client`, separate commit there)

Replace `loadTimingsBySpec` with:

```js
// Load committed timings (written by author_tutorial.py) so cy.tutorialStep can
// hold each step long enough for its narration audio. Two file shapes:
//   foo.timings.json       -> the spec's source language (legacy name)
//   foo.timings.<lang>.json -> an authored translation (e.g. foo.timings.de.json)
// Returns { "<spec rel>": { "<lang or 'default'>": [{ index, narration, duration_ms }, ...] } }.
const TIMINGS_RE = /\.timings(?:\.([a-z]{2}(?:-[A-Z]{2})?))?\.json$/;

function loadTimingsBySpec(specDir) {
  const out = {};
  const walk = (dir) => {
    let entries = [];
    try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch (e) { return; }
    for (const ent of entries) {
      const full = path.join(dir, ent.name);
      if (ent.isDirectory()) { walk(full); continue; }
      const m = ent.name.match(TIMINGS_RE);
      if (!m) continue;
      try {
        const data = JSON.parse(fs.readFileSync(full, "utf8"));
        const specFile = full.replace(TIMINGS_RE, ".tutorial.cy.js");
        const rel = path.relative(process.cwd(), specFile).split(path.sep).join("/");
        out[rel] = out[rel] || {};
        out[rel][m[1] || "default"] = Array.isArray(data.steps) ? data.steps : [];
      } catch (e) { /* ignore malformed timings */ }
    }
  };
  walk(specDir);
  return out;
}

// Pick one language per spec: the requested one when authored, else the default file.
function timingsForLang(bySpec, lang) {
  const out = {};
  for (const rel of Object.keys(bySpec)) {
    const langs = bySpec[rel];
    out[rel] = (lang && langs[lang]) || langs.default || [];
  }
  return out;
}
```

and change the assignment in `setupNodeEvents`:

```js
      const tutorialLang = process.env.CYPRESS_TUTORIAL_LANG || config.env.tutorialLang || "";
      config.env.tutorialLang = tutorialLang;
      config.env.tutorialTimingsBySpec = timingsForLang(loadTimingsBySpec(specDir), tutorialLang);
```

In `cypress/support/tutorial.js`, inside the `_pending = {` object add `lang: Cypress.env("tutorialLang") || "",` so the manifest records which timings paced the capture.

- [ ] **Step 5: Verify**

Run: `.venv/bin/python -m pytest tests/tutorial/test_cypress_bridge_lang.py -v` → PASS.

Client sanity (needs the demo app; collect-only, no video): from `../circuitauction-backoffice/client`,
`CYPRESS_TUTORIAL_LANG=de npx cypress run --config-file cypress.tutorial.config.js --spec cypress/e2e-tutorials/release-3.5/support-tickets.tutorial.cy.js --env tutorialCollectOnly=1 --browser chrome`
then check the produced manifest sidecar has `"lang": "de"` on each step (fallback timings are used until Task 5 authors `de`).

- [ ] **Step 6: Commit (both repos)**

```bash
git add tools/capture/cypress_bridge.py tests/tutorial/test_cypress_bridge_lang.py
git commit -m "feat(capture): pass the tutorial language to Cypress for per-language timings

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
cd ../circuitauction-backoffice && git add client/cypress.tutorial.config.js client/cypress/support/tutorial.js && \
git commit -m "tutorials: load <name>.timings.<lang>.json for CYPRESS_TUTORIAL_LANG

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" && cd -
```

---

### Task 4: `render_tutorial.py --lang`

**Files:**
- Modify: `render_tutorial.py` — `build_arg_parser` (add `--lang`), `main()` (tutorial resolution, translation application, capture call, title cards use the localized recipe)
- Test: `tests/tutorial/test_render_tutorial_lang.py`

**Interfaces:**
- Consumes: Task 1 (`apply_translation`, `localized_recipe`), Task 2 (`resolve_tutorial(..., lang)`), Task 3 (`run_tutorial_spec(..., lang=)`).
- Produces: `render_tutorial.prepare_language(tut: dict, steps: list[Step]) -> tuple[dict, str, list[str]]` — returns `(recipe_for_render, lang, warnings)`; raises `FileNotFoundError` when the sidecar is missing and `RuntimeError` when the per-language timings are missing (unless `allow_untimed=True`, used by `--offline-narration`/`--capture` test paths).

- [ ] **Step 1: Write the failing test**

```python
# tests/tutorial/test_render_tutorial_lang.py
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import render_tutorial as RT  # noqa: E402
from lib import tutorial as T  # noqa: E402


def _client(tmp_path: Path, with_de: bool) -> Path:
    d = tmp_path / "cypress" / "e2e-tutorials" / "s"
    d.mkdir(parents=True)
    (d / "tour.tutorial.cy.js").write_text("")
    (d / "tour.tutorial.json").write_text(json.dumps({"title": "Tour", "lang": "en", "outro_text": "Thanks"}))
    (d / "tour.timings.json").write_text(json.dumps({"lang": "en", "steps": [
        {"index": 0, "narration": "Hello.", "duration_ms": 800}]}))
    if with_de:
        (d / "tour.i18n.de.json").write_text(json.dumps({"lang": "de", "source_lang": "en",
            "recipe": {"title": "Rundgang", "outro_text": "Danke"},
            "steps": [{"index": 0, "source": "Hello.", "narration": "Hallo."}]}))
        (d / "tour.timings.de.json").write_text(json.dumps({"lang": "de", "steps": [
            {"index": 0, "narration": "Hallo.", "duration_ms": 900}]}))
    return tmp_path


def test_prepare_language_source_lang_is_passthrough(tmp_path):
    tut = RT.resolve_tutorial(_client(tmp_path, False), "tour")
    steps = [T.Step(index=0, narration="Hello.")]
    recipe, lang, warnings = RT.prepare_language(tut, steps)
    assert lang == "en" and recipe["title"] == "Tour" and steps[0].narration == "Hello." and warnings == []


def test_prepare_language_applies_german(tmp_path):
    tut = RT.resolve_tutorial(_client(tmp_path, True), "tour", lang="de")
    steps = [T.Step(index=0, narration="Hello.")]
    recipe, lang, warnings = RT.prepare_language(tut, steps)
    assert lang == "de" and recipe["lang"] == "de"
    assert recipe["title"] == "Rundgang" and recipe["outro_text"] == "Danke"
    assert steps[0].narration == "Hallo." and warnings == []


def test_prepare_language_requires_sidecar_and_timings(tmp_path):
    tut = RT.resolve_tutorial(_client(tmp_path, False), "tour", lang="de")
    with pytest.raises(FileNotFoundError, match="translate_tutorial"):
        RT.prepare_language(tut, [T.Step(index=0, narration="Hello.")])
    client = _client(tmp_path / "b", True)
    (client / "cypress" / "e2e-tutorials" / "s" / "tour.timings.de.json").unlink()
    tut = RT.resolve_tutorial(client, "tour", lang="de")
    with pytest.raises(RuntimeError, match="author_tutorial"):
        RT.prepare_language(tut, [T.Step(index=0, narration="Hello.")])
    recipe, lang, warnings = RT.prepare_language(tut, [T.Step(index=0, narration="Hello.")], allow_untimed=True)
    assert lang == "de" and any("timings" in w for w in warnings)


def test_cli_accepts_lang():
    args = RT.build_arg_parser().parse_args(["--tutorial", "t", "--client-dir", "/c", "--project-id", "p", "--lang", "de"])
    assert args.lang == "de"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/tutorial/test_render_tutorial_lang.py -v`
Expected: FAIL with `AttributeError: module 'render_tutorial' has no attribute 'prepare_language'`

- [ ] **Step 3: Implement**

In `build_arg_parser()` add after `--client-dir`:

```python
    ap.add_argument("--lang", default=None,
                    help="render in this language (e.g. de): needs <name>.i18n.<lang>.json "
                         "(translate_tutorial.py) and <name>.timings.<lang>.json (author_tutorial.py --lang). "
                         "Default: the recipe's source language.")
```

Add the helper (near `resolve_tutorial`):

```python
def prepare_language(tut: dict, steps: list, *, allow_untimed: bool = False) -> tuple[dict, str, list[str]]:
    """Swap narration/recipe texts for tut['lang']. Returns (recipe, lang, warnings)."""
    lang = tut["lang"]
    recipe = dict(tut["recipe"])
    if lang == tut["source_lang"]:
        return recipe, lang, []
    if not tut.get("i18n"):
        raise FileNotFoundError(
            f"no translation for {lang!r}: expected {tut['i18n_path']} — create it with "
            f"translate_tutorial.py --tutorial {tut['name']} --lang {lang}"
        )
    warnings = [f"WARN: {w}" for w in I18N.apply_translation(steps, tut["i18n"])]
    if not (tut.get("timings") or {}).get("steps"):
        msg = (f"no {lang} timings ({tut['timings_path'].name}): the capture is not paced to the "
               f"{lang} narration — run author_tutorial.py --tutorial {tut['name']} --lang {lang} --from-timings")
        if not allow_untimed:
            raise RuntimeError(msg)
        warnings.append("WARN: " + msg)
    return I18N.localized_recipe(recipe, tut["i18n"]), lang, warnings
```

In `main()`:
- `tut = resolve_tutorial(client_dir, args.tutorial, lang=args.lang)`; keep `recipe = tut["recipe"]` for the early validations, then **after** `steps = T.steps_from_manifest(manifest)` (step 3 of the flow) insert:

```python
    try:
        recipe, lang, lang_warnings = prepare_language(
            tut, steps, allow_untimed=bool(args.offline_narration or args.capture),
        )
    except (FileNotFoundError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    for w in lang_warnings:
        print(w, file=sys.stderr)
```

  Because the capture happens before this point but must already be paced for the language, also guard **before** the capture (right after `tut = resolve_tutorial(...)`):

```python
    if tut["lang"] != tut["source_lang"] and not args.capture:
        if not tut.get("i18n"):
            print(f"ERROR: no translation sidecar {tut['i18n_path']} — run translate_tutorial.py first",
                  file=sys.stderr)
            return 2
        if not (tut.get("timings") or {}).get("steps") and not args.offline_narration:
            print(f"ERROR: no {tut['lang']} timings {tut['timings_path'].name} — run "
                  f"author_tutorial.py --lang {tut['lang']} --from-timings first", file=sys.stderr)
            return 2
```

- The capture call becomes `bridge.run_tutorial_spec(str(client_dir), tut["spec_rel"], base_url=args.base_url, lang=tut["lang"] if tut["lang"] != tut["source_lang"] else None)`.
- `lang = recipe.get("lang", "en")` near the top stays for the early narration-choice call; after `prepare_language` the variable `lang` is the render language and `recipe` the localized recipe — every later use (`narrator.render(lang, …)`, `_build_srt`, `make_title_card(... recipe.get("intro_text") ...)`, `init_project(title=...)`) therefore picks up the translation. Move the `init_project(...)` call so it runs after `prepare_language` **or** keep it and accept the project title in the source language (choose the latter: simpler; the title cards are what viewers see).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/tutorial -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add render_tutorial.py tests/tutorial/test_render_tutorial_lang.py
git commit -m "feat(tutorial): render_tutorial --lang swaps narration, captions and cards

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: `author_tutorial.py --lang <x>` and `--from-timings`

**Files:**
- Modify: `author_tutorial.py` (whole `main()`)
- Test: `tests/tutorial/test_author_tutorial.py`

**Interfaces:**
- Consumes: Task 2 `resolve_tutorial(..., lang)`, Task 1 `apply_translation`, Plan A's `T.resolve_narration_choice` / `T.narration_client_for`.
- Produces: `author_tutorial.author_timings(tut: dict, client, *, steps: list[dict], backend: str, voice_id: str) -> dict` (pure except for `client.render` into a temp dir) returning the timings document `{"spec", "lang", "narration": {...}, "steps": [...]}`; CLI flags `--lang`, `--from-timings`.

- [ ] **Step 1: Write the failing test**

```python
# tests/tutorial/test_author_tutorial.py
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import author_tutorial as AT  # noqa: E402
import render_tutorial as RT  # noqa: E402


class _Client:
    def __init__(self):
        self.calls = []

    def health(self):
        return {"status": "ok"}

    def render(self, lang, text, out_path):
        self.calls.append((lang, text))
        Path(out_path).write_bytes(b"RIFF" + b"\0" * 40)
        return 1000 + 10 * len(text)


def _client_dir(tmp_path: Path) -> Path:
    d = tmp_path / "cypress" / "e2e-tutorials" / "s"
    d.mkdir(parents=True)
    (d / "tour.tutorial.cy.js").write_text("")
    (d / "tour.tutorial.json").write_text(json.dumps({"title": "Tour", "lang": "en"}))
    (d / "tour.timings.json").write_text(json.dumps({"lang": "en", "steps": [
        {"index": 0, "narration": "Hello.", "duration_ms": 1},
        {"index": 1, "narration": "Bye.", "duration_ms": 1}]}))
    (d / "tour.i18n.de.json").write_text(json.dumps({"lang": "de", "source_lang": "en", "recipe": {},
        "steps": [{"index": 0, "source": "Hello.", "narration": "Hallo."},
                  {"index": 1, "source": "Bye.", "narration": "Tschüss."}]}))
    return tmp_path


def test_author_german_from_source_timings(tmp_path):
    tut = RT.resolve_tutorial(_client_dir(tmp_path), "tour", lang="de")
    c = _Client()
    doc = AT.author_timings(tut, c, steps=tut["source_timings"]["steps"], backend="ttsd", voice_id="")
    assert c.calls == [("de", "Hallo."), ("de", "Tschüss.")]
    assert doc["lang"] == "de" and doc["narration"] == {"backend": "ttsd", "voice_id": ""}
    assert doc["steps"] == [{"index": 0, "narration": "Hallo.", "duration_ms": 1060},
                            {"index": 1, "narration": "Tschüss.", "duration_ms": 1080}]
    assert doc["source_lang"] == "en"


def test_author_source_lang_unchanged(tmp_path):
    tut = RT.resolve_tutorial(_client_dir(tmp_path), "tour")
    c = _Client()
    doc = AT.author_timings(tut, c, steps=tut["source_timings"]["steps"], backend="ttsd", voice_id="")
    assert c.calls == [("en", "Hello."), ("en", "Bye.")] and doc["lang"] == "en"


def test_author_german_without_sidecar_fails(tmp_path):
    client = _client_dir(tmp_path)
    (client / "cypress" / "e2e-tutorials" / "s" / "tour.i18n.de.json").unlink()
    tut = RT.resolve_tutorial(client, "tour", lang="de")
    with pytest.raises(FileNotFoundError, match="translate_tutorial"):
        AT.author_timings(tut, _Client(), steps=tut["source_timings"]["steps"], backend="ttsd", voice_id="")


def test_cli_flags():
    ap = AT.build_arg_parser()
    a = ap.parse_args(["--tutorial", "t", "--client-dir", "/c", "--lang", "de", "--from-timings"])
    assert a.lang == "de" and a.from_timings is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/tutorial/test_author_tutorial.py -v`
Expected: FAIL with `AttributeError: module 'author_tutorial' has no attribute 'author_timings'`

- [ ] **Step 3: Rewrite `author_tutorial.py` main section**

```python
from lib import tutorial_i18n as I18N  # noqa: E402  (add to imports)


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Generate a tutorial's narration timings (per language).")
    ap.add_argument("--tutorial", required=True)
    ap.add_argument("--client-dir", required=True)
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--narration-url", default="http://127.0.0.1:5557")
    ap.add_argument("--narration-backend", choices=list(T.NARRATION_BACKENDS), default=None)
    ap.add_argument("--voice-id", default=None)
    ap.add_argument("--lang", default=None,
                    help="language to author (default: the recipe's source language). A non-source "
                         "language needs <name>.i18n.<lang>.json and writes <name>.timings.<lang>.json")
    ap.add_argument("--manifest", default=None,
                    help="reuse an existing collect manifest instead of running Cypress")
    ap.add_argument("--from-timings", action="store_true",
                    help="take the step list from the committed source-language timings.json "
                         "(no Cypress run)")
    return ap


def author_timings(tut: dict, client, *, steps: list[dict], backend: str, voice_id: str) -> dict:
    """Synthesize every line once in tut['lang'] and return the timings document."""
    lang = tut["lang"]
    ordered = sorted(steps, key=lambda s: int(s.get("index", 0)))
    step_objs = [T.Step(index=int(s.get("index", 0)), narration=(s.get("narration") or "").strip())
                 for s in ordered]
    if lang != tut["source_lang"]:
        if not tut.get("i18n"):
            raise FileNotFoundError(
                f"no translation sidecar {tut['i18n_path']} — run translate_tutorial.py "
                f"--tutorial {tut['name']} --lang {lang} first"
            )
        for w in I18N.apply_translation(step_objs, tut["i18n"]):
            print(f"WARN: {w}", file=sys.stderr)
    out_steps = []
    with tempfile.TemporaryDirectory() as tmp:
        for st in step_objs:
            if not st.narration:
                continue
            dur = client.render(lang, st.narration, str(Path(tmp) / f"step_{st.index}.wav"))
            out_steps.append({"index": st.index, "narration": st.narration, "duration_ms": dur})
    return {
        "spec": tut["spec_rel"],
        "lang": lang,
        "source_lang": tut["source_lang"],
        "narration": {"backend": backend, "voice_id": voice_id},
        "steps": out_steps,
    }


def main() -> int:
    args = build_arg_parser().parse_args()
    client_dir = Path(args.client_dir).resolve()
    try:
        tut = resolve_tutorial(client_dir, args.tutorial, lang=args.lang)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    env = {**parse_env_file(REPO_ROOT / ".env"), **os.environ}
    try:
        backend, voice_id = T.resolve_narration_choice(
            cli_backend=args.narration_backend, cli_voice_id=args.voice_id,
            recipe=tut["recipe"], env=env,
        )
        client = T.narration_client_for(backend, narration_url=args.narration_url,
                                        voice_id=voice_id, env=env)
        client.health()
    except (ValueError, NarrationError) as e:
        print(f"ERROR: narration backend not ready: {e}", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: ttsd not reachable at {args.narration_url}: {e}", file=sys.stderr)
        return 2

    if args.from_timings:
        steps = (tut.get("source_timings") or {}).get("steps") or []
        if not steps:
            print("ERROR: --from-timings needs the source-language timings.json; author it first "
                  "(without --from-timings)", file=sys.stderr)
            return 2
    elif args.manifest:
        steps = json.loads(Path(args.manifest).read_text()).get("steps", [])
    else:
        manifest = bridge.run_tutorial_spec(
            str(client_dir), tut["spec_rel"], base_url=args.base_url, collect_only=True,
        )
        steps = manifest.get("steps", [])

    try:
        doc = author_timings(tut, client, steps=steps, backend=backend, voice_id=voice_id)
    except (FileNotFoundError, NarrationError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    tut["timings_path"].write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    print(f"OK wrote {tut['timings_path']} ({len(doc['steps'])} steps, lang={doc['lang']})")
    return 0
```

(Remove the old `--lang` default handling that passed the language straight to TTS with English text; `tut["lang"]` now carries it.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/tutorial -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add author_tutorial.py tests/tutorial/test_author_tutorial.py
git commit -m "feat(tutorial): author per-language timings from translations without Cypress

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: MCP — `lang` on `render_tutorial`, `get_tutorial_text`, `save_tutorial_translation`, `author_tutorial`

**Files:**
- Modify: `mcp_servers/circuit_video/config.py` (add `validate_lang` re-export)
- Modify: `mcp_servers/circuit_video/service.py` (`list_tutorials`, `render_argv`, `render_tutorial`, `_run_remote`; new `tutorial_text`, `save_translation`, `author_tutorial`)
- Modify: `mcp_servers/circuit_video/server.py` (`TOOLS`, `_call`, `INSTRUCTIONS`)
- Test: `tests/mcp/test_circuit_video.py` (append)

**Interfaces:**
- Consumes: `translate_tutorial.template_for` / `write_sidecar`, `render_tutorial.resolve_tutorial`, `author_tutorial.py` CLI (Task 5), Plan A's `elevenlabs_env`.
- Produces:
  - `service.list_tutorials` items gain `"source_lang"` and `"languages": {"de": {"translated": bool, "timed": bool}, ...}` (one entry per `*.i18n.*.json` / `*.timings.*.json` found).
  - `service.tutorial_text(tutorial, lang, cfg=None) -> dict` (the template; `steps[].stale`).
  - `service.save_translation(tutorial, lang, translation: dict, cfg=None) -> dict` → `{"path", "steps", "next": "author_tutorial"}`.
  - `service.author_tutorial(tutorial, lang=None, *, narration_backend=None, voice_id=None, from_timings=True, cfg=None) -> dict` → runs `author_tutorial.py` as a subprocess, returns `{"status", "timings_path", "steps", "log_tail"}`.
  - `service.render_argv(..., lang=None)` adds `--lang`; `service.render_tutorial(..., lang=None)`.
  - Tools: `render_tutorial.lang` (string), `author_tutorial`, `get_tutorial_text`, `save_tutorial_translation`.

- [ ] **Step 1: Write the failing tests** (append to `tests/mcp/test_circuit_video.py`)

```python
from circuit_video.service import author_tutorial, save_translation, tutorial_text  # noqa: E402


def _client_with_de(tmp_path):
    d = tmp_path / "cypress" / "e2e-tutorials" / "s"
    d.mkdir(parents=True)
    (d / "tour.tutorial.cy.js").write_text("")
    (d / "tour.tutorial.json").write_text(json.dumps({"title": "Tour", "lang": "en"}))
    (d / "tour.timings.json").write_text(json.dumps({"lang": "en", "steps": [
        {"index": 0, "narration": "Hello.", "duration_ms": 1}]}))
    return tmp_path


def test_list_tutorials_reports_languages(tmp_path):
    client = _client_with_de(tmp_path)
    d = client / "cypress" / "e2e-tutorials" / "s"
    (d / "tour.i18n.de.json").write_text("{}")
    (d / "tour.timings.fr.json").write_text("{}")
    out = list_tutorials({"client_dir": str(client)})["tutorials"][0]
    assert out["source_lang"] == "en"
    assert out["languages"] == {"de": {"translated": True, "timed": False},
                                "fr": {"translated": False, "timed": True}}


def test_tutorial_text_and_save_translation(tmp_path):
    cfg = {"client_dir": str(_client_with_de(tmp_path))}
    tpl = tutorial_text("tour", "de", cfg=cfg)
    assert tpl["steps"] == [{"index": 0, "source": "Hello.", "narration": "", "stale": False}]
    tpl["steps"][0]["narration"] = "Hallo."
    tpl["recipe"]["title"] = "Rundgang"
    res = save_translation("tour", "de", tpl, cfg=cfg)
    assert res["path"].endswith("tour.i18n.de.json") and res["steps"] == 1
    assert json.loads(Path(res["path"]).read_text())["recipe"]["title"] == "Rundgang"


def test_save_translation_rejects_bad_payload(tmp_path):
    cfg = {"client_dir": str(_client_with_de(tmp_path))}
    with pytest.raises(ValueError, match="step 0"):
        save_translation("tour", "de", {"lang": "de", "steps": [{"index": 0, "narration": ""}]}, cfg=cfg)
    with pytest.raises(ValueError, match="lang"):
        tutorial_text("tour", "German", cfg=cfg)


def test_render_argv_lang():
    cfg = {"client_dir": "/c", "narration_url": "http://127.0.0.1:5557", "render_runtime": "ffmpeg"}
    argv = render_argv(cfg, tutorial="t", project_id="p", base_url="https://d.example.com", lang="de")
    assert argv[argv.index("--lang") + 1] == "de"
    argv = render_argv(cfg, tutorial="t", project_id="p", base_url="https://d.example.com")
    assert "--lang" not in argv


def test_author_tutorial_runs_cli(tmp_path, monkeypatch):
    import subprocess as sp
    cfg = {**load_config(), "client_dir": str(_client_with_de(tmp_path)), "projects_dir": str(tmp_path / "p")}
    seen = {}

    class P:
        returncode = 0
        stdout = "OK wrote x (1 steps, lang=de)\n"

    def fake_run(argv, **kw):
        seen["argv"] = argv
        return P()

    monkeypatch.setattr(sp, "run", fake_run)
    out = author_tutorial("tour", "de", narration_backend="elevenlabs", voice_id="VX", cfg=cfg)
    a = seen["argv"]
    assert a[1].endswith("author_tutorial.py") and "--from-timings" in a
    assert a[a.index("--lang") + 1] == "de" and a[a.index("--voice-id") + 1] == "VX"
    assert a[a.index("--narration-backend") + 1] == "elevenlabs"
    assert out["status"] == "succeeded" and out["timings_path"].endswith("tour.timings.de.json")


def test_tools_list_has_i18n_tools():
    names = {t["name"] for t in TOOLS}
    assert {"get_tutorial_text", "save_tutorial_translation", "author_tutorial"} <= names
    rt = next(t for t in TOOLS if t["name"] == "render_tutorial")
    assert rt["inputSchema"]["properties"]["lang"]["type"] == "string"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/mcp/test_circuit_video.py -v`
Expected: FAIL with `ImportError: cannot import name 'author_tutorial' from 'circuit_video.service'`

- [ ] **Step 3: Implement in `service.py`**

Imports: add at module top

```python
import sys as _sys
if str(REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(REPO_ROOT))
from lib import tutorial_i18n as I18N  # noqa: E402
```

`list_tutorials`: replace the `items.append({...})` with

```python
        recipe_path = spec.with_name(f"{name}.tutorial.json")
        source_lang = "en"
        try:
            source_lang = json.loads(recipe_path.read_text()).get("lang", "en") if recipe_path.exists() else "en"
        except (OSError, json.JSONDecodeError):
            pass
        langs: dict[str, dict] = {}
        for p in spec.parent.glob(f"{name}.i18n.*.json"):
            code = p.name[len(f"{name}.i18n."):-len(".json")]
            langs.setdefault(code, {"translated": False, "timed": False})["translated"] = True
        for p in spec.parent.glob(f"{name}.timings.*.json"):
            code = p.name[len(f"{name}.timings."):-len(".json")]
            langs.setdefault(code, {"translated": False, "timed": False})["timed"] = True
        items.append({
            "name": name,
            "spec": rel,
            "has_recipe": recipe_path.exists(),
            "has_timings": spec.with_name(f"{name}.timings.json").exists(),
            "source_lang": source_lang,
            "languages": dict(sorted(langs.items())),
        })
```

New functions:

```python
def _resolve(cfg: dict, tutorial: str, lang: Optional[str]):
    from render_tutorial import resolve_tutorial

    tutorial = validate_tutorial_name(tutorial)
    lang = I18N.validate_lang(lang) if lang else None
    return resolve_tutorial(Path(cfg["client_dir"]), tutorial, lang=lang)


def tutorial_text(tutorial: str, lang: str, cfg: Optional[dict] = None) -> dict:
    """Template for translating `tutorial` into `lang` (agent fills `narration` + `recipe`)."""
    from translate_tutorial import template_for

    cfg = cfg or load_config()
    return template_for(_resolve(cfg, tutorial, lang))


def save_translation(tutorial: str, lang: str, translation: dict, cfg: Optional[dict] = None) -> dict:
    from translate_tutorial import write_sidecar

    cfg = cfg or load_config()
    if not isinstance(translation, dict):
        raise ValueError("translation must be the object returned by get_tutorial_text, filled in")
    tut = _resolve(cfg, tutorial, lang)
    path = write_sidecar(tut, {**translation, "lang": tut["lang"]})
    return {"path": str(path), "lang": tut["lang"], "steps": len(translation.get("steps", [])),
            "next": f"author_tutorial(tutorial={tutorial!r}, lang={tut['lang']!r}) then "
                    f"render_tutorial(..., lang={tut['lang']!r})"}


def author_tutorial(tutorial: str, lang: Optional[str] = None, *, narration_backend: Optional[str] = None,
                    voice_id: Optional[str] = None, from_timings: bool = True,
                    cfg: Optional[dict] = None) -> dict:
    """Run author_tutorial.py to (re)generate the timings file for a language."""
    cfg = cfg or load_config()
    tut = _resolve(cfg, tutorial, lang)
    narration_backend = validate_narration_backend(narration_backend or "")
    voice_id = validate_voice_id(voice_id or "")
    argv = [sys.executable, str(REPO_ROOT / "author_tutorial.py"),
            "--tutorial", tut["name"], "--client-dir", cfg["client_dir"],
            "--narration-url", cfg["narration_url"], "--lang", tut["lang"]]
    if from_timings:
        argv.append("--from-timings")
    elif cfg.get("base_url"):
        argv += ["--base-url", cfg["base_url"]]
    backend = narration_backend or cfg.get("narration_backend") or ""
    if backend:
        argv += ["--narration-backend", backend]
    vid = voice_id or cfg.get("voice_id") or ""
    if vid:
        argv += ["--voice-id", vid]
    env = os.environ.copy()
    env.update(elevenlabs_env(cfg))
    proc = subprocess.run(argv, cwd=str(REPO_ROOT), env=env, capture_output=True, text=True,
                          timeout=cfg.get("render_timeout_sec") or 1800)
    out = {
        "status": "succeeded" if proc.returncode == 0 else "failed",
        "lang": tut["lang"],
        "timings_path": str(tut["timings_path"]),
        "log_tail": _truncate((proc.stdout or "") + (proc.stderr or ""), 4000),
    }
    if proc.returncode == 0:
        try:
            out["steps"] = len(json.loads(tut["timings_path"].read_text()).get("steps", []))
        except (OSError, json.JSONDecodeError):
            out["steps"] = None
    return out
```

`render_argv`: add `lang: Optional[str] = None` and `if lang: argv += ["--lang", lang]`.
`render_tutorial`: add `lang: Optional[str] = None`; `lang = I18N.validate_lang(lang) if lang else None`; add `"lang": lang` to the job; `_run_local` passes `lang=job.get("lang")` to `render_argv`; `_run_remote` adds `body["lang"] = job["lang"]` when set. Early guard (before the Cypress capture): when `lang` is set and `not offline`, resolve the tutorial and fail with `RuntimeError` if `tut["i18n"] is None` ("translate first: get_tutorial_text / save_tutorial_translation") or `tut["timings"]` is empty ("author first: author_tutorial(lang=…)").

- [ ] **Step 4: Implement in `server.py`**

Add to `TOOLS`:

```python
    _tool(
        "get_tutorial_text",
        "Return the translation template for a tutorial: every narration step with its source "
        "text (from the committed timings.json) plus the translatable recipe texts (title, "
        "intro/outro). Fill `narration` for each step and the `recipe` values in the target "
        "language, then call save_tutorial_translation.",
        {
            "tutorial": {"type": "string", "description": "Tutorial name, e.g. support-tickets."},
            "lang": {"type": "string", "description": "Target language code, e.g. de."},
        },
        ["tutorial", "lang"],
    ),
    _tool(
        "save_tutorial_translation",
        "Validate and write <name>.i18n.<lang>.json next to the Cypress spec. Then run "
        "author_tutorial for that lang (voice durations) and render_tutorial with lang.",
        {
            "tutorial": {"type": "string"},
            "lang": {"type": "string"},
            "translation": {
                "type": "object",
                "description": "The object from get_tutorial_text with narration/recipe filled in.",
            },
        },
        ["tutorial", "lang", "translation"],
    ),
    _tool(
        "author_tutorial",
        "Synthesize each narration line once and write the timings file that paces the "
        "Cypress capture (<name>.timings.json, or <name>.timings.<lang>.json). Re-run after "
        "changing the voice, the narration text, or a translation. Uses the committed "
        "source timings as the step list (no Cypress run).",
        {
            "tutorial": {"type": "string"},
            "lang": {"type": "string", "description": "Language to author; default: the source language."},
            "narration_backend": {"type": "string", "enum": ["ttsd", "elevenlabs"]},
            "voice_id": {"type": "string"},
        },
        ["tutorial"],
    ),
```

and to `render_tutorial`'s properties:

```python
            "lang": {
                "type": "string",
                "description": "Render voice, captions and title cards in this language (e.g. de). "
                               "Needs the translation (get_tutorial_text → save_tutorial_translation) "
                               "and timings (author_tutorial) for that lang. Default: source language.",
            },
```

`_call` additions:

```python
        if name == "get_tutorial_text":
            return _ok(service.tutorial_text(args.get("tutorial") or "", args.get("lang") or ""))
        if name == "save_tutorial_translation":
            return _ok(service.save_translation(args.get("tutorial") or "", args.get("lang") or "",
                                                args.get("translation") or {}))
        if name == "author_tutorial":
            return _ok(service.author_tutorial(
                args.get("tutorial") or "", args.get("lang") or None,
                narration_backend=args.get("narration_backend") or None,
                voice_id=args.get("voice_id") or None,
            ))
```

and pass `lang=args.get("lang") or None` into `service.render_tutorial`. Append to `INSTRUCTIONS`: `" For another language: get_tutorial_text → translate → save_tutorial_translation → author_tutorial(lang) → render_tutorial(lang)."`

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/mcp tests/tutorial -q`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add mcp_servers/circuit_video/service.py mcp_servers/circuit_video/server.py mcp_servers/circuit_video/config.py tests/mcp/test_circuit_video.py
git commit -m "feat(circuit-video mcp): lang option plus translation and authoring tools

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: `tutorialctl` parity and docs

**Files:**
- Modify: `tutorialctl.py` (`cmd_author`, `cmd_render`, `common` args: add `--lang`; `cmd_list` shows languages)
- Modify: `mcp_servers/circuit_video/README.md`, `circuit-mcp.md`, `.agents/skills/circuit-video/SKILL.md`, `mcp_servers/circuit_video/env.example` (one line: `ELEVENLABS_VOICE_IDS` must include `de:`)

- [ ] **Step 1: `tutorialctl.py`** — add `common.add_argument("--lang", dest="lang", default=S, help="language to author/render (needs i18n + timings for it)")`; in `cmd_author` and `cmd_render` append `["--lang", cfg["lang"]]` only when `cfg["lang"]` differs from the recipe default (today `--lang` is always passed to author from `cfg["lang"]`, default `"en"`; keep that but it now means "authoring language", so for `tutorialctl author support-tickets --lang de` it passes `--lang de --from-timings`). Add a `translate` subcommand that shells to `translate_tutorial.py` with the same `--tutorial/--client-dir/--lang` and forwards `--template/-o/--from`.

- [ ] **Step 2: README section**

```markdown
## Other languages (German first)

Each tutorial has a source language (`lang` in the recipe, default `en`). To
render it in German:

1. `get_tutorial_text(tutorial, lang="de")` → translate every `narration` and the
   `recipe` texts → `save_tutorial_translation(...)` (writes `<name>.i18n.de.json`
   next to the spec; commit it in the client repo).
2. `author_tutorial(tutorial, lang="de")` → `<name>.timings.de.json` (German voice
   durations; uses the `de:` entry of `ELEVENLABS_VOICE_IDS` with either backend).
3. `render_tutorial(..., lang="de")` → Cypress is paced by the German timings
   (`CYPRESS_TUTORIAL_LANG=de`), narration, captions and title cards are German.

CLI equivalents: `translate_tutorial.py --template/--from`, `author_tutorial.py
--lang de --from-timings`, `render_tutorial.py --lang de`. When the English line
of a step changes, the render warns `stale translation for step N`; re-run step 1
(the template keeps existing translations and flags stale ones).
```

- [ ] **Step 3: Commit**

```bash
git add tutorialctl.py mcp_servers/circuit_video/README.md circuit-mcp.md .agents/skills/circuit-video/SKILL.md mcp_servers/circuit_video/env.example
git commit -m "docs(circuit-video): multilingual tutorial workflow; tutorialctl --lang

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: End-to-end German render (manual, needs demo app + a narration backend)

- [ ] **Step 1:** In the MCP: `get_tutorial_text("support-tickets", "de")` → translate the 6 lines + title/outro into German → `save_tutorial_translation`. Check the file landed at `../circuitauction-backoffice/client/cypress/e2e-tutorials/release-3.5/support-tickets.i18n.de.json`.
- [ ] **Step 2:** `author_tutorial("support-tickets", "de")` → `support-tickets.timings.de.json`; durations should be ~15–30 % longer than the English ones.
- [ ] **Step 3:** `render_tutorial(base_url=…, tutorial="support-tickets", lang="de")` → watch the first 20 s: German voice, German captions, German title card; the manifest in `projects/<id>/` shows `"lang": "de"` on the steps (proves the German timings paced the capture).
- [ ] **Step 4:** Render the same tutorial without `lang` → unchanged English output (regression check).
- [ ] **Step 5:** Commit the two new sidecar files in the client repo.
