"""ComfyUI image generation via a local or remote ComfyUI server.

Bundled model families (``model_family``):

* ``flux2`` (default): FLUX 2 Dev (NVFP4) with Mistral text encoder.
* ``qwen_image_2.1``: Qwen-Image-2.1 base text-to-image (INT8 ConvRot stack).

Supports custom workflows via the ``workflow_json`` input.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)
from tools._comfyui.client import ComfyUIClient, ComfyUIError
from tools._comfyui.metadata import (
    BUNDLED_MODEL_STACKS,
    COMFYUI_SETUP_OFFER,
    MODEL_LICENSE_NOTES,
    missing_models_payload,
    model_stack,
    workflow_hash,
)

_WORKFLOWS = Path(__file__).resolve().parent.parent / "_comfyui" / "workflows"


def _stack_models(stack_key: str) -> list[str]:
    """File names a bundled stack needs, taken from the metadata stack."""
    return [item["name"] for item in BUNDLED_MODEL_STACKS[stack_key]]


@dataclass(frozen=True)
class _Family:
    """A bundled text-to-image model family and its workflow wiring."""

    stack: str  # key in BUNDLED_MODEL_STACKS
    workflow: str  # file in tools/_comfyui/workflows
    output_node: str
    model_name: str
    default_steps: int
    default_guidance: float


_FAMILIES: dict[str, _Family] = {
    "flux2": _Family(
        stack="flux2-txt2img",
        workflow="flux2-txt2img.json",
        output_node="13",
        model_name="flux2-dev-nvfp4",
        default_steps=20,
        default_guidance=3.5,
    ),
    "qwen_image_2.1": _Family(
        stack="qwen-image-2-1-t2i",
        workflow="qwen-image-2-1-t2i.json",
        output_node="461",
        model_name="qwen-image-2.1",
        # The Comfy-Org template runs 25 steps; the model card's base setting
        # is 40. In the vastai-comfyui eval (20 pictures, 74 checks) 40 steps
        # fixed stray objects and sharpened sign lettering over 25 (17/20 vs
        # 16/20 pictures fully right) for ~1.6x the time, so 40 is the default.
        # Base Qwen-Image-2.1 runs at CFG 1.
        default_steps=40,
        default_guidance=1.0,
    ),
}
_DEFAULT_FAMILY = "flux2"

# Qwen-Image-2.1 size rules: each side a multiple of 32 within 256..2752, and
# no more than the native 2K area (2400 x 1792).
_QWEN_MIN_SIDE = 256
_QWEN_MAX_SIDE = 2752
_QWEN_MAX_AREA = 2400 * 1792


def _check_qwen_size(width: int, height: int) -> None:
    for side in (width, height):
        if side % 32 or not _QWEN_MIN_SIDE <= side <= _QWEN_MAX_SIDE:
            raise ComfyUIError(
                f"qwen_image_2.1 size {width}x{height}: each side must be a "
                f"multiple of 32 between {_QWEN_MIN_SIDE} and {_QWEN_MAX_SIDE}."
            )
    if width * height > _QWEN_MAX_AREA:
        raise ComfyUIError(
            f"qwen_image_2.1 size {width}x{height} is larger than the native 2K "
            f"area (2400x1792). Each side must be a multiple of 32 within the "
            f"{_QWEN_MIN_SIDE}-{_QWEN_MAX_SIDE} range and the area at most 2400x1792."
        )

# Models required by the bundled flux2-txt2img workflow
_REQUIRED_MODELS = _stack_models("flux2-txt2img")
# Models required by the bundled qwen-image-2-1-t2i workflow
_REQUIRED_MODELS_QWEN_IMAGE_2_1 = _stack_models("qwen-image-2-1-t2i")
_REQUIRED_BY_FAMILY = {
    "flux2": _REQUIRED_MODELS,
    "qwen_image_2.1": _REQUIRED_MODELS_QWEN_IMAGE_2_1,
}


class ComfyUIImage(BaseTool):
    name = "comfyui_image"
    version = "0.2.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "comfyui"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.LOCAL_GPU

    dependencies = []  # checked at runtime via server health
    setup_offer = COMFYUI_SETUP_OFFER
    install_instructions = (
        "Start a ComfyUI server and set COMFYUI_SERVER_URL "
        "(default http://localhost:8188).\n"
        "See https://github.com/comfyanonymous/ComfyUI for setup.\n"
        "Bundled model families: flux2 (default) and qwen_image_2.1 "
        "(research-only licence). Install the files listed in "
        "get_info()['bundled_model_stacks'] for the family you use.\n"
        "Running a separate ComfyUI instance for images? Set COMFYUI_IMAGE_SERVER_URL "
        "instead -- it takes priority over COMFYUI_SERVER_URL for this tool only."
    )
    agent_skills = ["comfyui", "flux-best-practices"]

    capabilities = ["text_to_image"]
    supports = {
        "seed": True,
        "custom_size": True,
        "custom_workflow": True,
        "custom_output_node": True,
        "offline": True,
    }
    best_for = [
        "local GPU generation without API costs",
        "Blackwell / DGX Spark hardware where diffusers is unsupported",
        "full control over sampling via custom ComfyUI workflows",
        "open-weight Qwen-Image-2.1 text-to-image (model_family=qwen_image_2.1)",
    ]
    not_good_for = [
        "setups without a running ComfyUI server",
        "CPU-only machines",
        "commercial work with Qwen-Image-2.1 (research-only licence)",
    ]
    fallback = "flux_image"
    fallback_tools = ["flux_image", "local_diffusion", "openai_image"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "description": "Text prompt for image generation"},
            "model_family": {
                "type": "string",
                "enum": list(_FAMILIES),
                "default": _DEFAULT_FAMILY,
                "description": (
                    "Bundled model family. flux2 = FLUX.2 Dev NVFP4; qwen_image_2.1 = "
                    "Qwen-Image-2.1 base (INT8, research-only licence). Ignored when "
                    "a custom workflow is supplied."
                ),
            },
            "negative_prompt": {
                "type": "string",
                "description": (
                    "qwen_image_2.1 only. Base Qwen-Image-2.1 samples at CFG 1, so "
                    "the negative prompt has little effect."
                ),
            },
            "width": {"type": "integer", "default": 1024},
            "height": {"type": "integer", "default": 1024},
            "steps": {
                "type": "integer",
                "description": "Sampling steps. Default 20 for flux2, 40 for qwen_image_2.1.",
            },
            "guidance": {
                "type": "number",
                "description": (
                    "FLUX guidance for flux2 (default 3.5); CFG for qwen_image_2.1 "
                    "(default 1.0, which is what the base model expects)."
                ),
            },
            "seed": {"type": "integer", "description": "Random if omitted"},
            "output_path": {"type": "string", "description": "Where to save the image"},
            "workflow_json": {
                "type": "string",
                "description": "Optional full ComfyUI workflow JSON. Requires output_node.",
            },
            "workflow_path": {
                "type": "string",
                "description": "Optional path to a ComfyUI workflow JSON file. Requires output_node.",
            },
            "output_node": {
                "type": "string",
                "description": "ComfyUI output node ID for custom workflow_json/workflow_path.",
            },
            "workflow_name": {
                "type": "string",
                "description": "Optional human-readable provenance label for a custom workflow.",
            },
            "workflow_model": {
                "type": "string",
                "description": (
                    "Optional model/provenance label for a custom workflow. "
                    "`model` is accepted as an alias when this is not set."
                ),
            },
            "workflow_model_stack": {
                "type": "array",
                "description": (
                    "Optional provenance metadata for custom workflow dependencies. "
                    "Items should include name, role, quantization, and LoRA strengths when known."
                ),
                "items": {"type": "object"},
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=8000, vram_mb=8000, disk_mb=500, network_required=False,
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["timeout"])
    idempotency_key_fields = ["prompt", "model_family", "width", "height", "steps", "seed"]
    side_effects = ["writes image file to output_path"]
    user_visible_verification = ["Inspect generated image for quality and prompt adherence"]

    def __init__(self) -> None:
        self._client = ComfyUIClient(capability="image")

    def get_status(self) -> ToolStatus:
        if not self._client.is_available():
            return ToolStatus.UNAVAILABLE
        # Ready as soon as any one bundled family has all of its files.
        for required in _REQUIRED_BY_FAMILY.values():
            _, missing = self._client.check_models(required)
            if not missing:
                return ToolStatus.AVAILABLE
        return ToolStatus.DEGRADED

    def model_family_statuses(self) -> dict[str, str]:
        """Return the readiness of each bundled family on the connected server."""
        if not self._client.is_available():
            return {family: "unavailable" for family in _FAMILIES}
        statuses: dict[str, str] = {}
        for family, required in _REQUIRED_BY_FAMILY.items():
            _, missing = self._client.check_models(required)
            statuses[family] = "available" if not missing else "degraded"
        return statuses

    def default_model_family(self, family_statuses: dict[str, str] | None = None) -> str:
        """Return the family a call without ``model_family`` runs.

        The first installed family wins, in ``_FAMILIES`` order (flux2 first).
        With none installed it stays flux2, so the missing-model report names
        the documented default.
        """
        statuses = family_statuses or self.model_family_statuses()
        return next(
            (family for family in _FAMILIES if statuses[family] == "available"),
            _DEFAULT_FAMILY,
        )

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        family = _FAMILIES.get(str(inputs.get("model_family", _DEFAULT_FAMILY)))
        default_steps = family.default_steps if family else _FAMILIES[_DEFAULT_FAMILY].default_steps
        return float(inputs.get("steps", default_steps)) * 1.5

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        info["setup_offer"] = self.setup_offer
        # Single-stack key kept for existing consumers.
        info["bundled_model_stack"] = BUNDLED_MODEL_STACKS["flux2-txt2img"]
        info["bundled_model_stacks"] = {
            key: BUNDLED_MODEL_STACKS[family.stack] for key, family in _FAMILIES.items()
        }
        info["license_notes"] = {"qwen_image_2.1": MODEL_LICENSE_NOTES["qwen-image-2.1"]}
        family_statuses = self.model_family_statuses()
        info["model_family_statuses"] = family_statuses
        info["default_model_family"] = self.default_model_family(family_statuses)
        return info

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        custom_workflow = bool(inputs.get("workflow_json") or inputs.get("workflow_path"))
        if custom_workflow and not inputs.get("output_node"):
            return ToolResult(
                success=False,
                error=(
                    "Custom ComfyUI workflows require output_node so OpenMontage "
                    "knows which ComfyUI node to download artifacts from."
                ),
            )

        # A caller that names no family gets whichever bundled family the server
        # has; an explicit choice is never swapped for another model.
        auto_family = not custom_workflow and not inputs.get("model_family")
        family_key = str(inputs.get("model_family") or _DEFAULT_FAMILY)
        if not custom_workflow and family_key not in _FAMILIES:
            return ToolResult(
                success=False,
                error=(
                    f"Unknown model_family {family_key!r}. "
                    f"Choose one of: {', '.join(_FAMILIES)}."
                ),
            )
        family = _FAMILIES.get(family_key, _FAMILIES[_DEFAULT_FAMILY])

        if not self._client.is_available():
            return ToolResult(
                success=False,
                error=self._client.unavailable_reason(),
            )

        if auto_family:
            family_key = self.default_model_family()
            family = _FAMILIES[family_key]

        if not custom_workflow:
            _, missing = self._client.check_models(_REQUIRED_BY_FAMILY[family_key])
            if missing:
                return ToolResult(
                    success=False,
                    data=missing_models_payload(
                        missing,
                        workflow_key=family.stack,
                        workflow_name=family.workflow,
                    ),
                    error=(
                        f"ComfyUI server is running but missing required models: "
                        f"{', '.join(missing)}.\n"
                        f"See data.missing_models for destination hints and download URLs."
                    ),
                )

        start = time.time()
        seed = inputs.get("seed") or ComfyUIClient.random_seed()
        output_path = Path(inputs.get("output_path", f"comfyui_image_{seed}.png"))

        try:
            if custom_workflow:
                workflow = self._load_custom_workflow(inputs)
                output_node = str(inputs["output_node"])
                params = {
                    "width": inputs.get("width", 1024),
                    "height": inputs.get("height", 1024),
                    "steps": inputs.get("steps", family.default_steps),
                    "guidance": inputs.get("guidance", family.default_guidance),
                }
            else:
                workflow, output_node, params = self._build_workflow(
                    family_key, inputs, seed, output_path
                )

            provenance = self._workflow_provenance(
                inputs, custom_workflow, output_node, workflow, family_key
            )
            paths = self._client.generate(
                workflow, output_node=output_node, dest=output_path, timeout=600,
            )

        except ComfyUIError as exc:
            return ToolResult(success=False, error=str(exc))
        except Exception as exc:
            return ToolResult(success=False, error=f"ComfyUI image generation failed: {exc}")

        model_name = self._model_name(inputs, custom_workflow, family_key)
        return ToolResult(
            success=True,
            data={
                "provider": "comfyui",
                "model": model_name,
                "prompt": inputs["prompt"],
                "width": params["width"],
                "height": params["height"],
                "steps": params["steps"],
                "guidance": params["guidance"],
                "output": str(paths[0]),
                "format": "png",
                "workflow_provenance": provenance,
                "model_family": None if custom_workflow else family_key,
                "model_family_auto_selected": auto_family,
            },
            artifacts=[str(p) for p in paths],
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
            seed=seed,
            model=model_name,
        )

    @staticmethod
    def _build_workflow(
        family_key: str,
        inputs: dict[str, Any],
        seed: int,
        output_path: Path,
    ) -> tuple[dict, str, dict[str, Any]]:
        """Patch the bundled graph for *family_key*.

        Returns ``(workflow, output_node, params)`` where ``params`` holds the
        width/height/steps/guidance actually used.
        """
        family = _FAMILIES[family_key]
        width = inputs.get("width", 1024)
        height = inputs.get("height", 1024)
        steps = inputs.get("steps", family.default_steps)
        guidance = inputs.get("guidance", family.default_guidance)

        workflow = ComfyUIClient.load_workflow(_WORKFLOWS / family.workflow)
        if family_key == "flux2":
            patches: dict[str, dict[str, Any]] = {
                "4": {"text": inputs["prompt"]},
                "5": {"guidance": guidance},
                "6": {"width": width, "height": height, "batch_size": 1},
                "7": {"noise_seed": seed},
                "10": {"steps": steps, "width": width, "height": height},
                "13": {"filename_prefix": output_path.stem},
            }
        else:  # qwen_image_2.1
            _check_qwen_size(width, height)
            patches = {
                "452": {
                    "prompt": inputs["prompt"],
                    "negative_prompt": inputs.get("negative_prompt", ""),
                },
                "456": {"width": width, "height": height, "batch_size": 1},
                "458": {"seed": seed, "steps": steps, "cfg": guidance},
                "461": {"filename_prefix": output_path.stem},
            }
        workflow = ComfyUIClient.patch_workflow(workflow, patches)
        params = {"width": width, "height": height, "steps": steps, "guidance": guidance}
        return workflow, family.output_node, params

    @staticmethod
    def _load_custom_workflow(inputs: dict[str, Any]) -> dict:
        if inputs.get("workflow_json"):
            return json.loads(inputs["workflow_json"])
        return ComfyUIClient.load_workflow(Path(inputs["workflow_path"]))

    @staticmethod
    def _model_name(
        inputs: dict[str, Any],
        custom_workflow: bool,
        family_key: str = _DEFAULT_FAMILY,
    ) -> str:
        if not custom_workflow:
            return _FAMILIES[family_key].model_name
        return (
            inputs.get("workflow_model")
            or inputs.get("model")
            or inputs.get("workflow_name")
            or "custom-comfyui-workflow"
        )

    @staticmethod
    def _workflow_provenance(
        inputs: dict[str, Any],
        custom_workflow: bool,
        output_node: str,
        workflow: dict[str, Any],
        family_key: str = _DEFAULT_FAMILY,
    ) -> dict[str, Any]:
        if not custom_workflow:
            family = _FAMILIES[family_key]
            return {
                "source": "bundled",
                "workflow": family.workflow,
                "workflow_hash_sha256": workflow_hash(workflow),
                "model_stack": model_stack(family.stack, inputs),
                "output_node": output_node,
            }
        return {
            "source": "user_supplied",
            "workflow_name": inputs.get("workflow_name"),
            "workflow_path": inputs.get("workflow_path"),
            "model": inputs.get("workflow_model") or inputs.get("model"),
            "workflow_hash_sha256": workflow_hash(workflow),
            "model_stack": model_stack(None, inputs),
            "model_stack_source": (
                "caller_supplied"
                if inputs.get("workflow_model_stack")
                else "unknown_custom_workflow"
            ),
            "output_node": output_node,
        }
