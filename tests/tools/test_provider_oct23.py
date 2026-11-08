"""Network-free regression coverage for the October 23 provider contracts."""

import base64
import io
import json
import wave
import zipfile
from unittest.mock import Mock
import pytest


def wav_bytes(frames=20, rate=44100):
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\0\0" * frames)
    return out.getvalue()


def response(body=None, content=b"audio"):
    return Mock(
        json=Mock(return_value=body), content=content, headers={}, status_code=200
    )


def test_v4_uses_dialogue_contract(monkeypatch, tmp_path):
    from tools.audio.elevenlabs_tts import ElevenLabsTTS

    post = Mock(return_value=response(content=b"\0\0" * 20))
    monkeypatch.setattr("requests.post", post)
    result = ElevenLabsTTS()._generate(
        {
            "text": "Hello",
            "model_id": "eleven_v4",
            "next_text": "World",
            "output_format": "pcm_24000",
            "output_path": str(tmp_path / "a.wav"),
        },
        "test",
    )
    assert result.success
    assert post.call_args.args[0].endswith("/text-to-dialogue")
    body = post.call_args.kwargs["json"]
    assert body["inputs"] == [
        {"text": "Hello", "voice_id": ElevenLabsTTS.DEFAULT_VOICE_ID}
    ]
    assert body["future_text"] == "World"
    assert "voice_settings" not in body and "settings" in body


def test_turbo_waits_for_global_final(monkeypatch):
    from tools.audio.elevenlabs_tts import ElevenLabsTTS

    socket = Mock()
    socket.__enter__ = Mock(return_value=socket)
    socket.__exit__ = Mock()
    socket.recv.side_effect = [
        json.dumps({"audio": base64.b64encode(b"one").decode()}),
        json.dumps({"is_final_audio_for_turn": True}),
        json.dumps({"audio": base64.b64encode(b"two").decode()}),
        json.dumps({"is_final": True}),
    ]
    connect = Mock(return_value=socket)
    monkeypatch.setattr("websockets.sync.client.connect", connect)
    content = ElevenLabsTTS._turbo_audio(
        {"text": "Hello"}, "key", "voice", "mp3_44100_128"
    )
    assert content == b"onetwo"
    assert "model_id=eleven_v4_turbo" in connect.call_args.args[0]
    assert json.loads(socket.send.call_args_list[0].args[0]) == {"voices": ["voice"]}


def test_grok_alignment_envelope(monkeypatch, tmp_path):
    from tools.audio.grok_tts import GrokTTS

    monkeypatch.setenv("XAI_API_KEY", "test")
    post = Mock(
        return_value=response(
            {
                "audio": base64.b64encode(wav_bytes()).decode(),
                "audio_timestamps": {
                    "graph_chars": ["H", "i"],
                    "graph_times": [[0, 0.1], [0.1, 0.2]],
                },
            }
        )
    )
    monkeypatch.setattr("requests.post", post)
    result = GrokTTS().execute(
        {
            "text": "Hi",
            "with_timestamps": True,
            "output_format": {"codec": "wav"},
            "output_path": str(tmp_path / "voice.wav"),
        }
    )
    assert result.success, result.error
    assert result.data["word_timestamps"] == [{"word": "Hi", "start": 0, "end": 0.2}]
    assert post.call_args.kwargs["json"]["language"] == "auto"
    assert Path(result.data["alignment_path"]).exists()


from pathlib import Path


def test_heygen_bad_extension_rejected_before_charge(monkeypatch, tmp_path):
    from tools.audio.heygen_tts import HeyGenTTS

    monkeypatch.setenv("HEYGEN_API_KEY", "test")
    post = Mock()
    monkeypatch.setattr("requests.post", post)
    result = HeyGenTTS().execute(
        {"text": "Hi", "voice_id": "v", "output_path": str(tmp_path / "bad.mp3")}
    )
    assert not result.success
    post.assert_not_called()


def test_heygen_stream_wav_containers_are_decoded():
    from tools.audio.heygen_tts import HeyGenTTS

    r = Mock()
    r.iter_lines.return_value = [
        "data: "
        + json.dumps(
            {
                "type": "audio",
                "part_index": 1,
                "audio": base64.b64encode(wav_bytes(30)).decode(),
            }
        ),
        "data: "
        + json.dumps(
            {
                "type": "audio",
                "part_index": 0,
                "audio": base64.b64encode(wav_bytes(20)).decode(),
            }
        ),
        "data: [DONE]",
    ]
    content, _ = HeyGenTTS._assemble_stream(r)
    with wave.open(io.BytesIO(content), "rb") as w:
        assert w.getnframes() == 50


def test_heygen_truncated_stream_is_failure():
    from tools.audio.heygen_tts import HeyGenTTS

    r = Mock()
    r.iter_lines.return_value = [
        "data: "
        + json.dumps(
            {
                "type": "audio",
                "part_index": 0,
                "audio": base64.b64encode(wav_bytes()).decode(),
            }
        )
    ]
    with pytest.raises(ValueError, match="Incomplete"):
        HeyGenTTS._assemble_stream(r)


def test_heygen_rate_limit_never_changes_model(monkeypatch):
    from tools.audio.heygen_tts import HeyGenTTS

    limited = response()
    limited.status_code = 429
    limited.headers = {"Retry-After": "0"}
    post = Mock(side_effect=[limited, response({"data": {}})])
    monkeypatch.setattr("requests.post", post)
    HeyGenTTS._post(
        "https://api.heygen.com/v3/models/audio/tts",
        json={"model": "heygen-voice-1-turbo-free"},
    )
    assert [c.kwargs["json"]["model"] for c in post.call_args_list] == [
        "heygen-voice-1-turbo-free"
    ] * 2


@pytest.mark.parametrize(
    "module,cls,field",
    [
        ("tools.audio.elevenlabs_soundtrack", "ElevenLabsSoundtrack", "video_paths"),
        ("tools.analysis.mistral_stt", "MistralSTT", "audio_path"),
        ("tools.audio.heygen_voice_convert", "HeyGenVoiceConvert", "audio_path"),
        ("tools.audio.mistral_tts", "MistralTTS", "reference_audio_path"),
        ("tools.audio.heygen_catalog_tts", "HeyGenCatalogTTS", "engine"),
    ],
)
def test_media_inputs_participate_in_cache_identity(module, cls, field):
    import importlib
    from tools.base_tool import Determinism

    tool = getattr(importlib.import_module(module), cls)()
    assert field in tool.idempotency_key_fields
    assert tool.determinism == Determinism.STOCHASTIC


def test_new_fal_routes_validate_exact_contracts():
    from tools.graphics.flux3_fal_image import Flux3FalImage
    from tools.video.flux3_video import Flux3Video
    from tools.video.vidu_video import ViduVideo

    assert (
        Flux3FalImage().build_request({"prompt": "A fox", "resolution": "4k"})[2]
        == "blackforestlabs/flux-3/text-to-image"
    )
    with pytest.raises(Exception):
        Flux3FalImage().build_request(
            {"prompt": "x", "provider_params": {"unknown_control": 1}}
        )
    with pytest.raises(Exception):
        Flux3Video().build_request({"prompt": "x", "operation": "image_to_video"})
    with pytest.raises(Exception):
        ViduVideo().build_request({"operation": "text_to_video", "prompt": "x"})


def test_nano_host_specific_routing():
    from tools.graphics.gemini_fal_image import GeminiFalImage
    from tools.graphics.gemini_replicate_image import GeminiReplicateImage

    f = GeminiFalImage().build_request(
        {
            "model": "gemini-nano-banana-2.1",
            "prompt": "Edit",
            "image_url": "https://example.com/a.png",
        }
    )
    r = GeminiReplicateImage().build_request(
        {
            "model": "gemini-nano-banana-2.1",
            "prompt": "Edit",
            "image_url": "https://example.com/a.png",
        }
    )
    assert f[2] == "google/nano-banana-2.1/edit"
    assert f[3]["image_urls"] == ["https://example.com/a.png"]
    assert r[3]["image_input"] == ["https://example.com/a.png"]


def test_grok_lite_and_pinned_frame_validation():
    from tools.video.grok_video import GrokVideo

    tool = GrokVideo()
    with pytest.raises(ValueError, match="Lite"):
        tool._build_payload(
            {
                "prompt": "x",
                "model": "grok-imagine-video-1.5-lite",
                "reference_audios": [{"voice_id": "eve"}],
            }
        )
    with pytest.raises(ValueError, match="strictly"):
        tool._build_payload(
            {
                "prompt": "x",
                "model": "grok-imagine-video-1.5",
                "duration": 5,
                "keyframes": [
                    {"image": {"url": "https://example.com/a.png"}, "timestamp_s": 5}
                ],
            }
        )
    payload = tool._build_payload(
        {
            "prompt": "x",
            "model": "grok-imagine-video-1.5",
            "operation": "reference_to_video",
            "reference_audios": [{"voice_id": "eve"}],
        }
    )
    assert payload["reference_audios"] == [{"voice_id": "eve"}]


def test_bfl_resume_does_not_resubmit(monkeypatch, tmp_path):
    from tools.graphics.bfl_image import BFLImage

    monkeypatch.setenv("BFL_API_KEY", "test")
    request = Mock(
        return_value={
            "status": "Ready",
            "result": {"sample": "https://example.com/out.png"},
        }
    )
    monkeypatch.setattr("tools.graphics.bfl_image.request_json", request)
    monkeypatch.setattr(
        "tools.graphics.bfl_image.download", lambda url, path: str(path)
    )
    job = {
        "provider": "bfl",
        "model": "flux-3-image",
        "id": "1",
        "polling_url": "https://api.bfl.ai/v1/get_result?id=1",
    }
    result = BFLImage().execute(
        {"resume_job": job, "output_path": str(tmp_path / "a.png")}
    )
    assert result.success, result.error
    assert request.call_args.args[0] == "GET"


def test_bfl_resume_cannot_send_key_to_other_host(monkeypatch):
    from tools.graphics.bfl_image import BFLImage

    monkeypatch.setenv("BFL_API_KEY", "test")
    req = Mock()
    monkeypatch.setattr("tools.graphics.bfl_image.request_json", req)
    result = BFLImage().execute(
        {
            "resume_job": {
                "provider": "bfl",
                "model": "flux-3-image",
                "polling_url": "https://example.com/steal",
            }
        }
    )
    assert not result.success
    req.assert_not_called()


def test_soundtrack_zip_traversal_rejected(monkeypatch, tmp_path):
    from tools.audio.elevenlabs_soundtrack import ElevenLabsSoundtrack

    monkeypatch.setenv("ELEVENLABS_API_KEY", "test")
    video = tmp_path / "a.mp4"
    video.write_bytes(b"video")
    monkeypatch.setattr(
        "tools.video._shared.probe_output", lambda p: {"duration_seconds": 10}
    )
    z = io.BytesIO()
    with zipfile.ZipFile(z, "w") as archive:
        archive.writestr("../escape.mp3", b"bad")
    monkeypatch.setattr(
        "requests.post", Mock(return_value=response(content=z.getvalue()))
    )
    result = ElevenLabsSoundtrack().execute(
        {
            "video_paths": [str(video)],
            "separate_tracks": True,
            "output_path": str(tmp_path / "music.mp3"),
        }
    )
    assert not result.success and "Unsafe" in result.error
    assert not (tmp_path / "escape.mp3").exists()


def test_mistral_tts_decodes_json_audio(monkeypatch, tmp_path):
    from tools.audio.mistral_tts import MistralTTS

    monkeypatch.setenv("MISTRAL_API_KEY", "test")
    post = Mock(
        return_value=response({"audio_data": base64.b64encode(wav_bytes()).decode()})
    )
    monkeypatch.setattr("requests.post", post)
    result = MistralTTS().execute(
        {
            "text": "Hi",
            "voice_id": "gb_jane_neutral",
            "output_format": "wav",
            "output_path": str(tmp_path / "a.wav"),
        }
    )
    assert result.success, result.error
    assert post.call_args.kwargs["json"]["model"] == "voxtral-mini-tts-3-0"


def test_mai_voice_qualified_name():
    from tools.audio.mai_tts import MAITTS

    t = MAITTS()
    assert (
        t._resolve_voice({"model_id": "MAI-Voice-2.1-Flash"})
        == "en-US-Harper:MAI-Voice-2.1-Flash"
    )
    with pytest.raises(ValueError):
        t._resolve_voice(
            {
                "model_id": "MAI-Voice-2.1",
                "voice_id": "en-US-Harper:MAI-Voice-2.1-Flash",
            }
        )


def test_realtime_eleven_mints_secret_and_does_not_persist_it(monkeypatch):
    from tools.audio._realtime_session import RealtimeAudioSession

    monkeypatch.setenv("ELEVENLABS_API_KEY", "server-key")
    post = Mock(return_value=response({"value": "ephemeral"}))
    monkeypatch.setattr("requests.post", post)
    socket = Mock()
    socket.recv.return_value = json.dumps({"type": "session.created"})
    connect = Mock(return_value=socket)
    monkeypatch.setattr("tools.audio._realtime_session.connect", connect)
    with RealtimeAudioSession("elevenlabs", "eleven_realtime_v1_mini") as session:
        assert (
            connect.call_args.kwargs["additional_headers"]["Authorization"]
            == "Bearer ephemeral"
        )
        session.cancel()
        assert json.loads(socket.send.call_args.args[0])["type"] == "response.cancel"
    assert session.headers == {}
    assert (
        post.call_args.kwargs["json"]["session"]["model"] == "eleven_realtime_v1_mini"
    )


def test_mai_realtime_requires_session_ack_and_raw_pcm(monkeypatch):
    from tools.audio._realtime_session import RealtimeAudioSession

    monkeypatch.setenv("MAI_ENDPOINT", "https://sample.services.ai.azure.com")
    monkeypatch.setenv("MAI_API_KEY", "test")
    monkeypatch.setenv("MAI_TRANSCRIBE_DEPLOYMENT", "my-deployment")
    socket = Mock()
    socket.recv.side_effect = [
        json.dumps({"type": "session.created"}),
        json.dumps({"type": "session.updated"}),
    ]
    monkeypatch.setattr(
        "tools.audio._realtime_session.connect", Mock(return_value=socket)
    )
    with RealtimeAudioSession("microsoft_mai", "MAI-Transcribe-2-Streaming") as session:
        session.append_audio(b"\0\0" * 10)
        session.commit()
    events = [json.loads(c.args[0]) for c in socket.send.call_args_list]
    assert events[0]["type"] == "session.update"
    assert (
        events[0]["session"]["audio"]["input"]["transcription"]["model"]
        == "my-deployment"
    )
    assert base64.b64decode(events[1]["audio"]) == b"\0\0" * 10
    assert events[2]["type"] == "input_audio_buffer.commit"


def test_catalog_preserves_returned_codec(monkeypatch, tmp_path):
    from tools.audio.heygen_catalog_tts import HeyGenCatalogTTS

    monkeypatch.setenv("HEYGEN_API_KEY", "test")
    post = Mock(
        return_value=response(
            {
                "data": {
                    "audio_url": "https://example.com/audio",
                    "engine": "starfish",
                    "duration": 1,
                }
            }
        )
    )
    monkeypatch.setattr("requests.post", post)
    monkeypatch.setattr(
        "tools.audio.heygen_catalog_tts.download",
        lambda url, path: path.write_bytes(wav_bytes()),
    )
    result = HeyGenCatalogTTS().execute(
        {
            "text": "Hi",
            "voice_id": "test",
            "engine": "starfish",
            "output_path": str(tmp_path / "out.mp3"),
        }
    )
    assert result.success, result.error
    assert result.data["output"] == str(tmp_path / "out.wav")
    assert (tmp_path / "out.wav").read_bytes() == wav_bytes()
    post.assert_called_once()
    post.reset_mock()
    invalid = HeyGenCatalogTTS().execute(
        {
            "text": "Hi",
            "voice_id": "test",
            "engine": "starfish",
            "output_path": str(tmp_path / "out.txt"),
        }
    )
    assert not invalid.success
    post.assert_not_called()


def test_bfl_string_reference_and_dimension_pair():
    from tools.graphics.bfl_image import BFLImage

    tool = BFLImage()
    assert tool.build_request(
        {"prompt": "Edit", "images": "https://example.com/image.png"}
    )["images"] == ["https://example.com/image.png"]
    with pytest.raises(ValueError, match="together"):
        tool.build_request({"prompt": "Photo", "width": 1024})
    assert {"width", "height", "images"} <= set(tool.idempotency_key_fields)


def test_mai_image_area_rejected_before_post(monkeypatch):
    from tools.graphics.mai_image import MAIImage

    monkeypatch.setenv("MAI_API_KEY", "test")
    post = Mock()
    monkeypatch.setattr("requests.post", post)
    result = MAIImage().execute(
        {"prompt": "Photo", "model": "MAI-Image-2.6", "width": 3072, "height": 1024}
    )
    assert not result.success and "pixels" in result.error
    post.assert_not_called()


def test_mai_selector_normalizes_controls():
    from tools.audio.mai_tts import MAITTS
    from tools.audio.tts_selector import TTSSelector

    result = TTSSelector._adapt_inputs(
        MAITTS(),
        {
            "model": "MAI-Voice-2.1-Flash",
            "speed": 1.2,
            "pitch": 2,
            "output_format": "mp3_44100_128",
        },
    )
    assert result["rate"] == "+20%"
    assert result["pitch"] == "+2st"
    assert result["output_format"] == "mp3"
    assert result["model_id"] == "MAI-Voice-2.1-Flash"


def test_veo_explicit_vertex_mode_supports_adc(monkeypatch):
    from tools.video.veo_video import VeoVideo

    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    assert VeoVideo()._get_google_credentials_status()


def test_bria_fal_url_edit_maps_instruction():
    from tools.graphics.bria_fal_image import BriaFalImage

    _, operation, _, payload = BriaFalImage().build_request(
        {"prompt": "Make it blue", "image_url": "https://example.com/a.png"}
    )
    assert operation == "edit"
    assert payload["instruction"] == "Make it blue"
