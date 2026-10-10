"""Offline request, routing and resume contracts for the October provider refresh."""

import base64
import json
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator, ValidationError

from tools.avatar.heygen_avatar import HeyGenAvatar
from tools.video.wan_fal_video import WanFalVideo
from tools.video.wan_atlas_video import WanAtlasVideo
from tools.video.wan_replicate_video import WanReplicateVideo
from tools.video.ltx_api_video import LTXAPIVideo
from tools.video.h3_max_video import H3MaxVideo
from tools.graphics.openai_fal_image import OpenAIFalImage
from tools.graphics.gemini_fal_image import GeminiFalImage
from tools.graphics.gemini_replicate_image import GeminiReplicateImage
from tools.graphics.atlas_refresh_image import AtlasRefreshImage
from tools.graphics.ideogram_fal_image import IdeogramFalImage
from tools.audio.gemini_tts import GeminiTTS
from tools.base_tool import ToolStatus


@pytest.mark.parametrize(
    "tool",
    [
        WanFalVideo,
        WanAtlasVideo,
        WanReplicateVideo,
        LTXAPIVideo,
        H3MaxVideo,
        OpenAIFalImage,
        GeminiFalImage,
        GeminiReplicateImage,
        AtlasRefreshImage,
        IdeogramFalImage,
    ],
)
def test_new_tools_have_valid_public_schemas(tool):
    instance = tool()
    Draft202012Validator.check_schema(instance.input_schema)
    assert instance.name and instance.agent_skills
    assert instance.retry_policy.max_retries == 0


def test_wan_hosts_use_their_own_image_contract():
    common = {
        "model": "wan-3.0",
        "operation": "image_to_video",
        "prompt": "Pan across a valley",
        "image_url": "https://example.com/source.png",
        "duration": 8,
    }
    assert (
        WanFalVideo().build_request(common)[3]["start_image_url"] == common["image_url"]
    )
    assert WanAtlasVideo().build_request(common)[3]["image"] == common["image_url"]
    assert WanReplicateVideo().build_request(common)[3]["image"] == common["image_url"]
    with pytest.raises(ValueError):
        WanReplicateVideo().build_request({**common, "operation": "reference_to_video"})
    with pytest.raises(ValidationError):
        WanFalVideo().build_request({**common, "duration": 31})


def test_unknown_model_and_invalid_native_parameter_rejected():
    with pytest.raises(ValueError):
        WanFalVideo().build_request({"model": "wan-4"})
    with pytest.raises(ValidationError):
        WanFalVideo().build_request(
            {"prompt": "test", "provider_params": {"invented_field": 1}}
        )


def test_fal_image_edits_preserve_mask_and_references(tmp_path):
    image = tmp_path / "image.png"
    image.write_bytes(b"input")
    _, mode, endpoint, payload = OpenAIFalImage().build_request(
        {
            "prompt": "Change sky",
            "image_path": str(image),
            "mask_url": "https://example.com/mask.png",
            "background": "transparent",
        }
    )
    assert mode == "edit" and endpoint.endswith("/edit")
    assert payload["image_urls"] == [
        "data:image/png;base64," + base64.b64encode(b"input").decode()
    ]
    assert payload["mask_url"].endswith("mask.png")


def test_ideogram_precise_edit_constraints():
    tool = IdeogramFalImage()
    payload = tool.build_request(
        {
            "operation": "precise_edit",
            "prompt": "Blue shoes",
            "image_url": "https://example.com/a.png",
        }
    )[3]
    assert payload["edit_precision"] == "high"
    with pytest.raises(ValueError):
        tool.build_request(
            {
                "operation": "precise_edit",
                "prompt": "Blue",
                "image_url": "https://example.com/a.png",
                "mask_url": "https://example.com/m.png",
                "reference_image_urls": ["https://example.com/r.png"] * 4,
            }
        )


def test_replicate_nano_banana_disables_fallback():
    tool = GeminiReplicateImage()
    assert tool.build_request({"prompt": "A tree"})[3]["allow_fallback_model"] is False
    with pytest.raises(ValueError):
        tool.build_request(
            {"prompt": "A tree", "provider_params": {"allow_fallback_model": True}}
        )


def test_ltx_matrix_and_last_frame():
    tool = LTXAPIVideo()
    base = {
        "model": "ltx-2-5-fast",
        "prompt": "Clouds",
        "duration": 20,
        "resolution": "1920x1080",
        "fps": 24,
    }
    assert tool.build_request(base)[3]["duration"] == 20
    for overrides in (
        {"fps": 50},
        {"model": "ltx-2-5-pro"},
        {"resolution": "3840x2160"},
        {"operation": "retake"},
    ):
        with pytest.raises(ValueError):
            tool.build_request({**base, **overrides})
    assert tool.build_request({**base, "duration": None})[3]["duration"] is None


def test_fal_resume_does_not_submit_twice(monkeypatch, tmp_path):
    monkeypatch.setenv("FAL_KEY", "test")
    import tools.fal_media as module

    calls = []

    def request(method, url, **kwargs):
        calls.append((method, url))
        if method == "POST":
            return {
                "request_id": "job",
                "status_url": "https://queue.fal.run/status",
                "response_url": "https://queue.fal.run/result",
            }
        if url.endswith("status"):
            return {"status": "COMPLETED"}
        return {"video": {"url": "data:video/mp4;base64,dmlkZW8="}}

    monkeypatch.setattr(module, "request_json", request)
    monkeypatch.setattr(
        module, "poll", lambda *a, **k: (_ for _ in ()).throw(TimeoutError("pending"))
    )
    tool = WanFalVideo()
    result = tool.execute({"prompt": "Clouds", "job_path": str(tmp_path / "job.json")})
    assert not result.success and result.data["resume_job"]["request_id"] == "job"
    assert json.loads((tmp_path / "job.json").read_text()) == result.data["resume_job"]
    monkeypatch.setattr(module, "poll", lambda fetch, **kw: fetch())
    result = tool.execute(
        {
            "resume_job": result.data["resume_job"],
            "output_path": str(tmp_path / "out.mp4"),
        }
    )
    assert result.success and result.cost_usd is None
    assert (tmp_path / "out.mp4").read_bytes() == b"video"
    assert sum(method == "POST" for method, url in calls) == 1


@pytest.mark.parametrize(
    "tool,provider_result,submission",
    [
        (
            WanAtlasVideo,
            {
                "data": {
                    "status": "completed",
                    "outputs": ["data:video/mp4;base64,dmlkZW8="],
                }
            },
            {"data": {"id": "job"}},
        ),
        (
            WanReplicateVideo,
            {"status": "succeeded", "output": "data:video/mp4;base64,dmlkZW8="},
            {"id": "job"},
        ),
        (
            LTXAPIVideo,
            {
                "status": "completed",
                "result": {"video_url": "data:video/mp4;base64,dmlkZW8="},
            },
            {"id": "job"},
        ),
    ],
)
def test_gateway_submit_and_resume(
    tool, provider_result, submission, monkeypatch, tmp_path
):
    instance = tool()
    monkeypatch.setenv(instance.credential, "test")
    import tools.schema_media as module

    calls = []

    def request(method, url, **kw):
        calls.append((method, url, kw))
        return submission if method == "POST" else provider_result

    monkeypatch.setattr(module, "request_json", request)
    result = instance.execute(
        {
            "prompt": "Clouds",
            "duration": 8,
            "resolution": "1920x1080" if tool is LTXAPIVideo else "1080p",
            "output_path": str(tmp_path / "a.mp4"),
        }
    )
    assert result.success, result.error
    again = instance.execute(
        {
            "resume_job": result.data["resume_job"],
            "output_path": str(tmp_path / "b.mp4"),
        }
    )
    assert again.success, again.error
    assert sum(x[0] == "POST" for x in calls) == 1


def test_avatar_v_eligibility_before_paid_post(monkeypatch, tmp_path):
    monkeypatch.setenv("HEYGEN_API_KEY", "test")
    import tools.avatar.heygen_avatar as module

    calls = []
    eligible = False

    def request(method, url, **kw):
        calls.append((method, url, kw))
        if "/avatars/looks/" in url:
            return {
                "data": {
                    "avatar_type": "digital_twin" if eligible else "photo_avatar",
                    "supported_api_engines": ["avatar_v"]
                    if eligible
                    else ["avatar_iv"],
                }
            }
        if method == "POST":
            return {"data": {"video_id": "v1"}}
        return {
            "data": {
                "status": "completed",
                "video_url": "data:video/mp4;base64,dmlkZW8=",
            }
        }

    monkeypatch.setattr(module, "request_json", request)
    inputs = {
        "avatar_id": "look",
        "script": "Hello",
        "voice_id": "voice",
        "output_path": str(tmp_path / "avatar.mp4"),
    }
    rejected = HeyGenAvatar().execute(inputs)
    assert not rejected.success and not any(c[0] == "POST" for c in calls)
    eligible = True
    result = HeyGenAvatar().execute(inputs)
    assert result.success, result.error
    assert next(c[2]["json"] for c in calls if c[0] == "POST")["engine"] == {
        "type": "avatar_v"
    }
    assert (
        HeyGenAvatar()
        .execute(
            {
                "resume_job": result.data["resume_job"],
                "output_path": str(tmp_path / "again.mp4"),
            }
        )
        .success
    )
    assert sum(c[0] == "POST" for c in calls) == 1


def test_avatar_audio_is_exclusive():
    with pytest.raises(ValueError):
        HeyGenAvatar.build_payload(
            {
                "avatar_id": "a",
                "script": "Hi",
                "voice_id": "v",
                "audio_url": "https://example.com/a.mp3",
            }
        )
    payload = HeyGenAvatar.build_payload(
        {"avatar_id": "a", "audio_url": "https://example.com/a.mp3"}
    )
    assert "voice_id" not in payload and payload["engine"]["type"] == "avatar_v"


def test_gemini_dialogue_contract():
    tool = GeminiTTS()
    result = tool.build_request(
        {
            "turns": [{"speaker": "Alice", "text": "Hi", "style": "whisper"}],
            "speakers": [{"speaker": "Alice", "voice": "Kore"}],
        }
    )
    assert (
        result["generation_config"]["speech_config"]["speakers"][0]["voice"] == "Kore"
    )
    assert result["input"][0]["content"][0]["annotations"][0]["speaker"] == "Alice"
    with pytest.raises(ValidationError):
        tool.build_request(
            {"turns": [{"speaker": "Unknown", "text": "Hi"}], "speakers": []}
        )


def test_exact_image_tool_selects_same_host_sibling(monkeypatch):
    from tools.graphics.image_selector import ImageSelector
    import lib.scoring

    a = OpenAIFalImage()
    b = GeminiFalImage()
    monkeypatch.setattr(a, "get_status", lambda: ToolStatus.AVAILABLE)
    monkeypatch.setattr(b, "get_status", lambda: ToolStatus.AVAILABLE)
    monkeypatch.setattr(
        lib.scoring,
        "rank_providers",
        lambda tools, ctx: [
            SimpleNamespace(provider=t.provider, tool_name=t.name)
            for t in reversed(tools)
        ],
    )
    selector = ImageSelector()
    selected, _ = selector._select_best_tool({}, [a, b], {})
    assert selected is b
    selected, _ = selector._select_best_tool({"preferred_tool": a.name}, [a, b], {})
    assert selected is a
    assert selector._filter_candidates({"model": "does-not-exist"}, [a, b]) == []
    assert (
        selector._filter_candidates(
            {"model": "gemini-3-pro-image", "hosting_provider": "replicate"}, [a, b]
        )
        == []
    )


def test_tts_v4_exact_routes(monkeypatch):
    from tools.audio.elevenlabs_tts import ElevenLabsTTS
    from tools.audio.fal_elevenlabs_tts import FalElevenLabsTTS
    from tools.provider_routing import filter_explicit_route

    tools = [ElevenLabsTTS(), FalElevenLabsTTS()]
    assert [
        t.name
        for t in filter_explicit_route(
            {"model_id": "eleven_v4", "hosting_provider": "fal.ai"}, tools
        )
    ] == ["fal_elevenlabs_tts"]


def test_local_qwen_missing_weights_is_unavailable(monkeypatch):
    from tools.graphics.qwen_image_21 import QwenImage21

    monkeypatch.delenv("QWEN_IMAGE_21_PATH", raising=False)
    assert QwenImage21().get_status() == ToolStatus.UNAVAILABLE


def test_ltx_local_does_not_fall_back_to_wan():
    from tools.video.comfyui_video import ComfyUIVideo

    result = ComfyUIVideo().execute(
        {"prompt": "Clouds", "model_family": "ltx_2.5_local"}
    )
    assert not result.success and result.data["setup_required"]


def test_openai_25_uses_edit_and_closes_files(monkeypatch, tmp_path):
    import sys
    from tools.graphics.openai_image import OpenAIImage

    monkeypatch.setenv("OPENAI_API_KEY", "test")
    source = tmp_path / "source.png"
    source.write_bytes(b"source")
    calls = []

    def edit(**params):
        assert params["image"][0].read() == b"source"
        calls.append(params)
        return SimpleNamespace(data=[SimpleNamespace(b64_json="b3V0cHV0")], usage=None)

    monkeypatch.setitem(
        sys.modules,
        "openai",
        SimpleNamespace(
            OpenAI=lambda **kwargs: SimpleNamespace(images=SimpleNamespace(edit=edit))
        ),
    )
    result = OpenAIImage().execute(
        {
            "prompt": "Change sky",
            "model": "gpt-image-2.5-sunburst",
            "image_path": str(source),
            "quality": "max",
            "background": "transparent",
            "output_path": str(tmp_path / "out.png"),
        }
    )
    assert result.success, result.error
    assert calls[0]["model"] == "gpt-image-2.5-sunburst"
    assert calls[0]["image"][0].closed
    assert result.cost_usd is None


def test_direct_eleven_v4_continuity_and_pcm(monkeypatch, tmp_path):
    import wave
    from unittest.mock import Mock
    from tools.audio.elevenlabs_tts import ElevenLabsTTS

    monkeypatch.setenv("ELEVENLABS_API_KEY", "test")
    response = Mock(content=b"\x00\x00" * 100, headers={"request-id": "r1"})
    post = Mock(return_value=response)
    monkeypatch.setattr("requests.post", post)
    output = tmp_path / "voice.wav"
    result = ElevenLabsTTS().execute(
        {
            "text": "Next sentence",
            "model_id": "eleven_v4_turbo",
            "previous_request_ids": ["r0"],
            "output_format": "pcm_24000",
            "output_path": str(output),
        }
    )
    assert result.success, result.error
    assert post.call_args.kwargs["json"]["previous_request_ids"] == ["r0"]
    assert result.data["request_id"] == "r1"
    with wave.open(str(output)) as wav:
        assert wav.getframerate() == 24000 and wav.getnframes() == 100


def test_fal_v4_native_fields_and_resume(monkeypatch, tmp_path):
    from unittest.mock import Mock
    from tools.audio.fal_elevenlabs_tts import FalElevenLabsTTS

    monkeypatch.setenv("FAL_KEY", "test")

    def response(data=None, content=b"audio"):
        mock = Mock(content=content)
        mock.json.return_value = data
        return mock

    post = Mock(
        return_value=response(
            {
                "request_id": "r1",
                "status_url": "https://queue.fal.run/status",
                "response_url": "https://queue.fal.run/result",
            }
        )
    )
    get = Mock(
        side_effect=[
            response({"status": "COMPLETED"}),
            response({"audio": {"url": "https://example.com/audio"}}),
            response(),
            response({"status": "COMPLETED"}),
            response({"audio": {"url": "https://example.com/audio"}}),
            response(),
        ]
    )
    monkeypatch.setattr("requests.post", post)
    monkeypatch.setattr("requests.get", get)
    tool = FalElevenLabsTTS()
    tool._POLL_INTERVAL_SECONDS = 0
    result = tool.execute(
        {
            "text": "Hello",
            "model_id": "eleven_v4",
            "output_path": str(tmp_path / "a.mp3"),
        }
    )
    assert result.success, result.error
    assert post.call_args.args[0] == "https://queue.fal.run/elevenlabs/tts/eleven-v4"
    assert "speed" not in post.call_args.kwargs["json"]
    assert tool.execute(
        {
            "resume_job": result.data["resume_job"],
            "output_path": str(tmp_path / "b.mp3"),
        }
    ).success
    assert post.call_count == 1


def test_ideogram_precise_multipart_and_quote(monkeypatch, tmp_path):
    import tools.graphics.ideogram_image as module

    source = tmp_path / "source.png"
    source.write_bytes(b"image")
    monkeypatch.setenv("IDEOGRAM_API_KEY", "test")
    calls = []

    def request(method, url, **kw):
        calls.append((method, url, kw))
        assert kw["files"][0][0] == "image"
        return {"price": 0.1}

    monkeypatch.setattr(module, "request_json", request)
    result = module.IdeogramImage().execute(
        {
            "prompt": "Blue shoes",
            "generation_mode": "precise_edit",
            "image_path": str(source),
            "dry_run": True,
        }
    )
    assert result.success, result.error
    assert calls[0][1].endswith("/precise-edit/ideogram-4-5")
    assert result.data["dry_run"] and not result.artifacts


def test_cartesia_version_and_inworld_auth(monkeypatch, tmp_path):
    from unittest.mock import Mock
    from tools.audio.cartesia_tts import CartesiaTTS
    import tools.audio.inworld_tts as inworld

    monkeypatch.setenv("CARTESIA_API_KEY", "test")
    post = Mock(return_value=Mock(content=b"RIFF-audio"))
    monkeypatch.setattr("requests.post", post)
    result = CartesiaTTS().execute(
        {"text": "Hi", "voice_id": "voice", "output_path": str(tmp_path / "a.wav")}
    )
    assert result.success, result.error
    assert post.call_args.kwargs["headers"]["Cartesia-Version"] == "2026-08-14"
    monkeypatch.setenv("INWORLD_API_KEY", "base64-credential")
    request = Mock(
        return_value={
            "audioContent": "YXVkaW8=",
            "usage": {"processedCharactersCount": 2},
        }
    )
    monkeypatch.setattr(inworld, "request_json", request)
    result = inworld.InworldTTS().execute(
        {
            "text": "Hi",
            "voice_id": "voice",
            "model_id": "inworld-tts-2-flash",
            "output_path": str(tmp_path / "a.mp3"),
        }
    )
    assert result.success, result.error
    assert (
        request.call_args.kwargs["headers"]["Authorization"]
        == "Basic base64-credential"
    )


def test_gemini_voice_library_is_read_only(monkeypatch):
    from unittest.mock import Mock
    import tools.provider_jobs as jobs

    monkeypatch.setenv("GEMINI_API_KEY", "test")
    request = Mock(return_value={"voices": [{"name": "Kore"}]})
    monkeypatch.setattr(jobs, "request_json", request)
    result = GeminiTTS().execute({"operation": "list_voices"})
    assert result.success and result.data["voices"]
    assert request.call_args.args[0] == "GET"


def test_unknown_price_preflight_is_not_free(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "test")
    result = WanFalVideo().dry_run({"prompt": "Clouds"})
    assert result["estimated_cost_usd"] is None
    assert result["cost_status"] == "quote_required"


def test_atlas_nano_aspect_ratio_and_local_mask(tmp_path):
    tool = AtlasRefreshImage()
    payload = tool.build_request(
        {"model": "gemini-3-pro-image", "prompt": "A tree", "aspect_ratio": "16:9"}
    )[3]
    assert payload["aspect_ratio"] == "16:9" and "ratio" not in payload
    mask = tmp_path / "mask.png"
    mask.write_bytes(b"mask")
    payload = tool.build_request(
        {
            "model": "gpt-image-2.5-flare",
            "prompt": "A tree",
            "image_url": "https://example.com/image.png",
            "mask_path": str(mask),
        }
    )[3]
    assert payload["mask"].startswith("data:image/png;base64,")


def test_fal_single_url_maps_to_gpt_references():
    payload = OpenAIFalImage().build_request(
        {"prompt": "Blue sky", "image_url": "https://example.com/image.png"}
    )[3]
    assert payload["image_urls"] == ["https://example.com/image.png"]
