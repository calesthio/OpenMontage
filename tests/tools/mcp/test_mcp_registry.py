import sys
from pathlib import Path

from mcp.types import Tool

from tools.mcp.mcp_catalog import MCPCatalog
from tools.mcp.mcp_call import MCPCall
from tools.mcp.mcp_config import McpServerConfig, McpToolOverride
from tools.mcp.mcp_registry import _config_signature, list_server_tools, sync_mcp_servers
from tools.mcp.mcp_tool import build_mcp_tools
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


def _register_builtin_tools(registry: ToolRegistry) -> None:
    """Register the two built-in discovery/raw-call tools."""
    registry.register(MCPCatalog())
    registry.register(MCPCall())


def _register_generated_tool(registry: ToolRegistry, server) -> str:
    """Register a bridge-generated MCPTool and return its name."""
    server.tools["generate_image_t2i_zit"] = McpToolOverride(capability="image_generation")
    defs = [Tool(name="generate_image_t2i_zit", description="x",
                 input_schema={"type": "object", "properties": {}})]
    generated = build_mcp_tools(server, defs)[0]
    registry._tools[generated.name] = generated
    return generated.name


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


def test_disabled_drops_mcp_tools(tmp_path, fake_server_config):
    cfg_file = tmp_path / "mcp_servers.yaml"
    cfg_file.write_text("mcp:\n  enabled: false\n  servers: {}\n", encoding="utf-8")
    registry = _fresh_registry()
    generated_name = _register_generated_tool(registry, fake_server_config)
    sync_mcp_servers(registry, config_path=str(cfg_file))
    assert generated_name not in registry._tools


def test_builtin_tools_preserved_with_populated_config(tmp_path):
    """mcp_catalog / mcp_call survive stale-tool cleanup after a real sync."""
    cfg_file = tmp_path / "mcp_servers.yaml"
    cfg_file.write_text(_config_text(), encoding="utf-8")
    registry = _fresh_registry()
    _register_builtin_tools(registry)
    sync_mcp_servers(registry, config_path=str(cfg_file))
    assert "mcp_catalog" in registry.list_all()
    assert "mcp_call" in registry.list_all()
    assert "mcp_fake_generate_image_t2i_zit" in registry.list_all()  # frozen bridged


def test_builtin_tools_preserved_with_empty_config(tmp_path, fake_server_config):
    """An enabled config with no servers must drop stale generated tools but keep built-ins."""
    cfg_file = tmp_path / "mcp_servers.yaml"
    cfg_file.write_text("mcp:\n  enabled: true\n  servers: {}\n", encoding="utf-8")
    registry = _fresh_registry()
    _register_builtin_tools(registry)
    generated_name = _register_generated_tool(registry, fake_server_config)
    sync_mcp_servers(registry, config_path=str(cfg_file))
    assert "mcp_catalog" in registry.list_all()
    assert "mcp_call" in registry.list_all()
    assert generated_name not in registry._tools


def test_discover_mcp_hook_nonfatal(tmp_path, monkeypatch):
    registry = _fresh_registry()
    monkeypatch.setenv("MCP_SERVERS_PATH", str(tmp_path / "none.yaml"))
    registry.discover_mcp()  # missing config -> must not raise or slow the pipeline
    assert getattr(registry, "_mcp_warnings", []) == []
