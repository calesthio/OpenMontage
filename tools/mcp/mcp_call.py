"""Raw MCP tool passthrough — reach any tool regardless of capability state."""

from __future__ import annotations

import json
import time
from typing import Any

from tools.base_tool import BaseTool, ToolResult, ToolRuntime, ToolStability, ToolTier
from tools.mcp.mcp_client import MCPClient, _redact
from tools.mcp.mcp_config import RESERVED_KEYS, load_mcp_config
from tools.mcp.mcp_tool import extract_outputs


class MCPCall(BaseTool):
    name = "mcp_call"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "mcp"
    provider = "openmontage"
    stability = ToolStability.BETA
    runtime = ToolRuntime.HYBRID

    capabilities = ["mcp_raw_call"]
    best_for = ["calling unfrozen or non-capability MCP tools directly"]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        server_slug = inputs.get("server")
        tool_name = inputs.get("tool")
        output_path = inputs.get("output_path")
        arguments = inputs.get("arguments") or {}
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                return ToolResult(success=False, error="arguments must be a dict or JSON string")
        cfg = load_mcp_config()
        server = cfg.server(server_slug)
        if server is None:
            return ToolResult(success=False, error=f"unknown mcp server {server_slug!r}")
        stripped = {k: v for k, v in arguments.items() if k not in RESERVED_KEYS}
        client = MCPClient(server)
        start = time.monotonic()
        try:
            result = client.call_tool(tool_name, stripped)
        except Exception as exc:
            return ToolResult(success=False, error=_redact(str(exc))[:500])
        finally:
            client.close()
        artifacts, texts, structured = extract_outputs(result, output_path)
        data: dict[str, Any] = {
            "server": server_slug,
            "tool": tool_name,
            "output": artifacts[0] if artifacts else None,
            "outputs": artifacts,
        }
        if texts:
            data["text"] = "\n".join(texts)
        if structured is not None:
            data["raw"] = structured
        if getattr(result, "is_error", False) and not artifacts:
            data["error"] = "\n".join(texts) or "remote tool reported an error"
            return ToolResult(success=False, data=data,
                              duration_seconds=round(time.monotonic() - start, 2))
        return ToolResult(success=True, data=data, artifacts=artifacts,
                          duration_seconds=round(time.monotonic() - start, 2))
