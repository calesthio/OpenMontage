"""Hunyuan 3D Rapid image-to-3D returns an OBJ plus a separate MTL and texture.

fal's documented result for ``fal-ai/hunyuan-3d/v3.1/rapid/image-to-3d`` has no
textured-GLB export: ``model_glb`` is really the OBJ, with ``material_mtl`` and
``texture`` beside it and the same three files repeated under ``model_urls``.
The OBJ's ``mtllib`` / ``map_Kd`` lines reference those companions by their
original file names, so they must land in the same directory under those names
or the mesh imports untextured.
"""

from __future__ import annotations

import json
from collections import Counter

from tools.graphics import fal_3d
from tools.graphics.fal_3d import Fal3D


class _Response:
    def __init__(self, payload=None, content=b""):
        self._payload = payload
        self.content = content

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


OBJ_URL = "https://cdn.example/out/model.obj"
MTL_URL = "https://cdn.example/out/material.mtl"
TEX_URL = "https://cdn.example/out/texture.png"
GLB_URL = "https://cdn.example/out/model.glb"

_BODIES = {
    OBJ_URL: b"mtllib material.mtl\nv 0 0 0\n",
    MTL_URL: b"newmtl mat\nmap_Kd texture.png\n",
    TEX_URL: b"png-bytes",
    GLB_URL: b"glb-bytes",
}


def _file(url: str, content_type: str) -> dict:
    return {
        "url": url,
        "content_type": content_type,
        "file_name": url.rsplit("/", 1)[-1],
        "file_size": len(_BODIES[url]),
    }


def _run(monkeypatch, result_payload: dict, output_path) -> tuple[object, Counter]:
    monkeypatch.setenv("FAL_KEY", "test-key")
    monkeypatch.setattr(fal_3d.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(fal_3d.requests, "post", lambda *args, **kwargs: _Response({
        "request_id": "req-obj",
        "status_url": "https://queue.example/status",
        "response_url": "https://queue.example/result",
    }))
    downloads: Counter = Counter()

    def fake_get(url, **_kwargs):
        if url.endswith("/status"):
            return _Response({"status": "COMPLETED"})
        if url.endswith("/result"):
            return _Response(result_payload)
        downloads[url] += 1
        return _Response(content=_BODIES[url])

    monkeypatch.setattr(fal_3d.requests, "get", fake_get)
    result = Fal3D().execute({
        "operation": "image_to_3d",
        "image_url": "https://images.example/concept.png",
        "output_path": str(output_path),
    })
    return result, downloads


def test_obj_result_downloads_mtl_and_texture_beside_the_mesh(monkeypatch, tmp_path):
    # Shaped like fal's documented output: the OBJ appears as model_glb AND model_urls.obj,
    # and the MTL/texture appear both at the top level and under model_urls.
    payload = {
        "model_glb": _file(OBJ_URL, "application/octet-stream"),
        "material_mtl": _file(MTL_URL, "application/octet-stream"),
        "texture": _file(TEX_URL, "image/png"),
        "model_urls": {
            "obj": _file(OBJ_URL, "application/octet-stream"),
            "mtl": _file(MTL_URL, "application/octet-stream"),
            "texture": _file(TEX_URL, "image/png"),
        },
    }
    asset_dir = tmp_path / "hero-lantern"
    result, downloads = _run(monkeypatch, payload, asset_dir / "hero-lantern.obj")
    assert result.success, result.error

    obj = asset_dir / "hero-lantern.obj"
    assert obj.read_bytes() == _BODIES[OBJ_URL]
    # Companions keep their original names, in the OBJ's directory, so mtllib/map_Kd resolve.
    assert (asset_dir / "material.mtl").read_bytes() == _BODIES[MTL_URL]
    assert (asset_dir / "texture.png").read_bytes() == _BODIES[TEX_URL]
    referenced_mtl = obj.read_text().split("mtllib ", 1)[1].split()[0]
    referenced_tex = (asset_dir / referenced_mtl).read_text().split("map_Kd ", 1)[1].split()[0]
    assert (asset_dir / referenced_tex).exists()

    # Each file fetched exactly once even though fal lists it twice.
    assert downloads == Counter({OBJ_URL: 1, MTL_URL: 1, TEX_URL: 1})

    provenance = json.loads((asset_dir / "hero-lantern.provenance.json").read_text(encoding="utf-8"))
    assert provenance["outputs"] == [str(obj), str(asset_dir / "material.mtl"), str(asset_dir / "texture.png")]
    assert result.data["outputs"] == provenance["outputs"]
    assert result.artifacts == provenance["outputs"] + [str(asset_dir / "hero-lantern.provenance.json")]


def test_glb_result_downloads_no_companions(monkeypatch, tmp_path):
    # A textured GLB embeds its materials; stray MTL/texture entries must not be fetched.
    payload = {
        "model_glb": _file(GLB_URL, "model/gltf-binary"),
        "texture": _file(TEX_URL, "image/png"),
        "model_urls": {
            "glb": _file(GLB_URL, "model/gltf-binary"),
            "texture": _file(TEX_URL, "image/png"),
        },
    }
    asset_dir = tmp_path / "hero-lantern"
    result, downloads = _run(monkeypatch, payload, asset_dir / "hero-lantern.glb")
    assert result.success, result.error

    assert (asset_dir / "hero-lantern.glb").read_bytes() == _BODIES[GLB_URL]
    assert downloads == Counter({GLB_URL: 1})
    assert sorted(p.name for p in asset_dir.iterdir()) == ["hero-lantern.glb", "hero-lantern.provenance.json"]
    assert result.data["outputs"] == [str(asset_dir / "hero-lantern.glb")]
