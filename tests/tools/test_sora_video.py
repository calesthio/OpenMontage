"""Regression coverage for first-class Sora provider discovery."""

from __future__ import annotations

import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

from tools.base_tool import ToolStatus


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_sora_video_is_discovered_as_openai_video_provider():
    from tools.tool_registry import ToolRegistry

    registry = ToolRegistry()
    registry.discover()

    tool = registry.get("sora_video")
    assert tool is not None
    assert tool.provider == "openai"
    assert tool.capability == "video_generation"


def test_sora_video_loads_openai_key_from_repo_dotenv_when_process_env_is_empty():
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        pytest.skip("Protect local .env contents; CI regression covers absent-.env checkout")

    env_path.write_text("OPENAI_API_KEY=test-openai-key\n", encoding="utf-8")
    try:
        env = os.environ.copy()
        env.pop("OPENAI_API_KEY", None)
        env["PYTHONPATH"] = str(PROJECT_ROOT)

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import os; "
                    "import tools.video.sora_video; "
                    "print('set' if os.environ.get('OPENAI_API_KEY') else 'missing')"
                ),
            ],
            cwd=PROJECT_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        env_path.unlink(missing_ok=True)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "set"


def test_sora_video_reports_unavailable_when_openai_sdk_lacks_video_api(monkeypatch):
    from tools.video.sora_video import SoraVideo

    fake_openai = types.ModuleType("openai")
    fake_openai.__version__ = "1.76.0"
    monkeypatch.setitem(sys.modules, "openai", fake_openai)
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    assert SoraVideo().get_status() == ToolStatus.UNAVAILABLE


def test_sora_video_executes_with_current_create_and_poll_sdk_surface(monkeypatch, tmp_path):
    from tools.video.sora_video import SoraVideo

    calls = {}

    class FakeContent:
        def write_to_file(self, path):
            Path(path).write_bytes(b"fake mp4")

    class FakeVideo:
        id = "video_test"
        status = "completed"

    class FakeVideos:
        def create_and_poll(self, **payload):
            calls["payload"] = payload
            return FakeVideo()

        def download_content(self, video_id, variant):
            calls["download"] = (video_id, variant)
            return FakeContent()

    class FakeOpenAI:
        def __init__(self):
            self.videos = FakeVideos()

    fake_openai = types.ModuleType("openai")
    fake_openai.__version__ = "2.44.0"
    fake_openai.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_openai)
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    output_path = tmp_path / "sample.mp4"
    result = SoraVideo().execute(
        {
            "prompt": "A calm product shot",
            "model": "sora-2",
            "size": "720x1280",
            "seconds": "4",
            "output_path": str(output_path),
        }
    )

    assert result.success, result.error
    assert output_path.read_bytes() == b"fake mp4"
    assert calls["payload"]["model"] == "sora-2"
    assert calls["payload"]["seconds"] == "4"
    assert calls["download"] == ("video_test", "video")
