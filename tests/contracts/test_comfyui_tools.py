"""Contract tests for ComfyUI provider tools.

These tests verify that the tools satisfy the BaseTool contract without
requiring a running ComfyUI server.  They check class attributes,
schemas, status reporting, and cost estimates.
"""

import json
from pathlib import Path

import pytest
import requests

from tools.base_tool import (
    BaseTool,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)
from tools.graphics.comfyui_image import ComfyUIImage
from tools.graphics.image_selector import ImageSelector
from tools.tool_registry import ToolRegistry
from tools.video.video_selector import VideoSelector
from tools.video.comfyui_video import ComfyUIVideo

TOOLS = [ComfyUIImage, ComfyUIVideo]
WORKFLOW_DIR = Path(__file__).resolve().parent.parent.parent / "tools" / "_comfyui" / "workflows"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ------------------------------------------------------------------
# ComfyUI polling transport contract
# ------------------------------------------------------------------

class TestComfyUIPolling:

    def test_poll_recovers_from_transient_timeout_and_connection_failures_with_deadline_bounds(self, monkeypatch):
        from tools._comfyui.client import ComfyUIClient
        import tools._comfyui.client as client_module

        clock = _AdvancingClock()
        request_timeouts: list[float] = []
        responses = iter([
            requests.ReadTimeout("loading model"),
            requests.ConnectionError("restarting worker"),
            _HistoryResponse({"prompt-1": {"status": {"status_str": "success"}}}),
        ])

        def fake_get(url, *, timeout):
            request_timeouts.append(timeout)
            result = next(responses)
            if isinstance(result, Exception):
                raise result
            return result

        monkeypatch.setattr(client_module.time, "time", clock.time)
        monkeypatch.setattr(client_module.time, "sleep", clock.sleep)
        monkeypatch.setattr(client_module.requests, "get", fake_get)

        result = ComfyUIClient("http://comfy.test").poll("prompt-1", timeout=10, interval=1)

        assert result == {"status": {"status_str": "success"}}
        assert request_timeouts == [10.0, 9.0, 8.0]
        assert clock.sleeps == [1, 1]

    def test_poll_stops_at_deadline_without_oversized_request_or_sleep(self, monkeypatch):
        from tools._comfyui.client import ComfyUIClient, ComfyUIError
        import tools._comfyui.client as client_module

        clock = _AdvancingClock()
        request_timeouts: list[float] = []

        def fake_get(url, *, timeout):
            request_timeouts.append(timeout)
            raise requests.ReadTimeout("still loading")

        monkeypatch.setattr(client_module.time, "time", clock.time)
        monkeypatch.setattr(client_module.time, "sleep", clock.sleep)
        monkeypatch.setattr(client_module.requests, "get", fake_get)

        with pytest.raises(ComfyUIError, match="did not complete within 2s"):
            ComfyUIClient("http://comfy.test").poll("prompt-1", timeout=2, interval=5)

        assert request_timeouts == [2.0]
        assert clock.sleeps == [2.0]

    def test_poll_immediately_propagates_http_status_errors(self, monkeypatch):
        from tools._comfyui.client import ComfyUIClient
        import tools._comfyui.client as client_module

        clock = _AdvancingClock()

        class HttpErrorResponse:
            def raise_for_status(self) -> None:
                raise requests.HTTPError("500 Server Error")

        monkeypatch.setattr(client_module.time, "time", clock.time)
        monkeypatch.setattr(client_module.time, "sleep", clock.sleep)
        monkeypatch.setattr(client_module.requests, "get", lambda url, *, timeout: HttpErrorResponse())

        with pytest.raises(requests.HTTPError, match="500 Server Error"):
            ComfyUIClient("http://comfy.test").poll("prompt-1", timeout=2, interval=1)

        assert clock.sleeps == []


class _AdvancingClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class _HistoryResponse:
    def __init__(self, history: dict) -> None:
        self.history = history

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.history


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
    "wan22-i2v-nvfp4.json",
    "wan22-t2v-4step.json",
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


def test_t2v_workflow_uses_14b_compatible_vae():
    with open(WORKFLOW_DIR / "wan22-t2v-4step.json") as f:
        w = json.load(f)
    assert w["4"]["inputs"]["vae_name"] == "wan_2.1_vae.safetensors"


# ------------------------------------------------------------------
# NVFP4 I2V stack (Blackwell path)
# ------------------------------------------------------------------

def test_i2v_nvfp4_workflow_has_same_templated_nodes_as_fp8():
    """The NVFP4 graph must expose the same node contract the tool patches.

    _build_i2v patches nodes 93/97/98/86/108 regardless of which stack is
    selected. If the NVFP4 graph renumbered anything, the patch would silently
    write to keys that do not exist and the clip would render with the
    template's placeholder prompt.
    """
    with open(WORKFLOW_DIR / "wan22-i2v-nvfp4.json") as f:
        w = json.load(f)
    assert w["93"]["class_type"] == "CLIPTextEncode"
    assert w["97"]["class_type"] == "LoadImage"
    assert w["98"]["class_type"] == "WanImageToVideo"
    assert w["86"]["class_type"] == "KSamplerAdvanced"
    assert w["108"]["class_type"] == "SaveVideo"
    # the fields the tool actually writes
    for node, field in (("93", "text"), ("97", "image"), ("86", "noise_seed"),
                        ("108", "filename_prefix")):
        assert field in w[node]["inputs"], f"node {node} missing {field}"
    for field in ("width", "height", "length"):
        assert field in w["98"]["inputs"], f"node 98 missing {field}"


def test_i2v_nvfp4_metadata_stack_is_registered():
    """The missing-model payload looks metadata up by workflow_key.

    Without this entry a missing NVFP4 file would fall back to role 'unknown'
    with no download URL, which is exactly the case the payload exists for.
    """
    from tools._comfyui.metadata import BUNDLED_MODEL_STACKS

    stack = BUNDLED_MODEL_STACKS["wan22-i2v-nvfp4"]
    names = {item["name"] for item in stack}
    assert "Wan2.2-I2V-A14B_NVFP4_Sparse_high_comfy.safetensors" in names
    assert "Wan2.2-I2V-A14B_NVFP4_Sparse_low_comfy.safetensors" in names
    assert "wan_2.1_vae.safetensors" in names
    for item in stack:
        assert item["role"] != "unknown"
        assert item.get("download_url"), f"{item['name']} has no download URL"


def test_i2v_stack_prefers_nvfp4_then_falls_back_to_fp8(monkeypatch):
    from tools.video import comfyui_video as mod

    tool = ComfyUIVideo()

    # both stacks complete -> NVFP4 wins
    monkeypatch.setattr(tool._client, "check_models", lambda models: ([], []))
    assert tool._i2v_stack() == "nvfp4"

    # NVFP4 incomplete, FP8 complete -> FP8
    # Note the two stacks share umt5_xxl and wan_2.1_vae, so a fake that marks
    # "the NVFP4 list" missing would also break the FP8 stack. Mark only the
    # files unique to NVFP4.
    nvfp4_only = set(mod._REQUIRED_MODELS_I2V_NVFP4) - set(mod._REQUIRED_MODELS_I2V)
    assert nvfp4_only, "expected NVFP4 to have files the FP8 stack does not"

    def fp8_ok(models):
        return [], [m for m in models if m in nvfp4_only]

    monkeypatch.setattr(tool._client, "check_models", fp8_ok)
    assert tool._i2v_stack() == "fp8"

    # NVFP4 complete, FP8 incomplete -> NVFP4 (the shared files are present)
    fp8_only = set(mod._REQUIRED_MODELS_I2V) - set(mod._REQUIRED_MODELS_I2V_NVFP4)

    def nvfp4_ok(models):
        return [], [m for m in models if m in fp8_only]

    monkeypatch.setattr(tool._client, "check_models", nvfp4_ok)
    assert tool._i2v_stack() == "nvfp4"

    # neither complete -> None
    monkeypatch.setattr(tool._client, "check_models", lambda models: ([], list(models)))
    assert tool._i2v_stack() is None


def test_i2v_missing_payload_reports_both_stacks(monkeypatch, tmp_path):
    """When no I2V stack is complete the payload must cover BOTH stacks.

    Regression: the first cut reported only the NVFP4 files while the error text
    claimed the FP8 fallback was incomplete too, so the structured payload could
    not explain the failure and hid the FP8 download URLs.
    """
    from tools.video import comfyui_video as mod  # noqa: F401
    from tools.base_tool import ToolResult  # noqa: F401

    tool = ComfyUIVideo()
    monkeypatch.setattr(tool._client, "is_available", lambda: True)
    # every model is missing
    monkeypatch.setattr(tool._client, "check_models", lambda models: ([], list(models)))

    ref = tmp_path / "ref.png"
    ref.write_bytes(b"\x89PNG\r\n\x1a\n")

    result = tool.execute({
        "prompt": "test",
        "operation": "image_to_video",
        "reference_image_path": str(ref),
        "output_path": str(tmp_path / "out.mp4"),
    })

    assert result.success is False
    reported = {item["name"] for item in result.data["missing_models"]}
    # at least one file unique to each stack must be present
    assert "Wan2.2-I2V-A14B_NVFP4_Sparse_high_comfy.safetensors" in reported
    assert "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors" in reported
    assert "wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors" in reported
    # and each reported file must carry usable provenance, not the 'unknown' fallback
    for item in result.data["missing_models"]:
        assert item["role"] != "unknown", f"{item['name']} lost its role"


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
