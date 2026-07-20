"""Contract tests for the Kling official TTS provider."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.audio.kling_tts import KlingTTS


def test_registry_discovers_kling_tts(monkeypatch, isolated_tool_registry):
    monkeypatch.delenv("KLING_API_KEY", raising=False)
    isolated_tool_registry.discover("tools")
    tool = isolated_tool_registry.get("kling_tts")
    assert tool is not None
    assert tool.capability == "tts"
    assert tool.provider == "kling_official"


def test_tts_schema_and_skill_metadata():
    tool = KlingTTS()
    props = tool.input_schema["properties"]
    assert "voice_id" in props
    assert props["voice_language"]["enum"] == ["zh", "en"]
    assert "kling-official" in tool.agent_skills
    assert "text-to-speech" in tool.agent_skills
    assert tool.estimate_cost({"text": "hello", "voice_id": "voice-a"}) > 0
    assert tool.dry_run({"text": "hello", "voice_id": "voice-a"})["cost_estimate_confidence"] == "low"


def test_tts_payload_and_validation():
    tool = KlingTTS()
    request = tool._build_request(
        {
            "text": "Hello from Kling",
            "voice_id": "voice-a",
            "voice_language": "en",
            "voice_speed": 1.2,
            "callback_url": "https://example.com/kling/callback",
        }
    )
    assert request["path"] == "/v1/audio/tts"
    assert request["payload"] == {
        "text": "Hello from Kling",
        "voice_id": "voice-a",
        "voice_language": "en",
        "voice_speed": 1.2,
        "callback_url": "https://example.com/kling/callback",
    }

    for bad_inputs in (
        {"text": "missing voice"},
        {"text": "x", "voice_id": "voice-a", "voice_language": "fr"},
        {"text": "x", "voice_id": "voice-a", "voice_speed": 9},
    ):
        try:
            tool._build_request(bad_inputs)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Invalid TTS inputs should fail: {bad_inputs}")


def test_execute_downloads_all_audio_results(monkeypatch, tmp_path):
    class FakeClient:
        def create_classic_task(self, path, payload):
            self.path = path
            self.payload = payload
            return "tts-task-1"

        def poll_classic(self, path, task_id, result_key, timeout_seconds, poll_interval):
            assert result_key == "audios"
            return [
                {"url": "https://example.com/a.mp3"},
                {"audio_url": "https://example.com/b.wav"},
            ]

        def download(self, url, output_path):
            output_path.write_bytes(url.encode("utf-8"))
            return output_path

    monkeypatch.setenv("KLING_API_KEY", "test-key")
    monkeypatch.setattr("tools.audio.kling_tts.KlingClient", lambda: FakeClient())
    monkeypatch.setattr("tools.audio.kling_tts.probe_duration", lambda path: 1.23)

    output_path = tmp_path / "speech.mp3"
    result = KlingTTS().execute(
        {
            "text": "Hello",
            "voice_id": "voice-a",
            "output_path": str(output_path),
        }
    )

    assert result.success
    assert result.data["provider"] == "kling_official"
    assert result.data["task_id"] == "tts-task-1"
    assert result.data["audio_duration_seconds"] == 1.23
    assert len(result.artifacts) == 2
    assert Path(result.artifacts[0]).name == "speech.mp3"
    assert Path(result.artifacts[1]).name == "speech_2.wav"
    assert result.cost_usd > 0


def test_execute_accepts_synchronous_create_response(monkeypatch, tmp_path):
    class FakeClient:
        def post(self, path, payload):
            assert path == "/v1/audio/tts"
            assert payload["voice_id"] == "voice-a"
            return {
                "code": 0,
                "message": "SUCCEED",
                "request_id": "req-1",
                "data": {
                    "task_id": "tts-task-sync",
                    "task_status": "succeed",
                    "task_result": {
                        "audios": [
                            {"url": "https://example.com/sync.mp3"},
                        ]
                    },
                },
            }

        def poll_classic(self, *args, **kwargs):
            raise AssertionError("synchronous TTS response should not poll")

        def download(self, url, output_path):
            output_path.write_bytes(url.encode("utf-8"))
            return output_path

    monkeypatch.setenv("KLING_API_KEY", "test-key")
    monkeypatch.setattr("tools.audio.kling_tts.KlingClient", lambda: FakeClient())
    monkeypatch.setattr("tools.audio.kling_tts.probe_duration", lambda path: 2.5)

    result = KlingTTS().execute(
        {
            "text": "Hello",
            "voice_id": "voice-a",
            "output_path": str(tmp_path / "sync.mp3"),
        }
    )

    assert result.success
    assert result.data["task_id"] == "tts-task-sync"
    assert result.data["remote_outputs"] == [{"url": "https://example.com/sync.mp3"}]
    assert result.data["audio_duration_seconds"] == 2.5


def test_tts_selector_prefers_kling_official(monkeypatch, isolated_tool_registry):
    monkeypatch.setenv("KLING_API_KEY", "test-key")
    isolated_tool_registry.discover("tools")

    def fake_execute(self, inputs):
        from tools.base_tool import ToolResult

        return ToolResult(success=True, data={"output_path": "out.mp3"}, artifacts=["out.mp3"])

    monkeypatch.setattr(KlingTTS, "execute", fake_execute)
    result = isolated_tool_registry.get("tts_selector").execute(
        {
            "text": "official speech",
            "voice_id": "voice-a",
            "preferred_provider": "kling_official",
            "allowed_providers": ["kling_official"],
        }
    )
    assert result.success
    assert result.data["selected_provider"] == "kling_official"
