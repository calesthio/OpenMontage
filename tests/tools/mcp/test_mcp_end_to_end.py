"""End-to-end: config -> sync -> image_selector routes to an MCP provider.

Selectors route through the module-level ``registry`` singleton (their
``_providers()`` reads it), so this test wires MCP tools into the global
registry exactly as production would, then removes them in cleanup.
"""

import sys
from pathlib import Path

from tools.mcp.mcp_registry import sync_mcp_servers
from tools.tool_registry import registry

FAKE = Path(__file__).resolve().parent.parent.parent / "fixtures" / "mcp" / "fake_server.py"


def _config_text() -> str:
    return (
        "mcp:\n"
        "  enabled: true\n"
        "  list_on_boot: false\n"
        "  servers:\n"
        "    fake:\n"
        "      transport: stdio\n"
        f"      command: {sys.executable}\n"
        f"      args: ['{FAKE}']\n"
        "      tools:\n"
        "        generate_image_t2i_zit: { capability: image_generation }\n"
    )


def test_selector_routes_to_mcp_image(tmp_path):
    cfg_file = tmp_path / "mcp_servers.yaml"
    cfg_file.write_text(_config_text(), encoding="utf-8")
    registry.discover()  # register core tools (image_selector etc.)
    sync_mcp_servers(registry, config_path=str(cfg_file))

    try:
        sel = registry.get("image_selector")
        assert sel is not None
        candidates = sel._providers()
        mcp_tool = next(t for t in candidates if t.name == "mcp_fake_generate_image_t2i_zit")
        # Pre-warm the MCP connection so get_status() resolves AVAILABLE and the
        # selector ranks it selectable.
        assert mcp_tool.get_status().value == "available"

        result = sel.execute({
            "prompt": "a red dot",
            "width": 512,
            "height": 512,
            "preferred_provider": "fake",
            "allowed_providers": ["fake"],
            "output_path": str(tmp_path / "dot.png"),
        })
        assert result.success is True, result.error
        assert result.data["selected_provider"] == "fake"
        out = result.data.get("output") or (result.artifacts or [None])[0]
        assert out and Path(out).exists()
        assert Path(out).stat().st_size > 0
    finally:
        # Remove the MCP provider from the shared registry and reap its session.
        mcp = registry._tools.pop("mcp_fake_generate_image_t2i_zit", None)
        if mcp is not None:
            try:
                mcp._client.close()
            except AttributeError:
                pass
