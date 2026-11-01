"""Owned loopback transport receipts for task creation and read retries."""

import json
import socket
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from tools._kling.client import KlingClient
from tools._kling.errors import KlingAPIError


@contextmanager
def task_server(drop_first=True, first_status=None):
    receipts = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def answer(self, method):
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            receipts.append((method, self.path, payload))
            if first_status is not None and len(receipts) == 1:
                content = json.dumps({"code": 5000, "message": "Temporary provider error", "request_id": "owned-first"}).encode()
                self.send_response(first_status)
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            if drop_first and len(receipts) == 1:
                # The task has been accepted; only its response is lost.
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
                self.close_connection = True
                return
            content = json.dumps({"code": 0, "data": {"task_id": "owned-task", "id": "owned-turbo"}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def do_POST(self):
            self.answer("POST")

        def do_GET(self):
            self.answer("GET")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", receipts
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()


@pytest.mark.parametrize("family", ["classic", "turbo"])
def test_lost_creation_response_is_not_replayed(monkeypatch, family):
    monkeypatch.setattr("tools._kling.client.time.sleep", lambda delay: None)
    with task_server() as (base_url, receipts):
        client = KlingClient(api_key="owned-offline-key", base_url=base_url)
        try:
            with pytest.raises(KlingAPIError):
                if family == "classic":
                    client.create_classic_task("/v1/images/generations", {"prompt": "A tree"})
                else:
                    client.create_turbo("/text-to-video/kling-3.0-turbo", {"prompt": "A tree"})
        finally:
            client.session.close()
            assert len(receipts) == 1, "One generation call must accept at most one task"
            assert receipts[0][0] == "POST"
            assert receipts[0][2] == {"prompt": "A tree"}


@pytest.mark.parametrize("first_status", [None, 503])
def test_read_transport_retry_remains_available(monkeypatch, first_status):
    monkeypatch.setattr("tools._kling.client.time.sleep", lambda delay: None)
    with task_server(first_status=first_status) as (base_url, receipts):
        client = KlingClient(api_key="owned-offline-key", base_url=base_url)
        try:
            result = client.get("/v1/images/generations/owned-task")
        finally:
            client.session.close()
        assert result["data"]["task_id"] == "owned-task"
        assert len(receipts) == 2
        assert all(method == "GET" for method, _, _ in receipts)


def test_successful_submission_is_sent_once():
    with task_server(drop_first=False) as (base_url, receipts):
        client = KlingClient(api_key="owned-offline-key", base_url=base_url)
        try:
            assert client.create_classic_task("/v1/images/generations", {"prompt": "A tree"}) == "owned-task"
        finally:
            client.session.close()
        assert len(receipts) == 1


def test_retryable_submission_error_is_reported_once(monkeypatch):
    monkeypatch.setattr("tools._kling.client.time.sleep", lambda delay: None)
    with task_server(first_status=503) as (base_url, receipts):
        client = KlingClient(api_key="owned-offline-key", base_url=base_url)
        try:
            with pytest.raises(KlingAPIError) as error:
                client.create_classic_task("/v1/images/generations", {"prompt": "A tree"})
        finally:
            client.session.close()
            assert len(receipts) == 1
        assert error.value.http_status == 503
        assert error.value.request_id == "owned-first"
        assert error.value.message == "Temporary provider error"
