#!/usr/bin/env python3
"""Google Flow image generation via Chrome DevTools Protocol (CDP).

Connects to a running Chrome instance with the gflow profile via the DevTools
WebSocket, opens flow.google.com, dismisses Russian consent dialogs, creates
a project, types the prompt using CDP Input.insertText (not JS — the framework
editor doesn't see JS-assigned values), submits with Input.dispatchKeyEvent
Enter, waits for NEW generated images (tracking data-media-id before send),
downloads full-resolution images via fetch() in page context (base64),
compares pixel hash with existing images to detect duplicates, discards black
frames, converts to real PNG via PIL (no resize), and writes a manifest.

Security:
  - Never prints cookies, tokens, profile contents, Local State, or DevToolsActivePort.
  - Does not read the profile directory.
  - Only downloads generated image files.
  - Strips Authorization/Cookie headers from network logs.
  - Veo/video not used. No publishing.

Usage:
  python scripts/flow_cdp_image.py \
    --prompt "simple blue circle on white background" \
    --ratio 16:9 --out /tmp/flow-test/test-photo.png \
    [--ws-port 35029] [--page-id <cdp page id>] [--timeout 120]

Batch mode:
  python scripts/flow_cdp_image.py --prompts-file prompts.json --out-dir work/flow_images

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

    def log_append(self, message: str) -> None:
        line = f"{ts()} {message}"
        self.log.append(line)
        print(line)

    async def connect(self) -> None:
        import websockets  # imported lazily so import without dep is OK

        self.ws = await websockets.connect(self.ws_uri)
        self.log_append(f"CDP connected: {self.ws_uri}")
        for domain in ["Network", "Page", "Input", "Accessibility", "Runtime"]:
            await self._send({"method": f"{domain}.enable"})
            await self._recv_until_id(self._seq)
        await self._send({"method": "Network.setCacheDisabled", "params": {"cacheDisabled": True}})
        await self._recv_until_id(self._seq)

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

    async def eval_js(self, expression: str) -> Any:
        """Evaluate JS in the page context and return the parsed result value.
        Uses awaitPromise: true so async IIFEs resolve before returning."""
        await self._send(
            {
                "method": "Runtime.evaluate",
                "params": {
                    "expression": expression,
                    "returnByValue": True,
                    "awaitPromise": True,
                },
            }
        )
        msg = await self._recv_until_id(self._seq)
        result = msg.get("result", {})
        if "exceptionDetails" in result:
            raise RuntimeError(f"JS error: {result['exceptionDetails']}")
        val = result["result"]
        if val.get("type") == "undefined":
            return None
        v = val.get("value")
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return v
        return v

    async def action_js(self, js_body: str) -> str:
        """Run an IIFE action (may contain return statements) and return its string result."""
        expr = f"(function() {{ {js_body} }})()"
        val = await self.eval_js(expr)
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
        self.log_append(f"screenshot saved: {path} ({len(img_bytes)} bytes) [low_res]")


async def dismiss_dialogs(session: CDPSession) -> None:
    """Dismiss Russian consent/cookie/storage dialogs by button label."""
    labels = ["ОК", "Включить", "Закрыть сообщение", "Закрыть баннер", "Отмена"]
    for label in labels:
        try:
            result = await session.eval_js(
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


async def fetch_fullres(session: CDPSession, src: str) -> dict[str, Any] | None:
    """Download full-resolution image via fetch() in page context (has cookies).
    Returns dict with bytes, size, sha256, or None on failure."""
    result = await session.eval_js(
        f"""
        (async () => {{
            try {{
                const resp = await fetch({json.dumps(src)});
                const ab = await resp.arrayBuffer();
                const uint8 = new Uint8Array(ab);
                const hex = Array.from(uint8).map(b => b.toString(16).padStart(2,'0')).join('');
                return {{status: resp.status, size: ab.byteLength, hex: hex, ct: resp.headers.get('content-type')||''}};
            }} catch(e) {{
                return {{status: 0, error: e.message}};
            }}
        }})()
        """
    )
    if isinstance(result, dict) and result.get("status") == 200 and result.get("hex"):
        img_bytes = bytes.fromhex(result["hex"])
        return {
            "bytes": img_bytes,
            "size": len(img_bytes),
            "sha256": hashlib.sha256(img_bytes).hexdigest(),
            "ct": result.get("ct", ""),
        }
    session.log_append(f"  fetch failed: status={result.get('status') if isinstance(result, dict) else 'N/A'}")
    return None


def pixel_hash(image_bytes: bytes) -> tuple[str, float]:
    """Compute 16x16 MD5 pixel hash and black pixel ratio."""
    from PIL import Image
    import io
    im = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    small = im.resize((16, 16), Image.LANCZOS)
    px_bytes = small.tobytes()
    ph = hashlib.md5(px_bytes).hexdigest()
    pixels = list(small.getdata())
    total = len(pixels)
    black = sum(1 for p in pixels if p[0] < 30 and p[1] < 30 and p[2] < 30)
    black_ratio = black / total if total > 0 else 0
    return ph[:12], round(black_ratio, 4), im.size


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate an image via Google Flow using CDP"
    )
    parser.add_argument("--prompt", default="simple blue circle on white background",
                        help="generation prompt (single mode)")
    parser.add_argument("--prompts-file", default=None,
                        help="JSON file with list of prompts (batch mode, max 12)")
    parser.add_argument("--ratio", default="16:9", help="aspect ratio (16:9, 9:16, 1:1, 4:3, 3:4)")
    parser.add_argument("--out", default="/tmp/flow-test/test-photo.png",
                        help="output image path (single mode)")
    parser.add_argument("--out-dir", default="/tmp/flow-test/batch",
                        help="output directory (batch mode)")
    parser.add_argument("--ws-port", type=int, default=35029, help="CDP websocket port")
    parser.add_argument(
        "--page-id", default="", help="CDP page target id for flow.google.com"
    )
    parser.add_argument(
        "--timeout", type=int, default=120, help="max seconds to wait for image"
    )
    parser.add_argument(
        "--delay", type=int, default=25, help="seconds between batch prompts (20-30)"
    )
    args = parser.parse_args()

    log: list[str] = []

    # Load prompts
    prompts: list[str] = []
    if args.prompts_file:
        with open(args.prompts_file) as f:
            data = json.load(f)
        if isinstance(data, list):
            prompts = [str(p) for p in data[:12]]
        elif isinstance(data, dict) and "prompts" in data:
            prompts = [str(p) for p in data["prompts"][:12]]
        else:
            print("ERROR: prompts-file must contain a list or {prompts: [...]}")
            return 1
        if not prompts:
            print("ERROR: no prompts found in prompts-file")
            return 1
    else:
        prompts = [args.prompt]

    os.makedirs(args.out_dir, exist_ok=True)
    os.makedirs("manifests", exist_ok=True)

    ws_uri = f"ws://127.0.0.1:{args.ws_port}/devtools/page/{args.page_id}"
    session = CDPSession(ws_uri, log)

    try:
        await session.connect()

        # Ensure on flow.google.com
        current_url = await session.eval_js("window.location.href")
        session.log_append(f"current url: {current_url}")
        if "flow.google.com" not in str(current_url):
            await session.eval_js("window.location.href = 'https://flow.google.com'")
            await asyncio.sleep(2)

        manifest_path = "manifests/ai_images.json"
        existing: list[dict[str, Any]] = []
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path) as f:
                    existing = json.load(f).get("images", [])
            except Exception:
                existing = []

        # Track known media IDs BEFORE sending each prompt (to detect NEW ones)
        known_media_ids: set[str] = set()
        # Track known pixel hashes (to detect duplicate images)
        known_phashes: set[str] = set()

        # Load existing manifest to get known media IDs and phashes
        for entry in existing:
            mid = entry.get("asset_id")
            if mid:
                known_media_ids.add(mid)
            ph = entry.get("phash")
            if ph:
                known_phashes.add(ph)

        for idx, prompt in enumerate(prompts):
            session.log_append(f"=== Prompt {idx + 1}/{len(prompts)}: {prompt[:80]} ===")

            # Dismiss consent dialogs
            await dismiss_dialogs(session)
            await asyncio.sleep(1)

            # Click "Новый проект" (New project) only if not already in a project
            session.log_append("checking for new project button")
            has_pb = await session.eval_js(
                "!!document.querySelector('[role=\"textbox\"][contenteditable=\"true\"]')"
            )
            if not has_pb:
                click_result = await session.action_js(
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
            else:
                session.log_append("already in a project, skipping new project click")

            # Wait for prompt box
            session.log_append("waiting for prompt box")
            prompt_found = False
            deadline = asyncio.get_event_loop().time() + 30
            while asyncio.get_event_loop().time() < deadline:
                has_pb = await session.eval_js(
                    "!!document.querySelector('[role=\"textbox\"][contenteditable=\"true\"]')"
                )
                if has_pb:
                    prompt_found = True
                    session.log_append("prompt box found")
                    break
                await asyncio.sleep(2)
            if not prompt_found:
                session.log_append("ERROR: prompt box not found within 30s")
                continue

            # Focus the textbox via DOM click, clear existing text
            session.log_append("focusing and clearing prompt textbox")
            await session.eval_js(
                """
                var pb = document.querySelector('[role="textbox"][contenteditable="true"]');
                pb.focus();
                pb.textContent = '';
                pb.dispatchEvent(new Event('input', {bubbles: true}));
            """
            )
            await asyncio.sleep(0.5)

            # Type the prompt via CDP Input.insertText (NOT JS)
            session.log_append(f"inserting text via CDP: '{prompt}'")
            await session.insert_text(prompt)
            await asyncio.sleep(0.5)

            # Verify text was inserted
            text_check = await session.eval_js(
                "document.querySelector('[role=\"textbox\"][contenteditable=\"true\"]').textContent"
            )
            session.log_append(f"textbox content: {text_check!r}")

            # Screenshot after text input
            await session.screenshot(f"{args.out_dir}/after_input_{idx + 1}.png")

            # Capture existing media IDs BEFORE sending (to detect NEW ones)
            before_ids = await session.eval_js(
                "JSON.stringify(Array.from(document.querySelectorAll('flow-image-tile img[data-media-id], img[data-media-id]')).map(img => img.getAttribute('data-media-id')).filter(Boolean))"
            )
            if not isinstance(before_ids, list):
                before_ids = []
            before_set = set(before_ids)
            session.log_append(f"existing media IDs before send: {len(before_set)}")

            # Press Enter via CDP Input.dispatchKeyEvent (NOT JS click)
            session.log_append("dispatching Enter key via CDP")
            await session.dispatch_key("Enter", "Enter", 13)
            await asyncio.sleep(0.5)

            # Screenshot after submit
            await session.screenshot(f"{args.out_dir}/after_submit_{idx + 1}.png")

            # Wait for NEW images (poll every 5s, up to timeout)
            session.log_append(f"waiting for NEW images (timeout {args.timeout}s)")
            deadline = asyncio.get_event_loop().time() + args.timeout
            new_media_ids: list[str] = []

            while asyncio.get_event_loop().time() < deadline:
                await asyncio.sleep(5)
                current_ids = await session.eval_js(
                    "JSON.stringify(Array.from(document.querySelectorAll('flow-image-tile img[data-media-id], img[data-media-id]')).map(img => img.getAttribute('data-media-id')).filter(Boolean))"
                )
                if not isinstance(current_ids, list):
                    current_ids = []
                current_set = set(current_ids)
                new_ids = current_set - before_set
                if new_ids:
                    new_media_ids = sorted(new_ids)
                    session.log_append(f"NEW media IDs: {new_media_ids}")
                    break
                session.log_append("no new images yet, waiting...")

            # Final screenshot
            await session.screenshot(f"{args.out_dir}/final_{idx + 1}.png")

            # Dump page text for debugging
            body_text = await session.eval_js("document.body.innerText")
            lines = str(body_text).split("\n")
            session.log_append("=== PAGE TEXT (first 50 lines) ===")
            for i, line in enumerate(lines[:50]):
                session.log_append(f"  {i + 1}: {line}")
            session.log_append("=== END PAGE TEXT ===")

            if not new_media_ids:
                session.log_append("ERROR: no NEW images found within timeout")
                continue

            # Get image rects and download NEW images via fetch
            img_rects = await session.eval_js(
                "JSON.stringify(Array.from(document.querySelectorAll('flow-image-tile img[data-media-id], img[data-media-id]')).map(img => { const rect = img.getBoundingClientRect(); return {x: rect.x, y: rect.y, w: rect.width, h: rect.height, src: img.src, mediaId: img.getAttribute('data-media-id')}; }))"
            )
            if not isinstance(img_rects, list) or len(img_rects) == 0:
                session.log_append("ERROR: no image rects found")
                continue

            # Filter to only NEW media IDs
            new_rects = [r for r in img_rects if r.get("mediaId") in new_media_ids]
            session.log_append(f"new rects to process: {len(new_rects)}")

            base_out = os.path.join(args.out_dir, f"img_{idx + 1}")
            downloaded = 0
            attempt = 0

            for rect in new_rects:
                if downloaded >= 2:
                    session.log_append("max 2 images per prompt reached, stopping")
                    break

                src = rect["src"]
                media_id = rect.get("mediaId", f"img_{idx + 1}_{len(new_rects)}")
                session.log_append(f"image mediaId={media_id}, src_prefix={src[:80]}...")

                # Try full-res download via fetch() in page context (has cookies)
                fetched = await fetch_fullres(session, src)

                if not fetched:
                    session.log_append("  full-res fetch failed, skipping")
                    continue

                # Compute pixel hash and check for duplicates
                ph, black_ratio, img_size = pixel_hash(fetched["bytes"])
                session.log_append(f"  phash={ph}, black_ratio={black_ratio}, px={img_size[0]}x{img_size[1]}")

                # Discard black frames
                if black_ratio > 0.5:
                    session.log_append(f"  DISCARDED: black frame (ratio={black_ratio})")
                    continue

                # Check for duplicate pixel hash
                if ph in known_phashes:
                    session.log_append(f"  DISCARDED: duplicate pixel hash (phash={ph})")
                    continue

                # Save as real PNG via PIL (no resize)
                from PIL import Image
                import io
                im = Image.open(io.BytesIO(fetched["bytes"])).convert("RGB")
                out_path = f"{base_out}_{media_id[:8]}.png"
                im.save(out_path, "PNG")
                session.log_append(f"  saved PNG: {out_path} ({im.size[0]}x{im.size[1]}, {len(fetched['bytes'])} bytes)")

                known_phashes.add(ph)
                known_media_ids.add(media_id)
                downloaded += 1

                manifest_entry = {
                    "asset_id": media_id,
                    "prompt": prompt,
                    "model": "Nano Banana 2.1",
                    "source_type": "newly_generated",
                    "asset_origin": "newly_generated",
                    "provider": "google-flow",
                    "file_path": out_path,
                    "file_size_bytes": len(fetched["bytes"]),
                    "sha256": fetched["sha256"],
                    "phash": ph,
                    "display_width": img_size[0],
                    "display_height": img_size[1],
                    "visual_class": "AI_RECONSTRUCTION",
                    "visual_claim": "AI_RECONSTRUCTION",
                    "disclosure_required": True,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "labels": ["AI-generated visualization"],
                }
                existing.append(manifest_entry)

            # Write manifest after each prompt
            with open(manifest_path, "w") as f:
                json.dump(
                    {"generated_at": datetime.now(timezone.utc).isoformat(), "images": existing},
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
            session.log_append(f"manifest written: {manifest_path} ({len(existing)} total entries)")
            session.log_append(f"prompt {idx + 1} done — {downloaded} new unique image(s)")

            # Delay between prompts (20-30s)
            if idx < len(prompts) - 1:
                delay = args.delay
                session.log_append(f"waiting {delay}s before next prompt")
                await asyncio.sleep(delay)

        session.log_append(f"done — {len(existing)} total images in manifest")
        return 0

    finally:
        await session.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
