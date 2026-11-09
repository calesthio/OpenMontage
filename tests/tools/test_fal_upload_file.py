"""Contracts for the generic fal.ai storage upload in tools/video/_shared.py.

`upload_file_fal` infers the MIME type from the extension (meshes, archives and media as
well as images); `upload_image_fal` delegates to it and keeps its image/png default.
"""

from __future__ import annotations

from typing import Any

import pytest
import requests

from tools.video import _shared
from tools.video._shared import upload_file_fal, upload_image_fal


class _Response:
    def __init__(self, payload: Any = None):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


@pytest.fixture()
def transport(monkeypatch) -> dict[str, Any]:
    """Fake the initiate (POST) and content (PUT) calls; record what was sent."""
    monkeypatch.setenv("FAL_KEY", "test-key")
    calls: dict[str, Any] = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["initiate"] = {"url": url, "headers": headers, "json": json, "timeout": timeout}
        return _Response({"upload_url": "https://upload.example/put/1", "file_url": "https://cdn.example/stored/1"})

    def fake_put(url, headers=None, data=None, timeout=None):
        calls["put"] = {"url": url, "headers": headers, "data": data, "timeout": timeout}
        return _Response()

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "put", fake_put)
    return calls


@pytest.mark.parametrize(
    ("file_name", "expected"),
    [
        ("hero.glb", "model/gltf-binary"),
        ("HERO.GLB", "model/gltf-binary"),
        ("hero.gltf", "model/gltf+json"),
        ("hero.fbx", "application/octet-stream"),
        ("hero.obj", "model/obj"),
        ("bundle.zip", "application/zip"),
        ("clip.mp4", "video/mp4"),
        ("voice.wav", "audio/wav"),
        ("frame.png", "image/png"),
        ("frame.jpg", "image/jpeg"),
        ("mystery.xyz", "application/octet-stream"),
        ("no_extension", "application/octet-stream"),
    ],
)
def test_upload_file_infers_content_type_from_extension(transport, tmp_path, file_name, expected):
    path = tmp_path / file_name
    path.write_bytes(b"payload")
    url = upload_file_fal(str(path))
    assert url == "https://cdn.example/stored/1"
    assert transport["initiate"]["json"] == {"content_type": expected, "file_name": file_name}
    assert transport["put"]["headers"] == {"Content-Type": expected}


def test_upload_file_sends_key_and_bytes(transport, tmp_path):
    path = tmp_path / "hero.glb"
    path.write_bytes(b"\x00glb-bytes")
    upload_file_fal(str(path))
    assert transport["initiate"]["url"] == "https://rest.alpha.fal.ai/storage/upload/initiate"
    assert transport["initiate"]["headers"]["Authorization"] == "Key test-key"
    assert transport["put"]["url"] == "https://upload.example/put/1"
    assert transport["put"]["data"] == b"\x00glb-bytes"
    assert transport["put"]["timeout"] >= 300  # textured meshes run to tens of MB


def test_explicit_content_type_overrides_inference(transport, tmp_path):
    path = tmp_path / "rig.bin"
    path.write_bytes(b"fbx")
    upload_file_fal(str(path), content_type="model/fbx")
    assert transport["initiate"]["json"]["content_type"] == "model/fbx"
    assert transport["put"]["headers"] == {"Content-Type": "model/fbx"}


def test_upload_file_requires_key(monkeypatch, tmp_path):
    monkeypatch.delenv("FAL_KEY", raising=False)
    monkeypatch.delenv("FAL_AI_API_KEY", raising=False)
    monkeypatch.setattr(requests, "post", lambda *a, **k: pytest.fail("must not call fal without a key"))
    path = tmp_path / "hero.glb"
    path.write_bytes(b"glb")
    with pytest.raises(RuntimeError, match="FAL_KEY"):
        upload_file_fal(str(path))


def test_upload_file_accepts_alias_key(monkeypatch, transport, tmp_path):
    monkeypatch.delenv("FAL_KEY", raising=False)
    monkeypatch.setenv("FAL_AI_API_KEY", "alias-key")
    path = tmp_path / "hero.glb"
    path.write_bytes(b"glb")
    upload_file_fal(str(path))
    assert transport["initiate"]["headers"]["Authorization"] == "Key alias-key"


def test_upload_file_missing_path(transport, tmp_path):
    with pytest.raises(FileNotFoundError):
        upload_file_fal(str(tmp_path / "missing.glb"))
    assert "initiate" not in transport


@pytest.mark.parametrize(
    ("file_name", "expected"),
    [
        ("frame.png", "image/png"),
        ("frame.jpeg", "image/jpeg"),
        ("frame.webp", "image/webp"),
        ("frame.unknown", "image/png"),  # image helper keeps its historical default
    ],
)
def test_upload_image_delegates_with_image_default(transport, tmp_path, file_name, expected):
    path = tmp_path / file_name
    path.write_bytes(b"img")
    assert upload_image_fal(str(path)) == "https://cdn.example/stored/1"
    assert transport["put"]["headers"] == {"Content-Type": expected}


def test_upload_image_goes_through_upload_file(monkeypatch, tmp_path):
    seen: list[tuple[str, str | None]] = []
    monkeypatch.setattr(_shared, "upload_file_fal", lambda p, ct=None: seen.append((p, ct)) or "https://cdn.example/x")
    path = tmp_path / "frame.png"
    path.write_bytes(b"img")
    assert upload_image_fal(str(path)) == "https://cdn.example/x"
    assert seen == [(str(path), "image/png")]


def test_upload_image_missing_path(transport, tmp_path):
    with pytest.raises(FileNotFoundError, match="Image not found"):
        upload_image_fal(str(tmp_path / "missing.png"))
