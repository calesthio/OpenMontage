import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.video.video_compose import VideoCompose  # noqa: E402


@pytest.fixture
def tool(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/npx")
    return VideoCompose()


def test_remotion_render_normalizes_absolute_cut_and_audio_paths(tool, tmp_path, monkeypatch):
    captured = {}

    def fake_run_command(cmd, *a, **k):
        props_arg = next(part for part in cmd if str(part).startswith("--props="))
        props_path = Path(str(props_arg).split("=", 1)[1])
        captured["props"] = json.loads(props_path.read_text(encoding="utf-8"))
        Path(cmd[5]).write_bytes(b"fake mp4")

    monkeypatch.setattr(tool, "run_command", fake_run_command)

    result = tool._remotion_render(
        {
            "composition_data": {
                "cuts": [
                    {"source": "/tmp/shot-a.mp4"},
                    {"source": r"C:\media\shot-b.mp4"},
                    {"source": "public/relative.png"},
                ],
                "audio": {
                    "narration": {"src": "/tmp/narration.wav"},
                    "music": {"src": r"C:\media\music.wav"},
                },
            },
            "output_path": str(tmp_path / "out.mp4"),
        }
    )

    assert result.success is True
    assert captured["props"]["cuts"][0]["source"] == "file:///tmp/shot-a.mp4"
    assert captured["props"]["cuts"][1]["source"] == "file:///C:/media/shot-b.mp4"
    assert captured["props"]["cuts"][2]["source"] == "public/relative.png"
    assert captured["props"]["audio"]["narration"]["src"] == "file:///tmp/narration.wav"
    assert captured["props"]["audio"]["music"]["src"] == "file:///C:/media/music.wav"
