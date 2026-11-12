"""Native reference inputs must reach the selected generation request."""

import base64
from pathlib import Path
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlparse

import pytest

from tools.graphics.atlas_refresh_image import AtlasRefreshImage
from tools.video.ltx_api_video import LTXAPIVideo
from tools.video.wan_atlas_video import WanAtlasVideo


CASES = [
    (AtlasRefreshImage, "images", ["https://owned.example/source.png"], "edit", {}),
    (WanAtlasVideo, "image", "https://owned.example/source.png", "image_to_video", {}),
    (LTXAPIVideo, "image_uri", "https://owned.example/source.png", "image_to_video", {"duration": 6, "resolution": "1920x1080"}),
]


@pytest.fixture
def gateway(monkeypatch):
    import tools.schema_media as module
    from tools.provider_jobs import request_json

    calls = []
    media = "data:application/octet-stream;base64," + base64.b64encode(b"owned-output").decode()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, data):
            content = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append(("POST", self.path, {"json": payload}))
            self.respond({"data": {"id": "owned-atlas"}} if self.path.startswith("/atlas/") else {"id": "owned-ltx"})

        def do_GET(self):
            calls.append(("GET", self.path, {}))
            self.respond({"data": {"status": "completed", "outputs": [media]}, "status": "completed", "result": {"video_url": media}})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    thread.start()

    def local_request(method, url, **kwargs):
        family = "atlas" if "atlascloud" in url else "ltx"
        local_url = f"http://127.0.0.1:{server.server_port}/{family}{urlparse(url).path}"
        return request_json(method, local_url, **kwargs)

    try:
        monkeypatch.setattr(module, "request_json", local_request)
        for name in ("ATLASCLOUD_API_KEY", "LTX_API_KEY"):
            monkeypatch.setenv(name, "owned-offline-key")
        yield calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()


@pytest.mark.parametrize("tool_type,field,reference,operation,extra", CASES)
def test_native_reference_selects_reference_route(tool_type, field, reference, operation, extra, gateway, tmp_path):
    tool = tool_type()
    result = tool.execute({"prompt": "Keep this source", field: reference, **extra, "output_path": str(tmp_path / "out.media")})
    assert result.success, result.error
    submission = next(kwargs["json"] for method, _, kwargs in gateway if method == "POST")
    assert submission.get(field) == reference, "The advertised source reference was lost before submission"
    assert result.data["operation"] == operation
    assert Path(result.data["output"]).read_bytes() == b"owned-output"
    assert sum(method == "POST" for method, _, _ in gateway) == 1


@pytest.mark.parametrize("tool_type,field,reference,operation,extra", CASES)
def test_explicit_text_route_cannot_silently_drop_native_reference(tool_type, field, reference, operation, extra, gateway, tmp_path):
    tool = tool_type()
    result = tool.execute({"prompt": "Keep this source", field: reference, "operation": "generate", **extra, "output_path": str(tmp_path / "out.media")})
    assert not result.success, "Unsupported source input must be rejected before paid submission"
    assert field in result.error
    assert not any(method == "POST" for method, _, _ in gateway)


@pytest.mark.parametrize("tool_type,field,reference,operation,extra", CASES)
def test_explicit_reference_route_preserves_native_reference(tool_type, field, reference, operation, extra, gateway, tmp_path):
    result = tool_type().execute({"prompt": "Keep this source", field: reference, "operation": operation, **extra, "output_path": str(tmp_path / "out.media")})
    assert result.success, result.error
    assert next(kwargs["json"] for method, _, kwargs in gateway if method == "POST")[field] == reference


@pytest.mark.parametrize("tool_type,field,reference,operation,extra", CASES)
def test_text_only_request_keeps_text_route(tool_type, field, reference, operation, extra, gateway, tmp_path):
    result = tool_type().execute({"prompt": "A tree", **extra, "output_path": str(tmp_path / "out.media")})
    assert result.success, result.error
    assert result.data["operation"] == ("generate" if tool_type is AtlasRefreshImage else "text_to_video")
    assert field not in next(kwargs["json"] for method, _, kwargs in gateway if method == "POST")


@pytest.mark.parametrize("tool_type,field,reference,operation,extra", CASES)
def test_canonical_reference_alias_keeps_existing_route(tool_type, field, reference, operation, extra, gateway, tmp_path):
    result = tool_type().execute({"prompt": "Keep this source", "image_url": "https://owned.example/source.png", **extra, "output_path": str(tmp_path / "out.media")})
    assert result.success, result.error
    assert result.data["operation"] == operation
    assert next(kwargs["json"] for method, _, kwargs in gateway if method == "POST")[field] == reference
