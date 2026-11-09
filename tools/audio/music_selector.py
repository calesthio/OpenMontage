"""Capability-level music selector spanning the three music capabilities.

Music is the one media family whose tools are split across three capability
names, which is why it historically had no selector while ``tts``, ``image_generation``
and ``video_generation`` all did:

    music_library      music_library                     free, user's own files
    music_search       pixabay_music, freesound_music    free (pixabay needs no key)
    music_generation   music_gen, google_music           paid API key

Checking only one of those is the classic mistake — it hides the free stock
sources and makes music look unavailable when it isn't. This selector discovers
all three from the registry, so adding a provider requires only creating the tool
file in ``tools/audio/``; no changes here.

Two operations:

``plan`` (default)
    Survey every tier and report what is actually reachable, with cost labels.
    This is what the mandatory Music Plan in AGENT_GUIDE.md needs at proposal
    time — it answers "what music can I offer the user?" without spending money.

``acquire``
    Actually obtain a track. Walks the tiers cheapest-first (library, then free
    stock search, then paid generation) and stops at the first success, unless
    ``preferred_provider`` or ``max_cost_tier`` says otherwise.

Free-before-paid is the default on purpose: burning a paid generation call when
a royalty-free track would do is pure waste.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

# Cheapest first. The whole point of the selector.
_TIERS: list[tuple[str, str]] = [
    ("music_library", "free-local"),
    ("music_search", "free-api"),
    ("music_generation", "paid"),
]

_COST_RANK = {"free-local": 0, "free-api": 1, "paid": 2}


class MusicSelector(BaseTool):
    name = "music_selector"
    version = "0.1.0"
    tier = ToolTier.SOURCE
    # Deliberately its own capability, NOT one of the three it aggregates.
    # Registering as "music_generation" would pollute the very lookup the
    # director skills perform, and would make _providers() recurse.
    capability = "music"
    provider = "selector"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.HYBRID

    dependencies = []  # the underlying providers declare their own
    install_instructions = (
        "No setup of its own. It routes to whatever music tools are available:\n"
        "  - music_library: drop audio files in music_library/ (free)\n"
        "  - pixabay_music: works with no API key at all (free)\n"
        "  - freesound_music: set FREESOUND_API_KEY (free key)\n"
        "  - music_gen: set ELEVENLABS_API_KEY (paid)\n"
        "  - google_music: set GEMINI_API_KEY or GOOGLE_API_KEY (paid, Lyria)"
    )

    agent_skills = ["music"]

    capabilities = [
        "music_planning",
        "music_acquisition",
        "provider_selection",
    ]
    supports = {
        "spans_three_capabilities": True,
        "free_before_paid": True,
        "cost_tier_ceiling": True,
    }
    best_for = [
        "the mandatory Music Plan at proposal time",
        "getting a track without knowing which providers are configured",
        "avoiding a paid generation call when free music would do",
    ]
    not_good_for = [
        "picking a specific track by ear (present options to the user instead)",
        "fine-grained provider parameters (call the provider tool directly)",
    ]

    input_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["plan", "acquire"],
                "default": "plan",
                "description": (
                    "'plan' surveys what music is reachable and costs nothing. "
                    "'acquire' actually obtains a track, cheapest tier first."
                ),
            },
            "query": {
                "type": "string",
                "description": "Search terms for stock music, e.g. 'ambient cinematic build'. Falls back to 'prompt' if absent.",
            },
            "prompt": {
                "type": "string",
                "description": "Generation prompt for music_gen / google_music. Falls back to 'query' if absent.",
            },
            "duration_seconds": {
                "type": "number",
                "description": "Target track length. Maps to duration_seconds for generation and min/max_duration for search.",
            },
            "output_path": {"type": "string"},
            "preferred_provider": {
                "type": "string",
                "default": "auto",
                "description": "Provider name (e.g. 'pixabay_music') or 'auto'. Valid values are discovered at runtime.",
            },
            "allowed_providers": {
                "type": "array",
                "items": {"type": "string"},
            },
            "max_cost_tier": {
                "type": "string",
                "enum": ["free-local", "free-api", "paid"],
                "default": "paid",
                "description": "Ceiling on what may be used. Set 'free-api' to forbid paid generation entirely.",
            },
            "library_dir": {
                "type": "string",
                "description": "Override for the music_library folder. Passed through.",
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "operation": {"type": "string"},
            "tiers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "capability": {"type": "string"},
                        "cost_tier": {"type": "string"},
                        "available": {"type": "array", "items": {"type": "string"}},
                        "unavailable": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "any_music_available": {"type": "boolean"},
            "cheapest_available": {"type": ["string", "null"]},
            "summary": {"type": "string"},
            "selected_tool": {"type": "string"},
            "selected_provider": {"type": "string"},
            "selection_reason": {"type": "string"},
            "attempted": {"type": "array", "items": {"type": "string"}},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=0, network_required=False
    )
    side_effects = []  # 'plan' is read-only; 'acquire' delegates to the provider
    user_visible_verification = [
        "Confirm the chosen track's mood matches the playbook's audio.music_mood",
        "Confirm you are not paying for generation when a free source would do",
    ]

    # ---- Discovery ---------------------------------------------------------

    def _tools_for(self, capability: str) -> list[BaseTool]:
        from tools.tool_registry import registry

        registry.ensure_discovered()
        return [t for t in registry.get_by_capability(capability) if t.name != self.name]

    def _all_providers(self) -> list[tuple[BaseTool, str, str]]:
        """Every music tool as (tool, capability, cost_tier), cheapest first."""
        found: list[tuple[BaseTool, str, str]] = []
        for capability, cost_tier in _TIERS:
            for tool in self._tools_for(capability):
                found.append((tool, capability, cost_tier))
        return found

    @property
    def fallback_tools(self) -> list[str]:
        return [t.name for t, _, _ in self._all_providers()]

    @property
    def provider_matrix(self) -> dict[str, dict[str, str]]:
        matrix: dict[str, dict[str, str]] = {}
        for tool, capability, cost_tier in self._all_providers():
            strength = ", ".join(tool.best_for) if tool.best_for else tool.name
            matrix[tool.provider] = {
                "tool": tool.name,
                "capability": capability,
                "cost": cost_tier,
                "strength": strength,
            }
        return matrix

    @staticmethod
    def _is_available(tool: BaseTool) -> bool:
        try:
            return tool.get_status() == ToolStatus.AVAILABLE
        except Exception:
            return False

    def get_status(self) -> ToolStatus:
        for tool, _, _ in self._all_providers():
            if self._is_available(tool):
                return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 2.0 if inputs.get("operation", "plan") == "plan" else 30.0

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        if inputs.get("operation", "plan") == "plan":
            return 0.0
        chosen = self._pick(inputs)
        if not chosen:
            return 0.0
        tool, _, _ = chosen
        try:
            return tool.estimate_cost(self._inputs_for(tool, inputs))
        except Exception:
            return 0.0

    # ---- Input mapping -----------------------------------------------------

    def _inputs_for(self, tool: BaseTool, inputs: dict[str, Any]) -> dict[str, Any]:
        """Translate the selector's inputs into what this provider expects."""
        query = inputs.get("query") or inputs.get("prompt") or ""
        prompt = inputs.get("prompt") or inputs.get("query") or ""
        duration = inputs.get("duration_seconds")
        out: dict[str, Any] = {}

        if tool.capability == "music_library":
            if inputs.get("library_dir"):
                out["library_dir"] = inputs["library_dir"]
            return out

        if tool.capability == "music_search":
            out["query"] = query
            if duration:
                # Give the search a window around the target rather than an
                # exact match, or short catalogs return nothing at all.
                out["min_duration"] = max(0, int(duration * 0.5))
                out["max_duration"] = int(duration * 2)
        else:  # music_generation
            out["prompt"] = prompt
            if duration:
                out["duration_seconds"] = duration

        if inputs.get("output_path"):
            out["output_path"] = inputs["output_path"]
        return out

    # ---- Selection ---------------------------------------------------------

    def _candidates(self, inputs: dict[str, Any]) -> list[tuple[BaseTool, str, str]]:
        allowed = set(inputs.get("allowed_providers") or [])
        ceiling = _COST_RANK.get(inputs.get("max_cost_tier", "paid"), 2)

        out = []
        for tool, capability, cost_tier in self._all_providers():
            if _COST_RANK[cost_tier] > ceiling:
                continue
            if allowed and tool.provider not in allowed and tool.name not in allowed:
                continue
            out.append((tool, capability, cost_tier))
        return out

    def _pick(self, inputs: dict[str, Any]) -> Optional[tuple[BaseTool, str, str]]:
        candidates = [c for c in self._candidates(inputs) if self._is_available(c[0])]
        if not candidates:
            return None

        preferred = inputs.get("preferred_provider", "auto")
        if preferred and preferred != "auto":
            for entry in candidates:
                if entry[0].provider == preferred or entry[0].name == preferred:
                    return entry

        return candidates[0]  # already cheapest-first

    # ---- Execution ---------------------------------------------------------

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        operation = inputs.get("operation", "plan")

        if operation == "plan":
            return self._plan(inputs, start)
        return self._acquire(inputs, start)

    def _plan(self, inputs: dict[str, Any], start: float) -> ToolResult:
        tiers: list[dict[str, Any]] = []
        cheapest: Optional[str] = None

        for capability, cost_tier in _TIERS:
            available, unavailable = [], []
            for tool in self._tools_for(capability):
                (available if self._is_available(tool) else unavailable).append(tool.name)
            if available and cheapest is None:
                cheapest = available[0]
            tiers.append(
                {
                    "capability": capability,
                    "cost_tier": cost_tier,
                    "available": available,
                    "unavailable": unavailable,
                }
            )

        any_available = cheapest is not None
        if any_available:
            lines = [
                f"{t['capability']} ({t['cost_tier']}): "
                + (", ".join(t["available"]) if t["available"] else "none configured")
                for t in tiers
            ]
            summary = (
                "MUSIC PLAN\n"
                + "\n".join("  " + line for line in lines)
                + f"\n  Cheapest available: {cheapest}"
            )
        else:
            summary = (
                "MUSIC PLAN\n  No music source is reachable. Offer the user the "
                "music_library/ drop path, or configure a key. Tell them now, not "
                "at the asset stage."
            )

        return ToolResult(
            success=True,
            data={
                "operation": "plan",
                "tiers": tiers,
                "any_music_available": any_available,
                "cheapest_available": cheapest,
                "summary": summary,
            },
            duration_seconds=round(time.time() - start, 2),
        )

    def _acquire(self, inputs: dict[str, Any], start: float) -> ToolResult:
        candidates = [c for c in self._candidates(inputs) if self._is_available(c[0])]
        if not candidates:
            return ToolResult(
                success=False,
                error=(
                    "No music provider available within max_cost_tier="
                    f"{inputs.get('max_cost_tier', 'paid')}. Run operation='plan' "
                    "to see what is reachable."
                ),
            )

        preferred = inputs.get("preferred_provider", "auto")
        if preferred and preferred != "auto":
            candidates.sort(
                key=lambda e: 0 if (e[0].provider == preferred or e[0].name == preferred) else 1
            )

        attempted: list[str] = []
        last_error = ""

        for tool, capability, cost_tier in candidates:
            attempted.append(tool.name)
            try:
                result = tool.execute(self._inputs_for(tool, inputs))
            except Exception as exc:  # a broken provider must not sink the chain
                last_error = f"{tool.name}: {exc}"
                continue

            if result.success:
                result.data = result.data or {}
                result.data.setdefault("selected_tool", tool.name)
                result.data["selected_provider"] = tool.provider
                result.data["selected_capability"] = capability
                result.data["cost_tier"] = cost_tier
                result.data["selection_reason"] = (
                    f"Selected {tool.name} ({cost_tier}). Cheapest reachable source "
                    f"within max_cost_tier={inputs.get('max_cost_tier', 'paid')}."
                )
                result.data["attempted"] = attempted
                return result

            last_error = f"{tool.name}: {result.error}"

        return ToolResult(
            success=False,
            error=f"All music providers failed. Attempted: {', '.join(attempted)}. Last error: {last_error}",
            data={"attempted": attempted},
            duration_seconds=round(time.time() - start, 2),
        )
