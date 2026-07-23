"""The renderer, not the agent, binds publish evidence to output bytes."""

import hashlib
from pathlib import Path

from tools.video.video_compose import VideoCompose


def test_render_evidence_contains_exact_hash_size_and_producer(tmp_path):
    render = tmp_path / "final.mp4"
    render.write_bytes(b"rendered-by-video-compose")

    evidence = VideoCompose._build_render_evidence(render)

    assert evidence == {
        "path": str(render.resolve()),
        "sha256": hashlib.sha256(render.read_bytes()).hexdigest(),
        "file_size_bytes": render.stat().st_size,
        "metadata": {"producer_tool": "video_compose", "operation": "render"},
    }


def test_render_evidence_hashes_large_outputs_without_reading_whole_file(
    tmp_path, monkeypatch
):
    render = tmp_path / "large.mp4"
    payload = b"video-chunk" * 200_000
    render.write_bytes(payload)

    def reject_read_bytes(_path: Path) -> bytes:
        raise AssertionError("render evidence must stream the file")

    monkeypatch.setattr(Path, "read_bytes", reject_read_bytes)

    evidence = VideoCompose._build_render_evidence(render)

    assert evidence["sha256"] == hashlib.sha256(payload).hexdigest()
