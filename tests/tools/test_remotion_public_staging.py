"""Remotion local-asset staging (verified live 2026-07-17).

The templated Remotion path converted absolute asset paths to file:// URIs.
That NEVER worked — proven by rendering real project assets:
  <Img>            → Chrome "Not allowed to load local resource"
  <OffthreadVideo> → its /proxy calls @remotion/renderer's readFile(), which
                     throws "Can only download URLs starting with http://"
Remotion has no file:// support at any slash count; local assets must be
served over http from the public dir via staticFile(). These tests pin the
staging contract so the file:// premise cannot creep back.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.video.video_compose import VideoCompose  # noqa: E402

COMPOSER_PUBLIC = PROJECT_ROOT / "remotion-composer" / "public" / "om-staged"


@pytest.fixture
def asset(tmp_path):
    p = tmp_path / "clip.mp4"
    p.write_bytes(b"fake-video-bytes")
    return p


def _cleanup(rewritten: str) -> None:
    if rewritten.startswith("om-staged/"):
        (COMPOSER_PUBLIC / rewritten.split("/", 1)[1]).unlink(missing_ok=True)


class TestStagePublicAssets:
    def test_absolute_path_becomes_public_relative(self, asset):
        props = {"cuts": [{"id": "c1", "source": str(asset)}]}
        _, staged = VideoCompose()._stage_public_assets(props)
        src = props["cuts"][0]["source"]
        try:
            assert staged == 1
            # The whole point: NOT a file:// URI.
            assert not src.startswith("file://")
            assert src.startswith("om-staged/")
            # staticFile() resolves this against the public dir, and the
            # staged entry must really exist there.
            assert (COMPOSER_PUBLIC / src.split("/", 1)[1]).exists()
        finally:
            _cleanup(src)

    def test_staged_entry_is_readable_by_a_plain_copy(self, asset):
        # Remotion BUNDLES public/ by copying it; symlinks did not survive
        # that copy (the staged names 404'd from inside the bundle), so the
        # entry must read as a real file — i.e. a hard link or a copy.
        props = {"cuts": [{"id": "c1", "source": str(asset)}]}
        VideoCompose()._stage_public_assets(props)
        src = props["cuts"][0]["source"]
        try:
            staged_path = COMPOSER_PUBLIC / src.split("/", 1)[1]
            assert staged_path.read_bytes() == b"fake-video-bytes"
            assert not staged_path.is_symlink(), (
                "symlinked staging does not survive Remotion's public-dir copy"
            )
        finally:
            _cleanup(src)

    def test_file_uri_input_is_also_staged(self, asset):
        props = {"cuts": [{"id": "c1", "source": f"file://{asset}"}]}
        VideoCompose()._stage_public_assets(props)
        src = props["cuts"][0]["source"]
        try:
            assert src.startswith("om-staged/")
        finally:
            _cleanup(src)

    def test_remote_and_data_urls_untouched(self):
        props = {"cuts": [
            {"id": "a", "source": "https://cdn.example/x.mp4"},
            {"id": "b", "source": "data:image/png;base64,AAAA"},
        ]}
        _, staged = VideoCompose()._stage_public_assets(props)
        assert staged == 0
        assert props["cuts"][0]["source"] == "https://cdn.example/x.mp4"
        assert props["cuts"][1]["source"] == "data:image/png;base64,AAAA"

    def test_public_relative_paths_untouched(self):
        # The convention the one working Remotion project already used.
        props = {"cuts": [{"id": "a", "source": "projects/xiaotuzi/video/a.mp4"}]}
        _, staged = VideoCompose()._stage_public_assets(props)
        assert staged == 0
        assert props["cuts"][0]["source"] == "projects/xiaotuzi/video/a.mp4"

    def test_missing_file_left_alone(self, tmp_path):
        # Not this function's job to fail — the renderer reports it with
        # better context.
        props = {"cuts": [{"id": "a", "source": str(tmp_path / "nope.mp4")}]}
        _, staged = VideoCompose()._stage_public_assets(props)
        assert staged == 0

    def test_every_asset_bearing_field_is_staged(self, asset, tmp_path):
        img = tmp_path / "bg.png"
        img.write_bytes(b"png")
        audio = tmp_path / "vo.mp3"
        audio.write_bytes(b"mp3")
        props = {
            "cuts": [{
                "id": "c1",
                "source": str(asset),
                "backgroundImage": str(img),
                "backgroundVideo": str(asset),
                "images": [str(img)],
            }],
            "scenes": [{"id": "s1", "src": str(asset), "backgroundSrc": str(img)}],
            "audio": {"narration": {"src": str(audio)}, "music": {"src": str(audio)}},
            "music": {"src": str(audio)},
            "videoSrc": str(asset),
        }
        VideoCompose()._stage_public_assets(props)
        cut = props["cuts"][0]
        rewritten = [
            cut["source"], cut["backgroundImage"], cut["backgroundVideo"],
            cut["images"][0], props["scenes"][0]["src"],
            props["scenes"][0]["backgroundSrc"],
            props["audio"]["narration"]["src"], props["audio"]["music"]["src"],
            props["music"]["src"], props["videoSrc"],
        ]
        try:
            for value in rewritten:
                assert value.startswith("om-staged/"), value
        finally:
            for value in rewritten:
                _cleanup(value)

    def test_same_source_reuses_one_staged_entry(self, asset):
        # Content-addressed by path → stable across cuts AND re-renders.
        props = {"cuts": [
            {"id": "a", "source": str(asset)},
            {"id": "b", "source": str(asset)},
        ]}
        VideoCompose()._stage_public_assets(props)
        try:
            assert props["cuts"][0]["source"] == props["cuts"][1]["source"]
        finally:
            _cleanup(props["cuts"][0]["source"])

    def test_captions_and_text_are_never_mangled(self, asset):
        # Traversal is an explicit key list, not "anything that looks like a
        # path" — a caption word must survive untouched.
        props = {
            "cuts": [{"id": "c1", "source": str(asset), "text": "/not/a/real/path"}],
            "captions": [{"word": "/usr/bin", "startMs": 0, "endMs": 100}],
        }
        VideoCompose()._stage_public_assets(props)
        try:
            assert props["cuts"][0]["text"] == "/not/a/real/path"
            assert props["captions"][0]["word"] == "/usr/bin"
        finally:
            _cleanup(props["cuts"][0]["source"])
