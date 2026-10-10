#!/usr/bin/env python3
"""stdio MCP server for the OpenMontage Circuit-video generator.

Logs go to stderr. stdout is the JSON-RPC channel — do not print() here.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any, Optional

# Allow `python3 mcp_servers/circuit_video/server.py` from the repo root.
_HERE = Path(__file__).resolve().parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

from circuit_video import service  # noqa: E402
from circuit_video.config import load_config  # noqa: E402

SERVER_NAME = "circuit-video"
SERVER_VERSION = "1.0.0"
PROTOCOL = "2024-11-05"
INSTRUCTIONS = (
    "OpenMontage Circuit tutorial-video generator. "
    "Call list_tutorials, then render_tutorial with the tutorial name and "
    "base_url (the demo app Cypress records against). When AWS credentials "
    "are set, the finished MP4 is uploaded to S3 and a presigned download URL "
    "is returned. Renders take several minutes; wait=false starts one in the background. "
    "Narration comes from the ttsd sidecar by default; pass narration_backend=\"elevenlabs\" "
    "(and optionally voice_id) to call ElevenLabs directly — run doctor first."
)


def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    }


TOOLS = [
    _tool(
        "list_tutorials",
        "List Cypress tutorial specs available in the Circuit backoffice client "
        "(cypress/e2e-tutorials/*.tutorial.cy.js).",
        {},
        [],
    ),
    _tool(
        "doctor",
        "Check that ffmpeg, Cypress/client specs, narration (ttsd or ElevenLabs per "
        "narration_backend), the demo app URL, and AWS S3 credentials are ready for a "
        "Circuit tutorial render.",
        {
            "base_url": {
                "type": "string",
                "description": "Optional demo-app URL to ping instead of the configured default.",
            },
            "narration_backend": {
                "type": "string",
                "enum": ["ttsd", "elevenlabs"],
                "description": "Check this backend instead of the configured one (use the "
                               "value you will pass to render_tutorial).",
            },
            "voice_id": {
                "type": "string",
                "description": "ElevenLabs voice id override to report in the check.",
            },
        },
        [],
    ),
    _tool(
        "render_tutorial",
        "Record a Cypress tutorial against a demo-app URL and assemble the video. "
        "This is the main Circuit-video generator call. Cypress capture plus assembly "
        "typically takes 5–20 minutes. Set wait=false to start it in the background "
        "and poll with get_render.",
        {
            "base_url": {
                "type": "string",
                "description": "Demo environment URL Cypress records against "
                               "(required; never production).",
            },
            "tutorial": {
                "type": "string",
                "description": "Tutorial name, e.g. sales-tour. Required unless the client "
                               "repo has exactly one spec.",
            },
            "project_id": {
                "type": "string",
                "description": "Optional render/project id. Default: <tutorial>-<8 hex chars>.",
            },
            "offline": {
                "type": "boolean",
                "description": "Silent placeholder narration (no ttsd / ElevenLabs). Default false.",
            },
            "narration_backend": {
                "type": "string",
                "enum": ["ttsd", "elevenlabs"],
                "description": "ttsd (default; sidecar at TUTORIAL_NARRATION_URL) or elevenlabs "
                               "(direct ElevenLabs API using ELEVENLABS_API_KEY and "
                               "ELEVENLABS_VOICE_IDS; cached per clip). Recipe narration_backend "
                               "is used when omitted.",
            },
            "voice_id": {
                "type": "string",
                "description": "ElevenLabs voice id to narrate with (elevenlabs backend). "
                               "Omit for the per-language voice from ELEVENLABS_VOICE_IDS "
                               "or the recipe's voice_id.",
            },
            "music": {
                "type": "string",
                "description": "Optional music file path or music_library/ track name.",
            },
            "render_runtime": {
                "type": "string",
                "enum": ["ffmpeg", "remotion"],
                "description": "ffmpeg (default, self-contained) or remotion (animated callouts).",
            },
            "upload": {
                "type": "boolean",
                "description": "Upload the finished MP4 to AWS S3. Default true.",
            },
            "wait": {
                "type": "boolean",
                "description": "Block until the render finishes. Default true. "
                               "Set false and poll get_render for long jobs.",
            },
        },
        ["base_url"],
    ),
    _tool(
        "get_render",
        "Look up a render by id (local project id or remote render-api id). "
        "Returns status, local path, and S3 download URL when available.",
        {
            "render_id": {
                "type": "string",
                "description": "The render_id returned by render_tutorial.",
            },
            "wait": {
                "type": "boolean",
                "description": "If true, poll a remote render-api job until it finishes.",
            },
        },
        ["render_id"],
    ),
    _tool(
        "upload_video",
        "Upload an existing local MP4 to the Circuit AWS S3 bucket and return a "
        "presigned download URL.",
        {
            "file_path": {
                "type": "string",
                "description": "Absolute path to the MP4 (e.g. projects/<id>/renders/final.mp4).",
            },
            "render_id": {
                "type": "string",
                "description": "Object-key prefix (default: parent project folder name).",
            },
            "key": {
                "type": "string",
                "description": "Optional full S3 object key override.",
            },
        },
        ["file_path"],
    ),
]


def _ok(value: Any) -> dict:
    text = value if isinstance(value, str) else json.dumps(value, indent=2, default=str)
    return {"content": [{"type": "text", "text": text}]}


def _err(message: str) -> dict:
    return {"content": [{"type": "text", "text": message}], "isError": True}


def _call(name: str, args: dict) -> dict:
    args = args or {}
    try:
        if name == "list_tutorials":
            return _ok(service.list_tutorials())
        if name == "doctor":
            return _ok(service.doctor(
                base_url=args.get("base_url") or None,
                narration_backend=args.get("narration_backend") or None,
                voice_id=args.get("voice_id") or None,
            ))
        if name == "render_tutorial":
            return _ok(service.render_tutorial(
                base_url=args.get("base_url") or "",
                tutorial=args.get("tutorial") or None,
                project_id=args.get("project_id") or None,
                offline=bool(args.get("offline", False)),
                music=args.get("music") or None,
                render_runtime=args.get("render_runtime") or None,
                upload=bool(args.get("upload", True)),
                wait=bool(args.get("wait", True)),
                narration_backend=args.get("narration_backend") or None,
                voice_id=args.get("voice_id") or None,
            ))
        if name == "get_render":
            return _ok(service.get_render(
                args.get("render_id") or "",
                wait=bool(args.get("wait", False)),
            ))
        if name == "upload_video":
            return _ok(service.upload_video(
                args.get("file_path") or "",
                render_id=args.get("render_id") or None,
                key=args.get("key") or None,
            ))
        return _err(f"unknown tool: {name}")
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        return _err(str(e))
    except Exception as e:  # noqa: BLE001
        traceback.print_exc(file=sys.stderr)
        return _err(f"{type(e).__name__}: {e}")


def _read_message() -> Optional[dict]:
    line = sys.stdin.readline()
    if line == "":
        return None
    if line.lower().startswith("content-length:"):
        headers = {"content-length": line.split(":", 1)[1].strip()}
        while True:
            extra = sys.stdin.readline()
            if extra in ("", "\n", "\r\n"):
                break
            if ":" in extra:
                k, v = extra.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        n = int(headers["content-length"])
        body = sys.stdin.read(n)
        return json.loads(body)
    line = line.strip()
    if not line:
        return _read_message()
    return json.loads(line)


def _write_message(msg: dict) -> None:
    sys.stdout.write(json.dumps(msg, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _handle(msg: dict) -> Optional[dict]:
    method = msg.get("method")
    msg_id = msg.get("id")
    params = msg.get("params") or {}
    if method is None:
        return None
    if msg_id is None:
        return None  # notification

    if method == "initialize":
        client_version = params.get("protocolVersion") or PROTOCOL
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": client_version if client_version.startswith("202") else PROTOCOL,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": INSTRUCTIONS,
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        result = _call(params.get("name") or "", params.get("arguments") or {})
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}
    if method in ("resources/list", "prompts/list"):
        key = "resources" if method.startswith("resources") else "prompts"
        return {"jsonrpc": "2.0", "id": msg_id, "result": {key: []}}
    if method == "logging/setLevel":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def serve() -> int:
    # Touch config once so a missing tutorial.config.json is a stderr warning,
    # not a surprise on the first tool call.
    try:
        load_config()
    except Exception as e:  # noqa: BLE001
        print(f"circuit-video config warning: {e}", file=sys.stderr)
    while True:
        try:
            msg = _read_message()
        except json.JSONDecodeError as e:
            _write_message({
                "jsonrpc": "2.0", "id": None,
                "error": {"code": -32700, "message": f"Parse error: {e}"},
            })
            continue
        if msg is None:
            return 0
        reply = _handle(msg)
        if reply is not None:
            _write_message(reply)


def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--job"] and len(argv) >= 2:
        from circuit_video.service import run_job_file
        return run_job_file(argv[1])
    if argv[:1] in (["-h"], ["--help"]):
        print("circuit-video MCP server (stdio). Tools: list_tutorials, doctor, "
              "render_tutorial, get_render, upload_video.", file=sys.stderr)
        return 0
    return serve()


if __name__ == "__main__":
    raise SystemExit(main())
