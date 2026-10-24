import os

import pytest

from lib.env_loader import load_env
from tools.graphics.pexels_image import PexelsImage
from tools.graphics.pixabay_image import PixabayImage
from tools.video.pexels_video import PexelsVideo
from tools.video.pixabay_video import PixabayVideo
from tools.video.stock_sources.pexels import PexelsSource
from tools.video.stock_sources.pixabay_video import PixabayVideoSource


@pytest.mark.parametrize(
    ("tool_cls", "env_name"),
    [
        (PexelsImage, "PEXELS_API_KEY"),
        (PexelsVideo, "PEXELS_API_KEY"),
        (PixabayImage, "PIXABAY_API_KEY"),
        (PixabayVideo, "PIXABAY_API_KEY"),
    ],
)
def test_stock_tools_require_and_detect_api_key(tool_cls, env_name, monkeypatch):
    monkeypatch.delenv(env_name, raising=False)
    tool = tool_cls()
    assert tool.get_status().value == "unavailable"

    monkeypatch.setenv(env_name, "safe-test-key")
    assert tool.get_status().value == "available"
    assert tool.dependencies == [f"env:{env_name}"]

    monkeypatch.setenv(env_name, "   ")
    assert tool.get_status().value == "unavailable"


@pytest.mark.parametrize(
    ("source_cls", "env_name"),
    [
        (PexelsSource, "PEXELS_API_KEY"),
        (PixabayVideoSource, "PIXABAY_API_KEY"),
    ],
)
def test_stock_source_adapters_use_non_empty_keys(source_cls, env_name, monkeypatch):
    monkeypatch.setenv(env_name, "safe-test-key")
    assert source_cls().is_available()

    monkeypatch.setenv(env_name, " ")
    assert not source_cls().is_available()


def test_load_env_replaces_empty_process_values_but_preserves_real_values(
    tmp_path, monkeypatch
):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "PEXELS_API_KEY=from-dotenv-pexels\n"
        "PIXABAY_API_KEY=from-dotenv-pixabay\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("PEXELS_API_KEY", "")
    monkeypatch.setenv("PIXABAY_API_KEY", "from-process")
    load_env(tmp_path)

    assert os.environ["PEXELS_API_KEY"] == "from-dotenv-pexels"
    assert os.environ["PIXABAY_API_KEY"] == "from-process"
