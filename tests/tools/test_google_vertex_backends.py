from pathlib import Path
from types import SimpleNamespace

import pytest


def test_blank_google_location_uses_documented_default(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "")
    from tools.google_credentials import resolve_google_location

    assert resolve_google_location() == "us-central1"


def test_google_music_requests_the_global_vertex_location(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    import tools.google_credentials as credentials

    captured = {}

    def stop_before_network(http_options=None, location=None):
        captured["location"] = location
        raise RuntimeError("stop before network")

    monkeypatch.setattr(credentials, "get_genai_client", stop_before_network)

    from tools.audio.google_music import GoogleMusic

    result = GoogleMusic().execute(
        {
            "prompt": "solo piano",
            "output_path": str(tmp_path / "music.mp3"),
        }
    )

    assert result.success is False
    assert captured["location"] == "global"


class _VideoAsset:
    uri = None

    def __init__(self, video_bytes):
        self.video_bytes = video_bytes

    def save(self, path):
        Path(path).write_bytes(self.video_bytes or b"")


class _Models:
    def __init__(self, video_bytes):
        self.video_bytes = video_bytes

    def generate_videos(self, **kwargs):
        asset = _VideoAsset(self.video_bytes)
        generated = SimpleNamespace(video=asset)
        response = SimpleNamespace(generated_videos=[generated])
        return SimpleNamespace(done=True, error=None, response=response)


class _VertexClient:
    vertexai = True

    def __init__(self, video_bytes):
        self.models = _Models(video_bytes)
        self.files = SimpleNamespace(
            download=lambda **kwargs: pytest.fail("Vertex must not call files.download")
        )


@pytest.mark.parametrize(
    ("video_bytes", "expected_success"),
    [(b"VIDEO_BYTES", True), (None, False)],
)
def test_veo_accepts_vertex_and_requires_inline_bytes(
    monkeypatch, tmp_path, video_bytes, expected_success
) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    import tools.google_credentials as credentials

    monkeypatch.setattr(
        credentials,
        "get_genai_client",
        lambda http_options=None, location=None, force_vertex=False: _VertexClient(
            video_bytes
        ),
    )

    from tools.video.veo_video import VeoVideo

    output = tmp_path / "video.mp4"
    result = VeoVideo().execute(
        {
            "backend": "google",
            "prompt": "wind moving across grassland",
            "output_path": str(output),
        }
    )

    assert result.success is expected_success
    if expected_success:
        assert output.read_bytes() == b"VIDEO_BYTES"
    else:
        assert "without inline bytes" in result.error
