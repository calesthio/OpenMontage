import os
from pathlib import Path
import pytest

from tools.mcp.mcp_config import (
    McpServerConfig, RESERVED_KEYS, load_mcp_config, mime_extension, validate_mcp_schema,
)


def _write(tmp_path, text):
    p = tmp_path / "mcp_servers.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_load_minimal_http_server(tmp_path):
    cfg = load_mcp_config(_write(tmp_path, (
        "mcp:\n"
        "  enabled: true\n"
        "  list_on_boot: true\n"
        "  servers:\n"
        "    comfy:\n"
        "      transport: http\n"
        "      url: http://127.0.0.1:8090/mcp\n"
        "      tools: {}\n"
    )))
    assert cfg.enabled is True and cfg.list_on_boot is True
    assert len(cfg.servers) == 1
    srv = cfg.servers[0]
    assert (srv.slug, srv.transport, srv.url) == ("comfy", "http", "http://127.0.0.1:8090/mcp")
    assert srv.frozen_tool_names == []


def test_frozen_capability_and_override(tmp_path):
    cfg = load_mcp_config(_write(tmp_path, (
        "mcp:\n"
        "  servers:\n"
        "    fal:\n"
        "      transport: stdio\n"
        "      command: npx\n"
        "      args: ['-y', '@fal-ai/mcp-server']\n"
        "      tools:\n"
        "        generate_image: { capability: image_generation }\n"
        "        text_to_video: { capability: video_generation, cost_usd: 0.2 }\n"
        "        helper: {}\n"
    )))
    fal = cfg.servers[0]
    assert fal.frozen_capability("generate_image") == "image_generation"
    assert fal.frozen_capability("text_to_video") == "video_generation"
    assert fal.frozen_capability("helper") is None
    assert fal.frozen_tool_names == ["generate_image", "text_to_video"]
    assert fal.tools["text_to_video"].cost_usd == 0.2


def test_transport_validation_errors(tmp_path):
    with pytest.raises(ValueError, match="transport"):
        load_mcp_config(_write(tmp_path, (
            "mcp:\n  servers:\n    bad:\n      transport: udp\n"
        )))
    with pytest.raises(ValueError, match="command"):
        load_mcp_config(_write(tmp_path, (
            "mcp:\n  servers:\n    s1:\n      transport: stdio\n"
        )))
    with pytest.raises(ValueError, match="url"):
        load_mcp_config(_write(tmp_path, (
            "mcp:\n  servers:\n    s2:\n      transport: http\n"
        )))


def test_missing_file_is_empty_config(tmp_path):
    cfg = load_mcp_config(tmp_path / "nope.yaml")
    assert cfg.servers == []
    assert cfg.enabled is True


def test_env_path_override(tmp_path, monkeypatch):
    p = _write(tmp_path, "mcp:\n  enabled: false\n  servers: {}\n")
    monkeypatch.setenv("MCP_SERVERS_PATH", str(p))
    cfg = load_mcp_config()
    assert cfg.enabled is False


def test_mime_extension():
    assert mime_extension("image/png") == ".png"
    assert mime_extension("audio/mpeg") == ".mp3"
    assert mime_extension("video/mp4") == ".mp4"
    assert mime_extension("application/x-subrip") == ".srt"
    assert mime_extension("image/avif") == ".bin"
    assert mime_extension(None) == ".bin"


def test_reserved_keys_are_closed_set():
    assert {"output_path", "scene_id", "task_context", "preferred_provider"} <= RESERVED_KEYS


def test_schema_rejects_bad_raw():
    with pytest.raises(Exception):
        validate_mcp_schema({"mcp": {"servers": "not-a-map"}})
