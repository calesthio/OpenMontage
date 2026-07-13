"""Contract tests for Kling official shared client, helpers, and docs."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools._kling.client import KlingClient
from tools._kling.errors import KlingAPIError, is_retryable_kling_error
from tools._kling.account import get_account_costs, reset_account_usage_cache
from tools._kling.elements import (
    get_custom_element,
    list_custom_elements,
    list_preset_elements,
    normalize_element_list,
    write_elements_artifact,
)
from tools._kling.schemas import DEFAULT_API_BASE_URL
from tools.audio.kling_tts import KlingTTS
from tools.avatar.kling_avatar import KlingAvatar
from tools.avatar.kling_lip_sync import KlingLipSync
from tools.graphics.kling_official_image import KlingOfficialImage
from tools.video.kling_official_video import KlingOfficialVideo


class FakeResponse:
    def __init__(self, data=None, status_code=200, content=b"data", text=""):
        self._data = data if data is not None else {"code": 0}
        self.status_code = status_code
        self.content = content
        self.text = text

    def json(self):
        if isinstance(self._data, Exception):
            raise self._data
        return self._data


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(("post", url, kwargs))
        return self.responses.pop(0)

    def get(self, url, **kwargs):
        self.calls.append(("get", url, kwargs))
        return self.responses.pop(0)


class HelperFakeClient:
    def __init__(self, api_key="fake-key", base_url="https://api.example.test"):
        self.api_key = api_key
        self.base_url = base_url
        self.calls = []

    def get(self, path, params=None):
        self.calls.append((path, params or {}))
        if path.startswith("/v1/general/advanced-custom-elements/"):
            return {"code": 0, "data": {"element_id": 123}}
        if path == "/v1/general/advanced-custom-elements":
            return {"code": 0, "data": [{"element_id": 456}]}
        if path == "/v1/general/advanced-presets-elements":
            return {"code": 0, "data": [{"element_id": 1}]}
        return {"code": 0, "data": {"resource_pack_subscribe_infos": [{"name": "pack-a"}]}}


class HelperFakeResponse:
    status_code = 200

    def json(self):
        return {"code": 0, "data": {"resource_pack_subscribe_infos": [{"name": "pack-a"}]}}


class HelperFakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("get", url, kwargs))
        return HelperFakeResponse()


def read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def test_missing_api_key_header_error(monkeypatch):
    monkeypatch.delenv("KLING_API_KEY", raising=False)
    client = KlingClient(session=FakeSession([]))
    with pytest.raises(KlingAPIError) as exc:
        _ = client.headers
    assert "KLING_API_KEY" in str(exc.value)


def test_headers_use_bearer_api_key(monkeypatch):
    monkeypatch.setenv("KLING_API_KEY", "test-key")
    session = FakeSession([FakeResponse({"code": 0, "data": {"ok": True}})])
    client = KlingClient(session=session)
    client.post("/v1/test", {"prompt": "x"})
    headers = session.calls[0][2]["headers"]
    assert headers["Authorization"] == "Bearer test-key"
    assert headers["Content-Type"] == "application/json"


def test_default_and_env_base_url(monkeypatch):
    monkeypatch.setenv("KLING_API_KEY", "test-key")
    monkeypatch.delenv("KLING_API_BASE_URL", raising=False)
    assert KlingClient().base_url == DEFAULT_API_BASE_URL
    monkeypatch.setenv("KLING_API_BASE_URL", "https://api-beijing.klingai.com")
    assert KlingClient().base_url == "https://api-beijing.klingai.com"


def test_business_error_preserves_code_message_request_id(monkeypatch):
    monkeypatch.setenv("KLING_API_KEY", "test-key")
    session = FakeSession([FakeResponse({"code": 1200, "message": "bad parameter", "request_id": "req-1"})])
    client = KlingClient(session=session, max_retries=0)
    with pytest.raises(KlingAPIError) as exc:
        client.post("/v1/videos/text2video", {})
    assert exc.value.code == 1200
    assert exc.value.message == "bad parameter"
    assert exc.value.request_id == "req-1"


def test_1303_retryable_message_mentions_concurrency(monkeypatch):
    monkeypatch.setenv("KLING_API_KEY", "test-key")
    session = FakeSession([FakeResponse({"code": 1303, "message": "parallel task over resource pack limit"})])
    client = KlingClient(session=session, max_retries=0)
    with pytest.raises(KlingAPIError) as exc:
        client.post("/v1/videos/text2video", {})
    assert is_retryable_kling_error(exc.value)
    assert "并发/资源包限制" in exc.value.message


def test_classic_create_and_poll_parse_result_paths(monkeypatch):
    monkeypatch.setenv("KLING_API_KEY", "test-key")
    session = FakeSession(
        [
            FakeResponse({"code": 0, "data": {"task_id": "task-1"}}),
            FakeResponse(
                {
                    "code": 0,
                    "data": {
                        "task_status": "succeed",
                        "task_result": {"videos": [{"url": "https://example.com/out.mp4"}]},
                    },
                }
            ),
        ]
    )
    client = KlingClient(session=session)
    task_id = client.create_classic_task("/v1/videos/text2video", {"prompt": "x"})
    outputs = client.poll_classic("/v1/videos/text2video", task_id, "videos")
    assert task_id == "task-1"
    assert outputs == [{"url": "https://example.com/out.mp4"}]


def test_turbo_create_and_poll_parse_result_paths(monkeypatch):
    monkeypatch.setenv("KLING_API_KEY", "test-key")
    session = FakeSession(
        [
            FakeResponse({"code": 0, "data": {"id": "turbo-1"}}),
            FakeResponse(
                {
                    "code": 0,
                    "data": [
                        {
                            "id": "turbo-1",
                            "status": "succeeded",
                            "outputs": [{"url": "https://example.com/out.mp4"}],
                        }
                    ],
                }
            ),
        ]
    )
    client = KlingClient(session=session)
    task_id = client.create_turbo("/text-to-video/kling-3.0-turbo", {"prompt": "x"})
    outputs = client.poll_turbo(task_id)
    assert task_id == "turbo-1"
    assert outputs == [{"url": "https://example.com/out.mp4"}]


def test_schema_snapshot_contains_phase1_contract_fields():
    fixture = PROJECT_ROOT / "tests/fixtures/kling_official/schema_snapshot.json"
    data = json.loads(fixture.read_text())
    assert data["build_id"] == "97939672"
    assert "index-0m3slU3p.js" in data["chunk_names"]
    assert "document-navigation-Dk7H_V3n.js" in data["chunk_names"]
    assert data["api_base"]["auth_env"] == "KLING_API_KEY"
    assert data["task_statuses"]["classic"] == ["submitted", "processing", "succeed", "failed"]
    assert data["task_statuses"]["turbo"] == ["submitted", "processing", "succeeded", "failed"]
    assert data["result_paths"]["classic_created_id"] == "data.task_id"
    assert data["result_paths"]["turbo_created_id"] == "data.id"
    assert "kling-v3" in data["models"]["video"]
    assert "kling-v3" in data["models"]["image"]
    assert data["endpoints"]["tts"]["path"] == "/v1/audio/tts"
    assert data["endpoints"]["avatar_image_to_video"]["path"] == "/v1/videos/avatar/image2video"
    assert data["endpoints"]["identify_face"]["path"] == "/v1/videos/identify-face"
    assert data["endpoints"]["advanced_lip_sync"]["path"] == "/v1/videos/advanced-lip-sync"
    assert data["endpoints"]["video_effects"]["path"] == "/v1/videos/effects"
    assert data["result_paths"]["classic_audio_results"] == "data.task_result.audios[]"
    assert data["result_paths"]["identify_face_session"] == "data.session_id"
    assert data["result_paths"]["identify_face_results"] == "data.face_data[]"
    assert data["core_field_enums"]["tts_voice_language"] == ["zh", "en"]
    assert data["core_field_enums"]["avatar_mode"] == ["std", "pro"]


def test_optional_live_doc_snapshot_check():
    if os.environ.get("RUN_KLING_DOC_LIVE_CHECK") != "1":
        pytest.skip("Set RUN_KLING_DOC_LIVE_CHECK=1 to compare fixture against current Kling docs HTML.")
    import re
    import urllib.request

    fixture = PROJECT_ROOT / "tests/fixtures/kling_official/schema_snapshot.json"
    expected = json.loads(fixture.read_text())
    with urllib.request.urlopen("https://kling.ai/document-api/api/video/3-0-turbo/text-to-video", timeout=20) as response:
        html = response.read().decode("utf-8", errors="ignore")
    match = re.search(r'<meta name="buildId" content="([^"]+)"', html)
    assert match, "Kling official docs HTML no longer exposes buildId; refresh schema fixture."
    assert match.group(1) == expected["build_id"], "Kling official docs buildId changed; refresh schema fixture before implementation."


def test_elements_helper_normalizes_and_records_metadata(tmp_path):
    assert normalize_element_list([123, {"element_id": "456"}]) == [
        {"element_id": 123},
        {"element_id": 456},
    ]
    artifact = write_elements_artifact(
        tmp_path / "kling_elements.json",
        [{"element_id": 123, "kind": "character", "name": "main-presenter"}],
    )
    data = json.loads(artifact.read_text())
    assert data["provider"] == "kling_official"
    assert data["elements"][0]["element_id"] == 123

    try:
        normalize_element_list([{"name": "missing-id"}])
    except ValueError as exc:
        assert "element_id" in str(exc)
    else:
        raise AssertionError("element_list items without element_id must be rejected")


def test_elements_helper_read_only_endpoints_do_not_enter_registry(isolated_tool_registry):
    fake = HelperFakeClient()
    assert get_custom_element(123, client=fake)["data"]["element_id"] == 123
    assert list_custom_elements(client=fake)["data"][0]["element_id"] == 456
    assert list_preset_elements(client=fake)["data"][0]["element_id"] == 1
    assert fake.calls == [
        ("/v1/general/advanced-custom-elements/123", {}),
        ("/v1/general/advanced-custom-elements", {}),
        ("/v1/general/advanced-presets-elements", {}),
    ]
    import tools._kling.elements as elements_module

    assert not hasattr(elements_module, "create_element")
    assert not hasattr(elements_module, "delete_element")

    isolated_tool_registry.discover("tools")
    assert isolated_tool_registry.get("kling_elements") is None
    assert isolated_tool_registry.get("kling_account_usage") is None


def test_account_usage_helper_uses_endpoint_cache_and_throttle():
    reset_account_usage_cache()
    fake = HelperFakeClient()
    first = get_account_costs(
        start_time="2026-07-01",
        end_time="2026-07-03",
        client=fake,
        now=100.0,
    )
    second = get_account_costs(
        start_time="2026-07-01",
        end_time="2026-07-03",
        client=fake,
        now=101.0,
    )
    throttled = get_account_costs(
        resource_pack_name="different",
        client=fake,
        now=102.0,
    )

    assert fake.calls == [
        ("/account/costs", {"start_time": "2026-07-01", "end_time": "2026-07-03"})
    ]
    assert first["throttle_status"] == "fresh"
    assert second["cached"] is True
    assert second["throttle_status"] == "cache_hit"
    assert throttled["throttle_status"] == "throttled_no_cache"


def test_account_usage_cache_is_scoped_by_api_identity():
    reset_account_usage_cache()
    first_client = HelperFakeClient(api_key="account-a")
    second_client = HelperFakeClient(api_key="account-b")

    get_account_costs(client=first_client, now=100.0)
    get_account_costs(client=second_client, now=111.0)
    cached = get_account_costs(client=second_client, now=112.0)

    assert first_client.calls == [("/account/costs", {})]
    assert second_client.calls == [("/account/costs", {})]
    assert cached["cached"] is True


def test_account_usage_helper_uses_kling_auth_header(monkeypatch):
    reset_account_usage_cache()
    monkeypatch.setenv("KLING_API_KEY", "test-key")
    session = HelperFakeSession()
    client = KlingClient(session=session, max_retries=0)

    result = get_account_costs(
        start_time="2026-07-01",
        end_time="2026-07-03",
        resource_pack_name="starter",
        client=client,
        now=200.0,
    )

    assert result["resource_pack_subscribe_infos"][0]["name"] == "pack-a"
    method, url, kwargs = session.calls[0]
    assert method == "get"
    assert url.endswith("/account/costs")
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert kwargs["params"] == {
        "start_time": "2026-07-01",
        "end_time": "2026-07-03",
        "resource_pack_name": "starter",
    }


def test_env_example_documents_kling_official_keys():
    env = read(".env.example")
    assert "KLING_API_KEY=" in env
    assert "KLING_API_BASE_URL=" in env


def test_provider_docs_distinguish_fal_and_official_kling():
    providers = read("docs/PROVIDERS.md")
    assert "Kling Official" in providers
    assert "kling_official_video" in providers
    assert "kling_official_image" in providers
    assert "kling_tts" in providers
    assert "kling_avatar" in providers
    assert "kling_lip_sync" in providers
    assert "fal.ai" in providers
    assert "provider=\"kling_official\"" in providers
    assert "provider=\"kling\"" in providers
    assert "Elements remain an internal Kling Official helper" in providers
    assert "Account Usage is available as a low-frequency diagnostic helper" in providers
    assert "callback_url" in providers
    assert "audio effects and video effects are documented but intentionally not registered" in providers


def test_architecture_env_mapping_includes_kling_official():
    architecture = read("docs/ARCHITECTURE.md")
    assert "`KLING_API_KEY` | kling_official_video, kling_official_image, kling_tts, kling_avatar, kling_lip_sync" in architecture
    assert "`KLING_API_BASE_URL` | kling_official_video, kling_official_image, kling_tts, kling_avatar, kling_lip_sync" in architecture
    assert "Elements and Account" in architecture
    assert "not separate pipeline stages" in architecture
    assert "Kling Official also adds provider tools only where OpenMontage already has a" in architecture


def test_ai_video_skill_metadata_and_new_skill_link():
    ai_video = read(".agents/skills/ai-video-gen/SKILL.md")
    index = read("skills/INDEX.md")
    creative = read("skills/creative/video-gen-prompting.md")
    official_skill = PROJECT_ROOT / ".agents/skills/kling-official/SKILL.md"

    assert "KLING_API_KEY" in ai_video
    assert "kling_official_video" in ai_video
    assert "kling_tts" in index
    assert "avatar/lip-sync face selection" in index
    assert ".agents/skills/kling-official/" in creative
    assert official_skill.is_file()
    official_skill_text = official_skill.read_text(encoding="utf-8")
    assert "Omni References" in official_skill_text
    assert "Callback Notes" in official_skill_text
    assert "TTS Parameters" in official_skill_text
    assert "Lip Sync Parameters" in official_skill_text
    assert "Audio Effects And Video Effects" in official_skill_text


def test_provider_agent_skills_reference_kling_official():
    assert "kling-official" in KlingOfficialVideo().agent_skills
    assert "kling-official" in KlingOfficialImage().agent_skills
    assert "kling-official" in KlingTTS().agent_skills
    assert "kling-official" in KlingAvatar().agent_skills
    assert "kling-official" in KlingLipSync().agent_skills


@pytest.mark.parametrize(
    ("tool", "output_variants"),
    [
        (
            KlingOfficialVideo(),
            {
                "prompt": "changed prompt",
                "operation": "image_to_video",
                "api_family": "omni",
                "model_name": "kling-v2-6",
                "model_variant": "kling-v2-5-turbo",
                "duration": "10",
                "aspect_ratio": "9:16",
                "resolution": "1080p",
                "mode": "pro",
                "sound": "on",
                "negative_prompt": "blur",
                "cfg_scale": 0.7,
                "reference_image_url": "https://example.com/first.png",
                "reference_image_path": "/tmp/first.png",
                "reference_tail_image_url": "https://example.com/tail.png",
                "reference_tail_image_path": "/tmp/tail.png",
                "reference_image_urls": ["https://example.com/ref.png"],
                "reference_image_paths": ["/tmp/ref.png"],
                "reference_video_url": "https://example.com/ref.mp4",
                "video_urls": ["https://example.com/ref-2.mp4"],
                "image_list": [{"image_url": "https://example.com/list.png"}],
                "video_list": [{"video_url": "https://example.com/list.mp4"}],
                "element_list": [{"element_id": 123}],
                "multi_shot": True,
                "shot_type": "intelligence",
                "multi_prompt": [{"prompt": "second shot", "duration": "3"}],
                "camera_control": {"type": "simple", "config": {"horizontal": 1}},
                "watermark": True,
            },
        ),
        (
            KlingOfficialImage(),
            {
                "prompt": "changed prompt",
                "negative_prompt": "blur",
                "operation": "omni",
                "api_family": "omni",
                "model_name": "kling-image-o1",
                "image_url": "https://example.com/source.png",
                "image_path": "/tmp/source.png",
                "image_urls": ["https://example.com/ref.png"],
                "image_paths": ["/tmp/ref.png"],
                "image_list": [{"image_url": "https://example.com/list.png"}],
                "image_reference": "subject",
                "image_fidelity": 0.7,
                "human_fidelity": 0.8,
                "resolution": "2k",
                "aspect_ratio": "1:1",
                "n": 2,
                "result_type": "series",
                "series_amount": "3",
                "element_list": [{"element_id": 123}],
                "watermark": True,
            },
        ),
        (
            KlingAvatar(),
            {
                "image_url": "https://example.com/avatar.png",
                "image_path": "/tmp/avatar.png",
                "audio_id": "audio-a",
                "sound_file": "inline-audio",
                "sound_file_url": "https://example.com/audio.mp3",
                "sound_file_path": "/tmp/audio.mp3",
                "audio_path": "/tmp/audio-alias.mp3",
                "prompt": "natural presenter motion",
                "mode": "pro",
            },
        ),
        (
            KlingLipSync(),
            {
                "operation": "full_lip_sync",
                "video_id": "video-a",
                "video_url": "https://example.com/video.mp4",
                "session_id": "session-a",
                "face_id": "face-a",
                "face_choose": [{"face_id": "face-a", "audio_id": "audio-a"}],
                "auto_select_face": True,
                "audio_id": "audio-a",
                "sound_file": "inline-audio",
                "sound_file_url": "https://example.com/audio.mp3",
                "sound_file_path": "/tmp/audio.mp3",
                "audio_path": "/tmp/audio-alias.mp3",
                "sound_start_time": 100,
                "sound_end_time": 4100,
                "sound_insert_time": 500,
                "sound_volume": 1.2,
                "original_audio_volume": 0.4,
            },
        ),
    ],
)
def test_kling_output_inputs_change_idempotency_keys(tool, output_variants):
    baseline = tool.idempotency_key({})
    collisions = [
        field
        for field, value in output_variants.items()
        if tool.idempotency_key({field: value}) == baseline
    ]

    assert collisions == [], f"{tool.name} idempotency key ignores: {collisions}"


def test_phase3_does_not_register_audio_or_video_effect_tools(isolated_tool_registry):
    isolated_tool_registry.discover("tools")
    assert isolated_tool_registry.get("kling_audio") is None
    assert isolated_tool_registry.get("kling_effects") is None
