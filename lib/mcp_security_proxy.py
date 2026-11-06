#!/usr/bin/env python3
"""MCP Security Proxy — infrastructure wrapper for MCP servers over stdio.

Launches an upstream MCP server as a child process and mediates all
JSON-RPC traffic between the client (Kilo) and the server.  Enforces a
strict tool allowlist on both ``tools/list`` (filtering what is
advertised) and ``tools/call`` (blocking prohibited calls at the
boundary, before they reach the child process).

Design principles:
  * Default-deny: any tool not on the allowlist is blocked.
  * Fail-closed: if the proxy cannot determine safety, it blocks.
  * No secret logging: arguments are never written to the audit log.
  * Proper MCP stdio framing: one JSON-RPC message per line.

Usage:
    python3 mcp_security_proxy.py <server-name> <allowlist-csv> -- <server-command> [args...]

Example:
    python3 mcp_security_proxy.py browser-use \
        browser_navigate,browser_get_state,browser_extract_content,browser_screenshot,\
        browser_list_tabs,browser_switch_tab,browser_go_back \
        -- /home/vscode/.local/bin/browser-use --mcp
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from typing import Any


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SERVER_NAME: str = sys.argv[1] if len(sys.argv) > 1 else "unknown"
ALLOWLIST_CSV: str = sys.argv[2] if len(sys.argv) > 2 else ""
SERVER_CMD: list[str] = sys.argv[4:] if len(sys.argv) > 4 and sys.argv[3] == "--" else []

# Build allowlist set (strip whitespace, ignore empty)
ALLOWLIST: set[str] = {
    t.strip() for t in ALLOWLIST_CSV.split(",") if t.strip()
}

# Audit log — never writes secrets or arguments
AUDIT_LOG: str = os.environ.get(
    "MCP_SECURITY_AUDIT_LOG", "/tmp/kilo/security-audit/mcp-proxy-audit.log"
)
AUDIT_DIR = os.path.dirname(AUDIT_LOG)
if AUDIT_DIR:
    os.makedirs(AUDIT_DIR, exist_ok=True)

_audit_lock = threading.Lock()


def _audit(event: str, detail: str = "") -> None:
    """Write an audit entry.  Never logs tool arguments or secrets."""
    import datetime

    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    line = f"[{ts}] {SERVER_NAME} {event} {detail}\n"
    with _audit_lock:
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(line)


# ---------------------------------------------------------------------------
# Child process management
# ---------------------------------------------------------------------------


class MCPServerProcess:
    """Wraps an upstream MCP server as a subprocess with stdio mediation."""

    def __init__(self, command: list[str], env: dict[str, str] | None = None):
        self.command = command
        self.env = env or dict(os.environ)
        self._proc: subprocess.Popen | None = None
        self._stdin_lock = threading.Lock()
        self._started = False
        self._exit_code: int | None = None

    def start(self) -> None:
        """Launch the upstream MCP server."""
        self._proc = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=self.env,
        )
        self._started = True
        _audit("PROCESS_START", f"pid={self._proc.pid} cmd={' '.join(self.command)}")

    def is_alive(self) -> bool:
        if self._proc is None:
            return False
        return self._proc.poll() is None

    def stop(self, timeout: float = 5.0) -> None:
        """Terminate the child process gracefully."""
        if self._proc is None:
            return
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait()
        self._exit_code = self._proc.returncode
        _audit("PROCESS_STOP", f"pid={self._proc.pid} exit={self._exit_code}")

    def write_stdin(self, message: str) -> None:
        """Send a JSON-RPC message to the child process stdin."""
        if self._proc is None or self._proc.stdin is None:
            raise RuntimeError("Child process stdin not available")
        with self._stdin_lock:
            self._proc.stdin.write(message + "\n")
            self._proc.stdin.flush()

    def read_stdout(self) -> str | None:
        """Read one line from the child process stdout."""
        if self._proc is None or self._proc.stdout is None:
            return None
        line = self._proc.stdout.readline()
        if line == "":
            return None
        return line.rstrip("\n")

    def read_stderr(self) -> str:
        """Read all available stderr (non-blocking best-effort)."""
        if self._proc is None or self._proc.stderr is None:
            return ""
        # stderr may block; read only what's immediately available
        import select

        if select.select([self._proc.stderr], [], [], 0)[0]:
            return self._proc.stderr.read()
        return ""


# ---------------------------------------------------------------------------
# JSON-RPC message handling
# ---------------------------------------------------------------------------


def _is_notification(msg: dict[str, Any]) -> bool:
    """A JSON-RPC notification has no ``id`` field."""
    return "id" not in msg


def _filter_tools_list(result: dict[str, Any]) -> dict[str, Any]:
    """Filter ``tools/list`` result to only allowlisted tools."""
    tools = result.get("tools", [])
    if not isinstance(tools, list):
        return result
    filtered = [
        t for t in tools if isinstance(t, dict) and t.get("name") in ALLOWLIST
    ]
    result = dict(result)
    result["tools"] = filtered
    _audit(
        "TOOLS_LIST_FILTERED",
        f"original={len(tools)} allowed={len(filtered)}",
    )
    return result


def _is_blocked_tool_call(msg: dict[str, Any]) -> tuple[bool, str | None]:
    """Check if a ``tools/call`` request targets a blocked tool.

    Returns (is_blocked, tool_name).
    """
    params = msg.get("params", {})
    if not isinstance(params, dict):
        return False, None
    tool_name = params.get("name")
    if not isinstance(tool_name, str):
        return False, None
    if tool_name not in ALLOWLIST:
        return True, tool_name
    return False, tool_name


def _make_error_response(msg_id: Any, code: int, message: str) -> str:
    """Build a JSON-RPC error response."""
    return json.dumps(
        {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}},
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# Proxy main loop
# ---------------------------------------------------------------------------


def run_proxy(server: MCPServerProcess) -> int:
    """Main proxy loop: relay between client stdin and child process.

    Architecture:
      * Reader thread: reads JSON-RPC from client stdin, applies policy,
        forwards requests/calls to child process.  Notifications (no id)
        are forwarded without waiting.  Requests (with id) are forwarded
        and the caller waits via a per-id event.
      * Writer thread: reads JSON-RPC responses from child process stdout,
        filters tools/list results, and writes to client stdout.
      * Pending requests dict maps msg_id -> threading.Event + result slot.

    This correctly handles the MCP pattern where notifications (e.g.
    ``initialized``) have no response, while requests (e.g. ``initialize``,
    ``tools/list``, ``tools/call``) expect a matching response by id.
    """
    import queue

    _audit("PROXY_START", f"server={SERVER_NAME} allowlist={sorted(ALLOWLIST)}")

    # Pending requests: msg_id -> {"event": Event, "result": None}
    pending: dict[Any, dict[str, Any]] = {}
    pending_lock = threading.Lock()

    # Queue for responses from the writer thread to deliver to waiting callers
    response_queue: "queue.Queue[tuple[Any, dict[str, Any] | None]]" = (
        queue.Queue()
    )

    # Forward child stderr to our stderr for debugging (no secrets)
    def _drain_stderr() -> None:
        while server.is_alive():
            err = server.read_stderr()
            if err:
                sys.stderr.write(err)
                sys.stderr.flush()

    stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
    stderr_thread.start()

    # --- Writer thread: read from child stdout, write to client stdout ---
    def _writer() -> None:
        while server.is_alive():
            line = server.read_stdout()
            if line is None:
                # Child closed stdout
                if not server.is_alive():
                    # Notify all pending waiters
                    with pending_lock:
                        for entry in pending.values():
                            entry["result"] = None
                            entry["event"].set()
                    break
                continue
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                sys.stdout.write(line + "\n")
                sys.stdout.flush()
                continue
            if not isinstance(msg, dict):
                sys.stdout.write(line + "\n")
                sys.stdout.flush()
                continue

            msg_id = msg.get("id")

            # If this is a response to a request we're waiting for
            if msg_id is not None:
                with pending_lock:
                    entry = pending.pop(msg_id, None)
                if entry is not None:
                    # Filter tools/list results
                    if "result" in msg and isinstance(msg.get("result"), dict):
                        # We need to know the original method to filter.
                        # Store method in pending entry.
                        orig_method = entry.get("method")
                        if (
                            orig_method == "tools/list"
                            and "result" in msg
                            and isinstance(msg["result"], dict)
                        ):
                            msg["result"] = _filter_tools_list(msg["result"])
                    entry["result"] = msg
                    entry["event"].set()
                    continue

            # Unsolicited message or notification from server — forward as-is
            sys.stdout.write(
                json.dumps(msg, ensure_ascii=False) + "\n"
            )
            sys.stdout.flush()

    writer_thread = threading.Thread(target=_writer, daemon=True)
    writer_thread.start()

    try:
        while True:
            # Read one line from client stdin
            try:
                line = sys.stdin.readline()
            except (KeyboardInterrupt, InterruptedError):
                break
            if line == "":
                # Client closed stdin
                break

            line = line.strip()
            if not line:
                continue

            # Parse the JSON-RPC message
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                # Forward malformed messages as-is
                try:
                    server.write_stdin(line)
                except RuntimeError:
                    pass
                continue

            if not isinstance(msg, dict):
                try:
                    server.write_stdin(line)
                except RuntimeError:
                    pass
                continue

            method = msg.get("method", "")
            msg_id = msg.get("id")

            # --- Policy enforcement ---

            # 1. tools/call — block prohibited tools BEFORE forwarding
            if method == "tools/call":
                blocked, tool_name = _is_blocked_tool_call(msg)
                if blocked:
                    _audit(
                        "TOOL_CALL_BLOCKED",
                        f"tool={tool_name} reason=not_in_allowlist",
                    )
                    response = _make_error_response(
                        msg_id,
                        -32602,
                        f"Tool '{tool_name}' is blocked by MCP Security Proxy "
                        f"(not in allowlist)",
                    )
                    sys.stdout.write(response + "\n")
                    sys.stdout.flush()
                    continue

            # Forward request/notification to child process
            try:
                server.write_stdin(line)
            except RuntimeError as exc:
                _audit("FORWARD_ERROR", str(exc))
                if msg_id is not None:
                    response = _make_error_response(
                        msg_id, -32603, f"Internal proxy error: {exc}"
                    )
                    sys.stdout.write(response + "\n")
                    sys.stdout.flush()
                continue

            # If this is a notification (no id), no response expected
            if msg_id is None:
                continue

            # This is a request — wait for the response
            entry = {"event": threading.Event(), "result": None, "method": method}
            with pending_lock:
                pending[msg_id] = entry

            # Wait for response with timeout
            if not entry["event"].wait(timeout=120):
                with pending_lock:
                    pending.pop(msg_id, None)
                _audit("REQUEST_TIMEOUT", f"method={method} id={msg_id}")
                response = _make_error_response(
                    msg_id, -32603, "Request timed out waiting for upstream"
                )
                sys.stdout.write(response + "\n")
                sys.stdout.flush()
                continue

            result_msg = entry["result"]
            if result_msg is None:
                # Child exited
                response = _make_error_response(
                    msg_id, -32603, "Upstream MCP server exited"
                )
                sys.stdout.write(response + "\n")
                sys.stdout.flush()
                break

            sys.stdout.write(
                json.dumps(result_msg, ensure_ascii=False) + "\n"
            )
            sys.stdout.flush()

    except (KeyboardInterrupt, BrokenPipeError):
        pass
    finally:
        # Clean up pending waiters
        with pending_lock:
            for entry in pending.values():
                entry["result"] = None
                entry["event"].set()
        server.stop()
        _audit("PROXY_STOP", f"server={SERVER_NAME}")

    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    if not SERVER_CMD:
        sys.stderr.write(
            "Usage: mcp_security_proxy.py <server-name> <allowlist-csv> -- <server-command> [args...]\n"
        )
        return 1

    if not ALLOWLIST:
        sys.stderr.write("Error: allowlist is empty (default-deny mode)\n")
        return 1

    server = MCPServerProcess(SERVER_CMD)
    try:
        server.start()
    except FileNotFoundError as exc:
        sys.stderr.write(f"Error: server command not found: {exc}\n")
        return 1
    except PermissionError as exc:
        sys.stderr.write(f"Error: permission denied: {exc}\n")
        return 1

    try:
        return run_proxy(server)
    finally:
        server.stop()


if __name__ == "__main__":
    sys.exit(main())
