"""Contract tests for the Kling official image provider."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.graphics.kling_official_image import KlingOfficialImage


def test_registry_discovers_kling_official_image(monkeypatch, isolated_tool_registry):
    monkeypatch.delenv("KLING_API_KEY", raising=False)
    isolated_tool_registry.discover("tools")
    tool = isolated_tool_registry.get("kling_official_image")
    assert tool is not None
    assert tool.capability == "image_generation"
    assert tool.provider == "kling_official"


def test_image_schema_and_skill():
    tool = KlingOfficialImage()
    props = tool.input_schema["properties"]
    assert "image_url" in props
    assert "api_family" in props
    assert "kling-official" in tool.agent_skills


def test_generation_payload():
    tool = KlingOfficialImage()
    request = tool._build_request(
        {
            "prompt": "portrait of a launch engineer",
            "negative_prompt": "blurry",
            "api_family": "generation",
            "resolution": "2k",
            "n": 2,
            "watermark": False,
        }
    )
    assert request["path"] == "/v1/images/generations"
    assert request["payload"]["model_name"] == "kling-v3"
    assert request["payload"]["negative_prompt"] == "blurry"
    assert request["payload"]["resolution"] == "2k"
    assert request["payload"]["n"] == 2
    assert request["payload"]["watermark_info"] == {"enabled": False}


def test_edit_payload_converts_image_path_to_base64(tmp_path):
    image_path = tmp_path / "subject.png"
    image_path.write_bytes(b"subject")
    tool = KlingOfficialImage()
    request = tool._build_request(
        {
            "prompt": "keep the subject, change background",
            "generation_mode": "edit",
            "image_path": str(image_path),
            "image_reference": "subject",
        }
    )
    assert request["path"] == "/v1/images/generations"
    assert request["payload"]["image"] == base64.b64encode(b"subject").decode("ascii")
    assert request["payload"]["image_reference"] == "subject"


def test_omni_payload_uses_image_list(tmp_path):
    image_path = tmp_path / "ref.png"
    image_path.write_bytes(b"ref")
    tool = KlingOfficialImage()
    request = tool._build_request(
        {
            "prompt": "combine <<<image_1>>> with neon product lighting",
            "api_family": "omni",
            "image_urls": ["https://example.com/ref-a.png"],
            "image_paths": [str(image_path)],
            "result_type": "series",
            "series_amount": "3",
        }
    )
    assert request["path"] == "/v1/images/omni-image"
    assert request["payload"]["model_name"] == "kling-image-o1"
    assert request["payload"]["image_list"][0] == {"image": "https://example.com/ref-a.png"}
    assert request["payload"]["image_list"][1] == {"image": base64.b64encode(b"ref").decode("ascii")}
    assert request["payload"]["series_amount"] == "3"
    assert request["references_used"][0]["placeholder"] == "<<<image_1>>>"


def test_omni_prompt_helper_adds_placeholders_and_validates_counts():
    tool = KlingOfficialImage()
    request = tool._build_request(
        {
            "prompt": "combine these into one scene",
            "api_family": "omni",
            "image_urls": ["https://example.com/a.png", "https://example.com/b.png"],
        }
    )
    assert "<<<image_1>>> <<<image_2>>>" in request["payload"]["prompt"]
    assert request["references_used"][1]["source"] == "https://example.com/b.png"

    existing = tool._build_request(
        {
            "prompt": "keep <<<image_1>>> as the subject",
            "api_family": "omni",
            "image_urls": ["https://example.com/a.png"],
        }
    )
    assert existing["payload"]["prompt"].count("<<<image_1>>>") == 1

    try:
        tool._build_request(
            {
                "prompt": "use <<<image_2>>>",
                "api_family": "omni",
                "image_urls": ["https://example.com/a.png"],
            }
        )
    except ValueError as exc:
        assert "only 1 image" in str(exc)
    else:
        raise AssertionError("Image Omni placeholders must match provided image count")


def test_image_omni_element_list_and_callback_payload():
    tool = KlingOfficialImage()
    request = tool._build_request(
        {
            "prompt": "render with element",
            "api_family": "omni",
            "element_list": [{"element_id": "321"}],
            "callback_url": "https://example.com/callback",
        }
    )
    assert request["payload"]["element_list"] == [{"element_id": 321}]
    assert request["payload"]["callback_url"] == "https://example.com/callback"
    assert request["element_ids"] == [321]

    try:
        tool._build_request(
            {
                "prompt": "bad callback",
                "api_family": "omni",
                "callback_url": "ftp://example.com/callback",
            }
        )
    except ValueError as exc:
        assert "callback_url" in str(exc)
    else:
        raise AssertionError("callback_url must be an absolute http(s) URL")


def test_image_model_must_match_api_family():
    tool = KlingOfficialImage()
    try:
        tool._build_request(
            {
                "prompt": "generation with omni model",
                "api_family": "generation",
                "model_name": "kling-image-o1",
            }
        )
    except ValueError as exc:
        assert "api_family=generation" in str(exc)
    else:
        raise AssertionError("generation requests must reject omni image models")

    try:
        tool._build_request(
            {
                "prompt": "omni with generation model",
                "api_family": "omni",
                "model_name": "kling-v3",
            }
        )
    except ValueError as exc:
        assert "api_family=omni" in str(exc)
    else:
        raise AssertionError("omni requests must reject generation image models")


def test_execute_downloads_all_image_results(monkeypatch, tmp_path):
    class FakeClient:
        def create_classic_task(self, path, payload):
            return "img-task-1"

        def poll_classic(self, path, task_id, result_key, timeout_seconds, poll_interval):
            return [
                {"url": "https://example.com/a.png"},
                {"url": "https://example.com/b.png"},
            ]

        def download(self, url, output_path):
            output_path.write_bytes(url.encode("utf-8"))
            return output_path

    monkeypatch.setenv("KLING_API_KEY", "test-key")
    monkeypatch.setattr("tools.graphics.kling_official_image.KlingClient", lambda: FakeClient())
    output_path = tmp_path / "image.png"
    result = KlingOfficialImage().execute({"prompt": "x", "n": 2, "output_path": str(output_path)})
    assert result.success
    assert result.data["provider"] == "kling_official"
    assert result.data["task_id"] == "img-task-1"
    assert result.data["remote_outputs"][0]["url"].endswith("a.png")
    assert len(result.artifacts) == 2
    assert Path(result.artifacts[0]).read_bytes() == b"https://example.com/a.png"
    assert Path(result.artifacts[1]).read_bytes() == b"https://example.com/b.png"
    assert result.cost_usd > 0


def test_execute_image_omni_series_records_references_callback_and_artifacts(monkeypatch, tmp_path):
    class FakeClient:
        def create_classic_task(self, path, payload):
            self.path = path
            self.payload = payload
            return "omni-img-task-1"

        def poll_classic(self, path, task_id, result_key, timeout_seconds, poll_interval):
            return [
                {"url": "https://example.com/series-a.png"},
                {"url": "https://example.com/series-b.png"},
            ]

        def download(self, url, output_path):
            output_path.write_bytes(url.encode("utf-8"))
            return output_path

    monkeypatch.setenv("KLING_API_KEY", "test-key")
    monkeypatch.setattr("tools.graphics.kling_official_image.KlingClient", lambda: FakeClient())
    result = KlingOfficialImage().execute(
        {
            "prompt": "series from references",
            "api_family": "omni",
            "image_urls": ["https://example.com/ref.png"],
            "element_list": [654],
            "result_type": "series",
            "series_amount": "2",
            "callback_url": "https://example.com/callback",
            "output_path": str(tmp_path / "series.png"),
        }
    )

    assert result.success
    assert result.data["api_family"] == "omni"
    assert result.data["remote_outputs"][1]["url"].endswith("series-b.png")
    assert result.data["references_used"][0]["placeholder"] == "<<<image_1>>>"
    assert result.data["element_ids"] == [654]
    assert result.data["callback_requested"] is True
    assert result.data["polling_used"] is True
    assert len(result.artifacts) == 2
    assert Path(result.artifacts[1]).name == "series_2.png"


def test_image_selector_prefers_official_provider(monkeypatch, isolated_tool_registry):
    monkeypatch.setenv("KLING_API_KEY", "test-key")
    isolated_tool_registry.discover("tools")

    def fake_execute(self, inputs):
        from tools.base_tool import ToolResult

        return ToolResult(success=True, data={"output_path": "out.png"}, artifacts=["out.png"])

    monkeypatch.setattr(KlingOfficialImage, "execute", fake_execute)
    result = isolated_tool_registry.get("image_selector").execute(
        {
            "prompt": "official image",
            "preferred_provider": "kling_official",
            "allowed_providers": ["kling_official"],
            "api_family": "omni",
            "image_reference": "subject",
        }
    )
    assert result.success
    assert result.data["selected_provider"] == "kling_official"


def test_image_cost_estimate_is_not_zero():
    tool = KlingOfficialImage()
    assert tool.estimate_cost({"prompt": "x"}) > 0
    base = tool.estimate_cost({"prompt": "x", "api_family": "omni"})
    series = tool.estimate_cost(
        {
            "prompt": "x",
            "api_family": "omni",
            "result_type": "series",
            "series_amount": "3",
            "resolution": "4k",
            "image_urls": ["https://example.com/a.png", "https://example.com/b.png"],
        }
    )
    assert series > base
    dry_run = tool.dry_run({"prompt": "x"})
    assert dry_run["cost_estimate_confidence"] == "low"
