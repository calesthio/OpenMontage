"""Contract tests for the LTX-on-Modal path.

The Modal endpoint itself can't run here (GPU + weights), but the *contract* between
the app-side client (tools/video/_shared.py::generate_ltx_modal_video) and the deploy
script (deploy/modal_ltx_endpoint.py) is verifiable without Modal:

- the client POSTs exactly the keys the endpoint reads, and
- the deploy script is valid Python that reads those same keys.

Also checks the realistic cost that makes the quality_tier 'draft' lane prefer LTX.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
import requests

import tools.video._shared as shared
from tools.video.ltx_video_modal import LTXVideoModal

DEPLOY_SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "modal_ltx_endpoint.py"

# Keys the endpoint's generate() reads from the JSON body.
ENDPOINT_KEYS = {"prompt", "width", "height", "num_frames", "steps", "fps", "negative_prompt"}


class _FakeResponse:
    def __init__(self, content=b"", headers=None, json_body=None):
        self.content = content
        self.headers = headers or {"content-type": "video/mp4"}
        self._json = json_body

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


@pytest.fixture
def captured_post(monkeypatch):
    """Capture the JSON payload the client POSTs, returning fake MP4 bytes."""
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["payload"] = json
        return _FakeResponse(content=b"FAKEMP4")

    monkeypatch.setenv("MODAL_LTX2_ENDPOINT_URL", "https://example--generate.modal.run")
    # generate_ltx_modal_video does `import requests` internally, so patch the module.
    monkeypatch.setattr(requests, "post", fake_post)
    return captured


def test_text_to_video_payload_matches_endpoint(tmp_path, captured_post):
    out = tmp_path / "clip.mp4"
    result = shared.generate_ltx_modal_video({
        "prompt": "a fox in snow",
        "aspect_ratio": "16:9",
        "output_path": str(out),
    })
    assert result.success is True
    payload = captured_post["payload"]
    # Every key the endpoint reads must be present, and nothing the endpoint needs is missing.
    assert ENDPOINT_KEYS.issubset(payload.keys())
    # LTX frame constraint the endpoint relies on: (num_frames - 1) % 8 == 0.
    assert (payload["num_frames"] - 1) % 8 == 0
    assert out.read_bytes() == b"FAKEMP4"


def test_image_to_video_sends_base64(tmp_path, captured_post):
    img = tmp_path / "ref.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    out = tmp_path / "clip.mp4"
    result = shared.generate_ltx_modal_video({
        "prompt": "animate this",
        "operation": "image_to_video",
        "reference_image_path": str(img),
        "output_path": str(out),
    })
    assert result.success is True
    # Endpoint reads input_image (base64) for image_to_video.
    assert "input_image" in captured_post["payload"]


def test_cost_is_realistic_and_beats_premium_video_api():
    # Must be well under the ~$0.30 premium-clip baseline so draft routing prefers LTX,
    # and specifically < $0.05 so the scorer's cost_efficiency lane scores it top-tier.
    cost = LTXVideoModal().estimate_cost({"prompt": "x"})
    assert 0 < cost < 0.05


def test_deploy_script_is_valid_python_and_reads_contract_keys():
    src = DEPLOY_SCRIPT.read_text()
    ast.parse(src)  # raises SyntaxError if the deploy script is malformed
    # The endpoint must actually reference the payload keys the client sends.
    for key in ENDPOINT_KEYS | {"seed", "input_image", "input_image_url"}:
        assert key in src, f"deploy script never reads payload key {key!r}"
