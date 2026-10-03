from mcp.types import AudioContent, CallToolResult, ImageContent, TextContent, Tool

from tools.mcp.mcp_config import McpToolOverride
from tools.mcp.mcp_tool import (
    MCPTool, _tool_slug, build_mcp_tools, capability_summary_keys, extract_outputs,
)


def _tool_def(name: str, props: dict) -> Tool:
    return Tool(name=name, description=f"{name} does things",
                input_schema={"type": "object", "properties": props, "required": list(props)})


def _image_block(data: str = "iVBO") -> ImageContent:
    return ImageContent(type="image", data=data, mimeType="image/png")


def test_extract_outputs_image(tmp_path):
    block = _image_block()
    result = CallToolResult(content=[block], is_error=False)
    artifacts, texts, structured = extract_outputs(result, str(tmp_path / "out"))
    assert len(artifacts) == 1
    assert artifacts[0].endswith(".png")
    assert texts == [] and structured is None


def test_extract_outputs_audio(tmp_path):
    block = AudioContent(type="audio", data="SUQzRkFLRU1QMw==", mimeType="audio/mpeg")
    result = CallToolResult(content=[block], is_error=False)
    artifacts, texts, structured = extract_outputs(result, str(tmp_path / "voice"))
    assert len(artifacts) == 1
    assert artifacts[0].endswith(".mp3")
    assert texts == []


def test_extract_outputs_text_only(tmp_path):
    result = CallToolResult(content=[TextContent(type="text", text="caption")], is_error=False)
    artifacts, texts, structured = extract_outputs(result, str(tmp_path / "out"))
    assert artifacts == []
    assert texts == ["caption"]


def test_build_mcp_tools_only_frozen(fake_server_config):
    server = fake_server_config
    server.tools = {
        "generate_image_t2i_zit": McpToolOverride(capability="image_generation"),
        "evaluate_media": McpToolOverride(),  # declared but not frozen
    }
    defs = [_tool_def("generate_image_t2i_zit", {"prompt": {"type": "string"}}),
            _tool_def("evaluate_media", {"prompt": {"type": "string"}, "urls": {"type": "array"}})]
    tools = build_mcp_tools(server, defs)
    assert len(tools) == 1
    instance = tools[0]
    assert instance.name == "mcp_fake_generate_image_t2i_zit"
    assert instance.capability == "image_generation"
    assert instance.provider == "fake"
    assert "prompt" in instance.input_schema["properties"]


def test_tool_slug():
    assert _tool_slug("Cost Effective Mixer") == "cost_effective_mixer"
    assert _tool_slug("text_to_speech") == "text_to_speech"


def test_capability_summary_keys():
    assert capability_summary_keys("image_generation", ["a.png"]) == {"images_generated": 1}
    assert capability_summary_keys("tts", []) == {}


def test_managed_not_registered_by_register_module():
    # The base class must carry the guard marker so tool_registry skips it.
    assert getattr(MCPTool, "_registry_managed", False) is True


def test_execute_is_error_with_artifacts_returns_failure(fake_server_config, tmp_path):
    """is_error is authoritative: even an error result carrying media must fail."""
    from pathlib import Path

    from mcp.types import CallToolResult, TextContent

    from tools.mcp.mcp_client import MCPClient
    from tools.mcp.mcp_config import McpToolOverride
    from tools.mcp.mcp_tool import build_mcp_tools

    cfg = fake_server_config
    cfg.tools["generate_image_t2i_zit"] = McpToolOverride(capability="image_generation")
    client = MCPClient(cfg)
    try:
        instances = build_mcp_tools(cfg, client.list_tools())
        instance = instances[0]
        # Error response that nonetheless ships an image block.
        instance._client.call_tool = lambda *a, **k: CallToolResult(
            content=[TextContent(type="text", text="boom"), _image_block()],
            is_error=True,
        )
        result = instance.execute({"prompt": "x", "output_path": str(tmp_path / "err.png")})
        assert result.success is False
        assert "boom" in result.error
        assert result.artifacts  # diagnostic artifact retained, not treated as success
        assert Path(result.artifacts[0]).exists()
    finally:
        client.close()


def test_execute_writes_png(fake_server_config, tmp_path):
    from pathlib import Path

    from tools.mcp.mcp_client import MCPClient
    from tools.mcp.mcp_config import McpToolOverride
    from tools.mcp.mcp_tool import build_mcp_tools

    cfg = fake_server_config
    cfg.tools["generate_image_t2i_zit"] = McpToolOverride(capability="image_generation")
    client = MCPClient(cfg)
    try:
        instances = build_mcp_tools(cfg, client.list_tools())
        out = tmp_path / "hit.png"
        result = instances[0].execute(
            {"prompt": "dot", "width": 512, "height": 512, "output_path": str(out)}
        )
        assert result.success is True, result.error
        assert result.artifacts and Path(result.artifacts[0]).exists()
        assert result.data["images_generated"] == 1
        assert result.data["provider"] == "fake"
    finally:
        client.close()
