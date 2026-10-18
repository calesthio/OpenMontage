"""Luma Agents image adapter contracts; every network request is mocked."""

import base64

from tools.base_tool import BaseTool, ToolStatus
from tools.graphics.luma_uni_image import LumaUniImage


class Response:
    def __init__(self, payload=None, content=b"", status_code=200):
        self.payload = payload or {}
        self.content = content
        self.status_code = status_code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(response=self)


def test_identity_and_credential_detection(monkeypatch):
    monkeypatch.delenv("LUMA_AGENTS_API_KEY", raising=False)
    monkeypatch.delenv("LUMA_API_KEY", raising=False)
    tool = LumaUniImage()
    assert issubclass(LumaUniImage, BaseTool)
    assert tool.name == "luma_uni_image"
    assert tool.get_status() == ToolStatus.UNAVAILABLE
    monkeypatch.setenv("LUMA_AGENTS_API_KEY", "mock-key")
    assert tool.get_status() == ToolStatus.AVAILABLE


def test_generate_payload_defaults_to_uni_1():
    payload = LumaUniImage().build_payload({"prompt": "A brutalist techno chamber"})
    assert payload == {
        "model": "uni-1", "type": "image", "prompt": "A brutalist techno chamber",
        "aspect_ratio": "16:9", "output_format": "png",
    }


def test_edit_payload_embeds_source_and_accepts_references(tmp_path):
    source = tmp_path / "plate.png"
    source.write_bytes(b"fake-image-bytes")
    payload = LumaUniImage().build_payload({
        "prompt": "Preserve the architecture, intensify the magenta light",
        "operation": "edit", "source_path": str(source), "reference_urls": ["https://example.test/ref.png"],
    })
    assert payload["type"] == "image_edit"
    assert payload["source"]["media_type"] == "image/png"
    assert base64.b64decode(payload["source"]["data"]) == b"fake-image-bytes"
    assert payload["image_ref"] == [{"url": "https://example.test/ref.png"}]


def test_mocked_submit_poll_download(monkeypatch, tmp_path):
    monkeypatch.setenv("LUMA_AGENTS_API_KEY", "never-print-this")
    import requests
    calls = []

    def post(url, **kwargs):
        calls.append(("post", url, kwargs["headers"]["Authorization"], kwargs["json"]))
        return Response({"id": "generation-123"})

    def get(url, **kwargs):
        calls.append(("get", url, kwargs.get("headers", {}).get("Authorization")))
        if url.endswith("generation-123"):
            return Response({"id": "generation-123", "model": "uni-1", "state": "completed", "output": [{"type": "image", "url": "https://example.test/temporary-output"}]})
        return Response(content=b"fake-png-output")

    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr("tools.graphics.luma_uni_image.time.sleep", lambda _: None)
    output = tmp_path / "result.png"
    result = LumaUniImage().execute({"prompt": "A scene", "output_path": str(output)})
    assert result.success
    assert result.data["job_id"] == "generation-123"
    assert output.read_bytes() == b"fake-png-output"
    assert result.cost_usd == 0.0404
    assert calls[0][0:2] == ("post", "https://agents.lumalabs.ai/v1/generations")
    assert calls[0][2] == "Bearer never-print-this"
    assert calls[1][1] == "https://agents.lumalabs.ai/v1/generations/generation-123"
