from pathlib import Path

from tools.analysis.doubao_vision_understand import DoubaoVisionUnderstand
from tools.base_tool import ToolStatus


class FakeResponse:
    def __init__(self, payload=None, status_code=200):
        self._payload = payload or {}
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def test_status_unavailable_without_api_key(monkeypatch):
    monkeypatch.delenv("DOUBAO_VISION_API_KEY", raising=False)
    monkeypatch.delenv("ARK_API_KEY", raising=False)

    assert DoubaoVisionUnderstand().get_status() == ToolStatus.UNAVAILABLE


def test_describes_images_with_responses_payload(monkeypatch, tmp_path):
    monkeypatch.setenv("DOUBAO_VISION_API_KEY", "test-key")
    monkeypatch.setenv("DOUBAO_VISION_MODEL", "doubao-vision-test")
    image = tmp_path / "frame.jpg"
    image.write_bytes(b"fake jpg")
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse(
            {
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": (
                                    '{"visual_summary":"人物正面口播，手持产品",'
                                    '"camera_motion":"固定机位轻微推近",'
                                    '"seedance_prompt":"竖屏口播，人物面向镜头，产品自然入镜",'
                                    '"pacing":"fast_hook"}'
                                ),
                            }
                        ],
                    }
                ],
                "usage": {"total_tokens": 100},
            }
        )

    monkeypatch.setattr("requests.post", fake_post)

    result = DoubaoVisionUnderstand().execute(
        {
            "image_paths": [str(image)],
            "prompt": "反推短视频画面提示词",
            "response_format": "json",
        }
    )

    assert result.success, result.error
    assert result.data["provider"] == "doubao"
    assert result.data["model"] == "doubao-vision-test"
    assert result.data["parsed"]["seedance_prompt"].startswith("竖屏口播")
    request = calls[0]
    assert request["url"].endswith("/api/v3/responses")
    assert request["headers"]["Authorization"] == "Bearer test-key"
    assert request["json"]["model"] == "doubao-vision-test"
    content = request["json"]["input"][0]["content"]
    assert content[0]["type"] == "input_image"
    assert content[0]["image_url"].startswith("data:image/jpeg;base64,")
    assert content[1]["type"] == "input_text"


def test_returns_clear_error_when_model_output_is_not_json(monkeypatch, tmp_path):
    monkeypatch.setenv("DOUBAO_VISION_API_KEY", "test-key")
    monkeypatch.setenv("DOUBAO_VISION_MODEL", "doubao-vision-test")
    image = tmp_path / "frame.jpg"
    image.write_bytes(b"fake jpg")

    def fake_post(url, headers=None, json=None, timeout=None):
        return FakeResponse({"output_text": "not json"})

    monkeypatch.setattr("requests.post", fake_post)

    result = DoubaoVisionUnderstand().execute(
        {
            "image_paths": [str(image)],
            "prompt": "Return JSON",
            "response_format": "json",
        }
    )

    assert not result.success
    assert "valid JSON" in result.error


def test_requires_model_or_endpoint_id(monkeypatch, tmp_path):
    monkeypatch.setenv("DOUBAO_VISION_API_KEY", "test-key")
    monkeypatch.delenv("DOUBAO_VISION_MODEL", raising=False)
    image = tmp_path / "frame.jpg"
    image.write_bytes(b"fake jpg")

    result = DoubaoVisionUnderstand().execute(
        {
            "image_paths": [str(image)],
            "prompt": "Return JSON",
            "response_format": "json",
        }
    )

    assert not result.success
    assert "DOUBAO_VISION_MODEL" in result.error
