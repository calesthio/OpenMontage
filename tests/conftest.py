"""Session-wide test safety net.

**No test may open a network connection.** Provider tools bill per call, so a
test that reaches a real endpoint costs the developer money — silently, and
every time CI runs. This blocks outbound sockets for the whole test session.

The guard is at the socket layer on purpose. Patching `requests` only covers
tools that use `requests`; the fleet also talks to vendor SDKs (google-cloud,
openai, boto3), `httpx`, and raw `urllib`. Everything bottoms out in
`socket.connect`, so that is where the wall goes.

Loopback is still allowed — local servers, ffmpeg RPC, and Backlot fixtures need it.

Proxy discovery is part of the wall: a proxy whose TCP peer is 127.0.0.1 (a
macOS system proxy, or *_PROXY environment variables) would pass the loopback
rule and tunnel straight to the real provider, so the fixture scrubs proxy
environment variables and neutralizes urllib's proxy lookup for the session.

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
import ssl
import urllib.request

import pytest

_ALLOW_ENV_FLAG = "OPENMONTAGE_ALLOW_NETWORK"

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", ""}

_PROXY_ENV_VARS = (
    "HTTP_PROXY",
    "http_proxy",
    "HTTPS_PROXY",
    "https_proxy",
    "ALL_PROXY",
    "all_proxy",
    "FTP_PROXY",
    "ftp_proxy",
)

_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex
_real_create_connection = socket.create_connection
_real_ssl_connect = ssl.SSLSocket.connect
_real_ssl_connect_ex = ssl.SSLSocket.connect_ex
_real_getproxies = urllib.request.getproxies
_real_getproxies_environment = urllib.request.getproxies_environment
_real_getproxies_macosx_sysconf = getattr(
    urllib.request, "getproxies_macosx_sysconf", None
)


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


def _blocked(address) -> NetworkCallInTestError:
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

    def guarded_connect(self, address, *args, **kwargs):
        if not _is_loopback(address):
            raise _blocked(address)
        return _real_connect(self, address, *args, **kwargs)

    def guarded_connect_ex(self, address, *args, **kwargs):
        if not _is_loopback(address):
            raise _blocked(address)
        return _real_connect_ex(self, address, *args, **kwargs)

    def guarded_create_connection(address, *args, **kwargs):
        if not _is_loopback(address):
            raise _blocked(address)
        return _real_create_connection(address, *args, **kwargs)

    def guarded_ssl_connect(self, address, *args, **kwargs):
        if not _is_loopback(address):
            raise _blocked(address)
        return _real_ssl_connect(self, address, *args, **kwargs)

    def guarded_ssl_connect_ex(self, address, *args, **kwargs):
        if not _is_loopback(address):
            raise _blocked(address)
        return _real_ssl_connect_ex(self, address, *args, **kwargs)

    # A proxy on loopback turns every client that honors it (requests via
    # urllib's proxy lookup, httpx via the environment) into a connection to
    # 127.0.0.1 — which the loopback rule passes — and the proxy then tunnels
    # the call to the real provider. Kill proxy discovery for the session.
    saved_proxy_env = {
        var: os.environ.pop(var) for var in _PROXY_ENV_VARS if var in os.environ
    }
    # Patch the lookup at its source: clients that imported `getproxies`
    # earlier (so a module-attribute patch can't reach them) still resolve
    # `getproxies_environment` / `getproxies_macosx_sysconf` from
    # urllib.request's globals at call time.
    urllib.request.getproxies = lambda: {}
    urllib.request.getproxies_environment = lambda: {}
    if _real_getproxies_macosx_sysconf is not None:
        urllib.request.getproxies_macosx_sysconf = lambda: {}

    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex
    socket.create_connection = guarded_create_connection
    ssl.SSLSocket.connect = guarded_ssl_connect
    ssl.SSLSocket.connect_ex = guarded_ssl_connect_ex
    try:
        yield
    finally:
        socket.socket.connect = _real_connect
        socket.socket.connect_ex = _real_connect_ex
        socket.create_connection = _real_create_connection
        ssl.SSLSocket.connect = _real_ssl_connect
        ssl.SSLSocket.connect_ex = _real_ssl_connect_ex
        urllib.request.getproxies = _real_getproxies
        urllib.request.getproxies_environment = _real_getproxies_environment
        if _real_getproxies_macosx_sysconf is not None:
            urllib.request.getproxies_macosx_sysconf = _real_getproxies_macosx_sysconf
        os.environ.update(saved_proxy_env)


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
