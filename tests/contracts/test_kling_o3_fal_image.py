"""Kling Image O3 fal.ai endpoint contracts (no billable network)."""
import base64

import pytest

from tools.graphics.kling_o3_fal_image import KlingO3FalImage
from tools.graphics.image_selector import ImageSelector
from tools.base_tool import ToolResult


@pytest.mark.parametrize("operation,endpoint", [
    ("text_to_image", "fal-ai/kling-image/o3/text-to-image"),
    ("image_to_image", "fal-ai/kling-image/o3/image-to-image"),
])
def test_o3_image_routes_and_payload(operation, endpoint):
    tool = KlingO3FalImage()
    inputs = {"model": "kling-o3-image", "operation": operation, "prompt": "A blue hat"}
    if operation == "image_to_image":
        inputs["image_urls"] = ["https://example.com/source.png"]
    model, selected, route, payload = tool.build_request(inputs)
    assert (model, selected, route) == ("kling-o3-image", operation, endpoint)
    assert payload == {key: value for key, value in inputs.items() if key in ("prompt", "image_urls")}
    assert tool.capability == "image_generation"


def test_o3_image_edit_requires_a_reference():
    with pytest.raises(Exception):
        KlingO3FalImage().build_request({"operation": "image_to_image", "prompt": "Change the hat"})


def test_o3_image_edit_local_reference(tmp_path):
    source = tmp_path / "source.png"
    source.write_bytes(b"source")
    _, _, _, payload = KlingO3FalImage().build_request({
        "operation": "image_to_image", "prompt": "Change the hat", "image_path": str(source),
    })
    assert payload["image_urls"] == ["data:image/png;base64," + base64.b64encode(b"source").decode()]


@pytest.mark.parametrize("selector_inputs,expected", [
    ({"operation": "generate"}, "text_to_image"),
    ({"operation": "generate", "generation_mode": "edit", "image_urls": ["https://example.com/source.png"]}, "image_to_image"),
])
def test_image_selector_modes_reach_kling_o3(selector_inputs, expected):
    tool = KlingO3FalImage()
    inputs = {"preferred_tool": tool.name, "hosting_provider": "fal.ai", "model": "kling-o3-image", "prompt": "A blue hat", **selector_inputs}
    assert ImageSelector()._filter_candidates(inputs, [tool]) == [tool]
    assert tool.build_request(inputs)[1] == expected


def test_image_selector_forwards_image_edit_to_o3(monkeypatch):
    tool = KlingO3FalImage()
    selector = ImageSelector()
    monkeypatch.setattr(selector, "_providers", lambda: [tool])
    monkeypatch.setattr(selector, "_select_best_tool", lambda *args: (tool, None))
    payloads = []
    def fake_execute(inputs):
        payloads.append(tool.build_request(inputs))
        return ToolResult(success=True, data={})
    monkeypatch.setattr(tool, "execute", fake_execute)
    result = selector.execute({
        "preferred_tool": tool.name, "hosting_provider": "fal.ai", "model": "kling-o3-image",
        "operation": "generate", "generation_mode": "edit", "prompt": "Blue hat",
        "image_urls": ["https://example.com/source.png"],
    })
    assert result.success, result.error
    assert payloads[0][1] == "image_to_image"
    assert payloads[0][3]["image_urls"] == ["https://example.com/source.png"]
