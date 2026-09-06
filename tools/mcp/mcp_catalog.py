"""Inspect all configured MCP servers and their tools (Agent review input)."""

from __future__ import annotations

from typing import Any

from tools.base_tool import BaseTool, ToolResult, ToolRuntime, ToolStability, ToolTier
from tools.mcp.mcp_config import load_mcp_config
from tools.mcp.mcp_registry import _signature_of, list_server_tools

_HINT_WORDS = ("video", "image", "audio", "text", "transcript", "speech")


class MCPCatalog(BaseTool):
    name = "mcp_catalog"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "mcp"
    provider = "openmontage"
    stability = ToolStability.BETA
    runtime = ToolRuntime.HYBRID

    capabilities = ["mcp_discovery"]
    best_for = ["reviewing which MCP tools exist before bridging them"]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        cfg = load_mcp_config()
        operation = inputs.get("operation", "list")
        signature = _signature_of(cfg)
        servers: list[dict[str, Any]] = []
        for server in cfg.servers:
            try:
                tools = list_server_tools(server, signature)
            except Exception as exc:
                servers.append({"slug": server.slug, "error": str(exc)[:200]})
                continue
            entries = [
                {
                    "server": server.slug,
                    "tool_name": tool.name,
                    "title": getattr(tool, "title", None) or tool.name,
                    "description": getattr(tool, "description", "") or "",
                    "input_schema": getattr(tool, "input_schema", {}) or {},
                    "frozen": server.frozen_capability(tool.name) is not None,
                    "capability": server.frozen_capability(tool.name),
                    "output_hints": sorted({
                        word for word in _HINT_WORDS
                        if word in f"{tool.name} {getattr(tool, 'description', '')}".lower()
                    }),
                }
                for tool in tools
            ]
            servers.append({"slug": server.slug, "tools": entries})
        if operation == "list":
            summary = [{
                "slug": s["slug"],
                "transport": next((x.transport for x in cfg.servers if x.slug == s["slug"]), "?"),
                "frozen_count": len([t for t in s.get("tools", []) if t["frozen"]]),
                "unfrozen_count": len([t for t in s.get("tools", []) if not t["frozen"]]),
                "error": s.get("error"),
            } for s in servers]
            return ToolResult(success=True, data={"servers": summary})
        return ToolResult(success=True, data={"tools": [
            item for s in servers for item in s.get("tools", [])
        ]})
