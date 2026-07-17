"""Capability-level image selector that routes between generation and stock providers.

Provider discovery is automatic — any BaseTool with capability="image_generation"
is picked up from the registry.  Adding a new image provider requires only creating
the tool file in tools/graphics/; no changes to this selector are needed.
"""

from __future__ import annotations

from typing import Any

from tools.base_tool import BaseTool, ToolRuntime, ToolStability, ToolTier
from tools.selector_base import CustomWorkflowSelectorMixin, SelectorBase


class ImageSelector(CustomWorkflowSelectorMixin, SelectorBase):
    name = "image_selector"
    version = "0.2.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "selector"
    stability = ToolStability.BETA
    runtime = ToolRuntime.HYBRID
    agent_skills = ["flux-best-practices", "bfl-api"]

    capabilities = [
        "generate_image", "search_image", "download_image",
        "provider_selection", "text_to_image", "stock_image",
    ]
    supports = {
        "user_preference_routing": True,
        "offline_fallback": True,
        "stock_fallback": True,
    }
    best_for = [
        "preflight routing — pick the best image provider for the task",
        "switching between generated and stock images",
        "automatic fallback when preferred provider is unavailable",
    ]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Image description (used as prompt for generation or query for stock)",
            },
            "negative_prompt": {
                "type": "string",
                "description": "What to avoid in the generated image. Passed to providers that support it.",
            },
            "width": {"type": "integer", "description": "Image width in pixels"},
            "height": {"type": "integer", "description": "Image height in pixels"},
            "seed": {"type": "integer", "description": "Random seed for reproducibility (generation providers only)"},
            "n": {"type": "integer", "description": "Number of image variations to request when supported."},
            "aspect_ratio": {
                "type": "string",
                "description": "Aspect ratio hint for providers that support ratio-based generation.",
            },
            "resolution": {
                "type": "string",
                "description": "Resolution tier for providers that support named resolutions.",
            },
            "generation_mode": {
                "type": "string",
                "enum": ["generate", "edit"],
                "default": "generate",
                "description": "Use 'edit' when providing one or more source images.",
            },
            "image_url": {"type": "string", "description": "Single source image URL for edit-capable providers."},
            "image_path": {"type": "string", "description": "Single local source image path for edit-capable providers."},
            "image_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Multiple source image URLs for compositing edits.",
            },
            "image_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Multiple local source image paths for compositing edits.",
            },
            "preferred_provider": {
                "type": "string",
                "description": "Provider name or 'auto'. Valid values are discovered at runtime from the registry.",
                "default": "auto",
            },
            "allowed_providers": {
                "type": "array",
                "items": {"type": "string"},
            },
            "operation": {
                "type": "string",
                "enum": ["generate", "rank"],
                "default": "generate",
                "description": "Operation mode. 'rank' returns scored provider rankings without generating.",
            },
            "workflow_json": {
                "type": "string",
                "description": (
                    "Optional full ComfyUI workflow JSON. Routes to a custom-workflow-capable "
                    "provider (e.g. comfyui_image) based on server availability, not bundled "
                    "model readiness. Requires output_node."
                ),
            },
            "workflow_path": {
                "type": "string",
                "description": (
                    "Optional path to a ComfyUI workflow JSON file. Routes to a custom-workflow-"
                    "capable provider based on server availability. Requires output_node."
                ),
            },
            "output_node": {
                "type": "string",
                "description": "ComfyUI output node ID for a custom workflow_json/workflow_path.",
            },
            "workflow_name": {
                "type": "string",
                "description": "Optional human-readable provenance label for a custom workflow.",
            },
            "workflow_model": {
                "type": "string",
                "description": "Optional model/provenance label for a custom workflow.",
            },
            "workflow_model_stack": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Optional provenance metadata for custom workflow dependencies.",
            },
            "output_path": {"type": "string"},
        },
    }

    # ── Discovery, scoring, rank mode and result decoration live in
    # SelectorBase. image customizes the task context (generation_mode takes
    # precedence over operation), candidate filtering for edit requests, and
    # the provider payload — and never overrides execute() (see the base's
    # docstring on double instrumentation).
    _prompt_key = "prompt"
    _default_operation = "generate"

    def _no_provider_error(self) -> str:
        return "No image provider available."

    def _prepare_task_context(self, inputs: dict[str, Any]) -> dict[str, Any]:
        from lib.scoring import normalize_task_context

        # generation_mode wins over operation here — an "edit" request must
        # score against edit-capable providers even when `operation` says
        # something else.
        return normalize_task_context(
            inputs.get("task_context", {}),
            prompt=inputs.get("prompt", ""),
            capability=self.capability,
            operation=inputs.get("generation_mode", inputs.get("operation", "generate")),
        )

    def _adapt_inputs(self, inputs: dict[str, Any], tool: BaseTool) -> dict[str, Any]:
        """Copy, add `query` for stock providers, and strip what the chosen
        provider's schema doesn't declare.

        Unlike tts/video (which forward `inputs` as-is), image has always
        stripped selector-only keys and unsupported passthrough params. Kept
        as an override rather than hoisted: hoisting would change what every
        video and tts provider receives.
        """
        import logging

        logger = logging.getLogger(__name__)
        adapted = dict(inputs)

        if hasattr(tool, "input_schema"):
            props = tool.input_schema.get("properties", {})
            if "query" in props and "query" not in adapted:
                adapted["query"] = adapted.get("prompt", "")

        # Strip selector-only keys that downstream tools don't understand
        adapted.pop("preferred_provider", None)
        adapted.pop("allowed_providers", None)

        # Pass through generation params only to tools that accept them.
        if hasattr(tool, "input_schema"):
            props = tool.input_schema.get("properties", {})
            stripped = []
            for passthrough_key in (
                "negative_prompt",
                "width",
                "height",
                "seed",
                "n",
                "aspect_ratio",
                "resolution",
                "generation_mode",
                "image_url",
                "image_path",
                "image_urls",
                "image_paths",
                "workflow_json",
                "workflow_path",
                "output_node",
                "workflow_name",
                "workflow_model",
                "workflow_model_stack",
            ):
                if passthrough_key in adapted and passthrough_key not in props:
                    stripped.append(f"{passthrough_key}={adapted.pop(passthrough_key)}")
            if stripped:
                logger.warning(
                    "image_selector: stripped unsupported params for %s: %s",
                    tool.name, ", ".join(stripped),
                )
        return adapted

    def _filter_candidates(self, inputs: dict[str, Any], candidates: list[BaseTool]) -> list[BaseTool]:
        # A caller-supplied custom workflow is provider-specific (ComfyUI graph
        # JSON). Route it only to custom-workflow-capable providers whose server
        # is reachable — bundled-model readiness is irrelevant in that case.
        if self._has_custom_workflow(inputs):
            return [t for t in candidates if self._custom_workflow_eligible(t, inputs)]

        wants_edit = (
            inputs.get("generation_mode") == "edit"
            or inputs.get("image_url")
            or inputs.get("image_path")
            or inputs.get("image_urls")
            or inputs.get("image_paths")
        )
        if not wants_edit:
            return candidates

        filtered: list[BaseTool] = []
        for tool in candidates:
            props = getattr(tool, "input_schema", {}).get("properties", {})
            supports = getattr(tool, "supports", {})
            if supports.get("image_edit") or any(
                key in props for key in ("image", "images", "image_url", "image_path", "image_urls", "image_paths")
            ):
                filtered.append(tool)
        return filtered or candidates
