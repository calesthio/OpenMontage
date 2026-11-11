"""Tool registry with status, stability, and support-envelope reporting.

The registry discovers all registered tools, reports their availability,
and lets the orchestrator/agents query capabilities by tier, status, etc.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from collections.abc import Iterable
from types import ModuleType
from typing import Any, Optional

from tools.base_tool import BaseTool, ToolStatus, ToolTier, ToolStability


# Unicode punctuation that breaks on Windows cp1252 stdout. Map each to an
# ASCII equivalent. This only touches strings rendered by registry helpers
# that an agent is likely to print to the user at preflight — not docstrings,
# comments, or markdown.
_UNICODE_DASH_REPLACEMENTS = {
    "\u2014": "--",   # em dash
    "\u2013": "-",    # en dash
    "\u2212": "-",    # minus sign
    "\u2018": "'",    # left single quote
    "\u2019": "'",    # right single quote
    "\u201c": '"',    # left double quote
    "\u201d": '"',    # right double quote
    "\u2026": "...",  # ellipsis
}


def _scrub_unicode_dashes(value: Any) -> Any:
    """Recursively normalize unicode punctuation in str leaves to ASCII.

    Used to keep `provider_menu_summary()` output readable on Windows cp1252
    stdout. Does NOT modify dict/list structure or non-string values.
    """
    if isinstance(value, str):
        out = value
        for needle, repl in _UNICODE_DASH_REPLACEMENTS.items():
            if needle in out:
                out = out.replace(needle, repl)
        return out
    if isinstance(value, list):
        return [_scrub_unicode_dashes(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_scrub_unicode_dashes(item) for item in value)
    if isinstance(value, dict):
        return {k: _scrub_unicode_dashes(v) for k, v in value.items()}
    return value


_COMPACT_HINT_CHARS = 160


def _group_setup_offers(
    setup_offers: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Collapse per-tool setup offers into one entry per credential.

    A machine with few keys configured has ~100 unavailable tools, and most of
    them share a handful of env vars. Listing each tool separately is what made
    the preflight summary ~40 KB; the agent then had to regroup it by env var
    anyway (AGENT_GUIDE.md > "Provider Menu"). Returns ``(groups, others)``:
    ``groups`` are env-var fixes ordered by how many tools they unlock,
    ``others`` are the offers that are not a plain env-var fix (local servers,
    installs), trimmed to a short hint.
    """
    grouped: dict[tuple[str, ...], dict[str, Any]] = {}
    others: list[dict[str, Any]] = []
    for offer in setup_offers:
        env_vars = tuple(sorted(offer.get("env_vars") or []))
        hint = offer.get("install_instructions") or ""
        if not env_vars:
            entry = {
                "capability": offer.get("capability"),
                "tool": offer.get("tool"),
                "install_instructions": (
                    hint
                    if len(hint) <= _COMPACT_HINT_CHARS
                    else hint[: _COMPACT_HINT_CHARS - 3].rstrip() + "..."
                ),
            }
            for key in ("kind", "fix_complexity"):
                if offer.get(key):
                    entry[key] = offer[key]
            others.append(entry)
            continue
        group = grouped.setdefault(
            env_vars,
            {
                "env_vars": list(env_vars),
                "unlocks": 0,
                "capabilities": {},
                "tools": [],
                "install_instructions": hint,
            },
        )
        group["unlocks"] += 1
        capability = offer.get("capability") or "generic"
        group["capabilities"][capability] = group["capabilities"].get(capability, 0) + 1
        group["tools"].append(offer.get("tool"))
    groups = sorted(grouped.values(), key=lambda g: (-g["unlocks"], g["env_vars"]))
    return groups, others


class ToolRegistry:
    """Central registry of all OpenMontage tools."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._discovered_packages: set[str] = set()
        # module name -> why it could not be imported/registered (discover()).
        self.discovery_errors: dict[str, str] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        if not tool.name:
            raise ValueError("Tool must have a non-empty name")
        self._tools[tool.name] = tool

    def clear(self) -> None:
        """Clear registered tools and discovery state."""
        self._tools.clear()
        self._discovered_packages.clear()
        self.discovery_errors.clear()

    def register_module(self, module: ModuleType) -> list[str]:
        """Register all concrete BaseTool subclasses defined in a module."""
        registered: list[str] = []
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls is BaseTool or not issubclass(cls, BaseTool):
                continue
            if cls.__module__ != module.__name__ or inspect.isabstract(cls):
                continue
            tool = cls()
            self.register(tool)
            registered.append(tool.name)
        return registered

    @staticmethod
    def _load_dotenv() -> None:
        """Load .env into os.environ if present, so tools can find API keys."""
        from pathlib import Path

        from lib.env_loader import load_env

        load_env(Path(__file__).resolve().parent.parent)

    def discover(self, package_name: str = "tools") -> list[str]:
        """Import a package tree and register any concrete tools it defines.

        One module that fails to import (a syntax error, a missing optional
        dependency at import time, a constructor that raises) must not take the
        whole registry — and with it preflight for every pipeline — down. Each
        module is isolated; what failed is kept in ``discovery_errors`` and
        surfaced in ``provider_menu_summary()["runtime_warnings"]`` so the
        breakage is visible instead of fatal or silent.
        """
        self._load_dotenv()
        package = importlib.import_module(package_name)
        discovered: list[str] = []
        package_paths = getattr(package, "__path__", None)
        if package_paths is None:
            return self.register_module(package)

        def note(module_name: str, exc: BaseException) -> None:
            self.discovery_errors[module_name] = f"{type(exc).__name__}: {exc}"[:300]

        def on_walk_error(module_name: str) -> None:
            # walk_packages imports a sub-package to walk into it.
            import sys

            note(module_name, sys.exc_info()[1] or ImportError("import failed"))

        for module_info in pkgutil.walk_packages(
            package_paths, f"{package.__name__}.", onerror=on_walk_error
        ):
            if module_info.name.endswith(".base_tool") or module_info.name.endswith(".tool_registry"):
                continue
            try:
                module = importlib.import_module(module_info.name)
                discovered.extend(self.register_module(module))
            except Exception as exc:
                note(module_info.name, exc)
                continue
            self.discovery_errors.pop(module_info.name, None)

        self._discovered_packages.add(package_name)
        return discovered

    def ensure_discovered(self, package_name: str = "tools") -> None:
        """Load tool modules once before reporting capabilities."""
        if package_name not in self._discovered_packages:
            self.discover(package_name)

    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_all(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def get_by_tier(self, tier: ToolTier) -> list[BaseTool]:
        """Get all tools in a given tier."""
        return [t for t in self._tools.values() if t.tier == tier]

    def get_by_capability(self, capability: str) -> list[BaseTool]:
        """Get all tools registered for a top-level capability family."""
        return [t for t in self._tools.values() if t.capability == capability]

    def capability_coverage(self, tool_names: Iterable[str]) -> dict[str, dict[str, int]]:
        """Count available concrete providers for capabilities touched by tools.

        Selector tools identify a capability but are excluded from its provider
        totals. Unknown tool names are ignored so stale optional manifest entries
        do not hide coverage for tools that are still registered.
        """
        self.ensure_discovered()
        capabilities = {
            tool.capability
            for name in tool_names
            if (tool := self._tools.get(name)) is not None
        }
        coverage: dict[str, dict[str, int]] = {}
        for capability in sorted(capabilities):
            providers = [
                tool
                for tool in self._tools.values()
                if tool.capability == capability and tool.provider != "selector"
            ]
            coverage[capability] = {
                "available": sum(
                    tool.get_status() == ToolStatus.AVAILABLE for tool in providers
                ),
                "total": len(providers),
            }
        return coverage

    def uncovered_capabilities(self, tool_names: Iterable[str]) -> list[str]:
        """Return touched capability families with no available provider."""
        return [
            capability
            for capability, counts in self.capability_coverage(tool_names).items()
            if counts["available"] == 0
        ]

    def get_by_provider(self, provider: str) -> list[BaseTool]:
        """Get all tools backed by a specific provider."""
        return [t for t in self._tools.values() if t.provider == provider]

    def get_by_status(self, status: ToolStatus) -> list[BaseTool]:
        """Get all tools with a given status."""
        return [t for t in self._tools.values() if t.get_status() == status]

    def get_available(self) -> list[BaseTool]:
        """Get all tools that are currently available."""
        return self.get_by_status(ToolStatus.AVAILABLE)

    def get_unavailable(self) -> list[BaseTool]:
        """Get all tools that are currently unavailable."""
        return self.get_by_status(ToolStatus.UNAVAILABLE)

    def get_by_stability(self, stability: ToolStability) -> list[BaseTool]:
        """Get all tools at a given stability level."""
        return [t for t in self._tools.values() if t.stability == stability]

    def find_by_capability(self, capability: str) -> list[BaseTool]:
        """Find tools that declare a given capability."""
        return [
            t for t in self._tools.values()
            if capability in t.capabilities
        ]

    def find_fallback(self, tool_name: str) -> Optional[BaseTool]:
        """Find the fallback tool for a given tool, if declared and available."""
        tool = self.get(tool_name)
        if tool is None:
            return None
        candidates = list(tool.fallback_tools or [])
        if tool.fallback and tool.fallback not in candidates:
            candidates.append(tool.fallback)
        for name in candidates:
            fb = self.get(name)
            if fb and fb.get_status() == ToolStatus.AVAILABLE:
                return fb
        return None

    def support_envelope(self) -> dict[str, Any]:
        """Generate a full support-envelope report for all tools.

        Returns a dict mapping tool name to its contract info + live status.
        This is the primary report the orchestrator uses to understand
        what the system can and cannot do.
        """
        self.ensure_discovered()
        report: dict[str, Any] = {}
        for name, tool in self._tools.items():
            info = tool.get_info()
            report[name] = info
        return report

    def capability_catalog(self) -> dict[str, list[dict[str, Any]]]:
        """Group the support envelope by top-level capability."""
        self.ensure_discovered()
        grouped: dict[str, list[dict[str, Any]]] = {}
        for tool in self._tools.values():
            grouped.setdefault(tool.capability, []).append(tool.get_info())
        for items in grouped.values():
            items.sort(key=lambda item: (item["provider"], item["name"]))
        return dict(sorted(grouped.items()))

    def provider_catalog(self) -> dict[str, list[dict[str, Any]]]:
        """Group the support envelope by provider."""
        self.ensure_discovered()
        grouped: dict[str, list[dict[str, Any]]] = {}
        for tool in self._tools.values():
            grouped.setdefault(tool.provider, []).append(tool.get_info())
        for items in grouped.values():
            items.sort(key=lambda item: (item["capability"], item["name"]))
        return dict(sorted(grouped.items()))

    def tier_summary(self) -> dict[str, dict[str, int]]:
        """Summarize tool counts by tier and status.

        Returns:
            {"core": {"available": 5, "unavailable": 2, "degraded": 0}, ...}
        """
        summary: dict[str, dict[str, int]] = {}
        for tier in ToolTier:
            tier_tools = self.get_by_tier(tier)
            counts = {"available": 0, "unavailable": 0, "degraded": 0}
            for t in tier_tools:
                status = t.get_status().value
                counts[status] = counts.get(status, 0) + 1
            if tier_tools:
                summary[tier.value] = counts
        return summary

    def provider_menu(self) -> dict[str, dict[str, Any]]:
        """Generate a capability-grouped provider menu for user-facing display.

        Returns a dict like:
        {
            "video_generation": {
                "available": [{"name": ..., "provider": ..., "best_for": ...}],
                "unavailable": [{"name": ..., "provider": ..., "install_instructions": ...}],
                "total": 12,
                "configured": 2,
            },
            ...
        }

        This powers the agent's preflight provider menu — the agent reads this
        output and presents it to the user.  Adding a new tool to tools/ is
        enough; this method auto-discovers it.
        """
        self.ensure_discovered()
        menu: dict[str, dict[str, Any]] = {}

        # Skip selectors — they aggregate, they aren't providers themselves
        tools = [t for t in self._tools.values() if t.provider != "selector"]

        for tool in tools:
            cap = tool.capability
            if cap not in menu:
                menu[cap] = {"available": [], "unavailable": [], "total": 0, "configured": 0}

            info = tool.get_info()
            status = tool.get_status()
            entry = {
                "name": tool.name,
                "provider": tool.provider,
                "runtime": tool.runtime.value,
                "best_for": tool.best_for,
                "dependencies": info.get("dependencies", []),
                "install_instructions": tool.install_instructions,
                "status": status.value,
            }
            for extra_key in (
                "source_provider_menu",
                "source_provider_summary",
                "render_engines",
                "remotion_note",
                "provider_matrix",
                "setup_offer",
                "operation_statuses",
                "resource_profiles",
                "resource_profile_note",
            ):
                if extra_key in info:
                    entry[extra_key] = info[extra_key]

            if status == ToolStatus.AVAILABLE:
                menu[cap]["available"].append(entry)
                menu[cap]["configured"] += 1
            else:
                menu[cap]["unavailable"].append(entry)
            menu[cap]["total"] += 1

        for bucket in menu.values():
            bucket["available"].sort(key=lambda entry: (entry["provider"], entry["name"]))
            bucket["unavailable"].sort(key=lambda entry: (entry["provider"], entry["name"]))

        return dict(sorted(menu.items()))

    def provider_menu_summary(self, compact: bool = False) -> dict[str, Any]:
        """Compact, human-ready rollup of provider_menu() for onboarding/preflight.

        ``compact=True`` is the form to print at preflight: it replaces the
        per-tool ``setup_offers`` list with ``setup_groups`` (one entry per
        credential, with the number of tools it unlocks per capability) and
        ``other_setup`` (local-server and install fixes, hint only). Same
        facts, a fraction of the output. The default keeps ``setup_offers``
        with each tool's full structured offer.

        Returns a dict shaped for the "N of M configured" capability menu the
        agent is supposed to present to the user per AGENT_GUIDE.md → "Provider
        Menu (Mandatory at Preflight)". Collapses the firehose of
        support_envelope() into something the agent can paraphrase in plain
        language in a few lines.

        Example output (abbreviated):
        {
          "composition_runtimes": {
            "ffmpeg": True,
            "remotion": True,
            "hyperframes": True,
          },
          "capabilities": [
            {"capability": "video_generation", "configured": 10, "total": 16,
             "available_providers": ["fal", "heygen", ...],
             "unavailable_providers": ["openai", ...]},
            ...
          ],
          "setup_offers": [
             {"capability": "music_generation", "tool": "suno_music",
              "install_instructions": "Add SUNO_API_KEY to .env"},
             ...
          ],
          "runtime_warnings": [
             "hyperframes: npm package `hyperframes` not resolvable: ...",
             ...
          ],
        }

        Agents should use this as the source for the preflight capability
        menu rather than rendering `support_envelope()` or `provider_menu()`
        raw. See AGENT_GUIDE.md > "Provider Menu (Mandatory at Preflight)".
        """
        self.ensure_discovered()
        menu = self.provider_menu()

        # Composition runtimes — lift from video_compose.get_info() since
        # they're the signal the runtime-selection contract depends on.
        comp_runtimes: dict[str, bool] = {}
        runtime_warnings: list[str] = []
        # A tool module that failed to load is missing from every count below.
        # Say so first: the menu would otherwise just look smaller.
        for module_name, error in sorted(self.discovery_errors.items()):
            runtime_warnings.append(
                f"tool module {module_name} failed to load and its tools are "
                f"missing from this menu: {error}"
            )
        vc = self._tools.get("video_compose")
        if vc is not None:
            info = vc.get_info()
            engines = info.get("render_engines") or {}
            comp_runtimes = {k: bool(v) for k, v in engines.items()}
        # If hyperframes_compose is registered, surface its npm-resolve reasons
        # explicitly — those are the "looks available but isn't" failures.
        hf = self._tools.get("hyperframes_compose")
        if hf is not None:
            hf_info = hf.get_info()
            rc = hf_info.get("hyperframes_runtime") or {}
            for reason in rc.get("reasons") or []:
                runtime_warnings.append(f"hyperframes: {reason}")

        diagram_gen = self._tools.get("diagram_gen")
        if diagram_gen is not None:
            operation_statuses = diagram_gen.get_info().get("operation_statuses") or {}
            if operation_statuses.get("mermaid") != "available":
                runtime_warnings.append(
                    "diagram_gen: Mermaid CLI (mmdc) is unavailable; install with "
                    "npm install -g @mermaid-js/mermaid-cli"
                )

        # Capabilities rollup (configured/total + provider lists).
        # When a provider has multiple tools (e.g. seedance-fal and
        # seedance-replicate both reporting provider="seedance"), a
        # naive set-split shows the provider in BOTH available and
        # unavailable — confusing for users. Dedupe: if the provider has
        # any available tool, do NOT list it as unavailable.
        capabilities: list[dict[str, Any]] = []
        for cap, bucket in menu.items():
            available_providers = {
                e.get("provider") for e in bucket.get("available", [])
            } - {None}
            unavailable_providers = (
                {e.get("provider") for e in bucket.get("unavailable", [])}
                - {None}
                - available_providers  # provider with any available tool wins
            )
            capabilities.append(
                {
                    "capability": cap,
                    "configured": bucket.get("configured", 0),
                    "total": bucket.get("total", 0),
                    "available_providers": sorted(available_providers),
                    "unavailable_providers": sorted(unavailable_providers),
                }
            )

        # Setup offers — unavailable tools that would be 1-minute env-var fixes.
        # Filter for short install instructions referencing an env var so the
        # agent can lead with the easy wins.
        setup_offers: list[dict[str, Any]] = []
        for cap, bucket in menu.items():
            for entry in bucket.get("unavailable", []):
                offer = entry.get("setup_offer")
                if offer:
                    setup_offers.append(
                        {
                            "capability": cap,
                            "tool": entry.get("name"),
                            "provider": entry.get("provider"),
                            "runtime": entry.get("runtime"),
                            "install_instructions": entry.get("install_instructions") or "",
                            **offer,
                        }
                    )
                    continue

                env_vars = [
                    dep[4:]
                    for dep in entry.get("dependencies", [])
                    if isinstance(dep, str) and dep.startswith("env:")
                ]
                if env_vars:
                    setup_offers.append(
                        {
                            "capability": cap,
                            "tool": entry.get("name"),
                            "provider": entry.get("provider"),
                            "runtime": entry.get("runtime"),
                            "kind": "env_var",
                            "fix_complexity": "1-minute env-var",
                            "env_vars": env_vars,
                            "install_instructions": entry.get("install_instructions") or "",
                        }
                    )
                    continue

                hint = entry.get("install_instructions") or ""
                # Heuristic: 1-minute fixes mention an env var or API key.
                if any(k in hint.lower() for k in ["api key", "env", "_key=", "_api"]):
                    setup_offers.append(
                        {
                            "capability": cap,
                            "tool": entry.get("name"),
                            "provider": entry.get("provider"),
                            "runtime": entry.get("runtime"),
                            "install_instructions": hint,
                        }
                    )

            for entry in bucket.get("available", []) + bucket.get("unavailable", []):
                if entry.get("resource_profile_note"):
                    runtime_warnings.append(
                        f"{entry.get('name')}: {entry.get('resource_profile_note')}"
                    )

        # A minimal FFmpeg build passes every `cmd:ffmpeg` check and then fails
        # at render time; say up front what this build cannot do.
        try:
            from tools.ffmpeg_capabilities import capability_warnings

            runtime_warnings.extend(capability_warnings())
        except Exception:
            pass

        result: dict[str, Any] = {
            "composition_runtimes": comp_runtimes,
            "capabilities": capabilities,
        }
        if compact:
            result["setup_groups"], result["other_setup"] = _group_setup_offers(
                setup_offers
            )
        else:
            result["setup_offers"] = setup_offers
        result["runtime_warnings"] = runtime_warnings
        # Normalize em-dashes and en-dashes to ASCII so preflight output prints
        # cleanly on Windows cp1252 stdout (the default on Git Bash / PowerShell
        # without PYTHONIOENCODING=utf-8). Agents paste this dict into chat; a
        # mojibake `�` in an install_instructions string looks like a bug.
        # Markdown docs keep their typographic dashes; this only touches the
        # runtime-reported strings.
        return _scrub_unicode_dashes(result)

    # Post-hoc fix: narrow helper that keeps the registry output stdout-safe on
    # Windows cp1252 without imposing a new style rule on every tool author.

    def gpu_required_tools(self) -> list[str]:
        """List tools that require GPU (VRAM > 0)."""
        return [
            t.name for t in self._tools.values()
            if t.resource_profile.vram_mb > 0
        ]

    def network_required_tools(self) -> list[str]:
        """List tools that require network access."""
        return [
            t.name for t in self._tools.values()
            if t.resource_profile.network_required
        ]


# Singleton registry instance
registry = ToolRegistry()
