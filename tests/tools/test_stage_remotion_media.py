"""Focused tests for Remotion media staging key coverage.

`VideoCompose._stage_remotion_media` walks an edit-decision tree and copies
local media references into the Remotion public dir so they resolve via
``staticFile()``. These tests pin the set of cut keys that participate —
in particular the ``backgroundImage``/``backgroundVideo`` fields used by
scene types that render media behind the component.

No network, no browser: the staging logic is pure filesystem work.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.video.video_compose import VideoCompose


@pytest.fixture
def media_file(tmp_path: Path) -> Path:
    path = tmp_path / "bg.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    return path


def _stage(tree, public_dir):
    staged = VideoCompose._stage_remotion_media(tree, public_dir)
    return staged, tree


def test_background_image_is_staged(media_file, tmp_path):
    public_dir = tmp_path / "public"
    tree = {"type": "text_card", "backgroundImage": str(media_file)}
    staged, tree = _stage(tree, public_dir)

    assert staged == 1
    assert (public_dir / tree["backgroundImage"]).is_file()
    # Rewritten to a bare, staticFile()-relative name
    assert "/" not in tree["backgroundImage"]


def test_background_video_is_staged(media_file, tmp_path):
    public_dir = tmp_path / "public"
    tree = {"type": "callout", "backgroundVideo": "file://" + str(media_file)}
    staged, tree = _stage(tree, public_dir)

    assert staged == 1
    assert (public_dir / tree["backgroundVideo"]).is_file()


def test_same_source_staged_once_across_keys(media_file, tmp_path):
    public_dir = tmp_path / "public"
    tree = {
        "backgroundImage": str(media_file),
        "nested": [{"backgroundVideo": str(media_file)}],
    }
    staged, tree = _stage(tree, public_dir)

    assert staged == 1
    assert tree["backgroundImage"] == tree["nested"][0]["backgroundVideo"]


def test_non_media_keys_are_left_alone(media_file, tmp_path):
    public_dir = tmp_path / "public"
    tree = {"type": "text_card", "text": str(media_file)}
    staged, tree = _stage(tree, public_dir)

    assert staged == 0
    assert tree["text"] == str(media_file)
    assert not list(public_dir.glob("*")) if public_dir.exists() else True


def test_remote_urls_pass_through(tmp_path):
    public_dir = tmp_path / "public"
    url = "https://example.com/bg.png"
    tree = {"backgroundImage": url}
    staged, tree = _stage(tree, public_dir)

    assert staged == 0
    assert tree["backgroundImage"] == url


def test_missing_local_file_pass_through(tmp_path):
    public_dir = tmp_path / "public"
    missing = str(tmp_path / "does-not-exist.png")
    tree = {"backgroundImage": missing}
    staged, tree = _stage(tree, public_dir)

    assert staged == 0
    assert tree["backgroundImage"] == missing
