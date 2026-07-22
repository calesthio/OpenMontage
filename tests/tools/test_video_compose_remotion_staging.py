"""Integration: video_compose Remotion path stages into project-scoped public dir."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from tools.video.video_compose import VideoCompose

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COMPOSER_DIR = REPO_ROOT / "remotion-composer"


@pytest.mark.skipif(
    not COMPOSER_DIR.exists() or not (COMPOSER_DIR / "node_modules").exists(),
    reason="remotion-composer not installed",
)
def test_remotion_render_stages_into_project_public_dir(monkeypatch, tmp_path):
    slug = f"pytest-staging-{uuid.uuid4().hex[:8]}"
    project_dir = tmp_path / "projects" / slug
    renders = project_dir / "renders"
    renders.mkdir(parents=True)

    img = project_dir / "assets" / "frame.jpg"
    narr = project_dir / "assets" / "narration.mp3"
    img.parent.mkdir(parents=True)
    img.write_bytes(b"\xff\xd8\xff")
    narr.write_bytes(b"ID3")

    output_path = renders / "out.mp4"
    captured: dict = {}

    def fake_run_command(cmd, timeout=None, cwd=None):
        captured["cmd"] = list(cmd)
        for arg in cmd:
            if isinstance(arg, str) and arg.startswith("--props="):
                captured["props"] = json.loads(Path(arg.split("=", 1)[1]).read_text())
            if isinstance(arg, str) and arg.startswith("--public-dir="):
                captured["public_dir"] = arg.split("=", 1)[1]
        for arg in cmd:
            if isinstance(arg, str) and arg.endswith(".mp4"):
                Path(arg).write_bytes(b"\x00\x00\x00\x18ftypmp42")
                break

    monkeypatch.setattr(VideoCompose, "run_command", staticmethod(fake_run_command))

    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/npx" if name == "npx" else None)

    tool = VideoCompose()
    result = tool._remotion_render(
        {
            "composition_data": {
                "version": "1.0",
                "render_runtime": "remotion",
                "renderer_family": "explainer-data",
                "cuts": [
                    {
                        "id": "c1",
                        "source": str(img),
                        "in_seconds": 0,
                        "out_seconds": 3,
                    }
                ],
                "audio": {
                    "narration": {"src": str(narr), "volume": 1.0},
                },
            },
            "output_path": str(output_path),
        }
    )

    project_public = project_dir / "remotion-public"
    shared_public = COMPOSER_DIR / "public" / slug
    report_path = renders / ".remotion_asset_staging.json"

    assert result.success, result.error
    props = captured["props"]
    assert props["cuts"][0]["source"] == "frame.jpg"
    assert props["audio"]["narration"]["src"] == "narration.mp3"
    assert "--public-dir=" in " ".join(captured["cmd"])
    assert Path(captured["public_dir"]).resolve() == project_public.resolve()
    # Media cleaned after render; shared composer public untouched.
    assert not project_public.exists()
    assert not shared_public.exists()
    # Debug report survives cleanup.
    assert report_path.exists()
    report = json.loads(report_path.read_text())
    assert report["project_slug"] == slug
    assert len(report["staged"]) == 2
    assert result.data["remotion_asset_staging_report"] == str(report_path)
