import sys
from pathlib import Path

from tools.mcp.mcp_config import McpServerConfig
from tools.mcp.mcp_registry import _config_signature, list_server_tools, sync_mcp_servers
from tools.tool_registry import ToolRegistry

FAKE = Path(__file__).resolve().parent.parent.parent / "fixtures" / "mcp" / "fake_server.py"


def _config_text():
    return (
        "mcp:\n"
        "  enabled: true\n"
        "  list_on_boot: true\n"
        "  servers:\n"
        "    fake:\n"
        "      transport: stdio\n"
        f"      command: {sys.executable}\n"
        f"      args: ['{FAKE}']\n"
        "      tools:\n"
        "        generate_image_t2i_zit: { capability: image_generation }\n"
        "        evaluate_media: {}\n"
    )


def _fresh_registry() -> ToolRegistry:
    return ToolRegistry()


def test_frozen_only_registered(tmp_path):
    cfg_file = tmp_path / "mcp_servers.yaml"
    cfg_file.write_text(_config_text(), encoding="utf-8")
    registry = _fresh_registry()
    sync_mcp_servers(registry, config_path=str(cfg_file))

    assert "mcp_fake_generate_image_t2i_zit" in registry.list_all()
    tool = registry.get("mcp_fake_generate_image_t2i_zit")
    assert tool.capability == "image_generation"
    assert tool.provider == "fake"
    assert "mcp_fake_evaluate_media" not in registry.list_all()  # unfrozen -> never bridged
    assert getattr(registry, "_mcp_warnings", []) == []


def test_list_server_tools_cached_and_live(tmp_path):
    server = McpServerConfig(slug="fake", transport="stdio", command=sys.executable, args=[str(FAKE)])
    digest = _config_signature({"servers": [server]})
    tools = list_server_tools(server, digest)
    names = {t.name for t in tools}
    assert "generate_image_t2i_zit" in names and "evaluate_media" in names
    # cache hit path returns same shape
    tools2 = list_server_tools(server, digest)
    assert {t.name for t in tools2} == names


def test_signature_diffs_on_tool_change():
    s1 = {"servers": [{"slug": "a", "tools": {"x": {"capability": "tts"}}}]}
    s2 = {"servers": [{"slug": "a", "tools": {"x": {"capability": "video_generation"}}}]}
    assert _config_signature(s1) != _config_signature(s2)


def test_disabled_drops_mcp_tools(tmp_path):
    cfg_file = tmp_path / "mcp_servers.yaml"
    cfg_file.write_text("mcp:\n  enabled: false\n  servers: {}\n", encoding="utf-8")
    registry = _fresh_registry()

    class StubMCPTool:
        name = "mcp_stale_x"

    registry._tools["mcp_stale_x"] = StubMCPTool()  # type: ignore[assignment]
    sync_mcp_servers(registry, config_path=str(cfg_file))
    assert "mcp_stale_x" not in registry._tools


def test_discover_mcp_hook_nonfatal(tmp_path, monkeypatch):
    registry = _fresh_registry()
    monkeypatch.setenv("MCP_SERVERS_PATH", str(tmp_path / "none.yaml"))
    registry.discover_mcp()  # missing config -> must not raise or slow the pipeline
    assert getattr(registry, "_mcp_warnings", []) == []
