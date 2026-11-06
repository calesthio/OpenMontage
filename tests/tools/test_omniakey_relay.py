"""OmniaKey media task contract, local-only: roles, billing, idempotency and resume."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from tools.relay.config import parse_relay_config
from tools.relay.mock_server import mock_mp4, mock_png
from tools.video.relay_video import RelayVideo


@pytest.fixture
def gateway(tmp_path, monkeypatch):
    state = SimpleNamespace(submits=[], released=False, asset_auth=[], expected_job=None)
    clip = mock_mp4(1)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, status, body, mime="application/json"):
            raw = json.dumps(body).encode() if mime == "application/json" else body
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self):
            assert self.path == "/v1/media/tasks"
            assert self.headers.get("Authorization") == "Bearer mock-omnia-key"
            key = self.headers.get("Idempotency-Key")
            assert key and len(key) == 32
            assert json.loads(state.expected_job.read_text())["idempotency_key"] == key
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state.submits.append((key, body))
            self.send(202, {"id": "task-local", "status": "queued"})

        def do_GET(self):
            if self.path == "/asset.mp4":
                state.asset_auth.append(self.headers.get("Authorization"))
                self.send(200, clip, "video/mp4")
            else:
                assert self.path == "/v1/media/tasks/task-local"
                self.send(200, {"status": "succeeded" if state.released else "processing",
                                "assets": [{"url": f"http://127.0.0.1:{self.server.server_port}/asset.mp4"}]})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setenv("OMNIAKEY_API_KEY", "mock-omnia-key")
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(name, raising=False)
    data = yaml.safe_load((Path(__file__).parents[2] / "relay_providers.omniakey.example.yaml").read_text(encoding="utf-8"))
    data["relays"]["omniakey"]["base_url"] = url
    cfg = parse_relay_config(data)
    assert not cfg.errors
    model = cfg.models[0]
    model.poll = {"interval_seconds": 0.01, "timeout_seconds": 0.02}
    frame = tmp_path / "frame.png"
    frame.write_bytes(mock_png())
    state.expected_job = tmp_path / "out.mp4.relay-job.json"
    inputs = {"prompt": "Gentle product camera move", "duration": 4, "resolution": "768P", "output_path": str(tmp_path / "out.mp4")}
    try:
        yield RelayVideo(model), state, inputs, str(frame)
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize("mode,expected", [("text_to_video", []), ("image_to_video", ["first_frame"]),
                                         ("first_last", ["first_frame", "last_frame"]),
                                         ("reference_to_video", ["reference_image"])])
def test_modes_resume_and_idempotency(gateway, mode, expected):
    tool, state, inputs, frame = gateway
    inputs["operation"] = "image_to_video" if mode == "first_last" else mode
    if mode in ("image_to_video", "first_last"):
        inputs["reference_image_path"] = frame
    if mode == "first_last":
        inputs["last_frame_path"] = frame
    if mode == "reference_to_video":
        inputs["reference_image_paths"] = [frame]
    preview = tool.execute(dict(inputs, dry_run=True))
    assert preview.success
    assert "data:image" not in json.dumps(preview.data)
    assert not state.submits and not state.expected_job.exists()
    pending = tool.execute(inputs)
    assert pending.data["status"] == "pending"
    state.released = True
    done = tool.execute(inputs)
    assert done.success, done.error
    assert len(state.submits) == 1
    key, body = state.submits[0]
    assert body["operation"] == inputs["operation"]
    assert [m["type"] for m in body["input"].get("media", [])] == expected
    assert all(m["url"].startswith("data:image/") for m in body["input"].get("media", []))
    assert body["parameters"] == {"duration": 4, "resolution": "768P", "aspect_ratio": "16:9"}
    assert done.cost_usd == pytest.approx(0.1076)
    assert tool.execute(inputs).cost_usd == 0
    assert len(state.submits) == 1
    assert "data:image" not in state.expected_job.read_text()


def test_resolution_pricing_and_invalid_duration(gateway):
    tool, state, inputs, _ = gateway
    assert tool.estimate_cost(inputs) == pytest.approx(0.1076)
    assert tool.estimate_cost(dict(inputs, resolution="2K")) == pytest.approx(0.1724)
    invalid = tool.execute(dict(inputs, duration=1))
    assert not invalid.success
    assert not state.submits


def test_rejected_large_body_does_not_reach_network(gateway):
    tool, state, inputs, _ = gateway
    tool.relay_model.limits["max_request_bytes"] = 20
    result = tool.execute(inputs)
    assert result.data["error_code"] == "request_too_large"
    assert not state.submits
