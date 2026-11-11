"""Re-scaffolding a workspace refreshes assets that changed at the same size.

The scaffold skipped a copy when the staged file had the same byte size as
the source. A character composition re-rendered for another profile only
swaps "1920" and "1080", so the stale landscape copy was rendered into a
vertical canvas.
"""

from __future__ import annotations

import os
from pathlib import Path

from tools.video.hyperframes_compose import HyperFramesCompose


def _scaffold(workspace: Path, assets: list[dict], cuts: list[dict], audio: dict | None = None):
    result = HyperFramesCompose().execute(
        {
            "operation": "scaffold_workspace",
            "workspace_path": str(workspace),
            "edit_decisions": {
                "version": "1.0",
                "render_runtime": "hyperframes",
                "cuts": cuts,
                **({"audio": audio} if audio else {}),
            },
            "asset_manifest": {"assets": assets},
        }
    )
    assert result.success, result.error
    return result


def _rewrite_same_size(path: Path, old: str, new: str) -> None:
    before = path.stat()
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace(old, new), encoding="utf-8")
    assert path.stat().st_size == before.st_size
    # A later edit has a later mtime; make that explicit so the test does
    # not depend on the filesystem's timestamp resolution.
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 5_000_000_000))


def test_changed_cut_asset_of_equal_size_is_restaged(tmp_path):
    source = tmp_path / "src" / "scene.html"
    source.parent.mkdir()
    source.write_text('<template><div data-width="1920" data-height="1080"></div></template>\n', encoding="utf-8")
    workspace = tmp_path / "hf"
    assets = [{"id": "scene", "type": "animation", "path": str(source)}]
    cuts = [{"id": "c1", "source": "scene", "in_seconds": 0, "out_seconds": 2}]

    _scaffold(workspace, assets, cuts)
    _rewrite_same_size(source, 'data-width="1920" data-height="1080"', 'data-width="1080" data-height="1920"')
    _scaffold(workspace, assets, cuts)

    assert (workspace / "assets" / "scene.html").read_text(encoding="utf-8") == source.read_text(encoding="utf-8")


def test_changed_audio_of_equal_size_is_restaged(tmp_path):
    narration = tmp_path / "src" / "voice.wav"
    music = tmp_path / "src" / "bed.wav"
    narration.parent.mkdir()
    narration.write_text("voice-take-1\n", encoding="utf-8")
    music.write_text("music-take-1\n", encoding="utf-8")
    workspace = tmp_path / "hf"
    assets = [
        {"id": "voice", "type": "audio", "path": str(narration)},
        {"id": "bed", "type": "music", "path": str(music)},
    ]
    cuts = [{"id": "c1", "type": "text_card", "text": "Hi", "in_seconds": 0, "out_seconds": 2}]
    audio = {
        "narration": {"segments": [{"asset_id": "voice", "start_seconds": 0, "end_seconds": 2}]},
        "music": {"asset_id": "bed", "volume": 0.2},
    }

    _scaffold(workspace, assets, cuts, audio)
    _rewrite_same_size(narration, "take-1", "take-2")
    _rewrite_same_size(music, "take-1", "take-2")
    _scaffold(workspace, assets, cuts, audio)

    assert (workspace / "assets" / "voice.wav").read_text(encoding="utf-8") == "voice-take-2\n"
    assert (workspace / "assets" / "bed.wav").read_text(encoding="utf-8") == "music-take-2\n"


def test_unchanged_asset_is_not_copied_again(tmp_path):
    source = tmp_path / "src" / "still.png"
    source.parent.mkdir()
    source.write_bytes(b"\x89PNG fake")
    workspace = tmp_path / "hf"
    assets = [{"id": "still", "type": "image", "path": str(source)}]
    cuts = [{"id": "c1", "source": "still", "in_seconds": 0, "out_seconds": 2}]

    _scaffold(workspace, assets, cuts)
    staged = workspace / "assets" / "still.png"
    first = staged.stat().st_ino, staged.stat().st_mtime_ns
    _scaffold(workspace, assets, cuts)
    assert (staged.stat().st_ino, staged.stat().st_mtime_ns) == first
