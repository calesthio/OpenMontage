"""Actual local Pillow rendering must retain every declared rendering input."""

import pytest
from PIL import Image

from tools.graphics.diagram_gen import DiagramGen


@pytest.mark.parametrize(
    "change",
    [
        {"width": 640},
        {"height": 480},
        {"theme": "light"},
        {"title": "Changed title"},
        {"connections": [{"from": 0, "to": 1, "label": "edge"}]},
    ],
)
def test_rendering_changes_match_uncached_producer(tmp_path, monkeypatch, change):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", "1")
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE_DIR", str(tmp_path / "cache"))
    request = {
        "diagram_type": "boxes",
        "boxes": [{"label": "Source"}, {"label": "Destination"}],
        "width": 400,
        "height": 300,
        "theme": "dark",
        "title": "Original title",
        "connections": [],
    }
    first = DiagramGen().execute({**request, "output_path": str(tmp_path / "first.png")})
    assert first.success, first.error
    changed = {**request, **change}
    actual_path = tmp_path / "changed.png"
    actual = DiagramGen().execute({**changed, "output_path": str(actual_path)})
    assert actual.success, actual.error
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", "0")
    oracle_path = tmp_path / "uncached.png"
    oracle = DiagramGen().execute({**changed, "output_path": str(oracle_path)})
    assert oracle.success, oracle.error
    with Image.open(actual_path) as rendered, Image.open(oracle_path) as expected:
        assert rendered.size == expected.size
        assert rendered.tobytes() == expected.tobytes()
    assert not actual.from_cache


def test_only_destination_changes_still_restore_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", "1")
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE_DIR", str(tmp_path / "cache"))
    request = {"diagram_type": "boxes", "boxes": [{"label": "Same"}], "width": 400}
    original = tmp_path / "original.png"
    first = DiagramGen().execute({**request, "output_path": str(original)})
    assert first.success, first.error
    restored = tmp_path / "restored.png"
    second = DiagramGen().execute({**request, "output_path": str(restored)})
    assert second.success, second.error
    assert second.from_cache is True
    assert restored.read_bytes() == original.read_bytes()
