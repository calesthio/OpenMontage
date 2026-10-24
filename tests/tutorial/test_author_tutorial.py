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
                  {"index": 1, "source": "Bye.", "narration": "Tschüss."}]}), encoding="utf-8")
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
