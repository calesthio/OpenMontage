"""Generic MCP-provider BaseTool adapter, content mapping, and factory."""

from __future__ import annotations

import base64
import re
import time
from pathlib import Path
from typing import Any

from mcp.types import Tool as McpToolDef

from tools.base_tool import (
    BaseTool, DependencyError, RetryPolicy, ToolResult, ToolRuntime, ToolStability, ToolStatus, ToolTier,
)
from tools.mcp.mcp_client import MCPClient, _redact
from tools.mcp.mcp_config import (
    RESERVED_KEYS, McpServerConfig, McpToolOverride, mime_extension,
)


DEFAULT_AGENT_SKILLS: dict[str, list[str]] = {
    "video_generation": ["ai-video-gen", "create-video", "ltx2"],
    "image_generation": ["flux-best-practices", "bfl-api"],
    "tts": ["text-to-speech"],
    "music_generation": ["music", "elevenlabs"],
    "analysis": ["speech-to-text"],
    "avatar": ["avatar-video", "create-video"],
}


def _tool_slug(tool_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", tool_name.lower()).strip("_")


def _derive_output_paths(output_path: str | None, count: int) -> list[Path]:
    path = Path(output_path or "mcp_output.bin")
    if not path.suffix:
        path = path.with_suffix(".bin")
    if count <= 1:
        return [path]
    return [path.with_name(f"{path.stem}_{i}{path.suffix}") for i in range(1, count + 1)]


def extract_outputs(result, output_path: str | None) -> tuple[list[str], list[str], Any]:
    """Persist media content blocks; return (artifacts, texts, structuredContent)."""
    blocks = list(getattr(result, "content", None) or [])
    media = [b for b in blocks if getattr(b, "type", None) in ("image", "audio", "resource")]
    paths = _derive_output_paths(output_path, len(media))
    artifacts: list[str] = []
    texts: list[str] = []
    idx = 0
    for block in blocks:
        btype = getattr(block, "type", None)
        if btype in ("image", "audio"):
            payload = _decode(getattr(block, "data", ""))
            mime = getattr(block, "mime_type", None) or getattr(block, "mimeType", None)
            target = _take_path(paths, output_path, idx)
            idx += 1
            target = target.with_suffix(mime_extension(mime))
            _write(target, payload)
            artifacts.append(str(target))
        elif btype == "resource":
            resource = getattr(block, "resource", None)
            uri = getattr(resource, "uri", "") or ""
            mime = getattr(resource, "mime_type", None) or getattr(resource, "mimeType", None)
            blob = getattr(resource, "blob", None)
            target = _take_path(paths, output_path, idx)
            idx += 1
            target = target.with_suffix(mime_extension(mime))
            if blob is not None:
                _write(target, _decode(blob))
            elif uri.startswith("http"):
                import requests
                resp = requests.get(uri, timeout=60)
                resp.raise_for_status()
                _write(target, resp.content)
            else:
                raise ValueError(f"resource '{uri}' has no blob and is not an http(s) URL")
            artifacts.append(str(target))
        elif btype == "text":
            texts.append(getattr(block, "text", "") or "")
    return artifacts, texts, getattr(result, "structured_content", None)


def _decode(value: Any) -> bytes:
    if isinstance(value, bytes):
        return value
    try:
        return base64.b64decode(value)
    except Exception:
        return str(value).encode("utf-8")


def _take_path(paths: list[Path], output_path: str | None, idx: int) -> Path:
    if idx < len(paths):
        return paths[idx]
    return _derive_output_paths(output_path, idx + 1)[-1]


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def capability_summary_keys(capability: str, artifacts: list[str]) -> dict[str, Any]:
    if capability == "image_generation":
        return {"images_generated": len(artifacts)}
    if capability == "video_generation":
        return {"video_clips": len(artifacts)}
    return {}


class MCPTool(BaseTool):
    """A single remote MCP tool, adapted to the OpenMontage BaseTool contract.

    Instances are created only by build_mcp_tools(); the class itself is
    skipped by tool_registry.register_module via the _registry_managed flag.
    """

    _registry_managed = True
    name = ""  # set per instance
    version = "0.1.0"
    tier = ToolTier.GENERATE
    stability = ToolStability.BETA
    runtime = ToolRuntime.API
    retry_policy = RetryPolicy(max_retries=0)

    def __init__(self, server: McpServerConfig, tool: McpToolDef, override: McpToolOverride) -> None:
        if not override.capability:
            raise ValueError(f"mcp tool '{server.slug}.{tool.name}' has no frozen capability")
        self._server = server
        self._tool = tool
        self._override = override
        self._client = MCPClient(server)
        self.name = f"mcp_{server.slug}_{_tool_slug(tool.name)}"
        self.provider = server.slug
        self.capability = override.capability
        self.runtime = ToolRuntime.HYBRID if server.transport == "stdio" else ToolRuntime.API
        self.agent_skills = list(override.agent_skills or DEFAULT_AGENT_SKILLS.get(override.capability, []))
        self.dependencies = [f"env:{server.auth_token_env}"] if server.auth_token_env else []
        self.install_instructions = (
            f"Configure MCP server '{server.slug}' in mcp_servers.yaml "
            f"(transport={server.transport})."
        )
        schema = dict(tool.input_schema or {"type": "object"})
        schema.setdefault("type", "object")
        props = dict(schema.get("properties") or {})
        props["output_path"] = {"type": "string", "description": "Where to write the first media output."}
        schema["properties"] = props
        schema["required"] = list(dict.fromkeys(schema.get("required", []) or []))
        self.input_schema = schema

    # -- status ------------------------------------------------------------

    def check_dependencies(self) -> None:
        if not self._client.probe(timeout=6.0):
            raise DependencyError(f"MCP server '{self._server.slug}' is unreachable. {self.install_instructions}")

    def get_status(self) -> ToolStatus:
        try:
            if self._client.probe(timeout=6.0):
                return ToolStatus.AVAILABLE
        except Exception:
            pass
        return ToolStatus.UNAVAILABLE

    # -- cost --------------------------------------------------------------

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return self._override.cost_usd or 0.0

    # -- execution ---------------------------------------------------------

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        stripped = {key: value for key, value in inputs.items() if key not in RESERVED_KEYS}
        output_path = inputs.get("output_path")
        start = time.monotonic()
        try:
            result = self._client.call_tool(self._tool.name, arguments=stripped)
        except Exception as exc:
            return ToolResult(success=False, error=f"MCP call to {self.name} failed: {_redact(str(exc))}")

        artifacts, texts, structured = extract_outputs(result, output_path)
        if getattr(result, "is_error", False):
            message = "\n".join(texts) or "remote tool reported an error"
            return ToolResult(success=False, error=message, artifacts=artifacts,
                              duration_seconds=round(time.monotonic() - start, 2))

        model = self._override.model or self._tool.name
        data: dict[str, Any] = {
            "provider": self.provider,
            "model": model,
            "output": artifacts[0] if artifacts else None,
            "outputs": artifacts,
        }
        if texts:
            data["text"] = "\n".join(texts)
        if structured is not None:
            data["raw"] = structured
        if self.capability == "analysis" and texts:
            data.setdefault("transcript", "\n".join(texts))
        if self.capability == "tts":
            data.setdefault("text", inputs.get("text") or "")
        data.update(capability_summary_keys(self.capability, artifacts))
        return ToolResult(
            success=True,
            data=data,
            artifacts=artifacts,
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.monotonic() - start, 2),
            model=model,
        )


def build_mcp_tools(server: McpServerConfig, tool_defs: list[McpToolDef]) -> list[MCPTool]:
    """Build MCPTool instances for frozen tools only."""
    instances: list[MCPTool] = []
    for tool in tool_defs:
        override = server.tools.get(tool.name)
        if override and override.capability:
            instances.append(MCPTool(server, tool, override))
    return instances
