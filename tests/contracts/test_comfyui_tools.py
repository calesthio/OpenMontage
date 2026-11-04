"""Contract tests for ComfyUI provider tools.

These tests verify that the tools satisfy the BaseTool contract without
requiring a running ComfyUI server.  They check class attributes,
schemas, status reporting, and cost estimates.
"""

import json
from pathlib import Path

import pytest

from tools.base_tool import (
    BaseTool,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)
from tools.audio.comfyui_music import ComfyUIMusic
from tools.graphics.comfyui_image import ComfyUIImage
from tools.graphics.image_selector import ImageSelector
from tools.tool_registry import ToolRegistry
from tools.video.video_selector import VideoSelector
from tools.video.comfyui_video import ComfyUIVideo

TOOLS = [ComfyUIImage, ComfyUIVideo, ComfyUIMusic]
WORKFLOW_DIR = Path(__file__).resolve().parent.parent.parent / "tools" / "_comfyui" / "workflows"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ------------------------------------------------------------------
# Contract compliance
# ------------------------------------------------------------------

@pytest.mark.parametrize("cls", TOOLS, ids=lambda c: c.name)
class TestContract:

    def test_inherits_base_tool(self, cls):
        assert issubclass(cls, BaseTool)

    def test_has_required_identity(self, cls):
        tool = cls()
        assert tool.name
        assert tool.version
        assert tool.capability
        assert tool.provider == "comfyui"
        assert tool.tier == ToolTier.GENERATE
        assert tool.stability == ToolStability.EXPERIMENTAL
        assert tool.runtime == ToolRuntime.LOCAL_GPU

    def test_has_input_schema(self, cls):
        tool = cls()
        schema = tool.input_schema
        assert schema.get("type") == "object"
        assert "prompt" in schema.get("properties", {})
        assert "prompt" in schema.get("required", [])

    def test_has_capabilities(self, cls):
        tool = cls()
        assert len(tool.capabilities) > 0

    def test_has_agent_skills(self, cls):
        tool = cls()
        assert tool.agent_skills
        assert "comfyui" in tool.agent_skills

    def test_comfyui_layer3_skill_exists(self, cls):
        skill_path = PROJECT_ROOT / ".agents" / "skills" / "comfyui" / "SKILL.md"
        assert skill_path.exists()
        assert "output_node" in skill_path.read_text(encoding="utf-8")

    def test_has_fallbacks(self, cls):
        tool = cls()
        assert tool.fallback or tool.fallback_tools

    def test_cost_is_zero(self, cls):
        tool = cls()
        assert tool.estimate_cost({"prompt": "test"}) == 0.0

    def test_runtime_estimate_positive(self, cls):
        tool = cls()
        assert tool.estimate_runtime({"prompt": "test"}) > 0

    def test_get_info_returns_dict(self, cls):
        tool = cls()
        info = tool.get_info()
        assert isinstance(info, dict)
        assert info["name"] == tool.name
        assert info["provider"] == "comfyui"
        assert info["runtime"] == "local_gpu"
        assert info["setup_offer"]["env_var"] == "COMFYUI_SERVER_URL"

    def test_video_resource_profile_does_not_mandate_16gb(self, cls):
        if cls is not ComfyUIVideo:
            return
        tool = ComfyUIVideo()
        info = tool.get_info()
        assert info["resource_profile"]["vram_mb"] == 8000
        assert info["resource_profiles"]["provider_floor"]["vram_mb"] == 8000
        assert info["resource_profiles"]["bundled_wan22_14b_fp8"]["vram_mb"] == 16000
        assert "not a ComfyUI provider-wide requirement" in (
            info["resource_profiles"]["bundled_wan22_14b_fp8"]["applies_to"]
        )

    def test_status_unavailable_without_server(self, cls):
        """Without a running server, status should be UNAVAILABLE."""
        tool = cls()
        # Point to a port that's almost certainly not running ComfyUI
        tool._client.server_url = "http://127.0.0.1:19999"
        assert tool.get_status() == ToolStatus.UNAVAILABLE

    def test_idempotency_key_fields(self, cls):
        tool = cls()
        assert len(tool.idempotency_key_fields) > 0
        assert "prompt" in tool.idempotency_key_fields

    def test_custom_workflow_schema_requires_output_node_contract(self, cls):
        tool = cls()
        props = tool.input_schema.get("properties", {})
        assert "workflow_json" in props
        assert "workflow_path" in props
        assert "output_node" in props

    def test_custom_workflow_requires_output_node(self, cls):
        tool = cls()
        result = tool.execute({"prompt": "test", "workflow_json": "{}"})
        assert result.success is False
        assert "output_node" in result.error


# ------------------------------------------------------------------
# Workflow files
# ------------------------------------------------------------------

EXPECTED_WORKFLOWS = [
    "flux2-txt2img.json",
    "wan22-i2v-4step.json",
    "wan22-t2v-4step.json",
    "ace-step-1-t2a.json",
]


@pytest.mark.parametrize("filename", EXPECTED_WORKFLOWS)
def test_workflow_exists_and_valid_json(filename):
    path = WORKFLOW_DIR / filename
    assert path.exists(), f"Missing workflow: {path}"
    with open(path) as f:
        data = json.load(f)
    assert isinstance(data, dict)
    assert len(data) > 0


def test_flux2_workflow_has_templated_nodes():
    with open(WORKFLOW_DIR / "flux2-txt2img.json") as f:
        w = json.load(f)
    assert "4" in w  # CLIPTextEncode (prompt)
    assert "7" in w  # RandomNoise (seed)
    assert "13" in w  # SaveImage (output)


def test_i2v_workflow_has_templated_nodes():
    with open(WORKFLOW_DIR / "wan22-i2v-4step.json") as f:
        w = json.load(f)
    assert "93" in w   # CLIPTextEncode (prompt)
    assert "97" in w   # LoadImage (reference)
    assert "86" in w   # KSamplerAdvanced (seed)
    assert "108" in w  # SaveVideo (output)


def test_t2v_workflow_has_templated_nodes():
    with open(WORKFLOW_DIR / "wan22-t2v-4step.json") as f:
        w = json.load(f)
    assert "2" in w   # CLIPTextEncode (prompt)
    assert "12" in w  # KSamplerAdvanced (seed)
    assert "16" in w  # SaveVideo (output)


def test_t2v_workflow_latent_is_temporal_not_an_image_batch():
    """A video model needs a video latent. This is not pedantry.

    Node 11 was an ``EmptyLatentImage`` with ``batch_size`` set to the frame
    count from the workflow's first commit until it was found by inspection.
    That asks for N unrelated images rather than one N-frame video, and the
    resulting mp4 has the right frame count, the right duration, the right
    codec and a clean ffprobe -- it just strobes. Every structural test in this
    file passed the whole time, because they checked that nodes existed rather
    than what they were.

    ComfyUI's own ``video_wan2_2_14B_t2v`` template uses
    ``EmptyHunyuanLatentVideo``; the i2v sibling in this directory has always
    used ``WanImageToVideo`` correctly.
    """
    with open(WORKFLOW_DIR / "wan22-t2v-4step.json") as f:
        w = json.load(f)
    latent = w["11"]
    assert latent["class_type"] != "EmptyLatentImage", (
        "node 11 is an image latent; output will be unrelated stills that "
        "strobe inside a structurally valid mp4"
    )
    assert latent["class_type"] in {
        "EmptyHunyuanLatentVideo",
        "Wan22ImageToVideoLatent",
        "WanImageToVideo",
    }, f"unexpected latent node {latent['class_type']!r}"
    inputs = latent["inputs"]
    assert "length" in inputs, "a temporal latent carries the frame count in `length`"
    assert inputs["length"] > 1, "a single-frame latent is not a video"
    assert inputs.get("batch_size", 1) == 1, (
        "batch_size is how many separate clips to generate, not how many "
        "frames each has -- setting it to the frame count is the original bug"
    )


def test_t2v_builder_patches_frame_count_into_length_not_batch_size():
    """The builder must not put the frame count back where it does not belong.

    Fixing the workflow alone is not enough: ``_build_t2v`` patches node 11 on
    every call, so a builder still writing ``batch_size: num_frames`` would
    reintroduce the bug against a corrected workflow.
    """
    from tools.video.comfyui_video import ComfyUIVideo

    workflow, _ = ComfyUIVideo()._build_t2v(
        {"prompt": "x", "width": 832, "height": 480, "num_frames": 81},
        seed=1,
        output_path=Path("out.mp4"),
    )
    assert workflow["11"]["inputs"]["length"] == 81
    assert workflow["11"]["inputs"]["batch_size"] == 1


def test_t2v_workflow_uses_14b_compatible_vae():
    with open(WORKFLOW_DIR / "wan22-t2v-4step.json") as f:
        w = json.load(f)
    assert w["4"]["inputs"]["vae_name"] == "wan_2.1_vae.safetensors"


def test_t2v_metadata_stack_uses_14b_compatible_vae():
    from tools._comfyui.metadata import BUNDLED_MODEL_STACKS

    vae_entry = next(item for item in BUNDLED_MODEL_STACKS["wan22-t2v-4step"] if item["role"] == "vae")
    assert vae_entry["name"] == "wan_2.1_vae.safetensors"
    assert "Wan_2.1_ComfyUI_repackaged" in vae_entry["download_url"]


# ------------------------------------------------------------------
# Client unit tests
# ------------------------------------------------------------------

class TestClientHelpers:

    def test_load_workflow(self):
        from tools._comfyui.client import ComfyUIClient
        w = ComfyUIClient.load_workflow(WORKFLOW_DIR / "flux2-txt2img.json")
        assert isinstance(w, dict)
        assert "1" in w

    def test_patch_workflow(self):
        from tools._comfyui.client import ComfyUIClient
        w = ComfyUIClient.load_workflow(WORKFLOW_DIR / "flux2-txt2img.json")
        patched = ComfyUIClient.patch_workflow(w, {
            "4": {"text": "hello world"},
            "7": {"noise_seed": 123},
        })
        assert patched["4"]["inputs"]["text"] == "hello world"
        assert patched["7"]["inputs"]["noise_seed"] == 123
        # Original unchanged
        assert w["4"]["inputs"]["text"] == ""

    def test_patch_workflow_bad_node(self):
        from tools._comfyui.client import ComfyUIClient, ComfyUIError
        w = {"1": {"inputs": {"x": 1}}}
        with pytest.raises(ComfyUIError, match="not found"):
            ComfyUIClient.patch_workflow(w, {"99": {"x": 2}})

    def test_submit_surfaces_node_errors_before_http_error(self, monkeypatch):
        from tools._comfyui.client import ComfyUIClient, ComfyUIError

        class FakeResponse:
            status_code = 400

            def json(self):
                return {
                    "error": {"message": "Prompt outputs failed validation"},
                    "node_errors": {"4": {"class_type": "MissingNode"}},
                }

            def raise_for_status(self):
                raise AssertionError("HTTPError should not hide node_errors")

        monkeypatch.setattr(
            "tools._comfyui.client.requests.post",
            lambda *args, **kwargs: FakeResponse(),
        )

        with pytest.raises(ComfyUIError, match="Node errors"):
            ComfyUIClient("http://comfy.test").submit({})

    def test_random_seed_range(self):
        from tools._comfyui.client import ComfyUIClient
        for _ in range(100):
            s = ComfyUIClient.random_seed()
            assert 0 <= s < 2**32

    def test_generate_passes_history_item_type_to_view(self, monkeypatch, tmp_path):
        from tools._comfyui.client import ComfyUIClient

        client = ComfyUIClient("http://comfy.test")
        seen = {}

        monkeypatch.setattr(client, "submit", lambda workflow: "prompt-1")
        monkeypatch.setattr(client, "poll", lambda prompt_id, **kwargs: {
            "outputs": {
                "9": {
                    "images": [{
                        "filename": "preview.png",
                        "subfolder": "previews",
                        "type": "temp",
                    }]
                }
            }
        })

        def fake_download(filename, subfolder, dest, folder_type="output"):
            seen["filename"] = filename
            seen["subfolder"] = subfolder
            seen["folder_type"] = folder_type
            return Path(dest)

        monkeypatch.setattr(client, "download", fake_download)

        client.generate({"9": {"inputs": {}}}, "9", tmp_path / "preview.png")

        assert seen == {
            "filename": "preview.png",
            "subfolder": "previews",
            "folder_type": "temp",
        }

    def test_poll_timeout_carries_prompt_id_for_recovery(self, monkeypatch):
        from tools._comfyui.client import ComfyUIClient, ComfyUIError

        client = ComfyUIClient("http://comfy.test")
        monkeypatch.setattr(
            "tools._comfyui.client.requests.get",
            lambda *a, **k: type("R", (), {
                "raise_for_status": lambda self: None,
                "json": lambda self: {},
            })(),
        )
        monkeypatch.setattr("tools._comfyui.client.time.sleep", lambda s: None)

        with pytest.raises(ComfyUIError) as excinfo:
            client.poll("prompt-timeout-1", timeout=0, interval=0)

        assert excinfo.value.prompt_id == "prompt-timeout-1"
        assert "prompt-timeout-1" in str(excinfo.value)

    def test_generate_resume_prompt_id_skips_resubmit(self, monkeypatch, tmp_path):
        from tools._comfyui.client import ComfyUIClient
        import sys

        client = ComfyUIClient("http://comfy.test")

        def fail_submit(workflow):
            raise AssertionError("submit() should not be called when resuming")

        monkeypatch.setattr(client, "submit", fail_submit)
        _install_fake_websocket(monkeypatch, frames=[])
        monkeypatch.setattr(
            sys.modules["websocket"],
            "create_connection",
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("resumed jobs must use history polling")
            ),
        )
        monkeypatch.setattr(client, "poll", lambda prompt_id, **kwargs: {
            "outputs": {"9": {"images": [{
                "filename": "resumed.png", "subfolder": "", "type": "output",
            }]}}
        })
        monkeypatch.setattr(client, "download", lambda filename, subfolder, dest, folder_type="output": Path(dest))

        paths = client.generate(
            {"9": {"inputs": {}}}, "9", tmp_path / "out.png",
            resume_prompt_id="already-running-id",
        )
        assert paths == [tmp_path / "out.png"]

    def test_generate_reads_audio_key_from_savaudio_node(self, monkeypatch, tmp_path):
        """The native SaveAudio node writes outputs under "audio", not
        "images"/"gifs" -- comfyui_music depends on this being handled."""
        from tools._comfyui.client import ComfyUIClient

        client = ComfyUIClient("http://comfy.test")
        monkeypatch.setattr(client, "submit", lambda workflow: "p1")
        monkeypatch.setattr(client, "poll", lambda prompt_id, **kwargs: {
            "outputs": {"9": {"audio": [{
                "filename": "track.flac", "subfolder": "", "type": "output",
            }]}}
        })
        monkeypatch.setattr(client, "download", lambda filename, subfolder, dest, folder_type="output": Path(dest))

        paths = client.generate({"9": {"inputs": {}}}, "9", tmp_path / "out.flac")
        assert paths == [tmp_path / "out.flac"]

    def test_is_default_url_when_env_not_set(self, monkeypatch):
        from tools._comfyui.client import ComfyUIClient
        monkeypatch.delenv("COMFYUI_SERVER_URL", raising=False)
        client = ComfyUIClient()
        assert client.is_default_url is True

    def test_is_not_default_url_when_env_set(self, monkeypatch):
        from tools._comfyui.client import ComfyUIClient
        monkeypatch.setenv("COMFYUI_SERVER_URL", "http://myhost:9999")
        client = ComfyUIClient()
        assert client.is_default_url is False

    def test_unavailable_reason_default_url(self, monkeypatch):
        from tools._comfyui.client import ComfyUIClient
        monkeypatch.delenv("COMFYUI_SERVER_URL", raising=False)
        client = ComfyUIClient()
        msg = client.unavailable_reason()
        assert "COMFYUI_SERVER_URL" in msg
        assert ".env" in msg

    def test_unavailable_reason_custom_url(self, monkeypatch):
        from tools._comfyui.client import ComfyUIClient
        monkeypatch.setenv("COMFYUI_SERVER_URL", "http://myhost:9999")
        client = ComfyUIClient()
        msg = client.unavailable_reason()
        assert "myhost:9999" in msg
        assert "COMFYUI_SERVER_URL" not in msg

    def test_submit_includes_client_id_for_websocket_targeting(self, monkeypatch):
        from tools._comfyui.client import ComfyUIClient

        client = ComfyUIClient("http://comfy.test")
        seen = {}

        def fake_post(url, json=None, timeout=None):
            seen.update(json)
            return type("R", (), {
                "raise_for_status": lambda self: None,
                "json": lambda self: {"prompt_id": "abc"},
            })()

        monkeypatch.setattr("tools._comfyui.client.requests.post", fake_post)
        client.submit({"1": {"inputs": {}}})
        assert seen["client_id"] == client.client_id


class TestMultiServer:

    def test_capability_env_var_takes_priority_over_shared(self, monkeypatch):
        from tools._comfyui.client import ComfyUIClient

        monkeypatch.setenv("COMFYUI_SERVER_URL", "http://shared:8188")
        monkeypatch.setenv("COMFYUI_VIDEO_SERVER_URL", "http://video-gpu:8188")
        client = ComfyUIClient(capability="video")
        assert client.server_url == "http://video-gpu:8188"

    def test_falls_back_to_shared_when_capability_var_unset(self, monkeypatch):
        from tools._comfyui.client import ComfyUIClient

        monkeypatch.setenv("COMFYUI_SERVER_URL", "http://shared:8188")
        monkeypatch.delenv("COMFYUI_IMAGE_SERVER_URL", raising=False)
        client = ComfyUIClient(capability="image")
        assert client.server_url == "http://shared:8188"

    def test_other_capability_env_var_does_not_leak_across_tools(self, monkeypatch):
        from tools._comfyui.client import ComfyUIClient

        monkeypatch.delenv("COMFYUI_SERVER_URL", raising=False)
        monkeypatch.setenv("COMFYUI_IMAGE_SERVER_URL", "http://image-gpu:8188")
        monkeypatch.delenv("COMFYUI_VIDEO_SERVER_URL", raising=False)
        video_client = ComfyUIClient(capability="video")
        assert video_client.server_url == "http://localhost:8188"

    def test_explicit_server_url_wins_over_capability_env_var(self, monkeypatch):
        from tools._comfyui.client import ComfyUIClient

        monkeypatch.setenv("COMFYUI_VIDEO_SERVER_URL", "http://video-gpu:8188")
        client = ComfyUIClient("http://explicit:1234", capability="video")
        assert client.server_url == "http://explicit:1234"

    def test_no_capability_behaves_as_before(self, monkeypatch):
        from tools._comfyui.client import ComfyUIClient

        monkeypatch.setenv("COMFYUI_SERVER_URL", "http://shared:8188")
        client = ComfyUIClient()
        assert client.server_url == "http://shared:8188"
        assert client.is_default_url is False

    def test_is_default_url_true_only_when_both_vars_unset(self, monkeypatch):
        from tools._comfyui.client import ComfyUIClient

        monkeypatch.delenv("COMFYUI_SERVER_URL", raising=False)
        monkeypatch.delenv("COMFYUI_IMAGE_SERVER_URL", raising=False)
        client = ComfyUIClient(capability="image")
        assert client.is_default_url is True

        monkeypatch.setenv("COMFYUI_IMAGE_SERVER_URL", "http://image-gpu:8188")
        client2 = ComfyUIClient(capability="image")
        assert client2.is_default_url is False

    def test_unavailable_reason_mentions_capability_and_shared_var(self, monkeypatch):
        from tools._comfyui.client import ComfyUIClient

        monkeypatch.delenv("COMFYUI_SERVER_URL", raising=False)
        monkeypatch.delenv("COMFYUI_VIDEO_SERVER_URL", raising=False)
        client = ComfyUIClient(capability="video")
        msg = client.unavailable_reason()
        assert "COMFYUI_VIDEO_SERVER_URL" in msg
        assert "COMFYUI_SERVER_URL" in msg

    def test_image_and_video_tools_use_independent_servers(self, monkeypatch):
        from tools.graphics.comfyui_image import ComfyUIImage
        from tools.video.comfyui_video import ComfyUIVideo

        monkeypatch.delenv("COMFYUI_SERVER_URL", raising=False)
        monkeypatch.setenv("COMFYUI_IMAGE_SERVER_URL", "http://image-gpu:8188")
        monkeypatch.setenv("COMFYUI_VIDEO_SERVER_URL", "http://video-gpu:8188")

        image_tool = ComfyUIImage()
        video_tool = ComfyUIVideo()

        assert image_tool._client.server_url == "http://image-gpu:8188"
        assert video_tool._client.server_url == "http://video-gpu:8188"


class _FakeWSTimeout(Exception):
    pass


class _FakeWSConn:
    def __init__(self, frames):
        self._frames = list(frames)

    def settimeout(self, value):
        pass

    def recv(self):
        if not self._frames:
            raise _FakeWSTimeout()
        return self._frames.pop(0)

    def close(self):
        pass


def _install_fake_websocket(monkeypatch, frames):
    """Inject a fake `websocket` module so wait_ws() runs without the real
    optional websocket-client dependency installed."""
    import sys
    import types

    fake_module = types.SimpleNamespace(
        WebSocketTimeoutException=_FakeWSTimeout,
        create_connection=lambda url, timeout=10: _FakeWSConn(frames),
    )
    monkeypatch.setitem(sys.modules, "websocket", fake_module)


class TestWebsocketWait:

    def test_wait_ws_returns_job_completed_before_connection(self, monkeypatch):
        from tools._comfyui.client import ComfyUIClient
        import sys

        client = ComfyUIClient("http://comfy.test")
        _install_fake_websocket(monkeypatch, frames=[])
        monkeypatch.setattr(
            sys.modules["websocket"],
            "create_connection",
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("completed history must avoid websocket connection")
            ),
        )
        monkeypatch.setattr(
            "tools._comfyui.client.requests.get",
            lambda *a, **k: type("R", (), {
                "raise_for_status": lambda self: None,
                "json": lambda self: {"done": {"outputs": {"9": {}}}},
            })(),
        )

        assert client.wait_ws("done", timeout=5) == {"outputs": {"9": {}}}

    def test_wait_ws_completes_on_executing_none_node(self, monkeypatch, tmp_path):
        from tools._comfyui.client import ComfyUIClient

        client = ComfyUIClient("http://comfy.test")
        progress_events = []
        frames = [
            json.dumps({"type": "progress", "data": {
                "value": 2, "max": 20, "prompt_id": "p1",
            }}),
            json.dumps({"type": "executing", "data": {
                "node": None, "prompt_id": "p1",
            }}),
        ]
        _install_fake_websocket(monkeypatch, frames)
        history_calls = iter(({}, {}, {"p1": {"outputs": {"9": {}}}}))
        monkeypatch.setattr(
            "tools._comfyui.client.requests.get",
            lambda *a, **k: type("R", (), {
                "raise_for_status": lambda self: None,
                "json": lambda self: next(history_calls),
            })(),
        )

        entry = client.wait_ws("p1", timeout=5, on_progress=progress_events.append)

        assert entry == {"outputs": {"9": {}}}
        assert progress_events == [{"value": 2, "max": 20, "prompt_id": "p1"}]

    def test_wait_ws_execution_error_raises_with_prompt_id(self, monkeypatch):
        from tools._comfyui.client import ComfyUIClient, ComfyUIError

        client = ComfyUIClient("http://comfy.test")
        frames = [
            json.dumps({"type": "execution_error", "data": {
                "prompt_id": "p2", "exception_message": "boom",
            }}),
        ]
        _install_fake_websocket(monkeypatch, frames)

        with pytest.raises(ComfyUIError) as excinfo:
            client.wait_ws("p2", timeout=5)

        assert excinfo.value.prompt_id == "p2"

    def test_wait_ws_ignores_other_prompts_on_shared_connection(self, monkeypatch):
        from tools._comfyui.client import ComfyUIClient

        client = ComfyUIClient("http://comfy.test")
        frames = [
            # Another job's event on the same client_id -- must not trigger completion.
            json.dumps({"type": "executing", "data": {
                "node": None, "prompt_id": "someone-elses-job",
            }}),
            json.dumps({"type": "executing", "data": {
                "node": None, "prompt_id": "p3",
            }}),
        ]
        _install_fake_websocket(monkeypatch, frames)
        monkeypatch.setattr(
            "tools._comfyui.client.requests.get",
            lambda *a, **k: type("R", (), {
                "raise_for_status": lambda self: None,
                "json": lambda self: {"p3": {"outputs": {}}},
            })(),
        )

        entry = client.wait_ws("p3", timeout=5)
        assert entry == {"outputs": {}}

    def test_wait_ws_timeout_raises_comfyuierror_with_prompt_id(self, monkeypatch):
        from tools._comfyui.client import ComfyUIClient, ComfyUIError

        client = ComfyUIClient("http://comfy.test")
        _install_fake_websocket(monkeypatch, frames=[])  # recv() always times out

        with pytest.raises(ComfyUIError) as excinfo:
            client.wait_ws("p4", timeout=0)

        assert excinfo.value.prompt_id == "p4"

    def test_wait_falls_back_to_poll_when_websocket_unavailable(self, monkeypatch):
        """No websocket-client installed (or any transport failure) must
        silently fall back to REST polling, not blow up the whole call."""
        from tools._comfyui.client import ComfyUIClient
        import sys

        client = ComfyUIClient("http://comfy.test")
        monkeypatch.delitem(sys.modules, "websocket", raising=False)
        monkeypatch.setattr(
            "builtins.__import__",
            _raise_on_websocket_import(__import__),
        )
        monkeypatch.setattr(
            client, "poll", lambda prompt_id, **kwargs: {"outputs": {"used": "poll"}}
        )

        entry = client._wait("p5", timeout=5, interval=5)
        assert entry == {"outputs": {"used": "poll"}}

    def test_wait_does_not_swallow_genuine_comfyuierror_from_websocket(self, monkeypatch):
        """A real execution error detected over the websocket must propagate,
        not be masked by a fallback-to-poll retry."""
        from tools._comfyui.client import ComfyUIClient, ComfyUIError

        client = ComfyUIClient("http://comfy.test")
        frames = [
            json.dumps({"type": "execution_error", "data": {
                "prompt_id": "p6", "exception_message": "bad node",
            }}),
        ]
        _install_fake_websocket(monkeypatch, frames)

        def fail_poll(prompt_id, **kwargs):
            raise AssertionError("poll() should not be called after a real ws error")

        monkeypatch.setattr(client, "poll", fail_poll)

        with pytest.raises(ComfyUIError) as excinfo:
            client._wait("p6", timeout=5, interval=5)
        assert excinfo.value.prompt_id == "p6"


def _raise_on_websocket_import(real_import):
    def _import(name, *args, **kwargs):
        if name == "websocket":
            raise ImportError("no module named websocket")
        return real_import(name, *args, **kwargs)
    return _import


# ------------------------------------------------------------------
# Model discovery (offline, no server needed)
# ------------------------------------------------------------------

class TestModelRequirements:

    def test_image_tool_has_required_models(self):
        from tools.graphics.comfyui_image import _REQUIRED_MODELS
        assert len(_REQUIRED_MODELS) > 0
        assert any("flux" in m.lower() for m in _REQUIRED_MODELS)

    def test_video_tool_has_required_models_i2v(self):
        from tools.video.comfyui_video import _REQUIRED_MODELS_I2V
        assert len(_REQUIRED_MODELS_I2V) > 0
        assert any("i2v" in m.lower() for m in _REQUIRED_MODELS_I2V)

    def test_video_tool_has_required_models_t2v(self):
        from tools.video.comfyui_video import _REQUIRED_MODELS_T2V
        assert len(_REQUIRED_MODELS_T2V) > 0
        assert any("t2v" in m.lower() for m in _REQUIRED_MODELS_T2V)

    def test_music_tool_has_required_models(self):
        from tools.audio.comfyui_music import _REQUIRED_MODELS
        assert len(_REQUIRED_MODELS) > 0
        assert any("ace_step" in m.lower() for m in _REQUIRED_MODELS)


# ------------------------------------------------------------------
# Custom workflow contract and provenance
# ------------------------------------------------------------------

class TestCustomWorkflowContract:

    def test_image_custom_workflow_uses_caller_output_node_and_provenance(self, tmp_path):
        tool = ComfyUIImage()
        tool._client.is_available = lambda: True
        seen = {}

        def fake_generate(workflow, output_node, dest, **kwargs):
            seen["workflow"] = workflow
            seen["output_node"] = output_node
            return [Path(dest)]

        tool._client.generate = fake_generate

        result = tool.execute({
            "prompt": "test",
            "workflow_json": json.dumps({"99": {"inputs": {}}}),
            "output_node": "99",
            "workflow_model": "custom-flux",
            "output_path": str(tmp_path / "image.png"),
        })

        assert result.success is True
        assert seen["output_node"] == "99"
        assert result.model == "custom-flux"
        assert result.data["model"] == "custom-flux"
        assert result.data["workflow_provenance"]["source"] == "user_supplied"
        assert result.data["workflow_provenance"]["output_node"] == "99"
        assert result.data["workflow_provenance"]["workflow_hash_sha256"]
        assert result.data["workflow_provenance"]["model_stack_source"] == (
            "unknown_custom_workflow"
        )

    def test_video_custom_workflow_uses_caller_output_node_and_provenance(self, tmp_path):
        tool = ComfyUIVideo()
        tool._client.is_available = lambda: True
        seen = {}

        def fake_generate(workflow, output_node, dest, **kwargs):
            seen["workflow"] = workflow
            seen["output_node"] = output_node
            return [Path(dest)]

        tool._client.generate = fake_generate

        result = tool.execute({
            "prompt": "test",
            "workflow_json": json.dumps({"42": {"inputs": {}}}),
            "output_node": "42",
            "workflow_model": "custom-wan",
            "output_path": str(tmp_path / "video.mp4"),
        })

        assert result.success is True
        assert seen["output_node"] == "42"
        assert result.model == "custom-wan"
        assert result.data["model"] == "custom-wan"
        assert result.data["workflow_provenance"]["source"] == "user_supplied"
        assert result.data["workflow_provenance"]["output_node"] == "42"
        assert result.data["workflow_provenance"]["workflow_hash_sha256"]
        assert result.data["workflow_provenance"]["model_stack_source"] == (
            "unknown_custom_workflow"
        )

    def test_custom_workflow_accepts_model_stack_provenance(self, tmp_path):
        tool = ComfyUIVideo()
        tool._client.is_available = lambda: True
        tool._client.generate = lambda workflow, output_node, dest, **kwargs: [Path(dest)]

        result = tool.execute({
            "prompt": "test",
            "workflow_json": json.dumps({"42": {"inputs": {}}}),
            "output_node": "42",
            "workflow_model_stack": [{"role": "lora", "name": "style.safetensors"}],
            "output_path": str(tmp_path / "video.mp4"),
        })

        provenance = result.data["workflow_provenance"]
        assert provenance["model_stack"] == [{"role": "lora", "name": "style.safetensors"}]
        assert provenance["model_stack_source"] == "caller_supplied"

    def test_video_timeout_surfaces_resumable_prompt_id(self, tmp_path):
        from tools._comfyui.client import ComfyUIError

        tool = ComfyUIVideo()
        tool._client.is_available = lambda: True

        def fake_generate(workflow, output_node, dest, **kwargs):
            raise ComfyUIError("Prompt timed-out-id did not complete within 5s", prompt_id="timed-out-id")

        tool._client.generate = fake_generate

        result = tool.execute({
            "prompt": "test",
            "workflow_json": json.dumps({"42": {"inputs": {}}}),
            "output_node": "42",
            "output_path": str(tmp_path / "video.mp4"),
            "timeout_seconds": 5,
        })

        assert result.success is False
        assert result.data["prompt_id"] == "timed-out-id"
        assert "resume_prompt_id" in result.error
        assert "timed-out-id" in result.error

    def test_video_passes_timeout_and_resume_prompt_id_through(self, tmp_path):
        tool = ComfyUIVideo()
        tool._client.is_available = lambda: True
        seen = {}

        def fake_generate(workflow, output_node, dest, **kwargs):
            seen.update(kwargs)
            return [Path(dest)]

        tool._client.generate = fake_generate

        result = tool.execute({
            "prompt": "test",
            "workflow_json": json.dumps({"42": {"inputs": {}}}),
            "output_node": "42",
            "output_path": str(tmp_path / "video.mp4"),
            "timeout_seconds": 7200,
            "resume_prompt_id": "already-running-id",
        })

        assert result.success is True
        assert seen["timeout"] == 7200
        assert seen["resume_prompt_id"] == "already-running-id"

    def test_video_default_timeout_is_generous_not_900s(self, tmp_path):
        tool = ComfyUIVideo()
        tool._client.is_available = lambda: True
        seen = {}

        def fake_generate(workflow, output_node, dest, **kwargs):
            seen.update(kwargs)
            return [Path(dest)]

        tool._client.generate = fake_generate

        tool.execute({
            "prompt": "test",
            "workflow_json": json.dumps({"42": {"inputs": {}}}),
            "output_node": "42",
            "output_path": str(tmp_path / "video.mp4"),
        })

        # Regression guard: the old hardcoded 900s timeout false-failed real
        # renders on modest local GPUs (observed ~1360-1630s for non-accelerated
        # custom Wan 1.3B workflows at 832x480/81-97 frames).
        assert seen["timeout"] > 900

    def test_image_missing_models_are_structured(self):
        tool = ComfyUIImage()
        tool._client.is_available = lambda: True
        tool._client.check_models = lambda required: (
            [],
            ["flux2-vae.safetensors"],
        )

        result = tool.execute({"prompt": "test"})

        assert result.success is False
        assert result.data["provider"] == "comfyui"
        assert result.data["missing_models"][0]["name"] == "flux2-vae.safetensors"
        assert result.data["missing_models"][0]["destination_hint"] == "ComfyUI/models/vae/"
        assert result.data["missing_models"][0]["download_url"]

    def test_video_missing_models_are_structured(self):
        tool = ComfyUIVideo()
        tool._client.is_available = lambda: True
        tool._client.check_models = lambda required: (
            [],
            ["wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors"],
        )

        result = tool.execute({"prompt": "test", "operation": "text_to_video"})

        assert result.success is False
        assert result.data["operation"] == "text_to_video"
        assert result.data["missing_models"][0]["role"] == "diffusion_model_high_noise"
        assert result.data["missing_models"][0]["download_url"]

    def test_bundled_workflow_provenance_records_hash_and_stack(self, tmp_path):
        tool = ComfyUIImage()
        tool._client.is_available = lambda: True
        tool._client.check_models = lambda required: (list(required), [])
        tool._client.generate = lambda workflow, output_node, dest, **kwargs: [Path(dest)]

        result = tool.execute({
            "prompt": "test",
            "output_path": str(tmp_path / "image.png"),
        })

        provenance = result.data["workflow_provenance"]
        assert provenance["source"] == "bundled"
        assert provenance["workflow_hash_sha256"]
        assert any(item["role"] == "vae" for item in provenance["model_stack"])


class TestComfyUIMusic:

    def test_capability_and_provider(self):
        tool = ComfyUIMusic()
        assert tool.capability == "music_generation"
        assert tool.provider == "comfyui"

    def test_bundled_path_requires_no_workflow_json_or_output_node(self, tmp_path):
        """Without workflow_json/workflow_path it should attempt the bundled
        ACE-Step workflow, not demand a custom one."""
        tool = ComfyUIMusic()
        tool._client.is_available = lambda: True
        tool._client.check_models = lambda required: (list(required), [])
        tool._client.generate = lambda workflow, output_node, dest, **kwargs: [Path(dest)]

        result = tool.execute({
            "prompt": "ambient pad",
            "output_path": str(tmp_path / "music.mp3"),
        })

        assert result.success is True
        assert result.data["workflow_provenance"]["source"] == "bundled"

    def test_custom_workflow_without_output_node_errors(self):
        tool = ComfyUIMusic()
        tool._client.is_available = lambda: True

        result = tool.execute({
            "prompt": "ambient pad",
            "workflow_json": json.dumps({"9": {"inputs": {}}}),
        })

        assert result.success is False
        assert "output_node" in result.error

    def test_bundled_missing_models_returns_structured_payload(self):
        tool = ComfyUIMusic()
        tool._client.is_available = lambda: True
        tool._client.check_models = lambda required: ([], list(required))

        result = tool.execute({"prompt": "ambient pad"})

        assert result.success is False
        assert result.data["missing_models"][0]["name"] == "ace_step_v1_3.5b.safetensors"
        assert result.data["missing_models"][0]["download_url"]

    def test_bundled_generation_patches_tags_lyrics_and_seed(self, tmp_path):
        tool = ComfyUIMusic()
        tool._client.is_available = lambda: True
        tool._client.check_models = lambda required: (list(required), [])
        seen = {}

        def fake_generate(workflow, output_node, dest, **kwargs):
            seen["workflow"] = workflow
            seen["output_node"] = output_node
            return [Path(dest)]

        tool._client.generate = fake_generate

        result = tool.execute({
            "prompt": "lofi hip hop, chill, rain sounds",
            "lyrics": "[verse]\nquiet streets",
            "duration_seconds": 45,
            "seed": 777,
            "output_path": str(tmp_path / "music.mp3"),
        })

        assert result.success is True
        assert seen["output_node"] == "10"
        assert seen["workflow"]["2"]["inputs"]["tags"] == "lofi hip hop, chill, rain sounds"
        assert seen["workflow"]["2"]["inputs"]["lyrics"] == "[verse]\nquiet streets"
        assert seen["workflow"]["4"]["inputs"]["seconds"] == 45
        assert seen["workflow"]["8"]["inputs"]["seed"] == 777
        assert result.data["model"] == "ace-step-v1-3.5b"

    def test_bundled_generation_preserves_seed_zero(self, tmp_path):
        tool = ComfyUIMusic()
        tool._client.is_available = lambda: True
        tool._client.check_models = lambda required: (list(required), [])
        seen = {}

        def fake_generate(workflow, output_node, dest, **kwargs):
            seen["seed"] = workflow["8"]["inputs"]["seed"]
            return [Path(dest)]

        tool._client.generate = fake_generate
        result = tool.execute({
            "prompt": "deterministic test",
            "seed": 0,
            "output_path": str(tmp_path / "music.mp3"),
        })

        assert result.success is True
        assert result.seed == 0
        assert seen["seed"] == 0

    def test_get_status_degraded_when_model_missing(self):
        tool = ComfyUIMusic()
        tool._client.is_available = lambda: True
        tool._client.check_models = lambda required: ([], list(required))
        assert tool.get_status() == ToolStatus.DEGRADED

    def test_unavailable_server_reports_unavailable_reason(self):
        tool = ComfyUIMusic()
        tool._client.is_available = lambda: False
        tool._client.unavailable_reason = lambda: "no server here"

        result = tool.execute({
            "prompt": "ambient pad",
            "workflow_json": json.dumps({"9": {"inputs": {}}}),
            "output_node": "9",
        })

        assert result.success is False
        assert result.error == "no server here"

    def test_successful_generation_returns_provenance_and_duration(self, tmp_path, monkeypatch):
        tool = ComfyUIMusic()
        tool._client.is_available = lambda: True

        dest_file = tmp_path / "music.mp3"

        def fake_generate(workflow, output_node, dest, **kwargs):
            Path(dest).write_bytes(b"fake-audio-bytes")
            return [Path(dest)]

        tool._client.generate = fake_generate
        monkeypatch.setattr("shutil.which", lambda name: None)  # no ffprobe in test env

        result = tool.execute({
            "prompt": "upbeat synthwave",
            "workflow_json": json.dumps({"9": {"inputs": {}}}),
            "output_node": "9",
            "output_path": str(dest_file),
            "workflow_name": "my-ace-step-graph",
            "workflow_model": "ace-step-v1-3.5b",
        })

        assert result.success is True
        assert result.data["provider"] == "comfyui"
        assert result.data["model"] == "ace-step-v1-3.5b"
        assert result.data["output"] == str(dest_file)
        assert result.data["format"] == "mp3"
        assert result.data["duration_seconds"] is None  # ffprobe unavailable
        provenance = result.data["workflow_provenance"]
        assert provenance["source"] == "user_supplied"
        assert provenance["output_node"] == "9"
        assert provenance["workflow_hash_sha256"]

    def test_timeout_surfaces_resumable_prompt_id(self, tmp_path):
        from tools._comfyui.client import ComfyUIError

        tool = ComfyUIMusic()
        tool._client.is_available = lambda: True

        def fake_generate(workflow, output_node, dest, **kwargs):
            raise ComfyUIError("timed out", prompt_id="music-prompt-id")

        tool._client.generate = fake_generate

        result = tool.execute({
            "prompt": "ambient pad",
            "workflow_json": json.dumps({"9": {"inputs": {}}}),
            "output_node": "9",
            "output_path": str(tmp_path / "music.mp3"),
        })

        assert result.success is False
        assert result.data["prompt_id"] == "music-prompt-id"
        assert "resume_prompt_id" in result.error

    def test_passes_timeout_and_resume_prompt_id_through(self, tmp_path):
        tool = ComfyUIMusic()
        tool._client.is_available = lambda: True
        seen = {}

        def fake_generate(workflow, output_node, dest, **kwargs):
            seen.update(kwargs)
            return [Path(dest)]

        tool._client.generate = fake_generate

        tool.execute({
            "prompt": "ambient pad",
            "workflow_json": json.dumps({"9": {"inputs": {}}}),
            "output_node": "9",
            "output_path": str(tmp_path / "music.mp3"),
            "timeout_seconds": 3600,
            "resume_prompt_id": "already-running-id",
        })

        assert seen["timeout"] == 3600
        assert seen["resume_prompt_id"] == "already-running-id"

    def test_registry_discovers_comfyui_music_under_music_generation(self):
        registry = ToolRegistry()
        tool = ComfyUIMusic()
        registry.register(tool)
        registry._discovered_packages.add("tools")

        by_capability = registry.get_by_capability("music_generation")
        assert any(t.name == "comfyui_music" for t in by_capability)

    def test_uses_music_capability_env_var_for_multi_server(self, monkeypatch):
        monkeypatch.delenv("COMFYUI_SERVER_URL", raising=False)
        monkeypatch.setenv("COMFYUI_MUSIC_SERVER_URL", "http://music-gpu:8188")
        tool = ComfyUIMusic()
        assert tool._client.server_url == "http://music-gpu:8188"


class TestComfyUISetupOffer:

    def test_provider_menu_summary_includes_structured_setup_offer(self):
        registry = ToolRegistry()
        tool = ComfyUIImage()
        tool._client.is_available = lambda: False
        registry.register(tool)
        registry._discovered_packages.add("tools")

        summary = registry.provider_menu_summary()

        offer = summary["setup_offers"][0]
        assert offer["tool"] == "comfyui_image"
        assert offer["env_var"] == "COMFYUI_SERVER_URL"
        assert offer["default_url"] == "http://localhost:8188"
        assert offer["health_check"] == "GET /system_stats"


# ------------------------------------------------------------------
# Operation-specific video readiness
# ------------------------------------------------------------------

class TestVideoOperationReadiness:

    def test_video_tool_reports_partial_operation_readiness(self):
        from tools.video.comfyui_video import _REQUIRED_MODELS_I2V, _REQUIRED_MODELS_T2V

        tool = ComfyUIVideo()
        tool._client.is_available = lambda: True

        def fake_check_models(required):
            if required == _REQUIRED_MODELS_T2V:
                return list(required), []
            if required == _REQUIRED_MODELS_I2V:
                return [], list(required)
            return [], list(required)

        tool._client.check_models = fake_check_models

        assert tool.get_status() == ToolStatus.AVAILABLE
        assert tool.is_operation_available("text_to_video") is True
        assert tool.is_operation_available("image_to_video") is False
        assert tool.operation_statuses() == {
            "text_to_video": "available",
            "image_to_video": "degraded",
        }

    def test_video_selector_filters_operation_unready_tools(self):
        class PartialVideoTool(BaseTool):
            name = "partial_video"
            capability = "video_generation"
            provider = "partial"
            supports = {"image_to_video": True}
            input_schema = {"type": "object", "properties": {}}

            def is_operation_available(self, operation):
                return operation == "text_to_video"

            def execute(self, inputs):
                raise AssertionError("not used")

        selector = VideoSelector()
        candidates = [PartialVideoTool()]

        assert selector._filter_candidates(
            {"operation": "image_to_video"}, candidates
        ) == []

    def test_video_selector_rank_uses_target_operation_for_readiness(self):
        class PartialVideoTool(BaseTool):
            name = "partial_video"
            capability = "video_generation"
            provider = "partial"
            supports = {"image_to_video": True}
            input_schema = {"type": "object", "properties": {}}

            def is_operation_available(self, operation):
                return operation == "text_to_video"

            def execute(self, inputs):
                raise AssertionError("not used")

        selector = VideoSelector()
        candidates = [PartialVideoTool()]
        rank_inputs = selector._rank_inputs({
            "operation": "rank",
            "target_operation": "image_to_video",
        })

        assert rank_inputs["operation"] == "image_to_video"
        assert selector._filter_candidates(rank_inputs, candidates) == []


# ------------------------------------------------------------------
# Custom-workflow selector eligibility
# ------------------------------------------------------------------

class _DegradedComfyVideo(BaseTool):
    """Server reachable, but bundled WAN models missing -> DEGRADED, no
    operation ready. Stands in for comfyui_video on a low-VRAM box."""

    name = "comfyui_video"
    capability = "video_generation"
    provider = "comfyui"
    supports = {"custom_workflow": True, "image_to_video": True}
    input_schema = {"type": "object", "properties": {"workflow_json": {"type": "string"}}}

    def get_status(self):
        return ToolStatus.DEGRADED

    def is_operation_available(self, operation):
        return False

    def execute(self, inputs):
        raise AssertionError("not used")


class _DegradedComfyImage(BaseTool):
    name = "comfyui_image"
    capability = "image_generation"
    provider = "comfyui"
    supports = {"custom_workflow": True}
    input_schema = {"type": "object", "properties": {"workflow_json": {"type": "string"}}}

    def get_status(self):
        return ToolStatus.DEGRADED

    def execute(self, inputs):
        raise AssertionError("not used")


class TestCustomWorkflowSelectorEligibility:

    def test_video_selector_passes_degraded_tool_for_custom_workflow(self):
        selector = VideoSelector()
        candidates = [_DegradedComfyVideo()]
        inputs = {
            "prompt": "x",
            "operation": "text_to_video",
            "workflow_json": "{}",
            "output_node": "14",
        }
        # Without the custom-workflow path this DEGRADED, operation-unready tool
        # would be filtered out; with it, it is eligible and selectable.
        filtered = selector._filter_candidates(inputs, candidates)
        assert [t.name for t in filtered] == ["comfyui_video"]
        assert selector._tool_selectable(candidates[0], inputs) is True

    def test_video_selector_custom_workflow_requires_output_node(self):
        selector = VideoSelector()
        candidates = [_DegradedComfyVideo()]
        inputs = {"prompt": "x", "operation": "text_to_video", "workflow_json": "{}"}
        # output_node missing -> not eligible -> filtered out.
        assert selector._filter_candidates(inputs, candidates) == []
        assert selector._tool_selectable(candidates[0], inputs) is False

    def test_video_selector_custom_workflow_needs_server(self):
        class _OfflineComfyVideo(_DegradedComfyVideo):
            def get_status(self):
                return ToolStatus.UNAVAILABLE

        selector = VideoSelector()
        candidates = [_OfflineComfyVideo()]
        inputs = {
            "prompt": "x",
            "operation": "text_to_video",
            "workflow_json": "{}",
            "output_node": "14",
        }
        assert selector._filter_candidates(inputs, candidates) == []

    def test_image_selector_passes_degraded_tool_for_custom_workflow(self):
        selector = ImageSelector()
        candidates = [_DegradedComfyImage()]
        inputs = {"prompt": "x", "workflow_json": "{}", "output_node": "13"}
        filtered = selector._filter_candidates(inputs, candidates)
        assert [t.name for t in filtered] == ["comfyui_image"]
        assert selector._tool_selectable(candidates[0], inputs) is True

    def test_image_selector_custom_workflow_requires_output_node(self):
        selector = ImageSelector()
        candidates = [_DegradedComfyImage()]
        inputs = {"prompt": "x", "workflow_json": "{}"}
        assert selector._filter_candidates(inputs, candidates) == []
        assert selector._tool_selectable(candidates[0], inputs) is False

    def test_selector_schemas_expose_custom_workflow_inputs(self):
        for selector in (VideoSelector(), ImageSelector()):
            props = selector.input_schema["properties"]
            for field in (
                "workflow_json",
                "workflow_path",
                "output_node",
                "workflow_name",
                "workflow_model",
                "workflow_model_stack",
            ):
                assert field in props, f"{selector.name} missing {field}"
