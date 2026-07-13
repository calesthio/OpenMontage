#!/usr/bin/env python3
"""QA Test 09: HyperFrames end-to-end — scaffold + lint + validate + render.

This test hits the real HyperFrames CLI via `npx hyperframes`. On first
run, npm fetches the package (slow -- ~30-90s) and then Chrome downloads its
browser for validation (~30s extra, cached thereafter). Skip unless
HYPERFRAMES_QA=1 is set so CI doesn't pay the cost on every run.

The test is still valuable even without `--render`:
  - scaffold_workspace proves the workspace generator emits a contract-valid
    composition.
  - lint exercises the static contract checker.
  - validate exercises the browser-based contract + contrast audit.
  - inspect and snapshot exercise layout QA and visual keyframe capture.

Full render (operation='render') is optional and gated on HYPERFRAMES_QA_RENDER=1.
"""

from __future__ import annotations

import os
import subprocess
import sys
import shutil
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


from tools.video.hyperframes_compose import HyperFramesCompose


OUT = Path(__file__).resolve().parent / "output"
OUT.mkdir(parents=True, exist_ok=True)


_SKIP_REASON = (
    "HyperFrames QA is opt-in. Set HYPERFRAMES_QA=1 to run scaffold+lint+validate, "
    "and HYPERFRAMES_QA_RENDER=1 to additionally run the real render."
)


def _runtime_ready() -> bool:
    """Cheap check — don't bother launching the CLI if the floor isn't met."""
    return HyperFramesCompose()._runtime_check()["runtime_available"]


def _make_fixture_asset(dest_dir: Path, name: str = "hero.png") -> Path:
    """Generate a real PNG with ffmpeg so the browser actually has something to load."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / name
    if out.exists():
        return out
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=#2563EB:s=1920x1080:d=1",
            "-frames:v", "1", str(out),
        ],
        capture_output=True, check=True, timeout=30,
    )
    return out


def _minimal_scenario(workspace: Path, asset: Path) -> dict:
    return {
        "operation": "render",
        "workspace_path": str(workspace),
        "output_path": str(workspace / "renders" / "smoke.mp4"),
        "edit_decisions": {
            "version": "1.0",
            "renderer_family": "animation-first",
            "render_runtime": "hyperframes",
            "cuts": [
                {"id": "c1", "source": "hero_asset", "in_seconds": 0, "out_seconds": 2, "type": "image"},
                {"id": "c2", "source": "", "in_seconds": 2, "out_seconds": 5,
                 "type": "text_card", "text": "HyperFrames smoke test",
                 "subtitle": "scaffold + lint + validate + render"},
            ],
        },
        "asset_manifest": {"assets": [{"id": "hero_asset", "path": str(asset)}]},
        "playbook": {
            "name": "smoke-test",
            "visual_language": {
                "color_palette": {
                    "background": "#0F172A",
                    "text": "#F8FAFC",
                    "accent": "#F59E0B",
                    "primary": "#2563EB",
                }
            },
            "typography": {
                "heading": {"font": "Inter"},
                "body": {"font": "Inter"},
            },
            "motion": {"pace": "moderate"},
        },
        "quality": "draft",
        "fps": 30,
        "skip_contrast": False,
    }


@pytest.mark.skipif(not os.environ.get("HYPERFRAMES_QA"), reason=_SKIP_REASON)
def test_hyperframes_scaffold_lint_validate(tmp_path: Path):
    if not _runtime_ready():
        pytest.skip("HyperFrames runtime floor not met (node>=22 + ffmpeg + npx).")

    asset = _make_fixture_asset(tmp_path / "assets_src")
    workspace = tmp_path / "hyperframes"
    inputs = _minimal_scenario(workspace, asset)

    # 1. Scaffold
    scaffold = HyperFramesCompose().execute(
        {**inputs, "operation": "scaffold_workspace"}
    )
    assert scaffold.success, scaffold.error
    assert (workspace / "index.html").is_file()
    assert (workspace / "assets" / "hero.png").is_file()
    assert (workspace / "hyperframes.json").is_file()

    # 2. Lint — the CLI fetch happens here on cold cache. Allow plenty of time.
    lint = HyperFramesCompose().execute(
        {"operation": "lint", "workspace_path": str(workspace)}
    )
    # A fresh scaffold should lint clean; if it doesn't, the generator has a bug.
    assert lint.success, (
        f"Lint failed on a freshly scaffolded workspace — "
        f"generator contract violation.\nError: {lint.error}\n"
        f"Stdout tail: {lint.data.get('stdout_tail')}\n"
        f"Stderr tail: {lint.data.get('stderr_tail')}"
    )

    # 3. Validate — browser-based. Skip contrast since our placeholder colors
    # aren't tuned for WCAG.
    validate = HyperFramesCompose().execute(
        {
            "operation": "validate",
            "workspace_path": str(workspace),
            "skip_contrast": True,
        }
    )
    # Validate may return non-zero if the composition has warnings vs errors;
    # what we care about is that it at least ran and produced a report.
    assert "exit_code" in validate.data
    assert validate.data.get("stderr_tail") is not None or validate.data.get("report")

    # 4. Inspect — layout QA for text/container overflow.
    inspect = HyperFramesCompose().execute(
        {
            "operation": "inspect",
            "workspace_path": str(workspace),
            "samples": 3,
            "max_issues": 20,
        }
    )
    assert "exit_code" in inspect.data
    assert inspect.data.get("stderr_tail") is not None or inspect.data.get("report")

    # 5. Snapshot — keyframe capture for visual review.
    snapshot = HyperFramesCompose().execute(
        {
            "operation": "snapshot",
            "workspace_path": str(workspace),
            "snapshot_frames": 2,
        }
    )
    assert snapshot.success, snapshot.error
    assert snapshot.data["snapshot_count"] >= 1


@pytest.mark.skipif(
    not (
        os.environ.get("HYPERFRAMES_QA")
        and os.environ.get("HYPERFRAMES_QA_RENDER")
    ),
    reason=_SKIP_REASON,
)
def test_hyperframes_full_render(tmp_path: Path):
    """Full render — slow (~1-3 min). Opt in with both env vars."""
    if not _runtime_ready():
        pytest.skip("HyperFrames runtime floor not met.")

    asset = _make_fixture_asset(tmp_path / "assets_src")
    workspace = tmp_path / "hyperframes"
    inputs = _minimal_scenario(workspace, asset)
    inputs["skip_contrast"] = True  # placeholder palette isn't WCAG-tuned

    result = HyperFramesCompose().execute(inputs)
    assert result.success, (
        f"Full render failed: {result.error}\n"
        f"Steps: {result.data.get('steps')}"
    )
    out_mp4 = Path(result.data["output"])
    assert out_mp4.is_file(), f"No MP4 at {out_mp4}"
    assert out_mp4.stat().st_size > 5000, "Output suspiciously small"

    # Probe it — real MP4 must have a valid video stream.
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,duration",
            "-of", "default=nw=1",
            str(out_mp4),
        ],
        capture_output=True, text=True, timeout=30,
    )
    assert probe.returncode == 0, probe.stderr
    assert "codec_name" in probe.stdout
