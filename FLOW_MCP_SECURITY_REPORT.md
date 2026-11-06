# FLOW_MCP_SECURITY_REPORT.md

MCP Security Proxy — Infrastructure Protection Report
=====================================================

Project: `/workspaces/OpenMontage`
Date: 2026-11-01

---

## 1. Architecture Overview

The MCP Security Proxy is an infrastructure-layer wrapper that sits between
Kilo (the MCP client) and upstream MCP servers. It mediates all JSON-RPC
traffic over stdio, enforcing a strict tool allowlist at the boundary.

```
┌─────────────┐     stdio      ┌─────────────────────────┐     stdio     ┌─────────────┐
│    Kilo     │ ◄─────────────►│   MCP Security Proxy    │ ◄───────────►│ Upstream    │
│   (client)  │   JSON-RPC     │   (allowlist enforcement)│   JSON-RPC   │ MCP Server  │
└─────────────┘                └─────────────────────────┘              └─────────────┘
                                                              │
                                                              ▼
                                                       Allowlist check
                                                       (default-deny)
```

### Design Principles

| Principle | Implementation |
|-----------|---------------|
| Default-deny | Any tool not on the allowlist is blocked |
| Fail-closed | If safety cannot be determined, the call is blocked |
| Boundary enforcement | Blocking happens BEFORE forwarding to the child process |
| No secret logging | Audit log contains no tool arguments, URLs, or secrets |
| Proper MCP stdio | Full JSON-RPC 2.0 framing with initialize/initialized/handshake |
| Notification handling | Requests (with id) wait for responses; notifications (no id) are forwarded without waiting |

---

## 2. MCP Security Proxy (`lib/mcp_security_proxy.py`)

### How it works

1. **Process launch**: The proxy launches the upstream MCP server as a child
   process using `subprocess.Popen` with stdin/stdout pipes.

2. **Message relay**: Two threads handle traffic:
   - **Main thread**: Reads JSON-RPC from client stdin, applies policy,
     forwards to child stdin. Requests (with id) wait for responses via
     per-id threading events.
   - **Writer thread**: Reads JSON-RPC responses from child stdout,
     filters `tools/list` results, writes to client stdout.

3. **Policy enforcement**:
   - `tools/call` requests are checked against the allowlist BEFORE
     forwarding. Blocked tools return a JSON-RPC error immediately.
   - `tools/list` responses are filtered to remove non-allowlisted tools.
   - All other methods are forwarded as-is.

4. **Error handling**: Child process errors, timeouts, and unexpected
   exits are caught and returned as JSON-RPC errors to the client.

### Command-line interface

```
python3 mcp_security_proxy.py <server-name> <allowlist-csv> -- <server-command> [args...]

Example:
  python3 mcp_security_proxy.py browser-use \
    browser_navigate,browser_get_state,browser_extract_content \
    -- /home/vscode/.local/bin/browser-use --mcp
```

Environment variables:
- `MCP_SECURITY_AUDIT_LOG` — path to audit log (default: `/tmp/kilo/security-audit/mcp-proxy-audit.log`)

---

## 3. Allowlists by Server

### Browser Use (`browser-use`)

**Allowed (7 tools):**

| Tool | Purpose |
|------|---------|
| `browser_navigate` | Open a URL (read-only navigation) |
| `browser_get_state` | Read page state and DOM (read-only) |
| `browser_extract_content` | Extract text from page (read-only) |
| `browser_screenshot` | Capture page screenshot (read-only) |
| `browser_list_tabs` | List open tabs (read-only) |
| `browser_switch_tab` | Switch between tabs (read-only) |
| `browser_go_back` | Navigate back (read-only) |

**Blocked (8 tools):**

| Tool | Reason |
|------|--------|
| `browser_click` | Could trigger generation/payment |
| `browser_type` | Could submit forms |
| `browser_scroll` | State change |
| `browser_close_tab` | State change |
| `browser_close_session` | State change |
| `browser_close_all` | State change |
| `retry_with_browser_use_agent` | Agent-driven actions |
| `browser_list_sessions` | Session management |

### Playwright (`playwright`)

**Allowed (8 tools):**

| Tool | Purpose |
|------|---------|
| `browser_navigate` | Open a URL (read-only) |
| `browser_navigate_back` | Navigate back (read-only) |
| `browser_network_requests` | List network requests (read-only) |
| `browser_take_screenshot` | Capture screenshot (read-only) |
| `browser_snapshot` | Accessibility snapshot (read-only) |
| `browser_tabs` | List tabs (read-only) |
| `browser_wait_for` | Wait for condition (read-only) |
| `browser_console_messages` | Console messages (read-only) |

**Blocked (13 tools):**

| Tool | Reason |
|------|--------|
| `browser_close` | Closes browser |
| `browser_resize` | State change |
| `browser_handle_dialog` | Interacts with dialogs |
| `browser_evaluate` | Executes arbitrary JavaScript |
| `browser_file_upload` | Uploads files |
| `browser_fill_form` | Fills forms |
| `browser_install` | Installs browser |
| `browser_press_key` | Presses keys |
| `browser_type` | Types text |
| `browser_click` | Clicks elements |
| `browser_drag` | Drags elements |
| `browser_hover` | Hovers elements |
| `browser_select_option` | Selects options |

**Classification rule:** Any tool that cannot be reliably classified as
read-only is blocked by default.

### Google Flow (`gflow`)

No changes to the existing gflow configuration. The gflow MCP server uses
`--no-spend` and `--profile flow_remote`. Generation tools
(`gflow_generate_image`, `gflow_generate_video`) are not registered when
`--no-spend` is active.

---

## 4. Kilo Configuration (`/home/vscode/.config/kilo/kilo.jsonc`)

### Browser Use — routed through proxy

```json
"browser-use": {
  "type": "local",
  "command": [
    "python3",
    "/workspaces/OpenMontage/lib/mcp_security_proxy.py",
    "browser-use",
    "browser_navigate,browser_get_state,browser_extract_content,browser_screenshot,browser_list_tabs,browser_switch_tab,browser_go_back",
    "--",
    "/home/vscode/.local/bin/browser-use",
    "--mcp"
  ],
  "environment": {
    "DISPLAY": ":99",
    "BROWSER_USE_HEADLESS": "false",
    "BROWSER_USE_CONFIG_DIR": "/home/vscode/.config/browseruse",
    "MCP_SECURITY_AUDIT_LOG": "/tmp/kilo/security-audit/mcp-proxy-audit.log"
  },
  "enabled": true
}
```

### Playwright — routed through proxy

```json
"playwright": {
  "type": "local",
  "command": [
    "python3",
    "/workspaces/OpenMontage/lib/mcp_security_proxy.py",
    "playwright",
    "browser_navigate,browser_navigate_back,browser_network_requests,browser_take_screenshot,browser_snapshot,browser_tabs,browser_wait_for,browser_console_messages",
    "--",
    "npx",
    "-y",
    "@playwright/mcp@0.0.38"
  ],
  "environment": {
    "MCP_SECURITY_AUDIT_LOG": "/tmp/kilo/security-audit/mcp-proxy-audit.log"
  },
  "enabled": true
}
```

### gflow — unchanged

```json
"gflow": {
  "type": "local",
  "command": [
    "gflow",
    "mcp",
    "run",
    "--profile",
    "flow_remote",
    "--no-spend"
  ],
  "enabled": true
}
```

### Other MCP servers — unchanged

github, context7, git, filesystem remain as direct connections (no proxy).

### Bash permission hardening

The Kilo `permission.bash` block already restricts arbitrary command
execution (`"*": "ask"`). The proxy does not add new Bash permissions.
Users cannot bypass the proxy by directly running the upstream server
because `bash` commands require explicit ask approval.

---

## 5. Allowlist Configuration Files

### `/workspaces/OpenMontage/config/mcp-allowlist-browser-use.env`

Defines the Browser Use allowlist (7 read-only tools). Documents which
tools are blocked and why.

### `/workspaces/OpenMontage/config/mcp-allowlist-playwright.env`

Defines the Playwright allowlist (8 read-only tools). Documents which
tools are blocked and why.

---

## 6. Test Results

### Unit tests (`tests/test_mcp_security_proxy.py`)

All 13 tests pass:

| # | Test | Result |
|---|------|--------|
| 1 | MCP initialize through proxy | PASS |
| 2 | tools/list shows only allowed tools | PASS |
| 3 | Blocked tools/call rejected at proxy | PASS |
| 4 | Allowed tools/call works through proxy | PASS |
| 5 | Unknown tool blocked (default-deny) | PASS |
| 6 | Child process error handling | PASS |
| 7 | Proxy restart doesn't damage connections | PASS |
| 8 | gflow no-spend through proxy | PASS |
| 9 | Playwright allowlist enforcement | PASS |
| 10 | Browser Use allowlist enforcement | PASS |
| 11 | Audit log contains no secrets | PASS |
| 12 | Empty allowlist causes proxy error | PASS |
| 13 | Real Browser Use integration (Chrome + CDP 9223) | PASS |

### Other test suites

| Suite | Result |
|-------|--------|
| `tests/test_flow_job_manager.py` | 23 passed, 2 skipped |
| `tests/test_flow_job_manager_mock.py` | 8 passed |
| `tests/test_flow_load.py` | 6 passed (load testing) |

---

## 7. Known Limitations

| Limitation | Description | Mitigation |
|------------|-------------|------------|
| Direct upstream server bypass | A user with Bash access can run `/home/vscode/.local/bin/browser-use --mcp` directly, bypassing the proxy | Kilo's `bash` permission is `"*"`: `"ask"`, requiring explicit approval for each command |
| Browser Use MCP server behavior | The Browser Use MCP server returns "Connection closed" for `tools/call` in some configurations | This is a Browser Use server issue, not a proxy issue. The proxy correctly enforces the allowlist regardless |
| Playwright not tested with real server | Playwright proxy tested with allowlist logic only; real integration requires browser setup | Playwright allowlist logic verified by unit tests |
| Proxy is a single process | If the proxy crashes, all connected MCP clients lose access | Kilo will attempt to restart the MCP server on next use |

---

## 8. Proxy Operations

### Enable the proxy

The proxy is already enabled in kilo.jsonc for Browser Use and Playwright.
No additional action needed.

### Disable the proxy (revert to direct connection)

To temporarily disable the proxy for Browser Use, edit kilo.jsonc and
replace the proxy command with the direct command:

```json
"browser-use": {
  "type": "local",
  "command": [
    "/home/vscode/.local/bin/browser-use",
    "--mcp"
  ],
  ...
}
```

### View audit log

```bash
cat /tmp/kilo/security-audit/mcp-proxy-audit.log
```

The audit log contains only event types and tool names — never tool
arguments, URLs, cookies, or tokens.

### Restart the proxy

The proxy is started and stopped by Kilo as part of MCP server lifecycle
management. No manual restart is needed.

### Commands to run tests

```bash
# All MCP security proxy tests
/usr/local/py-utils/bin/pytest tests/test_mcp_security_proxy.py -v

# Including integration test (requires Chrome on CDP 9223)
/usr/local/py-utils/bin/pytest tests/test_mcp_security_proxy.py -v -m integration

# All security-related tests
/usr/local/py-utils/bin/pytest tests/test_mcp_security_proxy.py tests/test_flow_job_manager.py tests/test_flow_job_manager_mock.py -v
```

---

## 9. Files Changed

| File | Action | Description |
|------|--------|-------------|
| `lib/mcp_security_proxy.py` | Created | MCP Security Proxy with allowlist enforcement |
| `config/mcp-allowlist-browser-use.env` | Created | Browser Use allowlist configuration |
| `config/mcp-allowlist-playwright.env` | Created | Playwright allowlist configuration |
| `tests/test_mcp_security_proxy.py` | Created | Test suite (13 tests) |
| `/home/vscode/.config/kilo/kilo.jsonc` | Modified | Browser Use and Playwright routed through proxies |
| `pytest.ini` | Modified | Registered `integration` test marker |

---

## 10. Security Summary

| Safeguard | Status |
|-----------|--------|
| Default-deny tool allowlist | ✅ Enforced at proxy boundary |
| `browser_click/type/scroll` blocked | ✅ Not in Browser Use allowlist |
| `browser_evaluate` (arbitrary JS) blocked | ✅ Not in Playwright allowlist |
| gflow `--no-spend` preserved | ✅ Unchanged in kilo.jsonc |
| gflow profile `flow_remote` preserved | ✅ Unchanged |
| No secrets in audit log | ✅ Verified by test |
| Proxy blocks at boundary (before child process) | ✅ Verified by test |
| Kilo Bash access requires approval | ✅ `"*"`: `"ask"` |
| No direct bypass through Kilo config | ✅ Browser Use and Playwright only accessible via proxy |
