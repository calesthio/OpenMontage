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
from tools.graphics.comfyui_image import ComfyUIImage
from tools.tool_registry import ToolRegistry
from tools.video.video_selector import VideoSelector
from tools.video.comfyui_video import ComfyUIVideo

TOOLS = [ComfyUIImage, ComfyUIVideo]
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

