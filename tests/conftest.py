"""Session-wide test safety net.

**No test may open a network connection.** Provider tools bill per call, so a
test that reaches a real endpoint costs the developer money — silently, and
every time CI runs. This blocks outbound sockets for the whole test session.

The guard is at the socket layer on purpose. Patching `requests` only covers
tools that use `requests`; the fleet also talks to vendor SDKs (google-cloud,
openai, boto3), `httpx`, and raw `urllib`. Everything bottoms out in
`socket.connect`, so that is where the wall goes.

Loopback is still allowed — local servers, ffmpeg RPC, and Backlot fixtures need it.

One loopback target is refused all the same: a ComfyUI server, on its default
port 8188 or wherever a ``COMFYUI_*_SERVER_URL`` variable points on this machine.
It is a real GPU, often a rented one behind an SSH tunnel, and a test that runs
an unmocked tool against it queues a real job (an unmocked ``image_selector``
call generated three images on a rented GPU before this was added).

To write a test that genuinely hits a live API:

    @pytest.mark.live_api
    def test_real_call():
        ...

Marked tests are **skipped by default** and only run with the env flag set:

    OPENMONTAGE_ALLOW_NETWORK=1 pytest -m live_api

Limitation: this guards the pytest process. A test that shells out to a
subprocess (node, ffmpeg, npx) is outside its reach — don't call paid APIs
from a subprocess in tests.
"""

from __future__ import annotations

import os
import socket
from urllib.parse import urlparse

import pytest

_ALLOW_ENV_FLAG = "OPENMONTAGE_ALLOW_NETWORK"

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", ""}

_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex
_real_create_connection = socket.create_connection


class NetworkCallInTestError(RuntimeError):
    """Raised when a test tries to open a non-loopback connection."""


def _network_allowed() -> bool:
    return os.environ.get(_ALLOW_ENV_FLAG, "").strip().lower() in {"1", "true", "yes"}


def _is_loopback(address) -> bool:
    """True for loopback TCP/UDP targets and for AF_UNIX socket paths."""
    if isinstance(address, (str, bytes)):
        return True  # AF_UNIX / abstract socket — local by definition
    if not isinstance(address, (tuple, list)) or not address:
        return True  # unrecognised shape; let the real call decide
    host = address[0]
    if isinstance(host, bytes):
        host = host.decode("utf-8", "replace")
    if not isinstance(host, str):
        return False
    host = host.strip("[]").lower()
    if host in _LOOPBACK_HOSTS:
        return True
    return host.startswith("127.")


# ---- Local generation servers (ComfyUI) ----

_COMFYUI_ENV_VARS = (
    "COMFYUI_SERVER_URL",
    "COMFYUI_IMAGE_SERVER_URL",
    "COMFYUI_VIDEO_SERVER_URL",
    "COMFYUI_MUSIC_SERVER_URL",
    "COMFYUI_TTS_SERVER_URL",
)
_COMFYUI_DEFAULT_PORT = 8188


def _local_generation_ports() -> set[int]:
    """Loopback ports a ComfyUI server may answer on, per the environment."""
    ports = {_COMFYUI_DEFAULT_PORT}
    for var in _COMFYUI_ENV_VARS:
        try:
            parsed = urlparse(os.environ.get(var) or "")
            port = parsed.port
        except ValueError:
            continue
        if port and parsed.hostname and _is_loopback((parsed.hostname, port)):
            ports.add(port)
    return ports


# Filled when the guard is installed, after collection has imported the tools
# (and with them any .env file), and before a test changes the environment.
_generation_ports: set[int] = {_COMFYUI_DEFAULT_PORT}


def _is_generation_server(address) -> bool:
    return (
        isinstance(address, (tuple, list))
        and len(address) >= 2
        and address[1] in _generation_ports
        and _is_loopback(address)
    )


def _refused(address) -> bool:
    return not _is_loopback(address) or _is_generation_server(address)


def _blocked(address) -> NetworkCallInTestError:
    if _is_generation_server(address):
        return NetworkCallInTestError(
            f"Blocked a network connection to {address!r} during a test: that is a "
            f"local generation server (ComfyUI).\n"
            f"\n"
            f"A job queued there is real work on a GPU. Fake the client instead\n"
            f"(see tests/contracts/test_comfyui_tools.py), or mark the test\n"
            f"@pytest.mark.live_api and run it deliberately with {_ALLOW_ENV_FLAG}=1."
        )
    return NetworkCallInTestError(
        f"Blocked a network connection to {address!r} during a test.\n"
        f"\n"
        f"Tests must not call real endpoints — provider APIs bill per request.\n"
        f"Mock the transport instead (see tests/tools/test_atlas_video.py for the\n"
        f"fake-`requests` pattern), or mark the test @pytest.mark.live_api and run\n"
        f"it deliberately with {_ALLOW_ENV_FLAG}=1."
    )


@pytest.fixture(scope="session", autouse=True)
def _block_network():
    """Refuse non-loopback sockets for the entire session."""
    if _network_allowed():
        yield
        return

    _generation_ports.update(_local_generation_ports())

    def guarded_connect(self, address, *args, **kwargs):
        if _refused(address):
            raise _blocked(address)
        return _real_connect(self, address, *args, **kwargs)

    def guarded_connect_ex(self, address, *args, **kwargs):
        if _refused(address):
            raise _blocked(address)
        return _real_connect_ex(self, address, *args, **kwargs)

    def guarded_create_connection(address, *args, **kwargs):
        if _refused(address):
            raise _blocked(address)
        return _real_create_connection(address, *args, **kwargs)

    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex
    socket.create_connection = guarded_create_connection
    try:
        yield
    finally:
        socket.socket.connect = _real_connect
        socket.socket.connect_ex = _real_connect_ex
        socket.create_connection = _real_create_connection


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live_api: test performs a real, billable API call. Skipped unless "
        f"{_ALLOW_ENV_FLAG}=1 is set.",
    )


def pytest_collection_modifyitems(config, items):
    """Skip live_api tests unless the operator explicitly opted in."""
    if _network_allowed():
        return
    skip = pytest.mark.skip(
        reason=f"live API test — costs money; set {_ALLOW_ENV_FLAG}=1 to run"
    )
    for item in items:
        if "live_api" in item.keywords:
            item.add_marker(skip)
