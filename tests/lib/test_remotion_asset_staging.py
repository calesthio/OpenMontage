"""Unit tests for Remotion public/ asset staging."""

from __future__ import annotations

from pathlib import Path

from lib.remotion_asset_staging import (
    _parse_file_uri,
    derive_staging_slug,
    stage_local_assets_for_remotion,
)


def test_derive_staging_slug_from_projects_path(tmp_path):
    out = tmp_path / "projects" / "assamese-journey" / "renders" / "final.mp4"
    out.parent.mkdir(parents=True)
    assert derive_staging_slug(out, {}) == "assamese-journey"


def test_derive_staging_slug_from_metadata():
    out = Path("/tmp/out.mp4")
    data = {"metadata": {"project_id": "my-story"}}
    assert derive_staging_slug(out, data) == "my-story"


def test_stage_rewrites_absolute_paths(tmp_path):
    public = tmp_path / "public"
    img = tmp_path / "photo.jpg"
    audio = tmp_path / "narration.mp3"
    img.write_bytes(b"\xff\xd8\xff")
    audio.write_bytes(b"ID3")

    props = {
        "cuts": [{"id": "c1", "source": str(img)}],
        "audio": {
            "narration": {"src": str(audio), "volume": 1.0},
            "music": {"src": str(audio), "volume": 0.1},
        },
    }

    report = stage_local_assets_for_remotion(
        props,
        public_dir=public,
        project_slug="demo-project",
    )

    assert props["cuts"][0]["source"] == "demo-project/photo.jpg"
    assert props["audio"]["narration"]["src"] == "demo-project/narration.mp3"
    assert props["audio"]["music"]["src"] == "demo-project/narration.mp3"
    assert (public / "demo-project" / "photo.jpg").exists()
    assert (public / "demo-project" / "narration.mp3").exists()
    assert len(report["staged"]) == 3
    assert report["skipped"] == []


def test_stage_leaves_https_unchanged(tmp_path):
    public = tmp_path / "public"
    props = {
        "cuts": [
            {
                "id": "c1",
                "source": "https://example.com/image.jpg",
            }
        ],
    }

    report = stage_local_assets_for_remotion(
        props,
        public_dir=public,
        project_slug="demo-project",
    )

    assert props["cuts"][0]["source"] == "https://example.com/image.jpg"
    assert report["skipped"][0]["reason"] == "remote"
    assert not (public / "demo-project").exists()


def test_stage_leaves_existing_public_relative_paths(tmp_path):
    public = tmp_path / "public"
    props = {
        "cuts": [{"id": "c1", "source": "demo-project/already-staged.jpg"}],
        "audio": {"narration": {"src": "demo-project/narration.mp3"}},
    }

    report = stage_local_assets_for_remotion(
        props,
        public_dir=public,
        project_slug="demo-project",
    )

    assert props["cuts"][0]["source"] == "demo-project/already-staged.jpg"
    assert props["audio"]["narration"]["src"] == "demo-project/narration.mp3"
    assert all(s["reason"] == "not_local_or_missing" for s in report["skipped"])


def test_stage_file_uri_naive_concat(tmp_path):
    """Regression: f'file://{path}' on Windows produces file://C:\\... .

    The old strip-and-prepend-/ logic treated that as a POSIX-rooted path and
    skipped staging. This is the failure CI hit on Windows.
    """
    public = tmp_path / "public"
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"ID3")

    props = {
        "audio": {"narration": {"src": f"file://{audio}"}},
    }

    stage_local_assets_for_remotion(
        props,
        public_dir=public,
        project_slug="uri-project",
    )

    assert props["audio"]["narration"]["src"] == "uri-project/voice.mp3"
    assert (public / "uri-project" / "voice.mp3").exists()


def test_stage_file_uri_pathlib_as_uri(tmp_path):
    """Path.as_uri() produces file:///... on POSIX and file:///C:/... on Windows."""
    public = tmp_path / "public"
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"ID3")

    props = {
        "audio": {"narration": {"src": audio.resolve().as_uri()}},
    }

    stage_local_assets_for_remotion(
        props,
        public_dir=public,
        project_slug="uri-project",
    )

    assert props["audio"]["narration"]["src"] == "uri-project/voice.mp3"
    assert (public / "uri-project" / "voice.mp3").exists()


def test_parse_file_uri_posix_form():
    parsed = _parse_file_uri("file:///Users/me/projects/voice.mp3")
    assert parsed is not None
    assert parsed.name == "voice.mp3"


def test_parse_file_uri_windows_drive_triple_slash():
    """file:///C:/Users/me/voice.mp3 — RFC-style Windows drive URI."""
    parsed = _parse_file_uri("file:///C:/Users/me/voice.mp3")
    assert parsed is not None
    assert parsed.name == "voice.mp3"
    text = str(parsed)
    assert text.startswith("C:")
    assert "Users" in parsed.parts
    # Must NOT stay POSIX-rooted /C:/...
    assert not text.startswith("/C:")


def test_parse_file_uri_windows_drive_as_authority():
    """file://C:/Users/me/voice.mp3 — drive letter in netloc."""
    parsed = _parse_file_uri("file://C:/Users/me/voice.mp3")
    assert parsed is not None
    assert parsed.name == "voice.mp3"
    assert str(parsed).startswith("C:")


def test_parse_file_uri_windows_naive_backslashes():
    """file://C:\\Users\\me\\voice.mp3 — produced by f'file://{Path}' on Windows."""
    parsed = _parse_file_uri(r"file://C:\Users\me\voice.mp3")
    assert parsed is not None
    assert parsed.name == "voice.mp3"
    text = str(parsed)
    assert text.startswith("C:")
    # Must NOT be POSIX-rooted /C:\...
    assert not text.startswith("/C:")
    assert not text.startswith("/C:\\")


def test_stage_disambiguates_basename_collision(tmp_path):
    public = tmp_path / "public"
    a_dir = tmp_path / "a"
    b_dir = tmp_path / "b"
    a_dir.mkdir()
    b_dir.mkdir()
    first = a_dir / "clip.jpg"
    second = b_dir / "clip.jpg"
    first.write_bytes(b"a")
    second.write_bytes(b"b")

    props = {
        "cuts": [
            {"id": "c1", "source": str(first)},
            {"id": "c2", "source": str(second)},
        ],
    }

    stage_local_assets_for_remotion(
        props,
        public_dir=public,
        project_slug="collision",
    )

    assert props["cuts"][0]["source"] == "collision/clip.jpg"
    assert props["cuts"][1]["source"] != props["cuts"][0]["source"]
    assert props["cuts"][1]["source"].startswith("collision/clip_")
