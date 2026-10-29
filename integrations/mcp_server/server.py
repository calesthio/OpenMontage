"""OpenMontage MCP server for ChatGPT.

Default mode is local stdio. Set OM_MCP_TRANSPORT=streamable-http to serve
MCP over HTTP. HTTP mode requires OM_MCP_BEARER_TOKEN and should sit behind
a TLS reverse proxy; never expose the backend port directly to the internet.
"""
from __future__ import annotations

import hmac
import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from lib.pipeline_loader import list_pipelines, load_pipeline_readonly

mcp = FastMCP("OpenMontage")


@mcp.tool()
def om_list_pipelines() -> dict[str, Any]:
    """List local pipeline manifests and stage names."""
    result = []
    for name in sorted(list_pipelines()):
        try:
            manifest = load_pipeline_readonly(name)
            result.append({
                "name": name,
                "version": str(manifest.get("version", "")),
                "category": manifest.get("category", "unknown"),
                "stages": [
                    stage.get("name", "")
                    for stage in manifest.get("stages", [])
                    if isinstance(stage, dict)
                ],
            })
        except Exception as exc:
            result.append({"name": name, "error": type(exc).__name__})
    return {"count": len(result), "pipelines": result}


@mcp.tool()
def om_estimate_production(pipeline_name: str) -> dict[str, Any]:
    """Return a pipeline's declared default budget and stages; no tools are run."""
    if not pipeline_name or len(pipeline_name) > 120:
        return {"ok": False, "error": "pipeline_name must be 1-120 characters"}
    names = sorted(list_pipelines())
    if pipeline_name not in names:
        return {"ok": False, "error": "Unknown pipeline", "available_pipelines": names}
    manifest = load_pipeline_readonly(pipeline_name)
    stages = [
        stage.get("name", "")
        for stage in manifest.get("stages", [])
        if isinstance(stage, dict)
    ]
    return {
        "ok": True,
        "pipeline": pipeline_name,
        "stage_count": len(stages),
        "stages": stages,
        "declared_default_budget_usd": (
            manifest.get("orchestration", {}) or {}
        ).get("budget_default_usd"),
        "estimate_note": "Declared default budget only; not a live cost quote.",
    }


@mcp.tool()
def om_get_capabilities() -> dict[str, Any]:
    """Summarize registered tools and their availability."""
    from tools.tool_registry import ToolRegistry

    registry = ToolRegistry()
    registry.ensure_discovered()
    envelope = registry.support_envelope()
    return {"tool_count": len(envelope), "tools": envelope}


class BearerTokenMiddleware:
    """Minimal ASGI bearer-token gate; fails closed when no token is configured."""

    def __init__(self, app, token: str):
        self.app = app
        self.token = token

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        supplied = headers.get(b"authorization", b"").decode("latin-1")
        expected = f"Bearer {self.token}"
        if not hmac.compare_digest(supplied, expected):
            body = b'{"error":"unauthorized"}'
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"cache-control", b"no-store"),
                ],
            })
            await send({"type": "http.response.body", "body": body})
            return
        await self.app(scope, receive, send)


def create_http_app():
    """Build the authenticated Streamable HTTP ASGI app."""
    token = os.environ.get("OM_MCP_BEARER_TOKEN", "")
    if len(token) < 32:
        raise RuntimeError(
            "OM_MCP_BEARER_TOKEN must be set to a secret of at least 32 characters"
        )
    # Mount the SDK-managed Streamable HTTP endpoint under /mcp. The outer
    # ASGI app enforces authentication before any MCP request reaches the SDK.
    mcp_app = mcp.streamable_http_app()
    return BearerTokenMiddleware(mcp_app, token)


def main() -> None:
    transport = os.environ.get("OM_MCP_TRANSPORT", "stdio").strip().lower()
    if transport == "stdio":
        mcp.run(transport="stdio")
        return
    if transport != "streamable-http":
        raise SystemExit("OM_MCP_TRANSPORT must be 'stdio' or 'streamable-http'")

    import uvicorn

    app = create_http_app()
    host = os.environ.get("OM_MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("OM_MCP_PORT", "8000"))
    if not 1 <= port <= 65535:
        raise SystemExit("OM_MCP_PORT must be between 1 and 65535")
    uvicorn.run(app, host=host, port=port, proxy_headers=False, server_header=False)


if __name__ == "__main__":
    main()
