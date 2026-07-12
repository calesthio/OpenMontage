"""Regression: maas_image.execute() must still download a `url`-shaped image
response correctly after the redundant local `import requests as _r` alias
was removed in favor of the `requests` already imported at the top of
execute().
"""

from __future__ import annotations

import pytest

from tools.graphics.maas_image import MaasImage


@pytest.fixture(autouse=True)
def _fake_api_key(monkeypatch):
    monkeypatch.setenv("MAAS_API_KEY", "sk-dlp-test-key")


class _FakeResponse:
    def __init__(self, json_data=None, content=b"fake-png-bytes"):
        self._json = json_data or {}
        self.content = content

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


def test_execute_downloads_url_shaped_image(monkeypatch, tmp_path):
    def fake_post(url, headers=None, json=None, timeout=None):
        return _FakeResponse({"data": [{"url": "https://example.com/generated.png"}]})

    def fake_get(url, timeout=None):
        assert url == "https://example.com/generated.png"
        return _FakeResponse(content=b"downloaded-png-bytes")

    import requests

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "get", fake_get)

    output_path = tmp_path / "out.png"
    tool = MaasImage()
    result = tool.execute({"prompt": "a cat", "output_path": str(output_path)})

    assert result.success is True
    assert output_path.read_bytes() == b"downloaded-png-bytes"
