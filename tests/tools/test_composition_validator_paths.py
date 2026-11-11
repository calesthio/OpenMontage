"""composition_validator must accept the media paths video_compose renders.

Found by the 2026-11-11 end-to-end audit run (animation pipeline): the compose
director validates the Remotion composition with
``assets_root="remotion-composer/public"``. The composition named its narration
by its repo-relative project path. ``video_compose`` stages any existing local
file named by ``source``/``src`` into the render's public dir
(``_stage_remotion_media``), so that render succeeds, but the validator joined
the path onto the public dir and reported "Missing narration audio".
"""

import json
import wave
from pathlib import Path

from tools.analysis.composition_validator import CompositionValidator


def _silent_wav(path: Path, seconds: float = 1.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"\x00\x00" * int(8000 * seconds))


def _composition(tmp_path: Path, narration_src: str, image_src: str) -> Path:
    comp = {
        "render_runtime": "remotion",
        "cuts": [
            {"id": "c1", "source": image_src, "in_seconds": 0, "out_seconds": 2},
            {"id": "c2", "source": "", "type": "text_card", "text": "hi", "in_seconds": 2, "out_seconds": 3},
        ],
        "audio": {"narration": {"src": narration_src}},
    }
    path = tmp_path / "projects" / "p" / "artifacts" / "remotion_composition.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(comp), encoding="utf-8")
    return path


def test_remotion_accepts_existing_repo_relative_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    public = tmp_path / "remotion-composer" / "public"
    public.mkdir(parents=True)
    _silent_wav(tmp_path / "projects" / "p" / "assets" / "audio" / "narration.wav")
    image = tmp_path / "projects" / "p" / "assets" / "images" / "a.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"png")
    comp_path = _composition(
        tmp_path, "projects/p/assets/audio/narration.wav", "projects/p/assets/images/a.png"
    )

    result = CompositionValidator().execute(
        {"composition_path": str(comp_path), "assets_root": str(public)}
    )

    assert result.data["errors"] == []
    assert result.data["valid"] is True


def test_remotion_still_reports_files_that_exist_nowhere(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    public = tmp_path / "remotion-composer" / "public"
    public.mkdir(parents=True)
    comp_path = _composition(tmp_path, "projects/p/missing.wav", "projects/p/missing.png")

    result = CompositionValidator().execute(
        {"composition_path": str(comp_path), "assets_root": str(public)}
    )

    assert result.data["valid"] is False
    assert any("Missing narration audio" in e for e in result.data["errors"])
    assert any("Missing asset" in e for e in result.data["errors"])


def test_public_relative_paths_still_resolve_against_assets_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    public = tmp_path / "remotion-composer" / "public"
    _silent_wav(public / "proj" / "narration.wav")
    (public / "proj" / "a.png").write_bytes(b"png")
    comp_path = _composition(tmp_path, "proj/narration.wav", "proj/a.png")

    result = CompositionValidator().execute(
        {"composition_path": str(comp_path), "assets_root": str(public)}
    )

    assert result.data["errors"] == []
