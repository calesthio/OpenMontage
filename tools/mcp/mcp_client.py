"""Synchronous facade over an asynchronous MCP client session.

One MCPClient owns one background thread running an asyncio (anyio) event
loop. Each call is submitted to that loop and awaited synchronously, so the
rest of OpenMontage keeps its sync BaseTool.execute() contract while MCP
transport stays async.
"""

from __future__ import annotations

import asyncio
import os
import threading
from typing import Any, Awaitable, Callable

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from tools.mcp.mcp_config import McpServerConfig


def _redact(message: str) -> str:
    """Strip known secrets from an error message."""
    for key, value in list(os.environ.items()):
        upper = key.upper()
        if any(seg in upper for seg in ("KEY", "TOKEN", "SECRET", "PASS")) and value and value in message:
            message = message.replace(value, "[redacted]")
    return message


class MCPConnectionError(Exception):
    """Raised when an MCP server cannot be reached or initialized."""


class MCPClient:
    """Synchronous wrapper over one remote MCP server."""

    def __init__(self, server: McpServerConfig) -> None:
        self._cfg = server
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._session: ClientSession | None = None
        self._ready = threading.Event()      # caller-thread wait; set from loop thread
        self._closed: asyncio.Event | None = None  # loop-bound; created in _serve
        self._lifecycle_lock = threading.Lock()
        self._lock = threading.Lock()
        self._last_error: str | None = None

    # -- lifecycle ---------------------------------------------------------

    def connect(self, timeout: float = 15.0) -> None:
        if (
            self._session is not None
            and self._ready.is_set()
            and self._thread and self._thread.is_alive()
        ):
            return
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, name=f"mcp-{self._cfg.slug}", daemon=True)
        self._thread.start()
        self._ready.wait(timeout)
        if self._session is None:
            raise MCPConnectionError(
                f"MCP server '{self._cfg.slug}' unavailable: {self._last_error or 'unknown error'}"
            )

    def close(self) -> None:
        with self._lifecycle_lock:
            closed, loop = self._closed, self._loop
        if closed is not None and loop is not None:
            loop.call_soon_threadsafe(closed.set)
        if self._thread:
            self._thread.join(timeout=3.0)

    def probe(self, timeout: float = 8.0) -> bool:
        try:
            self.connect(timeout=timeout)
            return True
        except (MCPConnectionError, TimeoutError):
            return False

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve())
        finally:
            try:
                self._loop.close()
            except Exception:
                pass

    async def _serve(self) -> None:
        with self._lifecycle_lock:
            self._closed = asyncio.Event()
        try:
            async with self._transport() as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self._session = session
                    self._ready.set()
                    await self._closed.wait()
        except Exception as exc:  # release waiting connect(); thread exits
            self._last_error = _redact(str(exc))[:500]
            self._ready.set()

    def _transport(self):
        if self._cfg.transport == "stdio":
            params = StdioServerParameters(command=self._cfg.command, args=self._cfg.args or [])
            return stdio_client(params)
        if self._cfg.transport == "http":
            from mcp.client.streamable_http import streamable_http_client

            http_client = None
            token_env = self._cfg.auth_token_env
            token = os.environ.get(token_env) if token_env else None
            if token:
                try:
                    import httpx2 as _httpx
                except ImportError:
                    import httpx as _httpx
                http_client = _httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"})
            return streamable_http_client(self._cfg.url, http_client=http_client)
        raise ValueError(f"unsupported transport {self._cfg.transport!r}")

    # -- calls -------------------------------------------------------------

    async def _invoke(self, method: str, *args: Any, **kwargs: Any) -> Any:
        """Call a session method with its coroutine created on the owning loop.

        mcp 2.x ClientSession methods must be instantiated (and awaited) on the
        loop that owns the session's internal streams; creating the coroutine in
        the caller thread and submitting it makes the call hang.
        """
        fn = getattr(self._session, method)
        return await fn(*args, **kwargs)

    def _submit(self, method: str, *args: Any, timeout: float, **kwargs: Any) -> Any:
        with self._lock:
            if not self._ready.is_set() or self._session is None:
                self.connect()
            future = asyncio.run_coroutine_threadsafe(self._invoke(method, *args, **kwargs), self._loop)
            return future.result(timeout=timeout)

    def list_tools(self, timeout: float = 30.0) -> list:
        result = self._submit("list_tools", timeout=timeout)
        return list(result.tools)

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None, timeout: float | None = None):
        timeout = timeout or self._cfg.timeout_seconds
        return self._submit("call_tool", name, arguments=arguments, timeout=timeout)
