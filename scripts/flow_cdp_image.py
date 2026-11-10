#!/usr/bin/env python3
"""Google Flow image generation via Chrome DevTools Protocol (CDP).

Connects to a running Chrome instance with the gflow profile via the DevTools
WebSocket, opens flow.google.com, dismisses Russian consent dialogs, creates a
project, types the prompt, submits generation, waits for the result image, and
downloads it to --out.

Security:
  - Never prints cookies, tokens, profile contents, Local State, or DevToolsActivePort.
  - Does not read the profile directory.
  - Only downloads the generated image file.

Usage:
  python scripts/flow_cdp_image.py --prompt "simple blue circle on white background" \
    --ratio 16:9 --out /tmp/flow-test/test-photo.png \
    [--ws-port 35029] [--page-id <cdp page id>] [--timeout 120]
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from typing import Any


WS_PORT = 35029
PAGE_ID = "44440557D049C84427755B228980E4FC"
WS_URI = f"ws://127.0.0.1:{WS_PORT}/devtools/page/{PAGE_ID}"
PROMPT_DEFAULT = "simple blue circle on white background"
RATIO_DEFAULT = "16:9"
OUT_DEFAULT = "/tmp/flow-test/test-photo.png"
TIMEOUT_DEFAULT = 120
POLL_INTERVAL = 5


class CDPSession:
    """Minimal Chrome DevTools Protocol WebSocket client."""

    def __init__(self, ws_uri: str, log: list[str]) -> None:
        self.ws_uri = ws_uri
        self.log = log
        self._seq = 0

    async def connect(self) -> None:
        import websockets  # imported lazily so import without dep is OK

        self.ws = await websockets.connect(self.ws_uri)
        self.log.append(f"CDP connected: {self.ws_uri}")
        await self._send({"method": "Runtime.enable"})
        await self._recv_until_id(self._seq)

    async def close(self) -> None:
        if hasattr(self, "ws"):
            await self.ws.close()

    async def _send(self, msg: dict[str, Any]) -> None:
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

    async def action(self, js_iife: str) -> str:
        """Run an IIFE action (may contain return statements) and return its string result."""
        expr = f"(function() {{ {js_iife} }})()"
        val = await self.eval(expr)
        if isinstance(val, str):
            return val
        return str(val)


def step_log(log: list[str], message: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{ts} {message}"
    log.append(line)
    print(line)


async def dismiss_dialogs(session: CDPSession, log: list[str]) -> None:
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
            step_log(log, f"dialog '{label}': {result}")
        except Exception as exc:  # noqa: BLE001 - dialog may not exist
            step_log(log, f"dialog '{label}': skipped ({exc})")
        await asyncio.sleep(0.3)


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate an image via Google Flow using CDP"
    )
    parser.add_argument("--prompt", default=PROMPT_DEFAULT, help="generation prompt")
    parser.add_argument("--ratio", default=RATIO_DEFAULT, help="aspect ratio (16:9)")
    parser.add_argument("--out", default=OUT_DEFAULT, help="output image path")
    parser.add_argument("--ws-port", type=int, default=WS_PORT, help="CDP websocket port")
    parser.add_argument(
        "--page-id", default=PAGE_ID, help="CDP page target id for flow.google.com"
    )
    parser.add_argument(
        "--timeout", type=int, default=TIMEOUT_DEFAULT, help="max seconds to wait for image"
    )
    args = parser.parse_args()

    log: list[str] = []
    step_log(log, f"start prompt='{args.prompt}' ratio={args.ratio} out={args.out}")

    ws_uri = f"ws://127.0.0.1:{args.ws_port}/devtools/page/{args.page_id}"
    session = CDPSession(ws_uri, log)

    try:
        await session.connect()

        # Ensure we're on flow.google.com
        current_url = await session.eval("window.location.href")
        step_log(log, f"current url: {current_url}")
        if "flow.google.com" not in str(current_url):
            await session.eval("window.location.href = 'https://flow.google.com'")
            await asyncio.sleep(2)

        # Dismiss consent dialogs
        await dismiss_dialogs(session, log)
        await asyncio.sleep(1)

        # Click "Новый проект" (New project)
        step_log(log, "clicking Новый проект")
        click_result = await session.action(
            """
            var els = Array.from(document.querySelectorAll('button')).filter(
                b => /Новый проект/.test(b.textContent || '')
            );
            if (els.length > 0) { els[0].click(); return 'clicked ' + els.length; }
            return 'no elements';
            """
        )
        step_log(log, f"new project: {click_result}")
        await asyncio.sleep(2)

        # Dismiss dialogs that reappear on new project
        await dismiss_dialogs(session, log)
        await asyncio.sleep(1)

        # Wait for prompt box
        step_log(log, "waiting for prompt box")
        prompt_found = False
        deadline = asyncio.get_event_loop().time() + 30
        while asyncio.get_event_loop().time() < deadline:
            has_pb = await session.eval(
                "!!document.querySelector('[role=\"textbox\"][contenteditable=\"true\"]')"
            )
            if has_pb:
                prompt_found = True
                step_log(log, "prompt box found")
                break
            await asyncio.sleep(2)
        if not prompt_found:
            step_log(log, "ERROR: prompt box not found within 30s")
            return 1

        # Type the prompt
        step_log(log, "typing prompt")
        await session.eval(
            f"""
            (function() {{
                var pb = document.querySelector('[role="textbox"][contenteditable="true"]');
                pb.focus();
                pb.textContent = {json.dumps(args.prompt)};
                pb.dispatchEvent(new Event('input', {{bubbles: true}}));
                return 'typed: ' + pb.textContent;
            }})()
            """
        )
        await asyncio.sleep(1)

        # Click submit ("Начать генерацию")
        step_log(log, "clicking Начать генерацию")
        submit_result = await session.action(
            """
            var els = Array.from(document.querySelectorAll('button, [role="button"]')).filter(
                b => (b.getAttribute('aria-label')||'').includes('Начать генерацию')
                  || /Начать генерацию/.test(b.textContent || '')
            );
            if (els.length > 0) { els[0].click(); return 'clicked submit'; }
            return 'no submit btn';
            """
        )
        step_log(log, f"submit: {submit_result}")

        # Wait for result image (poll every POLL_INTERVAL s, up to timeout)
        step_log(log, f"waiting for image (timeout {args.timeout}s)")
        deadline = asyncio.get_event_loop().time() + args.timeout
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(POLL_INTERVAL)
            img_count = await session.eval(
                "document.querySelectorAll('flow-image-tile img[data-media-id], img[data-media-id]').length"
            )
            step_log(log, f"images found: {img_count}")
            if isinstance(img_count, (int, float)) and img_count > 0:
                break

        # Get image URLs
        img_data = await session.eval(
            "JSON.stringify(Array.from(document.querySelectorAll('flow-image-tile img[data-media-id], img[data-media-id]')).map(img => ({src: img.src, mediaId: img.getAttribute('data-media-id')})).slice(0, 3))"
        )
        if not isinstance(img_data, list) or len(img_data) == 0:
            step_log(log, "ERROR: no image URLs found")
            return 1

        img_url = img_data[0]["src"]
        step_log(log, f"downloading from: {img_url[:80]}...")

        # Download the image
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        urllib.request.urlretrieve(img_url, args.out)

        # Compute sha256
        with open(args.out, "rb") as f:
            file_bytes = f.read()
        sha256 = hashlib.sha256(file_bytes).hexdigest()
        size = len(file_bytes)

        step_log(log, f"saved: {args.out} ({size} bytes, sha256={sha256})")
        step_log(log, "done")

        # Write log to stdout only (no file with secrets)
        return 0

    finally:
        await session.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
