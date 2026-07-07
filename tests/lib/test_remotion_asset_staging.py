"""Unit tests for Remotion public/ asset staging."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.remotion_asset_staging import (
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


def test_stage_file_uri_paths(tmp_path):
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
