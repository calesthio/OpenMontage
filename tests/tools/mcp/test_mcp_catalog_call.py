import sys
from pathlib import Path

from tools.mcp.mcp_catalog import MCPCatalog
from tools.mcp.mcp_call import MCPCall
from tools.mcp.mcp_config import RESERVED_KEYS

FAKE = Path(__file__).resolve().parent.parent.parent / "fixtures" / "mcp" / "fake_server.py"


def _env(monkeypatch, tmp_path, frozen: dict[str, str]):
    py = tmp_path / "mcp_servers.yaml"
    lines = ["mcp:", "  enabled: true", "  servers:", "    fake:",
             f"      transport: stdio", f"      command: {sys.executable}", f"      args: ['{FAKE}']",
             "      tools:"]
    for name, cap in frozen.items():
        lines.append(f"        {name}: {{ capability: {cap} }}")
    py.write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setenv("MCP_SERVERS_PATH", str(py))


def test_catalog_review_lists_unfrozen_and_frozen(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path, {"generate_image_t2i_zit": "image_generation"})
    catalog = MCPCatalog()
    result = catalog.execute({"operation": "review"})
    assert result.success is True
    tools = result.data["tools"]
    by_name = {t["tool_name"]: t for t in tools}
    assert by_name["generate_image_t2i_zit"]["frozen"] is True
    assert by_name["generate_image_t2i_zit"]["capability"] == "image_generation"
    assert by_name["evaluate_media"]["frozen"] is False
    assert by_name["generate_video_t2va_minimax_h3"]["frozen"] is False
    required = {"server", "tool_name", "title", "description", "input_schema", "frozen", "capability", "output_hints"}
    for item in tools:
        assert required <= set(item)


def test_catalog_list_summary(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path, {})
    result = MCPCatalog().execute({"operation": "list"})
    assert result.success is True
    assert result.data["servers"][0]["slug"] == "fake"


def test_call_raw_passthrough(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path, {})
    caller = MCPCall()
    result = caller.execute({"server": "fake", "tool": "expand_prompt",
                             "arguments": {"prompt": "a cat", "target_model": "zit"}})
    assert result.success is True, result.error
    assert result.data["text"] == "expanded:zit:a cat"


def test_call_unknown_server(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path, {})
    result = MCPCall().execute({"server": "nope", "tool": "x"})
    assert result.success is False


def test_call_strips_reserved_keys():
    # RESERVED_KEYS must never be forwarded to a remote tool.
    assert "output_path" in RESERVED_KEYS
