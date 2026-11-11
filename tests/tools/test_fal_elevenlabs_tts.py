from __future__ import annotations

from unittest.mock import MagicMock, patch

from tools.audio.fal_elevenlabs_tts import FalElevenLabsTTS
from tools.base_tool import ToolStatus
from tools.tool_registry import ToolRegistry


def _response(*, json_data=None, content=b""):
    response = MagicMock()
    response.json.return_value = json_data
    response.content = content
    response.raise_for_status.return_value = None
    return response


def test_contract_models_and_cost(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "test-key")
    tool = FalElevenLabsTTS()

    assert tool.get_status() == ToolStatus.AVAILABLE
    assert tool.get_info()["capability"] == "tts"
    assert tool.get_info()["provider"] == "fal.ai"
    assert tool.estimate_cost({"text": "a" * 1000, "model_id": "eleven-v3"}) == 0.1
    assert (
        tool.estimate_cost({"text": "a" * 1000, "model_id": "multilingual-v2"}) == 0.1
    )
    assert tool.estimate_cost({"text": "a" * 1000, "model_id": "turbo-v2.5"}) == 0.05


def test_registry_discovers_fal_tts(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "test-key")
    registry = ToolRegistry()
    registry.discover()

    tool = registry.get("fal_elevenlabs_tts")
    assert tool is not None
    assert tool.get_status() == ToolStatus.AVAILABLE


def test_tts_selector_routes_to_fal_provider(monkeypatch):
    from tools.audio.tts_selector import TTSSelector
    from tools.base_tool import ToolResult

    monkeypatch.setenv("FAL_KEY", "test-key")
    tool = FalElevenLabsTTS()
    selector = TTSSelector()
    monkeypatch.setattr(selector, "_providers", lambda: [tool])
    monkeypatch.setattr(
        selector,
        "_select_best_tool",
        lambda _inputs, _candidates, _context: (tool, None),
    )
    monkeypatch.setattr(
        tool,
        "execute",
        lambda inputs: ToolResult(success=True, data={"received": inputs}),
    )
    result = selector.execute(
        {"text": "hello", "preferred_provider": "fal.ai", "voice_id": "Rachel"}
    )
    assert result.success
    assert result.data["selected_tool"] == "fal_elevenlabs_tts"
    assert result.data["selected_provider"] == "fal.ai"


def test_execute_submits_once_and_downloads_audio(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", "test-key")
    output_path = tmp_path / "speech.mp3"
    tool = FalElevenLabsTTS()
    tool._POLL_INTERVAL_SECONDS = 0

    post_response = _response(
        json_data={
            "status_url": "https://queue.fal.run/status",
            "response_url": "https://queue.fal.run/result",
        }
    )
    status_response = _response(json_data={"status": "COMPLETED"})
    result_response = _response(
        json_data={"audio": {"url": "https://media.example/speech.mp3"}}
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
                "text": "A calm, measured test.",
                "voice_id": "Rachel",
                "model_id": "eleven-v3",
                "stability": 0.65,
                "language_code": "en",
                "output_path": str(output_path),
            }
        )

    assert result.success is True
    assert result.model == "fal-ai/elevenlabs/tts/eleven-v3"
    assert output_path.read_bytes() == b"fake-mp3"
    assert mock_post.call_count == 1
    assert mock_post.call_args.args[0].endswith("/fal-ai/elevenlabs/tts/eleven-v3")
    assert mock_post.call_args.kwargs["json"]["voice"] == "Rachel"
    assert mock_post.call_args.kwargs["json"]["stability"] == 0.65
    assert mock_get.call_count == 3


def test_invalid_model_does_not_submit(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "test-key")
    with patch("requests.post") as mock_post:
        result = FalElevenLabsTTS().execute(
            {"text": "hello", "model_id": "not-a-model"}
        )

    assert result.success is False
    assert "model_id must be one of" in result.error
    mock_post.assert_not_called()


def test_error_redacts_fal_key(monkeypatch):
    secret = "test-production-shaped-fal-key"
    monkeypatch.setenv("FAL_KEY", secret)
    with patch("requests.post", side_effect=RuntimeError(f"request used {secret}")):
        result = FalElevenLabsTTS().execute({"text": "hello"})

    assert result.success is False
    assert secret not in result.error
    assert "[REDACTED]" in result.error
