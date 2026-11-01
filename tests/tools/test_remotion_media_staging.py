"""Regression coverage for Remotion media staging (`_stage_remotion_media`).

Two defects this locks down:

1. ``file://C:\\Users\\...`` — the naive ``f"file://{path}"`` form Windows
   tooling produces — parsed as a UNC authority and never resolved, so the
   asset was silently skipped.
2. ``--public-dir`` REPLACES Remotion's default public dir, so assets staged
   into ``remotion-composer/public/`` by earlier pipeline stages 404 once a
   render points at its own staging dir.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.video.video_compose import VideoCompose


# --- file:// URI parsing ---------------------------------------------------
# Parsing is asserted on the string form (not the filesystem) so the Windows
# cases are meaningful when the suite runs on POSIX.

@pytest.mark.parametrize(
    ("label", "uri", "expected"),
    [
        ("posix", "file:///Users/me/voice.mp3", "/Users/me/voice.mp3"),
        ("windows_rfc", "file:///C:/Users/me/voice.mp3", "C:/Users/me/voice.mp3"),
        ("windows_authority", "file://C:/Users/me/voice.mp3", "C:/Users/me/voice.mp3"),
        # The regression: no slash after the scheme, so urlsplit puts the whole
        # drive path in netloc and leaves path empty.
        ("windows_naive", "file://C:\\Users\\me\\voice.mp3", "C:\\Users\\me\\voice.mp3"),
        ("percent_encoded", "file:///Users/me/my%20voice.mp3", "/Users/me/my voice.mp3"),
        ("localhost", "file://localhost/Users/me/voice.mp3", "/Users/me/voice.mp3"),
    ],
)
def test_file_uri_to_raw_path(label, uri, expected):
    assert VideoCompose._file_uri_to_raw_path(uri) == expected


def test_unc_authority_still_treated_as_network_path():
    """A genuine UNC host must not be mistaken for a drive path."""
    assert (
        VideoCompose._file_uri_to_raw_path("file://server/share/voice.mp3")
        == "//server/share/voice.mp3"
    )


def test_stage_resolves_bare_concat_file_uri(tmp_path):
    """End-to-end: a bare f"file://{path}" concat round-trips through staging.

    On POSIX this exercises the ``file:///...`` shape, which already worked —
    the Windows drive forms cannot be exercised end-to-end off Windows because
    the path has to exist on disk. Parsing for those is asserted directly in
    ``test_file_uri_to_raw_path`` above; this covers the copy/rewrite half.
    """
    src = tmp_path / "voice.mp3"
    src.write_bytes(b"ID3")
    public_dir = tmp_path / "public"

    # Simulate the naive f"file://{path}" concat using the real temp path.
    props = {"audio": {"narration": {"src": f"file://{src}"}}}
    staged = VideoCompose._stage_remotion_media(props, public_dir)

    assert staged == 1
    rewritten = props["audio"]["narration"]["src"]
    assert not rewritten.startswith("file://")
    assert (public_dir / rewritten).is_file()


# --- public/ mirroring -----------------------------------------------------

def test_mirror_public_dir_exposes_prestaged_assets(tmp_path):
    """anime_scene.images[] / screenshot_scene.backgroundImage are staticFile()
    refs resolved against the real public/ dir and staged there by the
    asset-director stage — not by _stage_remotion_media. They must survive a
    render that overrides --public-dir.
    """
    composer_public = tmp_path / "remotion-composer" / "public"
    (composer_public / "demo-project").mkdir(parents=True)
    (composer_public / "demo-project" / "scene1-a.png").write_bytes(b"\x89PNG")
    (composer_public / "logo.svg").write_bytes(b"<svg/>")

    staging = tmp_path / "renders" / ".remotion-public-final"
    VideoCompose._mirror_public_dir(composer_public, staging)

    mirrored = staging / "demo-project" / "scene1-a.png"
    assert mirrored.is_file()
    assert mirrored.read_bytes() == b"\x89PNG"
    assert (staging / "logo.svg").is_file()


def test_mirror_never_clobbers_staged_media(tmp_path):
    """Staged render media wins over a same-named entry in public/."""
    composer_public = tmp_path / "public"
    composer_public.mkdir()
    (composer_public / "voice.mp3").write_bytes(b"FROM_PUBLIC")

    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "voice.mp3").write_bytes(b"FROM_RENDER")

    VideoCompose._mirror_public_dir(composer_public, staging)

    assert (staging / "voice.mp3").read_bytes() == b"FROM_RENDER"


def test_mirror_is_read_only_toward_source(tmp_path):
    """Cleanup deletes the staging dir; the real public/ must survive."""
    import shutil

    composer_public = tmp_path / "public"
    (composer_public / "assets").mkdir(parents=True)
    (composer_public / "assets" / "keep.png").write_bytes(b"\x89PNG")

    staging = tmp_path / "staging"
    VideoCompose._mirror_public_dir(composer_public, staging)
    # Mirrors what _remotion_render's finally block does.
    shutil.rmtree(staging, ignore_errors=True)

    assert (composer_public / "assets" / "keep.png").is_file()


def test_mirror_missing_source_is_noop(tmp_path):
    staging = tmp_path / "staging"
    VideoCompose._mirror_public_dir(tmp_path / "does-not-exist", staging)
    assert not staging.exists()
