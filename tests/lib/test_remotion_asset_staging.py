"""Unit tests for Remotion public/ asset staging."""

from __future__ import annotations

from pathlib import Path

import pytest

from lib.remotion_asset_staging import (
    _parse_file_uri,
    _sanitize_slug,
    cleanup_staging_dir,
    derive_staging_slug,
    ensure_contained,
    resolve_project_public_dir,
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


def test_sanitize_slug_rejects_dot_segments():
    assert _sanitize_slug(".") == "remotion-staged"
    assert _sanitize_slug("..") == "remotion-staged"
    assert _sanitize_slug("...") == "remotion-staged"
    assert _sanitize_slug("./..") == "remotion-staged"
    # Dots stripped / replaced — never path traversal
    assert ".." not in _sanitize_slug("foo..bar")
    assert _sanitize_slug("my.project") == "my-project"
    assert _sanitize_slug("safe-slug_1") == "safe-slug_1"


def test_sanitize_slug_blocks_metadata_traversal_into_public(tmp_path):
    """Regression: project_slug='..' must not stage into public/.. (escape)."""
    public = tmp_path / "public"
    public.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("nope")

    props = {
        "metadata": {"project_id": ".."},
        "cuts": [{"id": "c1", "source": str(outside)}],
    }
    slug = derive_staging_slug(tmp_path / "out.mp4", props)
    assert slug == "remotion-staged"

    report = stage_local_assets_for_remotion(
        props,
        public_dir=public,
        project_slug=slug,
    )
    dest = public / "secret.txt"
    assert dest.exists()
    assert ensure_contained(dest, public) == dest.resolve()
    # Must not have written into tmp_path parent via ..
    assert not (tmp_path.parent / "secret.txt").exists() or (
        tmp_path.parent / "secret.txt"
    ).resolve() != dest.resolve()
    assert report["public_dir"] == str(public.resolve())


def test_ensure_contained_rejects_escape(tmp_path):
    root = tmp_path / "public"
    root.mkdir()
    with pytest.raises(ValueError, match="escapes root"):
        ensure_contained(tmp_path / "outside.txt", root)


def test_resolve_project_public_dir_under_projects(tmp_path):
    out = tmp_path / "projects" / "demo" / "renders" / "final.mp4"
    out.parent.mkdir(parents=True)
    public = resolve_project_public_dir(out, {})
    assert public == tmp_path / "projects" / "demo" / "remotion-public"
    assert public.name == "remotion-public"


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

    assert props["cuts"][0]["source"] == "photo.jpg"
    assert props["audio"]["narration"]["src"] == "narration.mp3"
    assert props["audio"]["music"]["src"] == "narration.mp3"
    assert (public / "photo.jpg").exists()
    assert (public / "narration.mp3").exists()
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
    assert list(public.iterdir()) == [] if public.exists() else True


def test_stage_leaves_existing_public_relative_paths(tmp_path):
    public = tmp_path / "public"
    props = {
        "cuts": [{"id": "c1", "source": "already-staged.jpg"}],
        "audio": {"narration": {"src": "narration.mp3"}},
    }

    report = stage_local_assets_for_remotion(
        props,
        public_dir=public,
        project_slug="demo-project",
    )

    assert props["cuts"][0]["source"] == "already-staged.jpg"
    assert props["audio"]["narration"]["src"] == "narration.mp3"
    assert all(s["reason"] == "not_local_or_missing" for s in report["skipped"])


def test_stage_file_uri_naive_concat(tmp_path):
    """Regression: f'file://{path}' on Windows produces file://C:\\... ."""
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

    assert props["audio"]["narration"]["src"] == "voice.mp3"
    assert (public / "voice.mp3").exists()


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

    assert props["audio"]["narration"]["src"] == "voice.mp3"
    assert (public / "voice.mp3").exists()


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

    assert props["cuts"][0]["source"] == "clip.jpg"
    assert props["cuts"][1]["source"] != props["cuts"][0]["source"]
    assert props["cuts"][1]["source"].startswith("clip_")


def test_cleanup_staging_dir_only_named_contract(tmp_path):
    safe = tmp_path / "remotion-public"
    safe.mkdir()
    (safe / "a.mp3").write_bytes(b"x")
    other = tmp_path / "not-staging"
    other.mkdir()
    (other / "keep.txt").write_text("keep")

    cleanup_staging_dir(safe)
    cleanup_staging_dir(other)

    assert not safe.exists()
    assert other.exists()
    assert (other / "keep.txt").exists()
