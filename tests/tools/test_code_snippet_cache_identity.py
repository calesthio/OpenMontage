"""Cache-backed code cards must retain their supported presentation options."""

import pytest
from PIL import Image

from tools.graphics.code_snippet import CodeSnippet


@pytest.mark.parametrize(
    "change", [{"padding": 80}, {"line_numbers": False}, {"title": "Example.py"}]
)
def test_presentation_changes_match_uncached_producer(tmp_path, monkeypatch, change):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", "1")
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE_DIR", str(tmp_path / "cache"))
    request = {
        "code": "print('hello')\nprint('world')",
        "language": "python",
        "theme": "monokai",
        "font_size": 20,
        "padding": 40,
        "line_numbers": True,
    }
    first = CodeSnippet().execute({**request, "output_path": str(tmp_path / "first.png")})
    assert first.success, first.error
    changed = {**request, **change}
    actual_path = tmp_path / "changed.png"
    actual = CodeSnippet().execute({**changed, "output_path": str(actual_path)})
    assert actual.success, actual.error
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", "0")
    expected_path = tmp_path / "uncached.png"
    expected = CodeSnippet().execute({**changed, "output_path": str(expected_path)})
    assert expected.success, expected.error
    with Image.open(actual_path) as rendered, Image.open(expected_path) as oracle:
        assert rendered.size == oracle.size
        assert rendered.tobytes() == oracle.tobytes()
    assert not actual.from_cache


def test_code_card_destination_only_change_remains_cache_hit(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", "1")
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE_DIR", str(tmp_path / "cache"))
    first_path, second_path = tmp_path / "first.png", tmp_path / "second.png"
    request = {"code": "answer = 42", "title": "Answer.py", "padding": 50, "line_numbers": False}
    first = CodeSnippet().execute({**request, "output_path": str(first_path)})
    second = CodeSnippet().execute({**request, "output_path": str(second_path)})
    assert first.success and second.success
    assert second.from_cache
    assert first_path.read_bytes() == second_path.read_bytes()
