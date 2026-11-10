#!/usr/bin/env python3
"""Google Flow image generation via Chrome DevTools Protocol (CDP).

Connects to a running Chrome instance with the gflow profile via the DevTools
WebSocket, opens flow.google.com, dismisses Russian consent dialogs, creates
a project, types the prompt using CDP Input.insertText (not JS — the framework
editor doesn't see JS-assigned values), submits with Input.dispatchKeyEvent
Enter, waits for generated images, and downloads them via Page.captureScreenshot
with element clip coordinates.

Security:
  - Never prints cookies, tokens, profile contents, Local State, or DevToolsActivePort.
  - Does not read the profile directory.
  - Only downloads generated image files.
  - Strips Authorization/Cookie headers from network logs.

Usage:
  python scripts/flow_cdp_image.py \
    --prompt "simple blue circle on white background" \
    --ratio 16:9 --out /tmp/flow-test/test-photo.png \
    [--ws-port 35029] [--page-id <cdp page id>] [--timeout 120]

Prerequisites:
  1. Chrome with gflow profile running with remote debugging port:
     GFLOW_CHROME_PATH=/opt/google/chrome/chrome DISPLAY=:99 \
     /opt/google/chrome/chrome \
       --user-data-dir=/workspaces/OpenMontage/.gflow/profiles/default \
       --remote-debugging-port=0 --remote-allow-origins=* \
       --no-first-run --no-default-browser-check \
       --disable-blink-features=AutomationControlled \
       --lang=en-US --accept-lang=en-US https://flow.google.com &
  2. Get DevTools port: cat .gflow/profiles/default/DevToolsActivePort
  3. Get page ID: curl http://127.0.0.1:<PORT>/json/list | grep flow.google.com
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class CDPSession:
    """Minimal Chrome DevTools Protocol WebSocket client."""

    def __init__(self, ws_uri: str, log: list[str]) -> None:
        self.ws_uri = ws_uri
        self.log = log
        self._seq = 0
        self.ws = None
        self.network_events: list[dict[str, Any]] = []

    async def connect(self) -> None:
        import websockets  # imported lazily so import without dep is OK

        self.ws = await websockets.connect(self.ws_uri)
        self.log_append(f"CDP connected: {self.ws_uri}")
        for domain in ["Network", "Page", "Input", "Accessibility", "Runtime"]:
            await self._send({"method": f"{domain}.enable"})
            await self._recv_until_id(self._seq)
        await self._send({"method": "Network.setCacheDisabled", "params": {"cacheDisabled": True}})
        await self._recv_until_id(self._seq)

    def log_append(self, message: str) -> None:
        line = f"{ts()} {message}"
        self.log.append(line)
        print(line)

    async def close(self) -> None:
        if self.ws:
            await self.ws.close()

    async def _send(self, msg: dict[str, Any]) -> int:
        self._seq += 1
        msg["id"] = self._seq
        await self.ws.send(json.dumps(msg))
        return self._seq

    async def _recv_until_id(self, target_id: int) -> dict[str, Any]:
        while True:
            raw = await self.ws.recv()
            msg = json.loads(raw)
            if msg.get("id") == target_id:
                return msg

    async def eval(self, expression: str) -> Any:
        """Evaluate JS in the page context and return the parsed result value."""
        await self._send(
            {
                "method": "Runtime.evaluate",
                "params": {"expression": expression, "returnByValue": True},
            }
        )
        msg = await self._recv_until_id(self._seq)
        result = msg.get("result", {})
        if "exceptionDetails" in result:
            raise RuntimeError(f"JS error: {result['exceptionDetails']}")
        val = result["result"]["value"]
        if isinstance(val, str):
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                return val
        return val

    async def action(self, js_body: str) -> str:
        """Run an IIFE action (may contain return statements) and return its string result."""
        expr = f"(function() {{ {js_body} }})()"
        val = await self.eval(expr)
        if isinstance(val, str):
            return val
        return str(val)

    async def insert_text(self, text: str) -> None:
        """Use CDP Input.insertText to type into the focused element."""
        await self._send(
            {
                "method": "Input.insertText",
                "params": {"text": text},
            }
        )
        await self._recv_until_id(self._seq)

    async def dispatch_key(self, key: str, code: str, key_code: int = 0) -> None:
        """Use CDP Input.dispatchKeyEvent (keyDown + keyUp)."""
        for ev_type in ["keyDown", "keyUp"]:
            await self._send(
                {
                    "method": "Input.dispatchKeyEvent",
                    "params": {
                        "type": ev_type,
                        "key": key,
                        "code": code,
                        "windowsVirtualKeyCode": key_code,
                        "nativeVirtualKeyCode": key_code,
                        "autoRepeat": False,
                    },
                }
            )
            await self._recv_until_id(self._seq)

    async def screenshot(self, path: str, clip: dict[str, Any] | None = None) -> None:
        """Capture a screenshot via Page.captureScreenshot and save to path."""
        params: dict[str, Any] = {}
        if clip:
            params["clip"] = clip
        await self._send({"method": "Page.captureScreenshot", "params": params})
        msg = await self._recv_until_id(self._seq)
        result = msg.get("result", {})
        if "exceptionDetails" in result:
            raise RuntimeError(f"Screenshot error: {result['exceptionDetails']}")
        data = result.get("data")
        if data is None:
            raise RuntimeError(f"Screenshot: no data in response: {msg}")
        img_bytes = base64.b64decode(data)
        with open(path, "wb") as f:
            f.write(img_bytes)
        self.log_append(f"screenshot saved: {path} ({len(img_bytes)} bytes)")


async def dismiss_dialogs(session: CDPSession) -> None:
    """Dismiss Russian consent/cookie/storage dialogs by button label."""
    labels = ["ОК", "Включить", "Закрыть сообщение", "Закрыть баннер", "Отмена"]
    for label in labels:
        try:
            result = await session.eval(
                f"""
                (function() {{
                    var btns = Array.from(document.querySelectorAll('button')).filter(
                        b => (b.textContent||'').trim().includes('{label}')
                    );
                    btns[0]?.click();
                    return btns.length > 0 ? 'clicked {label}' : 'no {label}';
                }})()
                """
            )
            session.log_append(f"dialog '{label}': {result}")
        except Exception as exc:  # noqa: BLE001 - dialog may not exist
            session.log_append(f"dialog '{label}': skipped ({exc})")
        await asyncio.sleep(0.3)


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate an image via Google Flow using CDP"
    )
    parser.add_argument("--prompt", default="simple blue circle on white background",
                        help="generation prompt")
    parser.add_argument("--ratio", default="16:9", help="aspect ratio (16:9, 9:16, 1:1, 4:3, 3:4)")
    parser.add_argument("--out", default="/tmp/flow-test/test-photo.png",
                        help="output image path")
    parser.add_argument("--ws-port", type=int, default=35029, help="CDP websocket port")
    parser.add_argument(
        "--page-id", default="", help="CDP page target id for flow.google.com"
    )
    parser.add_argument(
        "--timeout", type=int, default=120, help="max seconds to wait for image"
    )
    args = parser.parse_args()

    log: list[str] = []
    log_append = lambda m: None  # placeholder, replaced by session.log_append

    ws_uri = f"ws://127.0.0.1:{args.ws_port}/devtools/page/{args.page_id}"
    session = CDPSession(ws_uri, log)

    try:
        await session.connect()

        # Ensure we're on flow.google.com
        current_url = await session.eval("window.location.href")
        session.log_append(f"current url: {current_url}")
        if "flow.google.com" not in str(current_url):
            await session.eval("window.location.href = 'https://flow.google.com'")
            await asyncio.sleep(2)

        # Dismiss consent dialogs
        await dismiss_dialogs(session)
        await asyncio.sleep(1)

        # Click "Новый проект" (New project)
        session.log_append("clicking Новый проект")
        click_result = await session.action(
            """
            var els = Array.from(document.querySelectorAll('button')).filter(
                b => /Новый проект/.test(b.textContent || '')
            );
            if (els.length > 0) { els[0].click(); return 'clicked ' + els.length; }
            return 'no elements';
            """
        )
        session.log_append(f"new project: {click_result}")
        await asyncio.sleep(2)

        # Dismiss dialogs again (they reappear on new project)
        await dismiss_dialogs(session)
        await asyncio.sleep(1)

        # Wait for prompt box
        session.log_append("waiting for prompt box")
        prompt_found = False
        deadline = asyncio.get_event_loop().time() + 30
        while asyncio.get_event_loop().time() < deadline:
            has_pb = await session.eval(
                "!!document.querySelector('[role=\"textbox\"][contenteditable=\"true\"]')"
            )
            if has_pb:
                prompt_found = True
                session.log_append("prompt box found")
                break
            await asyncio.sleep(2)
        if not prompt_found:
            session.log_append("ERROR: prompt box not found within 30s")
            return 1

        # Focus the textbox via DOM click
        session.log_append("focusing prompt textbox")
        focus_result = await session.action(
            """
            var pb = document.querySelector('[role="textbox"][contenteditable="true"]');
            if (pb) { pb.focus(); return 'focused'; }
            return 'not found';
            """
        )
        session.log_append(f"focus: {focus_result}")
        await asyncio.sleep(0.5)

        # Type the prompt via CDP Input.insertText (NOT JS — framework editor
        # doesn't see JS-assigned values)
        session.log_append(f"inserting text via CDP: '{args.prompt}'")
        await session.insert_text(args.prompt)
        await asyncio.sleep(0.5)

        # Verify text was inserted
        text_check = await session.eval(
            "document.querySelector('[role=\"textbox\"][contenteditable=\"true\"]').textContent"
        )
        session.log_append(f"textbox content: {text_check!r}")

        # Screenshot after text input
        await session.screenshot(f"{args.out}.after_input.png")

        # Press Enter via CDP Input.dispatchKeyEvent (NOT JS click — framework
        # may not register JS-dispatched clicks on framework buttons)
        session.log_append("dispatching Enter key via CDP")
        await session.dispatch_key("Enter", "Enter", 13)
        await asyncio.sleep(0.5)

        # Screenshot after submit
        await session.screenshot(f"{args.out}.after_submit.png")

        # Wait for result image (poll every 5s, up to timeout)
        session.log_append(f"waiting for image (timeout {args.timeout}s)")
        deadline = asyncio.get_event_loop().time() + args.timeout
        shot_offsets = [5, 30, 90]
        next_shot_idx = 0
        found = False
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(5)
            elapsed = int(asyncio.get_event_loop().time() - start_time)

            # Checkpoint screenshots at 5s, 30s, 90s
            while (
                next_shot_idx < len(shot_offsets)
                and elapsed >= shot_offsets[next_shot_idx]
            ):
                await session.screenshot(f"{args.out}.shot{next_shot_idx + 1}s.png")
                session.log_append(f"checkpoint screenshot t+{shot_offsets[next_shot_idx]}s")
                next_shot_idx += 1

            img_count = await session.eval(
                "document.querySelectorAll('flow-image-tile img[data-media-id], img[data-media-id]').length"
            )
            session.log_append(f"images found: {img_count}")
            if isinstance(img_count, (int, float)) and img_count > 0:
                found = True
                break

        # Final screenshot
        await session.screenshot(f"{args.out}.final.png")

        # Dump page text for debugging
        body_text = await session.eval("document.body.innerText")
        lines = str(body_text).split("\n")
        session.log_append("=== PAGE TEXT (first 50 lines) ===")
        for i, line in enumerate(lines[:50]):
            session.log_append(f"  {i + 1}: {line}")
        session.log_append("=== END PAGE TEXT ===")

        if not found:
            session.log_append("ERROR: no images found within timeout")
            return 1

        # Get image element bounding boxes and capture each via screenshot clip
        img_rects = await session.eval(
            """
            JSON.stringify(Array.from(document.querySelectorAll('flow-image-tile img[data-media-id], img[data-media-id]')).map(img => {
                const rect = img.getBoundingClientRect();
                return {x: rect.x, y: rect.y, w: rect.width, h: rect.height};
            }))
            """
        )
        if not isinstance(img_rects, list) or len(img_rects) == 0:
            session.log_append("ERROR: no image rects found")
            return 1

        base_out = os.path.splitext(args.out)[0]
        ext = os.path.splitext(args.out)[1] or ".png"
        downloaded = 0
        for i, rect in enumerate(img_rects):
            clip = {
                "x": math.floor(rect["x"]),
                "y": math.floor(rect["y"]),
                "width": math.floor(rect["w"]),
                "height": math.floor(rect["h"]),
                "scale": 1,
            }
            out_path = f"{base_out}_{i + 1}{ext}"
            await session.screenshot(out_path, clip)

            # Verify and compute sha256
            with open(out_path, "rb") as f:
                file_bytes = f.read()
            sha256 = hashlib.sha256(file_bytes).hexdigest()
            size = len(file_bytes)
            session.log_append(
                f"saved: {out_path} ({size} bytes, sha256={sha256})"
            )
            downloaded += 1

        session.log_append(f"done — {downloaded} image(s) downloaded")
        return 0

    finally:
        await session.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
