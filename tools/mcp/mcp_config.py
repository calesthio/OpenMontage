"""Configuration loading and shared constants for MCP-backed provider tools.

Capability assignments for remote tools are "frozen" in mcp_servers.yaml by the
Agent (or declared manually). Tools without a frozen capability are never
bridged; they surface only through mcp_catalog.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from jsonschema import validate as _json_validate


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "mcp_servers.yaml"

# OpenMontage-internal keys that must never be forwarded to a remote MCP tool.
RESERVED_KEYS = frozenset({
    "output_path", "output_dir", "output_format", "output_name",
    "scene_id", "scene_name", "task_context",
    "preferred_provider", "allowed_providers",
})

# MIME type -> file extension for persisting media content blocks.
MIME_EXT: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/ogg": ".ogg",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "application/x-subrip": ".srt",
    "text/plain": ".txt",
    "application/json": ".json",
}
DEFAULT_EXT = ".bin"


def mime_extension(mime: str | None, fallback: str = DEFAULT_EXT) -> str:
    if not mime:
        return fallback
    return MIME_EXT.get(mime.lower(), fallback)


MCP_SERVERS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "mcp": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "list_on_boot": {"type": "boolean"},
                "servers": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "transport": {"enum": ["stdio", "http"]},
                            "command": {"type": "string"},
                            "args": {"type": "array", "items": {"type": "string"}},
                            "url": {"type": "string"},
                            "auth_token_env": {"type": "string"},
                            "timeout_seconds": {"type": "number"},
                            "tools": {
                                # ``tools:`` written bare parses as null; treat it as "{}".
                                "type": ["object", "null"],
                                "additionalProperties": {
                                    "type": "object",
                                    "properties": {
                                        "capability": {"type": "string"},
                                        "cost_usd": {"type": "number"},
                                        "agent_skills": {"type": "array", "items": {"type": "string"}},
                                        "model": {"type": "string"},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    },
}


def validate_mcp_schema(raw: Any) -> None:
    _json_validate(raw, MCP_SERVERS_SCHEMA)


@dataclass
class McpToolOverride:
    """Per-tool config overrides. A non-None capability means 'frozen'."""
    capability: str | None = None
    cost_usd: float | None = None
    agent_skills: list[str] | None = None
    model: str | None = None


@dataclass
class McpServerConfig:
    slug: str
    transport: str
    command: str | None = None
    args: list[str] | None = None
    url: str | None = None
    auth_token_env: str | None = None
    timeout_seconds: float = 120.0
    tools: dict[str, McpToolOverride] = field(default_factory=dict)

    def frozen_capability(self, tool_name: str) -> str | None:
        override = self.tools.get(tool_name)
        return override.capability if override else None

    @property
    def frozen_tool_names(self) -> list[str]:
        return [name for name, ov in self.tools.items() if ov.capability]


@dataclass
class McpConfig:
    enabled: bool = True
    list_on_boot: bool = True
    servers: list[McpServerConfig] = field(default_factory=list)

    def server(self, slug: str) -> McpServerConfig | None:
        return next((s for s in self.servers if s.slug == slug), None)


def load_mcp_config(path: str | Path | None = None) -> McpConfig:
    """Load and validate mcp_servers.yaml. A missing file yields an empty config."""
    config_path = Path(path) if path else Path(os.environ.get("MCP_SERVERS_PATH", DEFAULT_CONFIG_PATH))
    if not config_path.is_file():
        return McpConfig()
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    try:
        validate_mcp_schema(raw)
    except Exception as exc:
        raise ValueError(f"mcp_servers.yaml schema violation: {exc}") from exc
    mcp = raw.get("mcp", {}) or {}

    # Note: PyYAML collapses duplicate mapping keys, so slugs are unique by
    # construction after YAML parsing; no dedup guard is needed here.
    servers: list[McpServerConfig] = []
    for slug, srv in (mcp.get("servers") or {}).items():
        transport = srv.get("transport")
        if transport not in ("stdio", "http"):
            raise ValueError(f"mcp server '{slug}': transport must be 'stdio' or 'http', got {transport!r}")
        tools: dict[str, McpToolOverride] = {}
        for tool_name, tov in (srv.get("tools") or {}).items():
            tools[tool_name] = McpToolOverride(
                capability=tov.get("capability"),
                cost_usd=tov.get("cost_usd"),
                agent_skills=list(tov.get("agent_skills", [])) if tov.get("agent_skills") else None,
                model=tov.get("model"),
            )
        server = McpServerConfig(
            slug=slug,
            transport=transport,
            command=srv.get("command"),
            args=list(srv.get("args", [])),
            url=srv.get("url"),
            auth_token_env=srv.get("auth_token_env"),
            timeout_seconds=srv.get("timeout_seconds", 120.0),
            tools=tools,
        )
        if server.transport == "stdio" and not server.command:
            raise ValueError(f"mcp server '{slug}': stdio transport requires 'command'")
        if server.transport == "http" and not server.url:
            raise ValueError(f"mcp server '{slug}': http transport requires 'url'")
        servers.append(server)

    return McpConfig(
        enabled=bool(mcp.get("enabled", True)),
        list_on_boot=bool(mcp.get("list_on_boot", True)),
        servers=servers,
    )
