"""Loopback mock relay for tests and dry runs (never bills anything).

Implements every protocol the relay adapters speak, records each request so
tests can assert *how many paid submits happened*, whether the first frame
arrived, and whether the API key leaked to result-file URLs.

Prompt tags steer behaviour:
    [fail]        the async task ends in a failed state
    [504]         the submit answers HTTP 504 (outcome unknown)
    [400]         the submit is rejected with model_not_found
    [slow:N]      the task needs N polls before it completes (default 2)
    [hold]        the task stays running until ``state.released = True``

Run standalone:  python -m tools.relay mock-server --port 8765 --key test-key
"""

from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import tempfile
import threading
import uuid
import wave
from dataclasses import dataclass, field
from email.parser import BytesParser
from email.policy import default as email_policy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit

_VIDEO_CACHE: dict[str, bytes] = {}


def mock_png(color=(40, 120, 200), size=(64, 36)) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def mock_wav(seconds: float = 1.0, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(seconds * rate))
    return buf.getvalue()


def mock_mp4(seconds: int = 2, color: str = "0x2a6fdb") -> bytes:
    """A real tiny H.264 clip when ffmpeg exists (so ffprobe validation passes)."""
    key = f"{seconds}:{color}"
    if key in _VIDEO_CACHE:
        return _VIDEO_CACHE[key]
    data = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64
    if shutil.which("ffmpeg"):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "clip.mp4"
            cmd = [
                "ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                "-i", f"color=c={color}:s=320x180:r=24:d={seconds}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out),
            ]
            if subprocess.run(cmd, capture_output=True, check=False).returncode == 0:
                data = out.read_bytes()
    _VIDEO_CACHE[key] = data
    return data


@dataclass
class MockTask:
    id: str
    kind: str  # video | image
    prompt: str
    polls_needed: int
    fail: bool = False
    hold: bool = False
    polls: int = 0


@dataclass
class MockState:
    expected_key: Optional[str] = None
    tasks: dict[str, MockTask] = field(default_factory=dict)
    requests: list[dict[str, Any]] = field(default_factory=list)
    models: list[str] = field(default_factory=lambda: ["gpt-image-2", "sora-2", "kling-v2", "tts-1"])
    released: bool = False  # flips [hold] tasks to finishing
    lock: threading.Lock = field(default_factory=threading.Lock)

    def submits(self, path_fragment: str = "") -> list[dict[str, Any]]:
        return [r for r in self.requests if r["method"] == "POST" and path_fragment in r["path"]]


def _summarize(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("data:"):
        return {"data_uri_mime": value[5:value.find(";")], "length": len(value)}
    if isinstance(value, dict):
        return {k: _summarize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_summarize(v) for v in value]
    return value


class _Handler(BaseHTTPRequestHandler):
    server_version = "MockRelay/1.0"

    def log_message(self, *args: Any) -> None:  # silence
        pass

    # -- plumbing -------------------------------------------------------------
    @property
    def state(self) -> MockState:
        return self.server.state  # type: ignore[attr-defined]

    @property
    def base(self) -> str:
        host, port = self.server.server_address[:2]  # type: ignore[attr-defined]
        return f"http://{host}:{port}"

    def _send(self, code: int, body: Any = None, ctype: str = "application/json") -> None:
        raw = json.dumps(body).encode() if ctype == "application/json" else (body or b"")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read(self) -> tuple[Any, dict[str, Any]]:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        ctype = self.headers.get("Content-Type", "")
        if ctype.startswith("multipart/form-data"):
            msg = BytesParser(policy=email_policy).parsebytes(
                f"Content-Type: {ctype}\r\n\r\n".encode() + raw
            )
            fields, files = {}, {}
            for part in msg.iter_parts():
                name = part.get_param("name", header="content-disposition")
                payload = part.get_payload(decode=True) or b""
                if part.get_filename():
                    files.setdefault(name, []).append(
                        {"filename": part.get_filename(), "bytes": len(payload),
                         "content_type": part.get_content_type(),
                         "magic": payload[:4].hex()}
                    )
                else:
                    fields[name] = payload.decode("utf-8", "replace")
            return fields, {"multipart_files": files}
        if raw:
            try:
                return json.loads(raw), {}
            except ValueError:
                return raw.decode("utf-8", "replace"), {}
        return {}, {}

    def _record(self, body: Any, extra: dict[str, Any]) -> dict[str, Any]:
        entry = {
            "method": self.command,
            "path": urlsplit(self.path).path,
            "auth": self.headers.get("Authorization"),
            "body": _summarize(body),
            **extra,
        }
        with self.state.lock:
            self.state.requests.append(entry)
        return entry

    def _authorized(self) -> bool:
        expected = self.state.expected_key
        return expected is None or self.headers.get("Authorization") == f"Bearer {expected}"

    def _new_task(self, kind: str, prompt: str) -> MockTask:
        slow = re.search(r"\[slow:(\d+)\]", prompt)
        task = MockTask(
            id=f"task_{uuid.uuid4().hex[:10]}",
            kind=kind,
            prompt=prompt,
            polls_needed=int(slow.group(1)) if slow else 2,
            fail="[fail]" in prompt,
            hold="[hold]" in prompt,
        )
        with self.state.lock:
            self.state.tasks[task.id] = task
        return task

    def _advance(self, task_id: str) -> Optional[tuple[MockTask, str]]:
        with self.state.lock:
            task = self.state.tasks.get(task_id)
            if not task:
                return None
            task.polls += 1
            if task.hold and not self.state.released:
                return task, "running"
            if task.polls < task.polls_needed:
                return task, "running"
            return task, "failed" if task.fail else "done"

    # -- routes ---------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        self._record(None, {})
        if path.startswith("/files/"):
            name = path.rsplit("/", 1)[-1]
            if name.endswith(".mp4"):
                return self._send(200, mock_mp4(), "video/mp4")
            if name.endswith(".png"):
                return self._send(200, mock_png((200, 80, 40)), "image/png")
            return self._send(404, {"error": "no such file"})
        if not self._authorized():
            return self._send(401, {"error": {"message": "invalid api key"}})
        if path.endswith("/models"):
            return self._send(200, {"data": [{"id": m} for m in self.state.models]})

        m = re.search(r"/videos/([^/]+)/content$", path)
        if m:
            if m.group(1) not in self.state.tasks:
                return self._send(404, {"error": "not found"})
            return self._send(200, mock_mp4(), "video/mp4")
        m = re.search(r"/videos/([^/]+)$", path)
        if m:
            step = self._advance(m.group(1))
            if not step:
                return self._send(404, {"error": {"message": "task not found"}})
            task, phase = step
            status = {"running": "in_progress", "failed": "failed", "done": "completed"}[phase]
            body = {"id": task.id, "object": "video", "status": status, "progress": 50 if phase == "running" else 100}
            if phase == "failed":
                body["error"] = {"message": "content policy violation (mock)"}
            return self._send(200, body)
        m = re.search(r"/custom/api/task/([^/]+)$", path)
        if m:
            step = self._advance(m.group(1))
            if not step:
                return self._send(404, {"code": 404, "msg": "task not found"})
            task, phase = step
            data: dict[str, Any] = {"task_id": task.id,
                                    "state": {"running": "PROCESSING", "failed": "FAILED", "done": "SUCCESS"}[phase]}
            if phase == "done":
                ext = "mp4" if task.kind == "video" else "png"
                data["result"] = {"url": f"{self.base}/files/{task.id}.{ext}"}
            if phase == "failed":
                data["fail_msg"] = "upstream rejected the prompt (mock)"
            return self._send(200, {"code": 0, "data": data})
        m = re.search(r"/contents/generations/tasks/([^/]+)$", path)
        if m:
            step = self._advance(m.group(1))
            if not step:
                return self._send(404, {"error": {"code": "NotFound", "message": "task not found"}})
            task, phase = step
            body = {"id": task.id, "model": "doubao-seedance-mock",
                    "status": {"running": "running", "failed": "failed", "done": "succeeded"}[phase]}
            if phase == "done":
                body["content"] = {"video_url": f"{self.base}/files/{task.id}.mp4"}
            if phase == "failed":
                body["error"] = {"code": "OutputVideoSensitiveContentDetected", "message": "mock failure"}
            return self._send(200, body)
        return self._send(404, {"error": f"unknown path {path}"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        body, extra = self._read()
        self._record(body, extra)
        if not self._authorized():
            return self._send(401, {"error": {"message": "invalid api key"}})
        prompt = ""
        if isinstance(body, dict):
            prompt = str(body.get("prompt") or body.get("input") or "")
            if not prompt and isinstance(body.get("content"), list):
                prompt = " ".join(str(c.get("text", "")) for c in body["content"] if isinstance(c, dict))
        if "[504]" in prompt:
            return self._send(504, {"error": "gateway timeout"})
        if "[400]" in prompt:
            return self._send(400, {"error": {"message": "model_not_found: no available channel"}})

        if path.endswith("/images/generations"):
            import base64

            return self._send(200, {"created": 1, "data": [{"b64_json": base64.b64encode(mock_png()).decode()}]})
        if path.endswith("/images/edits"):
            files = (extra.get("multipart_files") or {})
            if not files:
                return self._send(400, {"error": {"message": "image is required"}})
            return self._send(200, {"created": 1, "data": [{"url": f"{self.base}/files/edit_{uuid.uuid4().hex[:6]}.png"}]})
        if path.endswith("/audio/speech"):
            return self._send(200, mock_wav(1.5), "audio/wav")
        if path.endswith("/videos") or path.endswith("/video/generations"):
            task = self._new_task("video", prompt)
            return self._send(200, {"id": task.id, "object": "video", "status": "queued"})
        if path.endswith("/custom/api/submit"):
            kind = "image" if isinstance(body, dict) and body.get("type") == "image" else "video"
            task = self._new_task(kind, prompt)
            return self._send(200, {"code": 0, "data": {"task_id": task.id}})
        if path.endswith("/contents/generations/tasks"):
            task = self._new_task("video", prompt)
            return self._send(200, {"id": task.id})
        return self._send(404, {"error": f"unknown path {path}"})


class MockRelay:
    def __init__(self, *, expected_key: Optional[str] = None, port: int = 0):
        self.state = MockState(expected_key=expected_key)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
        self.httpd.state = self.state  # type: ignore[attr-defined]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        host, port = self.httpd.server_address[:2]
        return f"http://{host}:{port}"

    def start(self) -> "MockRelay":
        self.thread.start()
        return self

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    def __enter__(self) -> "MockRelay":
        return self.start()

    def __exit__(self, *exc: Any) -> None:
        self.stop()


def start_mock_relay(expected_key: Optional[str] = None, port: int = 0) -> MockRelay:
    return MockRelay(expected_key=expected_key, port=port).start()
