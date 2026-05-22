import json
import sys
from datetime import timedelta
from pathlib import Path
from enum import Enum
from types import SimpleNamespace

from tools.audio.azure_tts import AzureTTS
from tools.base_tool import ToolStatus


class FakeResponse:
    def __init__(self, *, content=b"", payload=None, headers=None):
        self.content = content
        self._payload = payload
        self.headers = headers or {}

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_status_requires_key_and_region(monkeypatch):
    tool = AzureTTS()
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    monkeypatch.delenv("SPEECH_REGION", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_ENDPOINT", raising=False)
    assert tool.get_status() == ToolStatus.UNAVAILABLE

    monkeypatch.setenv("AZURE_SPEECH_KEY", "test-key")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "eastus")
    assert tool.get_status() == ToolStatus.AVAILABLE


def test_builds_ssml_with_style_prosody_and_silence():
    tool = AzureTTS()
    ssml = tool._build_ssml({
        "text": "你好，研发同学。",
        "voice": "zh-CN-YunxiNeural",
        "language_code": "zh-CN",
        "style": "chat",
        "style_degree": 1.2,
        "role": "YoungAdultMale",
        "rate": "+8%",
        "pitch": "+1st",
        "volume": "medium",
        "sentence_silence_ms": 180,
    })

    assert 'xml:lang="zh-CN"' in ssml
    assert '<voice name="zh-CN-YunxiNeural">' in ssml
    assert '<mstts:silence type="Sentenceboundary" value="180ms"/>' in ssml
    assert '<mstts:express-as style="chat" styledegree="1.2" role="YoungAdultMale">' in ssml
    assert '<prosody rate="+8%" pitch="+1st" volume="medium">' in ssml


def test_synthesize_writes_audio_and_metadata(monkeypatch, tmp_path):
    calls = {}

    def fake_post(url, *, headers, data, timeout):
        calls["url"] = url
        calls["headers"] = headers
        calls["data"] = data.decode("utf-8")
        calls["timeout"] = timeout
        return FakeResponse(content=b"mp3-bytes", headers={"X-RequestId": "req-123"})

    monkeypatch.setenv("AZURE_SPEECH_KEY", "test-key")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "eastus")
    monkeypatch.setitem(sys.modules, "requests", SimpleNamespace(post=fake_post))

    output = tmp_path / "voice.mp3"
    result = AzureTTS().execute({
        "text": "系统问题分析助手可以串联日志和代码上下文。",
        "voice": "zh-CN-YunxiNeural",
        "style": "chat",
        "rate": "+5%",
        "output_path": str(output),
    })

    assert result.success
    assert output.read_bytes() == b"mp3-bytes"
    assert calls["url"] == "https://eastus.tts.speech.microsoft.com/cognitiveservices/v1"
    assert calls["headers"]["Ocp-Apim-Subscription-Key"] == "test-key"
    assert calls["headers"]["X-Microsoft-OutputFormat"] == "audio-24khz-160kbitrate-mono-mp3"
    assert "mstts:express-as" in calls["data"]

    metadata = json.loads((tmp_path / "voice.mp3.json").read_text(encoding="utf-8"))
    assert metadata["provider"] == "azure"
    assert metadata["request_id"] == "req-123"
    assert metadata["output"] == str(output)


def test_list_voices_filters_locale(monkeypatch):
    def fake_get(url, *, headers, timeout):
        assert url == "https://eastus.tts.speech.microsoft.com/cognitiveservices/voices/list"
        assert headers["Ocp-Apim-Subscription-Key"] == "test-key"
        return FakeResponse(payload=[
            {"ShortName": "zh-CN-XiaoxiaoNeural", "Locale": "zh-CN"},
            {"ShortName": "en-US-JennyNeural", "Locale": "en-US"},
        ])

    monkeypatch.setenv("AZURE_SPEECH_KEY", "test-key")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "eastus")
    monkeypatch.setitem(sys.modules, "requests", SimpleNamespace(get=fake_get))

    result = AzureTTS().execute({"operation": "list_voices", "language_code": "zh-CN"})

    assert result.success
    assert result.data["voice_count"] == 1
    assert result.data["voices"][0]["ShortName"] == "zh-CN-XiaoxiaoNeural"


def test_custom_endpoint_and_deployment_id(monkeypatch, tmp_path):
    calls = {}

    def fake_post(url, *, headers, data, timeout):
        calls["url"] = url
        return FakeResponse(content=b"audio")

    monkeypatch.setenv("AZURE_SPEECH_KEY", "test-key")
    monkeypatch.setenv("AZURE_SPEECH_ENDPOINT", "https://example.cognitiveservices.azure.com")
    monkeypatch.setitem(sys.modules, "requests", SimpleNamespace(post=fake_post))

    result = AzureTTS().execute({
        "text": "custom voice",
        "deployment_id": "deploy-1",
        "output_path": str(tmp_path / "custom.mp3"),
    })

    assert result.success
    assert calls["url"] == "https://example.cognitiveservices.azure.com/cognitiveservices/v1?deploymentId=deploy-1"


def test_full_synthesis_endpoint_is_not_duplicated(monkeypatch, tmp_path):
    calls = {}

    def fake_post(url, *, headers, data, timeout):
        calls["url"] = url
        return FakeResponse(content=b"audio")

    monkeypatch.setenv("AZURE_SPEECH_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "requests", SimpleNamespace(post=fake_post))

    result = AzureTTS().execute({
        "text": "endpoint",
        "endpoint": "https://eastus.tts.speech.microsoft.com/cognitiveservices/v1",
        "output_path": str(tmp_path / "endpoint.mp3"),
    })

    assert result.success
    assert calls["url"] == "https://eastus.tts.speech.microsoft.com/cognitiveservices/v1"


def test_word_boundaries_require_optional_sdk(monkeypatch, tmp_path):
    monkeypatch.setenv("AZURE_SPEECH_KEY", "test-key")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "eastus")

    def missing_sdk(module_name):
        if module_name == "azure.cognitiveservices.speech":
            raise ImportError("missing sdk")
        raise AssertionError(module_name)

    monkeypatch.setattr("tools.audio.azure_tts.importlib.import_module", missing_sdk)

    result = AzureTTS().execute({
        "text": "需要时间戳。",
        "enable_word_boundaries": True,
        "output_path": str(tmp_path / "timed.mp3"),
    })

    assert not result.success
    assert "pip install azure-cognitiveservices-speech" in result.error


def test_sdk_backend_writes_word_boundary_metadata(monkeypatch, tmp_path):
    class BoundaryType(Enum):
        Word = 0

    class Signal:
        def __init__(self):
            self.callback = None

        def connect(self, callback):
            self.callback = callback

    class FakeSpeechConfig:
        def __init__(self, subscription=None, region=None, endpoint=None):
            self.subscription = subscription
            self.region = region
            self.endpoint = endpoint
            self.authorization_token = None
            self.speech_synthesis_voice_name = None
            self.output_format = None

        def set_speech_synthesis_output_format(self, fmt):
            self.output_format = fmt

    class FakeAudioOutputConfig:
        def __init__(self, filename):
            self.filename = filename

    class FakeSynthesizer:
        def __init__(self, speech_config, audio_config):
            self.speech_config = speech_config
            self.audio_config = audio_config
            self.synthesis_word_boundary = Signal()

        def speak_ssml_async(self, ssml):
            output_path = self.audio_config.filename
            callback = self.synthesis_word_boundary.callback
            if callback:
                callback(SimpleNamespace(
                    boundary_type=BoundaryType.Word,
                    text="系统",
                    audio_offset=5_000_000,
                    duration=timedelta(milliseconds=200),
                    text_offset=0,
                    word_length=2,
                ))
            Path(output_path).write_bytes(b"sdk-audio")
            return SimpleNamespace(get=lambda: SimpleNamespace(reason="completed"))

    fake_sdk = SimpleNamespace(
        SpeechConfig=FakeSpeechConfig,
        SpeechSynthesizer=FakeSynthesizer,
        ResultReason=SimpleNamespace(SynthesizingAudioCompleted="completed"),
        CancellationDetails=lambda result: "cancelled",
        SpeechSynthesisOutputFormat=SimpleNamespace(Audio24Khz160KBitRateMonoMp3="fmt"),
        audio=SimpleNamespace(AudioOutputConfig=FakeAudioOutputConfig),
    )

    monkeypatch.setenv("AZURE_SPEECH_KEY", "test-key")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "eastus")
    monkeypatch.setitem(sys.modules, "azure.cognitiveservices.speech", fake_sdk)

    output = tmp_path / "sdk.mp3"
    result = AzureTTS().execute({
        "text": "系统问题分析助手。",
        "backend": "sdk",
        "voice": "zh-CN-YunxiNeural",
        "output_path": str(output),
    })

    assert result.success
    assert output.read_bytes() == b"sdk-audio"
    assert result.data["backend"] == "sdk"
    assert result.data["word_boundary_count"] == 1
    assert result.data["words"][0]["audio_offset_seconds"] == 0.5
    assert result.data["words"][0]["duration_seconds"] == 0.2

    metadata = json.loads((tmp_path / "sdk.mp3.json").read_text(encoding="utf-8"))
    assert metadata["words"][0]["text"] == "系统"
