"""captionProps: caption style as CaptionOverlay props, forwarded as-is.

remotion_caption_burn (caption_props) and video_compose (edit_decisions.subtitles.caption_props)
only forward the object; without it, the props are unchanged.
"""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from schemas.artifacts import validate_artifact
from tools.video.remotion_caption_burn import RemotionCaptionBurn
from tools.video.video_compose import VideoCompose

CAPS = [{"word": "hello", "startMs": 0, "endMs": 400}]
STYLE = {"fontSize": 59.4, "boxStyle": {"maxWidth": "72%"}, "wordPop": {"scale": 1.12}}


def _burn_props(tmp_path, monkeypatch, **kw):
    """Run _render_remotion with ffprobe/npx faked; return the props JSON written."""
    root = tmp_path / "composer"
    root.mkdir()
    video = tmp_path / "in.mp4"
    video.write_bytes(b"v")
    out = tmp_path / "out.mp4"
    tool = RemotionCaptionBurn()
    monkeypatch.setattr(tool, "_find_remotion_root", lambda: root)

    def fake_run(cmd, *a, **k):
        if "format=duration" in cmd:
            return SimpleNamespace(stdout="1.0\n")
        if "stream=width,height" in cmd:
            return SimpleNamespace(stdout="1920x1080\n")
        out.write_bytes(b"x")
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(tool, "run_command", fake_run)
    result = tool._render_remotion(str(video), str(out), CAPS, 4, 52, "#22D3EE", **kw)
    assert result.success, result.error
    return json.loads((root / "public" / "demo-props" / "caption-burn-in.json").read_text())


def test_burn_without_caption_props_keeps_original_props(tmp_path, monkeypatch):
    props = _burn_props(tmp_path, monkeypatch)
    assert "captionProps" not in props
    assert props["captions"] == CAPS and props["wordsPerPage"] == 4


def test_burn_passes_caption_props_through(tmp_path, monkeypatch):
    props = _burn_props(tmp_path, monkeypatch, caption_props=STYLE)
    assert props["captionProps"] == STYLE
    assert props["wordsPerPage"] == 4  # everything else untouched


def test_burn_schema_declares_caption_props():
    p = RemotionCaptionBurn.input_schema["properties"]
    assert p["caption_props"]["type"] == "object"


def test_burn_execute_forwards_caption_props(tmp_path, monkeypatch):
    video = tmp_path / "in.mp4"
    video.write_bytes(b"v")
    seen = {}
    tool = RemotionCaptionBurn()
    monkeypatch.setattr(tool, "_remotion_available", lambda: True)

    def fake_render(*a, **k):
        seen.update(k)
        return SimpleNamespace(success=True)

    monkeypatch.setattr(tool, "_render_remotion", fake_render)
    tool.execute({"input_path": str(video), "output_path": str(tmp_path / "o.mp4"),
                  "segments": [{"start": 0, "end": 1, "text": "hello", "words": [{"word": "hello", "start": 0, "end": 1}]}],
                  "caption_props": STYLE})
    assert seen["caption_props"] == STYLE


def _compose_props(tmp_path, monkeypatch, subtitles):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/npx")
    tool = VideoCompose()
    seen = {}

    def fake_run(cmd, *a, **k):
        path = next(c for c in cmd if str(c).startswith("--props="))[len("--props="):]
        seen.update(json.loads(Path(path).read_text()))

    monkeypatch.setattr(tool, "run_command", fake_run)
    data = {"cuts": [], "renderer_family": "explainer-data"}
    if subtitles is not None:
        data["subtitles"] = subtitles
    tool._remotion_render({"composition_data": data, "output_path": str(tmp_path / "o.mp4")})
    return seen


def test_compose_passes_subtitles_caption_props(tmp_path, monkeypatch):
    props = _compose_props(tmp_path, monkeypatch, {"enabled": True, "caption_props": STYLE})
    assert props["captionProps"] == STYLE


@pytest.mark.parametrize("subtitles", [None, {"enabled": True}])
def test_compose_without_caption_props_adds_nothing(tmp_path, monkeypatch, subtitles):
    props = _compose_props(tmp_path, monkeypatch, subtitles)
    assert "captionProps" not in props


def test_edit_decisions_schema_accepts_caption_props():
    validate_artifact("edit_decisions", {
        "version": "1.0",
        "render_runtime": "remotion",
        "cuts": [{"id": "c1", "source": "a.mp4", "in_seconds": 0, "out_seconds": 1}],
        "subtitles": {"enabled": True, "caption_props": STYLE},
    })
