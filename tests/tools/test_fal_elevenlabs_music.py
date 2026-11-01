from __future__ import annotations

from unittest.mock import MagicMock, patch

from tools.audio.fal_elevenlabs_music import FalElevenLabsMusic
from tools.base_tool import ToolStatus
from tools.tool_registry import ToolRegistry


def _response(*, json_data=None, content=b""):
    response = MagicMock()
    response.json.return_value = json_data
    response.content = content
    response.raise_for_status.return_value = None
    return response


def test_contract_and_rounded_cost(monkeypatch):
    tool = FalElevenLabsMusic()

    monkeypatch.setenv("FAL_KEY", "test-key")
    assert tool.get_status() == ToolStatus.AVAILABLE
    assert tool.estimate_cost({"duration_seconds": 20}) == 0.80
    assert tool.estimate_cost({"duration_seconds": 61}) == 1.60
    assert tool.get_info()["capability"] == "music_generation"
    assert tool.get_info()["provider"] == "fal.ai"


def test_registry_discovers_provider(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "test-key")
    registry = ToolRegistry()
    registry.discover()

    tool = registry.get("fal_elevenlabs_music")
    assert tool is not None
    assert tool.get_status() == ToolStatus.AVAILABLE


def test_execute_submits_once_and_downloads_audio(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", "test-key")
    output_path = tmp_path / "music.mp3"
    tool = FalElevenLabsMusic()
    tool._POLL_INTERVAL_SECONDS = 0

    post_response = _response(
        json_data={
            "status_url": "https://queue.example/status",
            "response_url": "https://queue.example/result",
        }
    )
    status_response = _response(json_data={"status": "COMPLETED"})
    result_response = _response(
        json_data={"audio": {"url": "https://media.example/music.mp3"}}
    )
    audio_response = _response(content=b"fake-mp3")

    with (
        patch("requests.post", return_value=post_response) as mock_post,
        patch(
            "requests.get",
            side_effect=[status_response, result_response, audio_response],
        ) as mock_get,
    ):
        result = tool.execute(
            {
                "prompt": "gentle felt piano",
                "duration_seconds": 20,
                "force_instrumental": True,
                "output_path": str(output_path),
            }
        )

    assert result.success is True
    assert result.cost_usd == 0.80
    assert result.model == "fal-ai/elevenlabs/music"
    assert output_path.read_bytes() == b"fake-mp3"
    assert mock_post.call_count == 1
    assert mock_post.call_args.kwargs["json"]["music_length_ms"] == 20000
    assert mock_post.call_args.kwargs["json"]["force_instrumental"] is True
    assert mock_get.call_count == 3


def test_execute_rejects_missing_duration_without_request(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "test-key")
    with patch("requests.post") as mock_post:
        result = FalElevenLabsMusic().execute({"prompt": "gentle piano"})

    assert result.success is False
    assert result.error == "duration_seconds is required"
    mock_post.assert_not_called()


def test_error_redacts_fal_key(monkeypatch):
    secret = "test-production-shaped-fal-key"
    monkeypatch.setenv("FAL_KEY", secret)
    with patch("requests.post", side_effect=RuntimeError(f"request used {secret}")):
        result = FalElevenLabsMusic().execute(
            {"prompt": "gentle piano", "duration_seconds": 20}
        )

    assert result.success is False
    assert secret not in result.error
    assert "[REDACTED]" in result.error
