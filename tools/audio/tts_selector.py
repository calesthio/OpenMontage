"""Capability-level text-to-speech selector that chooses among provider tools.

Provider discovery is automatic — any BaseTool with capability="tts"
is picked up from the registry.  Adding a new TTS provider requires only creating
the tool file in tools/audio/; no changes to this selector are needed.
"""

from __future__ import annotations

from typing import Any

from tools.base_tool import (
    BaseTool,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
    ToolStatus,
)


class TTSSelector(BaseTool):
    name = "tts_selector"
    version = "0.2.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "selector"
    stability = ToolStability.BETA
    runtime = ToolRuntime.HYBRID
    agent_skills = ["text-to-speech", "elevenlabs"]

    capabilities = [
        "text_to_speech",
        "provider_selection",
    ]
    supports = {
        "user_preference_routing": True,
        "offline_fallback": True,
        "multilingual": True,
    }
    best_for = [
        "preflight tool selection",
        "user-facing recommendation flows",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "preferred_tool": {
                "type": "string",
                "description": "Exact tool name; never falls back.",
            },
            "hosting_provider": {
                "type": "string",
                "description": "Required API host, e.g. fal.ai, atlascloud, replicate.",
            },
            "text": {"type": "string"},
            "voice_id": {
                "type": "string",
                "description": "Provider-specific voice ID. Passed through to the selected TTS provider.",
            },
            "voice": {
                "type": "string",
                "description": "Provider-specific voice name or ID. fal.ai ElevenLabs accepts names such as Rachel.",
            },
            "voice_language": {
                "type": "string",
                "enum": ["zh", "en"],
                "description": "Kling official voice language. Passed through when selected provider supports it.",
            },
            "voice_speed": {
                "type": "number",
                "minimum": 0.5,
                "maximum": 2.0,
                "description": "Kling official voice speed. Use speed for OpenAI/ElevenLabs-style controls.",
            },
            "model_id": {
                "type": "string",
                "description": "TTS model to use (e.g. eleven-v3 or eleven_multilingual_v2). Passed through to provider.",
            },
            "stability": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Voice stability (ElevenLabs). Lower = more expressive.",
            },
            "similarity_boost": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Voice similarity boost (ElevenLabs).",
            },
            "style": {
                "type": ["number", "string"],
                "description": "Style exaggeration (ElevenLabs). Higher = more expressive.",
            },
            "instructions": {
                "type": "string",
                "description": "Provider-level delivery instructions for expressive narration when supported.",
            },
            "speaking_rate": {
                "type": "number",
                "minimum": 0.25,
                "maximum": 2.0,
                "description": "Google-style speakingRate control. Use speed for OpenAI/ElevenLabs-style controls.",
            },
            "speed": {
                "type": "number",
                "minimum": 0.25,
                "maximum": 4.0,
                "description": "Alias for speaking speed used by some providers.",
            },
            "pitch": {
                "type": "number",
                "minimum": -50,
                "maximum": 50,
                "description": "Provider-specific pitch control. Google TTS accepts -20..20; HeyGen-style providers may accept wider ranges.",
            },
            "input_type": {
                "type": "string",
                "enum": ["text", "ssml"],
                "default": "text",
                "description": "Use 'ssml' only when the selected provider supports tags such as <break>.",
            },
            "language_code": {
                "type": "string",
                "description": "Provider-specific language code, such as en-US for Google or en for fal.ai ElevenLabs.",
            },
            "timestamps": {
                "type": "boolean",
                "default": False,
                "description": "Request word timestamps when the selected provider supports them.",
            },
            "apply_text_normalization": {
                "type": "string",
                "enum": ["auto", "on", "off"],
                "description": "Text normalization mode for providers that support it.",
            },
            "seed": {
                "type": "integer",
                "description": "Optional generation seed for providers that support reproducible speech.",
            },
            "voice_performance": {
                "type": "object",
                "description": "Structured voice-performance plan or section delivery cues from the script artifact.",
            },
            "sample_mode": {
                "type": "boolean",
                "default": False,
                "description": "True when generating an approval sample before batch narration.",
            },
            "output_format": {
                "type": "string",
                "description": "Audio output format (e.g. mp3_44100_128). Passed through to provider.",
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
            "output_path": {"type": "string"},
        },
    }

    def _providers(self) -> list[BaseTool]:
        """Auto-discover TTS providers from the registry."""
        from tools.tool_registry import registry

        registry.ensure_discovered()
        return [t for t in registry.get_by_capability("tts") if t.name != self.name]

    @property
    def fallback_tools(self) -> list[str]:
        """Dynamically built from discovered providers."""
        return [t.name for t in self._providers()]

    @property
    def provider_matrix(self) -> dict[str, dict[str, str]]:
        """Built at runtime from each provider's best_for field."""
        matrix = {}
        for tool in self._providers():
            strength = ", ".join(tool.best_for) if tool.best_for else tool.name
            matrix[tool.provider] = {"tool": tool.name, "strength": strength}
        return matrix

    def get_status(self) -> ToolStatus:
        if any(tool.get_status() == ToolStatus.AVAILABLE for tool in self._providers()):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        candidates = self._providers()
        if not candidates:
            return 0.0
        tool, _ = self._select_best_tool(
            inputs, candidates, self._prepare_task_context(inputs)
        )
        return tool.estimate_cost(inputs) if tool else 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        from lib.scoring import rank_providers

        task_context = self._prepare_task_context(inputs)
        from tools.provider_routing import filter_explicit_route

        candidates = filter_explicit_route(inputs, self._providers())

        # Rank mode — return scored provider rankings without generating
        if inputs.get("operation") == "rank":
            rankings = rank_providers(candidates, task_context)
            return ToolResult(
                success=True,
                data={
                    "rankings": self._serialize_rankings(candidates, rankings),
                    "explanation": "\n".join(r.explain() for r in rankings[:5]),
                    "normalized_task_context": task_context,
                },
            )

        # Normal generation — use scored selection
        tool, score = self._select_best_tool(inputs, candidates, task_context)
        if tool is None:
            return ToolResult(success=False, error="No TTS provider available.")

        result = tool.execute(self._adapt_inputs(tool, inputs))
        if result.success:
            result.data.setdefault("selected_tool", tool.name)
            result.data["selected_provider"] = tool.provider
            result.data["selection_reason"] = (
                score.explain() if score else f"Selected {tool.provider} ({tool.name})"
            )
            if score:
                result.data["provider_score"] = score.to_dict()
            result.data.update(self._tool_context_payload(tool))
            result.data["alternatives_considered"] = [
                t.name
                for t in candidates
                if t.name != tool.name and t.get_status().value == "available"
            ]
        return result

    @staticmethod
    def _adapt_inputs(tool: BaseTool, inputs: dict[str, Any]) -> dict[str, Any]:
        """Translate capability-level controls to provider-native inputs."""
        adapted = dict(inputs)
        if tool.name != "azure_tts":
            return adapted

        if inputs.get("voice_id") and not inputs.get("voice"):
            adapted["voice"] = inputs["voice_id"]

        speed = inputs.get("speaking_rate", inputs.get("speed"))
        if speed is not None and "rate" not in inputs:
            percent = round((float(speed) - 1.0) * 100)
            adapted["rate"] = f"{percent:+d}%" if percent else "0%"

        pitch = inputs.get("pitch")
        if isinstance(pitch, (int, float)):
            adapted["pitch"] = f"{pitch:+g}st" if pitch else "0%"

        # The selector's numeric style is ElevenLabs-specific. Azure's style
        # is a named express-as value such as "calm" or "newscast".
        if not isinstance(inputs.get("style"), str):
            adapted.pop("style", None)

        output_format = str(inputs.get("output_format", ""))
        if output_format.startswith("mp3"):
            adapted["output_format"] = "mp3"
        elif output_format.startswith(("wav", "riff", "pcm")):
            adapted["output_format"] = "wav"
        return adapted

    def _select_best_tool(
        self,
        inputs: dict[str, Any],
        candidates: list[BaseTool],
        task_context: dict[str, Any],
    ) -> tuple[BaseTool | None, object]:
        """Select the best TTS provider using scored ranking."""
        from lib.scoring import rank_providers

        from tools.provider_routing import filter_explicit_route

        candidates = filter_explicit_route(inputs, candidates)
        preferred = inputs.get("preferred_provider", "auto")
        allowed = set(inputs.get("allowed_providers") or [])
        if allowed:
            candidates = [tool for tool in candidates if tool.provider in allowed]

        rankings = rank_providers(candidates, task_context)

        tool_by_name: dict[str, BaseTool] = {}
        for tool in candidates:
            if (
                tool.name not in tool_by_name
                and tool.get_status() == ToolStatus.AVAILABLE
            ):
                tool_by_name[tool.name] = tool

        if preferred != "auto":
            for score_item in rankings:
                if (
                    score_item.provider == preferred
                    and score_item.tool_name in tool_by_name
                ):
                    return tool_by_name[score_item.tool_name], score_item

        for score_item in rankings:
            if score_item.tool_name in tool_by_name:
                return tool_by_name[score_item.tool_name], score_item

        return None, None

    def _prepare_task_context(self, inputs: dict[str, Any]) -> dict[str, Any]:
        from lib.scoring import normalize_task_context

        return normalize_task_context(
            inputs.get("task_context", {}),
            prompt=inputs.get("text", ""),
            capability=self.capability,
            operation=inputs.get("operation", "generate"),
        )

    @staticmethod
    def _tool_context_payload(tool: BaseTool) -> dict[str, Any]:
        info = tool.get_info()
        return {
            "selected_tool_agent_skills": info.get("agent_skills", []),
            "required_agent_skills": info.get("agent_skills", []),
            "selected_tool_usage_location": info.get("usage_location"),
            "selected_tool_best_for": info.get("best_for", []),
        }

    def _serialize_rankings(
        self, candidates: list[BaseTool], rankings: list[object]
    ) -> list[dict[str, Any]]:
        tool_by_name = {tool.name: tool for tool in candidates}
        serialized: list[dict[str, Any]] = []
        for score in rankings:
            item = score.to_dict()
            tool = tool_by_name.get(score.tool_name)
            if tool:
                info = tool.get_info()
                item["agent_skills"] = info.get("agent_skills", [])
                item["usage_location"] = info.get("usage_location")
                item["best_for"] = info.get("best_for", [])
                item["status"] = str(tool.get_status())
            serialized.append(item)
        return serialized
