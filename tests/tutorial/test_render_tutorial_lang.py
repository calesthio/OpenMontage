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


def test_main_german_render_fails_before_capture_without_sidecar(tmp_path, monkeypatch, capsys):
    client = _client(tmp_path, False)
    monkeypatch.setattr(RT.bridge, "run_tutorial_spec",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("capture ran")))
    monkeypatch.setattr(RT, "parse_env_file", lambda path: {})
    monkeypatch.setattr(sys, "argv", [
        "render_tutorial.py", "--tutorial", "tour", "--client-dir", str(client),
        "--project-id", "p", "--base-url", "https://d.example.com", "--lang", "de",
        "--offline-narration",
    ])
    assert RT.main() == 2
    assert "translate_tutorial" in capsys.readouterr().err
