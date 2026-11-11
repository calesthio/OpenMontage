"""three.js for the Three.js world comes from a local npm install.

The world runtime imported GLTFLoader from the CDN without an import map, so
its bare `import ... from 'three'` never resolved and the 3D world was never
built. The workspace now gets an import map for `three` and `three/addons/`,
pointing at a copy of the pinned npm install (or the pinned CDN without one).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import tools.three_runtime as three_runtime
from tools.three_runtime import THREE_CDN_ROOT, THREE_VERSION, stage_three

REPO_ROOT = Path(__file__).resolve().parents[2]

FAKE_TREE = {
    "build/three.module.js": "import { A } from './three.core.js';\nexport { A };\n",
    "build/three.core.js": "export const A = 1;\n",
    "build/three.webgpu.js": "export const unused = 1;\n",
    "examples/jsm/loaders/GLTFLoader.js": (
        "import { A } from 'three';\n"
        "import { toTrianglesDrawMode } from '../utils/BufferGeometryUtils.js';\n"
        "// resource '../textures/texture.png' will be loaded from the model URL\n"
        "export class GLTFLoader {}\n"
    ),
    "examples/jsm/utils/BufferGeometryUtils.js": "import { A } from 'three';\nexport function toTrianglesDrawMode() {}\n",
    "examples/jsm/loaders/OBJLoader.js": "export class OBJLoader {}\n",
}


@pytest.fixture
def local_three(tmp_path, monkeypatch) -> Path:
    root = tmp_path / "node_modules" / "three"
    for rel, text in FAKE_TREE.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    monkeypatch.setattr(three_runtime, "LOCAL_THREE_ROOT", root)
    return root


@pytest.fixture
def no_local_three(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(three_runtime, "LOCAL_THREE_ROOT", tmp_path / "missing" / "three")


def test_stage_three_copies_the_import_closure(tmp_path, local_three):
    workspace = tmp_path / "world"
    workspace.mkdir()
    imports, files = stage_three(workspace)
    assert imports == {
        "three": "./vendor/three/build/three.module.js",
        "three/addons/": "./vendor/three/examples/jsm/",
    }
    vendor = workspace / "vendor" / "three"
    copied = sorted(p.relative_to(vendor).as_posix() for p in vendor.rglob("*") if p.is_file())
    assert copied == [
        "build/three.core.js",
        "build/three.module.js",
        "examples/jsm/loaders/GLTFLoader.js",
        "examples/jsm/utils/BufferGeometryUtils.js",
    ]
    assert sorted(files) == sorted(str(vendor / rel) for rel in copied)


def test_stage_three_falls_back_to_pinned_cdn(tmp_path, no_local_three):
    workspace = tmp_path / "world"
    workspace.mkdir()
    imports, files = stage_three(workspace)
    assert imports == {
        "three": f"{THREE_CDN_ROOT}build/three.module.js",
        "three/addons/": f"{THREE_CDN_ROOT}examples/jsm/",
    }
    assert f"three@{THREE_VERSION}/" in THREE_CDN_ROOT
    assert files == []
    assert not (workspace / "vendor").exists()


def test_npm_manifest_pins_the_three_version():
    package = json.loads((REPO_ROOT / "remotion-composer" / "package.json").read_text(encoding="utf-8"))
    assert package["dependencies"]["three"] == THREE_VERSION
    lock = json.loads((REPO_ROOT / "remotion-composer" / "package-lock.json").read_text(encoding="utf-8"))
    assert lock["packages"]["node_modules/three"]["version"] == THREE_VERSION


def test_local_root_points_at_the_npm_install():
    assert three_runtime.LOCAL_THREE_ROOT == REPO_ROOT / "remotion-composer" / "node_modules" / "three"


@pytest.mark.skipif(
    not (REPO_ROOT / "remotion-composer" / "node_modules" / "three" / "build" / "three.module.js").is_file(),
    reason="three is not installed in remotion-composer/node_modules",
)
def test_real_install_closure_includes_core_and_loader_helpers(tmp_path, monkeypatch):
    monkeypatch.setattr(
        three_runtime, "LOCAL_THREE_ROOT", REPO_ROOT / "remotion-composer" / "node_modules" / "three"
    )
    _, files = stage_three(tmp_path)
    rels = {Path(f).relative_to(tmp_path / "vendor" / "three").as_posix() for f in files}
    assert {
        "build/three.module.js",
        "build/three.core.js",
        "examples/jsm/loaders/GLTFLoader.js",
        "examples/jsm/utils/BufferGeometryUtils.js",
    } <= rels


def test_tools_do_not_hard_code_a_three_cdn_url():
    offenders = []
    for path in (REPO_ROOT / "tools").rglob("*"):
        if path.suffix not in {".py", ".html", ".js"} or "__pycache__" in path.parts:
            continue
        if path.name == "three_runtime.py":
            continue
        if re.search(r"three@\d", path.read_text(encoding="utf-8", errors="ignore")):
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == []


def test_threejs_world_resolves_three_through_an_import_map(tmp_path, local_three):
    from tests.tools.test_threejs_world import _world_spec
    from tools.graphics.threejs_world import ThreeJSWorld

    workspace = tmp_path / "world"
    result = ThreeJSWorld().execute(
        {
            "operation": "build",
            "world_spec": _world_spec(),
            "output_path": str(workspace),
            "duration_seconds": 12,
            "width": 1280,
            "height": 720,
            "render_mode": "semantic",
        }
    )
    assert result.success, result.error
    index = (workspace / "index.html").read_text(encoding="utf-8")
    match = re.search(r'<script type="importmap">(.*?)</script>', index, re.S)
    assert match, "index.html has no import map"
    assert json.loads(match.group(1)) == {
        "imports": {
            "three": "./vendor/three/build/three.module.js",
            "three/addons/": "./vendor/three/examples/jsm/",
        }
    }
    # An import map only applies to module scripts that come after it.
    assert index.index('type="importmap"') < index.index('type="module"')
    runtime = (workspace / "world-runtime.js").read_text(encoding="utf-8")
    assert 'from "three";' in runtime
    assert 'from "three/addons/loaders/GLTFLoader.js";' in runtime
    assert "cdn.jsdelivr.net" not in index + runtime
    assert (workspace / "vendor" / "three" / "examples" / "jsm" / "utils" / "BufferGeometryUtils.js").is_file()
