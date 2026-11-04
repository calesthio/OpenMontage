"""Meta-tests: prove the session network guard actually blocks paid calls.

If these fail, every other test in the suite is one bug away from spending money.
"""

from __future__ import annotations

import socket

import pytest

from tools.graphics.atlas_image import AtlasImage
from tools.video.atlas_video import AtlasVideo


class TestGuardBlocksOutbound:

    def test_raw_socket_connect_is_blocked(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        with pytest.raises(Exception) as exc:
            sock.connect(("api.atlascloud.ai", 443))
        assert "Blocked a network connection" in str(exc.value)

    def test_create_connection_is_blocked(self):
        with pytest.raises(Exception) as exc:
            socket.create_connection(("api.atlascloud.ai", 443), timeout=5)
        assert "Blocked a network connection" in str(exc.value)

    def test_requests_cannot_reach_a_provider(self):
        requests = pytest.importorskip("requests")
        with pytest.raises(Exception):
            requests.get("https://api.atlascloud.ai/api/v1/model/prediction/x", timeout=5)

    def test_loopback_still_permitted(self):
        """Local servers and fixtures must keep working."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        try:
            client = socket.create_connection(("127.0.0.1", port), timeout=5)
            client.close()
        finally:
            server.close()


class TestPaidToolsCannotSpend:
    """The guard must hold even with a real key present in the environment."""

    def test_atlas_image_fails_instead_of_billing(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ATLASCLOUD_API_KEY", "sk-looks-real-but-must-not-be-used")
        result = AtlasImage().execute({
            "prompt": "this must never reach the API",
            "output_path": str(tmp_path / "nope.png"),
        })
        assert result.success is False
        assert result.cost_usd == 0.0

    def test_atlas_video_fails_instead_of_billing(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ATLASCLOUD_API_KEY", "sk-looks-real-but-must-not-be-used")
        result = AtlasVideo().execute({
            "prompt": "this must never reach the API",
            "output_path": str(tmp_path / "nope.mp4"),
        })
        assert result.success is False
        assert result.cost_usd == 0.0


class TestLiveApiMarkerIsSkipped:

    @pytest.mark.live_api
    def test_this_should_never_run_by_default(self):
        raise AssertionError(
            "A @live_api test executed without OPENMONTAGE_ALLOW_NETWORK=1 — "
            "the opt-in gate is broken and real spending is possible."
        )
