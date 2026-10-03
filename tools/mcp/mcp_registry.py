"""Registry orchestration: register frozen MCP tools, keep definitions cached."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from tools.mcp.mcp_client import MCPClient
from tools.mcp.mcp_config import McpServerConfig, load_mcp_config
from tools.mcp.mcp_tool import MCPTool, _tool_slug, build_mcp_tools

_CACHE_ROOT = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "openmontage" / "mcp"


def _config_signature(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:12]


def _signature_of(cfg) -> str:
    servers = [
        {
            "slug": s.slug,
            "transport": s.transport,
            "command": s.command,
            "args": s.args,
            "url": s.url,
            "timeout": s.timeout_seconds,
            "auth_token_env": s.auth_token_env,
            "tools": {name: {"capability": ov.capability, "cost_usd": ov.cost_usd}
                      for name, ov in s.tools.items()},
        }
        for s in cfg.servers
    ]
    return _config_signature({"enabled": cfg.enabled, "service": "openmontage-mcp", "servers": servers})


def list_server_tools(server: McpServerConfig, signature: str, timeout: float = 30.0) -> list:
    """List remote tools, preferring the signature-keyed on-disk cache."""
    cache_file = _CACHE_ROOT / f"{signature}_{server.slug}.json"
    if cache_file.is_file():
        try:
            from mcp.types import Tool
            payload = json.loads(cache_file.read_text(encoding="utf-8"))
            return [Tool.model_validate(item) for item in payload]
        except Exception:
            pass  # corrupt cache -> refresh live
    client = MCPClient(server)
    tools = client.list_tools(timeout=timeout)
    client.close()
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(
            json.dumps([t.model_dump() for t in tools], default=str), encoding="utf-8"
        )
    except Exception:
        pass  # cache is best-effort
    return tools


def sync_mcp_servers(registry, config_path: str | None = None) -> None:
    """Register MCP-backed provider tools. Idempotent; never raises."""
    try:
        cfg = load_mcp_config(config_path)
    except Exception as exc:
        _warn(registry, f"mcp config error: {exc}")
        return
    if not cfg.enabled:
        _drop_mcp_tools(registry)
        return
    signature = _signature_of(cfg)
    for server in cfg.servers:
        if not server.frozen_tool_names and not cfg.list_on_boot:
            continue  # nothing to bridge now; catalog polls lazily
        try:
            tools = list_server_tools(server, signature)
        except Exception as exc:
            _warn(registry, f"mcp server '{server.slug}': list_tools failed: {exc}")
            continue
        for instance in build_mcp_tools(server, tools):
            registry.register(instance)
    _drop_stale_mcp_tools(registry, cfg)


def _warn(registry, message: str) -> None:
    warnings = getattr(registry, "_mcp_warnings", None)
    if warnings is not None:
        warnings.append(message)


def _generated_mcp_tools(registry) -> dict:
    """Only bridge-generated MCPTool instances.

    Cleanup must never touch the built-in ``mcp_catalog`` / ``mcp_call``
    tools: they share the ``mcp_`` name prefix but are ordinary BaseTool
    subclasses auto-registered by the registry. Discriminate by type, not
    prefix, so discovery/raw-call tools survive every sync.
    """
    return {
        name: tool for name, tool in getattr(registry, "_tools", {}).items()
        if isinstance(tool, MCPTool)
    }


def _drop_mcp_tools(registry) -> None:
    for name in list(_generated_mcp_tools(registry)):
        registry._tools.pop(name, None)


def _drop_stale_mcp_tools(registry, cfg) -> None:
    desired = {f"mcp_{s.slug}_{_tool_slug(name)}" for s in cfg.servers for name in s.frozen_tool_names}
    for name in list(_generated_mcp_tools(registry)):
        if name not in desired:
            registry._tools.pop(name, None)
