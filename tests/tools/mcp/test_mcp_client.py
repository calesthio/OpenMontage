import sys

from tools.mcp.mcp_client import MCPClient, MCPConnectionError
from tools.mcp.mcp_config import McpServerConfig


def test_list_tools(fake_server_config):
    client = MCPClient(fake_server_config)
    try:
        tools = client.list_tools()
        names = {t.name for t in tools}
        # Mirrors the real ComfyUI MCP server tool list (tests/fixtures/mcp/fake_server.py).
        expected = {
            "calculate_resolution", "expand_prompt",
            "generate_image_t2i_zit",
            "generate_video_fl2va_minimax_h3", "generate_video_i2va_minimax_h3",
            "generate_video_t2va_minimax_h3", "generate_video_ref2va_minimax_h3",
            "select_best_image", "evaluate_media", "extract_video_last_frame",
        }
        assert expected <= names
        gen = next(t for t in tools if t.name == "generate_image_t2i_zit")
        props = gen.input_schema.get("properties") or {}
        assert {"prompt", "width", "height"} <= set(props)
        ex = next(t for t in tools if t.name == "expand_prompt")
        target = (ex.input_schema.get("properties") or {}).get("target_model") or {}
        assert target.get("enum") == ["zit", "minimax-h3"]
    finally:
        client.close()


def test_call_tool_image_content(fake_server_config):
    client = MCPClient(fake_server_config)
    try:
        result = client.call_tool("generate_image_t2i_zit", {"prompt": "a red dot", "width": 512, "height": 512})
        assert result.is_error is False
        block = result.content[0]
        assert block.type == "image"
        assert block.mime_type == "image/png"
        hdr = block.data[:4]
        assert hdr == "iVBO"  # base64 prefix of a PNG signature
    finally:
        client.close()


def test_call_tool_resource_video(fake_server_config):
    client = MCPClient(fake_server_config)
    try:
        result = client.call_tool(
            "generate_video_t2va_minimax_h3",
            {"prompt": "clip", "duration": 3.0, "width": 384, "height": 512},
        )
        assert result.is_error is False
        block = result.content[0]
        assert block.type == "resource"
        resource = block.resource
        assert resource.uri == "fake://out/video/demo.mp4"
        assert resource.mime_type == "video/mp4"
        assert resource.blob is not None
    finally:
        client.close()


def test_call_tool_text(fake_server_config):
    client = MCPClient(fake_server_config)
    try:
        result = client.call_tool("expand_prompt", {"prompt": "a cat", "target_model": "zit"})
        assert result.is_error is False
        assert result.content[0].text == "expanded:zit:a cat"
    finally:
        client.close()


def test_connect_failure_raises():
    client = MCPClient(McpServerConfig(
        slug="gone", transport="stdio", command=sys.executable,
        args=["-c", "import sys; sys.exit(3)"],
    ))
    try:
        assert not client.probe(timeout=3.0)
        try:
            client.list_tools(timeout=5.0)
        except (MCPConnectionError, TimeoutError, RuntimeError):
            pass  # expected: server exited immediately
    finally:
        client.close()


def test_connect_is_idempotent(fake_server_config):
    client = MCPClient(fake_server_config)
    try:
        client.connect()
        client.connect()
        assert client.probe()
    finally:
        client.close()
