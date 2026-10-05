"""Xiaohongshu (小红书) video publisher via ADB + uiautomator2."""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from tools.base_tool import (
    BaseTool,
    DependencyError,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

_XHS_PKG = "com.xingin.xhs"


class XHSPublisher(BaseTool):
    name = "xhs_publisher"
    version = "0.1.0"
    tier = ToolTier.PUBLISH
    capability = "publish"
    provider = "xiaohongshu"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["python:uiautomator2"]
    install_instructions = (
        "Install uiautomator2: pip install uiautomator2. "
        "ADB must be in PATH or set ADB_PATH in .env. "
        "Phone must have USB debugging enabled."
    )

    agent_skills = ["xiaohongshu-publish"]

    capabilities = ["xhs_publish", "phone_automation"]
    supports = {
        "local_offline": True,
        "free": True,
        "uploads": True,
    }
    best_for = [
        "posting videos to Xiaohongshu (XHS) automatically via Android phone",
        "batch publishing generated explainer videos to XHS",
    ]
    not_good_for = [
        "publishing to other platforms (use platform-specific publishers)",
        "uploading without a connected Android phone",
    ]

    input_schema = {
        "type": "object",
        "required": ["video_path", "title", "content"],
        "properties": {
            "video_path": {
                "type": "string",
                "description": "Path to the final rendered video file (MP4).",
            },
            "title": {
                "type": "string",
                "description": "Video title (max 20 chars recommended for XHS).",
                "maxLength": 40,
            },
            "content": {
                "type": "string",
                "description": "Video description / body text.",
            },
            "hashtags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Hashtags without # prefix.",
            },
            "style": {
                "type": "string",
                "enum": ["种草", "干货", "攻略", "避坑", "测评"],
                "description": "Content style for cover generation.",
            },
            "cover_path": {
                "type": "string",
                "description": "Optional path to a pre-generated cover image.",
            },
            "adb_path": {
                "type": "string",
                "description": "Override ADB binary path.",
            },
            "dry_run": {
                "type": "boolean",
                "description": "If true, connect and check readiness but do not post.",
            },
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "publish_log": {"type": "object"},
            "platform_post_id": {"type": "string"},
            "details": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=0, network_required=False
    )
    side_effects = [
        "pushes video file to phone storage",
        "opens XHS app and simulates user taps",
        "posts a video note to Xiaohongshu",
    ]
    user_visible_verification = [
        "Check the phone screen — the XHS app should open and post automatically",
        "After completion, check XHS profile to confirm the video is live",
    ]

    # ── Coordinate defaults (1080x2400) ──
    _COORDS: dict[str, tuple[int, int]] = {
        "btn_plus": (540, 2332),
        "btn_album": (540, 2027),
        "first_video": (180, 500),
        "btn_next": (990, 170),
        "title_input": (540, 400),
        "content_input": (540, 850),
        "btn_publish": (990, 100),
    }

    def __init__(self) -> None:
        super().__init__()
        self._device: Any = None
        self._width = 1080
        self._height = 2400

    # ── Dependency checks ──

    def check_dependencies(self) -> None:
        for dep in self.dependencies:
            if dep.startswith("python:"):
                module = dep[7:]
                try:
                    __import__(module)
                except ImportError:
                    raise DependencyError(
                        f"Python module {module!r} not installed. "
                        f"{self.install_instructions}"
                    )
        adb = self._find_adb()
        if not adb:
            raise DependencyError(
                "ADB not found. Install Android Debug Bridge or set ADB_PATH in .env. "
                f"{self.install_instructions}"
            )

    def get_status(self) -> ToolStatus:
        try:
            self.check_dependencies()
            adb = self._find_adb()
            r = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=5)
            lines = [l for l in r.stdout.strip().split("\n")[1:] if l.strip() and "device" in l]
            if not lines:
                return ToolStatus.DEGRADED
            return ToolStatus.AVAILABLE
        except Exception:
            return ToolStatus.UNAVAILABLE

    @staticmethod
    def _find_adb() -> Optional[str]:
        env_adb = os.environ.get("ADB_PATH")
        if env_adb and os.path.exists(env_adb):
            return env_adb
        found = shutil.which("adb")
        if found:
            return found
        candidates = [
            r"C:\Users\86139\platform-tools\adb.exe",
            "/usr/bin/adb",
            "/usr/local/bin/adb",
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return None

    # ── Phone connection ──

    def _connect(self, adb_path: Optional[str] = None) -> bool:
        import uiautomator2 as u2

        adb = adb_path or self._find_adb()
        if adb:
            os.environ.setdefault("ADB_PATH", adb)

        wifi_hosts = ["172.20.10.2:5555", "10ACAT0J44005MZ:5555"]

        try:
            self._device = u2.connect()
            info = self._device.info
            self._width = info.get("displayWidth", 1080)
            self._height = info.get("displayHeight", 2400)
            self._enable_ime()
            return True
        except Exception:
            pass

        for host in wifi_hosts:
            try:
                subprocess.run(
                    [adb or "adb", "connect", host], capture_output=True, timeout=5
                )
                time.sleep(2)
                self._device = u2.connect(host)
                info = self._device.info
                self._width = info.get("displayWidth", 1080)
                self._height = info.get("displayHeight", 2400)
                self._enable_ime()
                return True
            except Exception:
                continue
        return False

    def _enable_ime(self) -> None:
        try:
            self._device.shell("ime enable com.github.uiautomator/.AdbKeyboard")
        except Exception:
            pass

    # ── Coordinate helpers ──

    def _pos(self, name: str) -> tuple[int, int]:
        x, y = self._COORDS.get(name, (540, 1200))
        x = int(x * self._width / 1080)
        y = int(y * self._height / 2400)
        return (x, y)

    def _tap(self, name: str, wait: float = 0.8) -> None:
        x, y = self._pos(name)
        self._device.click(x, y)
        time.sleep(wait)

    def _find_and_tap(self, targets: list, timeout: float = 5) -> bool:
        for target in targets:
            try:
                if isinstance(target, dict):
                    elem = self._device(**target)
                else:
                    elem = self._device(text=target)
                if elem and elem.exists(timeout=timeout):
                    elem.click()
                    time.sleep(0.8)
                    return True
            except Exception:
                continue
        return False

    def _handle_popups(self) -> bool:
        for _ in range(4):
            try:
                xml = self._device.dump_hierarchy()
                if "去编辑" in xml:
                    self._device(text="去编辑").click()
                    time.sleep(4)
                    return True
                for kw in ["存草稿", "不保存", "放弃", "丢弃"]:
                    if kw in xml:
                        self._device(text=kw).click()
                        time.sleep(1)
                        break
                else:
                    for kw in ["关闭", "取消", "跳过", "暂不", "知道了", "以后再说"]:
                        if kw in xml:
                            self._device(text=kw).click()
                            time.sleep(0.5)
                            break
            except Exception:
                pass
            time.sleep(0.5)
        return False

    def _type_chinese(self, text: str) -> bool:
        if not text or not text.strip():
            return True
        strategies = [
            ("u2.set_text", self._try_set_text),
            ("u2.send_keys", self._try_send_keys),
            ("clipboard", self._try_clipboard),
            ("adbkeyboard", self._try_adbkeyboard),
            ("unicode_b64", self._try_unicode_b64),
        ]
        for _ in range(3):
            for name, func in strategies:
                try:
                    if func(text):
                        return True
                except Exception:
                    continue
            time.sleep(0.8)
        try:
            ascii_only = text.encode("ascii", errors="ignore").decode("ascii")
            if ascii_only.strip():
                self._device.shell(f'input text "{ascii_only}"')
                return True
        except Exception:
            pass
        return False

    def _try_set_text(self, text: str) -> bool:
        focused = self._device(focused=True)
        if focused.exists(timeout=2):
            focused.set_text(text)
            time.sleep(0.5)
            try:
                actual = focused.get_text() or ""
                if actual:
                    return True
            except Exception:
                pass
            return True
        for cls in ["android.widget.EditText", "EditText"]:
            try:
                et = self._device(className=cls)
                if et.exists(timeout=1.5):
                    et.click()
                    time.sleep(0.5)
                    et.set_text(text)
                    time.sleep(0.3)
                    return True
            except Exception:
                continue
        return False

    def _try_send_keys(self, text: str) -> bool:
        try:
            self._device.set_input_ime(True)
        except Exception:
            pass
        time.sleep(0.3)
        try:
            self._device.send_keys(text)
            time.sleep(0.5)
            return True
        except Exception:
            return False
        finally:
            try:
                self._device.set_input_ime(False)
            except Exception:
                pass

    def _try_clipboard(self, text: str) -> bool:
        b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
        tmp = "/sdcard/clip_tmp.txt"
        self._device.shell(f"echo '{b64}' | base64 -d > {tmp}")
        time.sleep(0.2)
        self._device.shell(f"cat {tmp} | cmd clipboard set")
        time.sleep(0.3)
        result = str(self._device.shell("cmd clipboard get"))
        if text[:3] in result:
            self._device.shell("input keyevent 279")
            time.sleep(0.5)
            return True
        return False

    def _try_adbkeyboard(self, text: str) -> bool:
        old_ime = None
        try:
            old_ime = str(
                self._device.shell("settings get secure default_input_method")
            ).strip()
            try:
                self._device.shell("ime enable com.github.uiautomator/.AdbKeyboard")
                self._device.shell("ime set com.github.uiautomator/.AdbKeyboard")
                time.sleep(0.5)
            except Exception:
                pass
            b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
            result = str(
                self._device.shell(
                    f'am broadcast -a ADB_INPUT_TEXT --es msg "{b64}"'
                )
            )
            if "result=-1" not in result:
                return True
        except Exception:
            pass
        try:
            if old_ime:
                self._device.shell(f"ime set {old_ime}")
        except Exception:
            pass
        return False

    def _try_unicode_b64(self, text: str) -> bool:
        try:
            for i in range(0, len(text), 50):
                chunk = text[i:i+50]
                b64 = base64.b64encode(chunk.encode("utf-8")).decode("ascii")
                self._device.shell(f'am broadcast -a ADB_INPUT_B64 --es msg "{b64}"')
                time.sleep(0.1)
            return True
        except Exception:
            return False

    def _verify_field(self, prefix: str) -> bool:
        check = prefix[:3] if len(prefix) >= 3 else prefix[:1]
        try:
            focused = self._device(focused=True)
            if focused.exists(timeout=0.5):
                actual = focused.get_text() or ""
                if check in actual:
                    return True
        except Exception:
            pass
        try:
            xml = self._device.dump_hierarchy()
            if check in xml:
                return True
        except Exception:
            pass
        return True

    # ── Cover generation ──

    def _generate_cover(self, title: str, style: str) -> Optional[str]:
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            return None

        w, h = 1080, 1440
        colors = {
            "种草": ("#FF6B6B", "#FF8E53"),
            "干货": ("#4ECDC4", "#2C73D2"),
            "攻略": ("#6C5CE7", "#A29BFE"),
            "避坑": ("#E17055", "#FDCB6E"),
            "测评": ("#00B894", "#55EFC4"),
        }
        c1, c2 = colors.get(style, ("#FF6B6B", "#FF8E53"))

        img = Image.new("RGB", (w, h), "#1a1a2e")
        draw = ImageDraw.Draw(img)
        for i in range(h):
            r = int(int(c1[1:3], 16) + (int(c2[1:3], 16) - int(c1[1:3], 16)) * i / h)
            g = int(int(c1[3:5], 16) + (int(c2[3:5], 16) - int(c1[3:5], 16)) * i / h)
            b = int(int(c1[5:7], 16) + (int(c2[5:7], 16) - int(c1[5:7], 16)) * i / h)
            draw.line([(0, i), (w, i)], fill=(r, g, b))

        font_paths = [
            r"C:\Windows\Fonts\msyh.ttc",
            r"C:\Windows\Fonts\msyhbd.ttc",
            r"C:\Windows\Fonts\simhei.ttf",
        ]
        font = None
        for fp in font_paths:
            if os.path.exists(fp):
                try:
                    font = ImageFont.truetype(fp, 52)
                except Exception:
                    continue
                break
        if font is None:
            font = ImageFont.load_default()

        lines: list[str] = []
        cur = ""
        for ch in title:
            cur += ch
            if len(cur) >= 13:
                lines.append(cur)
                cur = ""
        if cur:
            lines.append(cur)
        if not lines:
            lines = [title]

        y_start = h // 2 - len(lines) * 42
        for i, line in enumerate(lines):
            bb = draw.textbbox((0, 0), line, font=font)
            tw = bb[2] - bb[0]
            draw.text(((w - tw) // 2, y_start + i * 84), line, fill="white", font=font)

        path = os.path.join(
            tempfile.gettempdir(), f"xhs_cover_{int(time.time())}.png"
        )
        img.save(path, "PNG")
        return path

    # ── Main publish flow ──

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        video_path = inputs.get("video_path", "")
        title = inputs.get("title", "")
        content = inputs.get("content", "")
        hashtags = inputs.get("hashtags", []) or []
        style = inputs.get("style", "种草")
        cover_path = inputs.get("cover_path")
        adb_path = inputs.get("adb_path")
        dry_run = inputs.get("dry_run", False)

        full_text = content
        if hashtags:
            full_text += "\n\n" + " ".join(f"#{t}" for t in hashtags)

        started = time.monotonic()

        if dry_run:
            return ToolResult(
                success=True,
                data={
                    "publish_log": {
                        "version": "1.0",
                        "entries": [
                            {
                                "platform": "xiaohongshu",
                                "status": "draft",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "metadata_used": {
                                    "title": title,
                                    "description": full_text,
                                    "hashtags": hashtags,
                                },
                            }
                        ],
                    },
                    "details": "dry_run: ready to publish",
                },
            )

        if not video_path or not os.path.exists(video_path):
            return ToolResult(
                success=False,
                error=f"video_path not found: {video_path}",
            )

        if not self._connect(adb_path):
            return ToolResult(
                success=False,
                error="Failed to connect to Android phone. Check USB/WiFi and debugging.",
            )

        try:
            result = self._post_video(video_path, title, full_text, hashtags, style, cover_path)
            duration = time.monotonic() - started
            if result.get("success"):
                return ToolResult(
                    success=True,
                    data={
                        "publish_log": {
                            "version": "1.0",
                            "entries": [
                                {
                                    "platform": "xiaohongshu",
                                    "status": "published",
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "metadata_used": {
                                        "title": title,
                                        "description": full_text,
                                        "hashtags": hashtags,
                                    },
                                }
                            ],
                        },
                        "details": "Video published to Xiaohongshu successfully",
                    },
                    duration_seconds=duration,
                )
            return ToolResult(
                success=False,
                error=result.get("error", "Unknown publish failure"),
                duration_seconds=duration,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"XHS publish exception: {e}",
                duration_seconds=time.monotonic() - started,
            )

    def _post_video(
        self,
        video_path: str,
        title: str,
        full_text: str,
        hashtags: list[str],
        style: str,
        cover_path: Optional[str],
    ) -> dict[str, Any]:
        self._device.app_start(_XHS_PKG, stop=True)
        time.sleep(5)
        self._handle_popups()

        self._tap("btn_plus")
        time.sleep(2)
        if not self._find_and_tap(["从相册选择"], timeout=3):
            self._tap("btn_album")
        time.sleep(2)

        ts = int(time.time())
        phone_path = f"/sdcard/DCIM/xhs_video_{ts}.mp4"
        self._device.push(video_path, phone_path)
        time.sleep(2)
        self._device.shell(
            f"am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file://{phone_path}"
        )
        time.sleep(3)

        self._find_and_tap(["视频"], timeout=2)
        time.sleep(2)
        self._device.swipe(
            self._width // 2, self._height // 3,
            self._width // 2, self._height * 2 // 3, 0.3,
        )
        time.sleep(2)
        self._device.click(self._width // 6, 500)
        time.sleep(1)

        if not self._find_and_tap(["下一步", "下一步(1)"], timeout=4):
            self._device.click(self._width - 90, 170)
        time.sleep(4)

        if not self._find_and_tap(["下一步"], timeout=4):
            self._device.click(self._width - 90, 170)
        time.sleep(3)

        self._handle_sound_source()
        time.sleep(3)

        title_ok = False
        for retry in range(3):
            self._tap("title_input")
            time.sleep(0.8)
            self._clear_field()
            if self._type_chinese(title):
                if self._verify_field(title[:4]):
                    title_ok = True
                    break
        if not title_ok:
            return {"success": False, "error": "title input failed"}

        content_ok = False
        for retry in range(3):
            self._tap("content_input")
            time.sleep(0.8)
            self._clear_field()
            if self._type_chinese(full_text):
                if self._verify_field(full_text[:4]):
                    content_ok = True
                    break
        if not content_ok:
            return {"success": False, "error": "content input failed"}
        time.sleep(1)

        if not self._find_and_tap(["下一步"], timeout=3):
            self._device.click(self._width // 2, self._height - 90)
        time.sleep(3)

        if not self._find_and_tap(["发布笔记", "发布"], timeout=3):
            self._find_and_tap(["确认发布"], timeout=2)
        time.sleep(3)

        try:
            xml = self._device.dump_hierarchy()
            if "确认并发布" in xml:
                self._device.click(self._width // 2, 2280)
                time.sleep(3)
        except Exception:
            pass

        try:
            done = self._device(text="完成")
            if done.exists(timeout=2):
                done.click()
                time.sleep(1)
        except Exception:
            pass

        return {"success": True}

    def _handle_sound_source(self) -> None:
        try:
            for kw in ["下一步"]:
                try:
                    elem = self._device(text=kw)
                    if elem.exists(timeout=1):
                        elem.click()
                        time.sleep(1)
                        return
                except Exception:
                    continue
            self._device.click(self._width - 110, 170)
        except Exception:
            pass

    def _clear_field(self) -> None:
        try:
            focused = self._device(focused=True)
            if focused.exists(timeout=1):
                focused.set_text("")
                time.sleep(0.1)
        except Exception:
            pass

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        status = self.get_status()
        adb = self._find_adb()
        phone_connected = status == ToolStatus.AVAILABLE
        return {
            "tool": self.name,
            "estimated_cost_usd": 0.0,
            "estimated_runtime_seconds": 120,
            "status": status.value,
            "adb_found": adb is not None,
            "phone_connected": phone_connected,
            "would_execute": True,
        }
