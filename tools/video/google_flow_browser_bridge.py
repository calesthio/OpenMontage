"""Local browser bridge for Google Flow.

This module intentionally drives the public Flow web UI through Playwright.
It stores browser session state only in the dedicated local Chrome profile and
does not call private Google endpoints or write browser artifacts into the
OpenMontage project tree.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


DEFAULT_FLOW_URL = "https://labs.google/fx/tools/flow"
DEFAULT_PROFILE_DIR = "~/.openmontage/google-flow-profile"
ALLOWED_FLOW_HOSTS = {"labs.google", "labs.google.com", "flow.google.com"}


_SENSITIVE_PATTERNS = [
    re.compile(r"(?i)\b(cookie|set-cookie|authorization|x-client-data)\s*[:=]\s*[^\n\r,;]+"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"\bya29\.[A-Za-z0-9._-]+"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b(?:SID|HSID|SSID|SAPISID|APISID|__Secure-[A-Za-z0-9_-]+)=[^;\s]+"),
    re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
]


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def redact_text(value: object, *, profile_dir: str | Path | None = None) -> str:
    """Remove auth/session/account material from public errors and metadata."""
    text = str(value)
    for pattern in _SENSITIVE_PATTERNS:
        text = pattern.sub("[REDACTED]", text)

    candidates: list[str] = []
    configured = profile_dir or os.environ.get("GOOGLE_FLOW_BROWSER_PROFILE_DIR") or DEFAULT_PROFILE_DIR
    if configured:
        expanded = str(Path(str(configured)).expanduser())
        candidates.extend({expanded, str(configured), str(Path(expanded).parent)})

    for candidate in sorted({c for c in candidates if c}, key=len, reverse=True):
        text = text.replace(candidate, "[REDACTED_PROFILE_PATH]")
    return text


def redact_payload(value: Any, *, profile_dir: str | Path | None = None) -> Any:
    """Recursively redact values before returning ToolResult data."""
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            key_lower = key_text.lower()
            is_sensitive_key = (
                key_lower in {
                    "cookie",
                    "set-cookie",
                    "authorization",
                    "auth_header",
                    "auth_headers",
                    "token",
                    "access_token",
                    "refresh_token",
                    "id_token",
                    "account",
                    "email",
                    "profile_dir",
                    "profile_path",
                    "browser_profile",
                }
                or key_lower.endswith("_token")
            )
            if is_sensitive_key:
                redacted["redacted_sensitive_field"] = "[REDACTED]"
            else:
                redacted[key_text] = redact_payload(item, profile_dir=profile_dir)
        return redacted
    if isinstance(value, list):
        return [redact_payload(item, profile_dir=profile_dir) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_payload(item, profile_dir=profile_dir) for item in value)
    if isinstance(value, str):
        return redact_text(value, profile_dir=profile_dir)
    return value


@dataclass
class GoogleFlowBridgeError(RuntimeError):
    """Public, categorized bridge failure."""

    message: str
    code: str = "ui_changed"
    retryable: bool = False
    details: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        RuntimeError.__init__(self, self.message)

    def public_message(self, *, profile_dir: str | Path | None = None) -> str:
        return redact_text(self.message, profile_dir=profile_dir)

    def public_details(self, *, profile_dir: str | Path | None = None) -> dict[str, Any]:
        return redact_payload(self.details or {}, profile_dir=profile_dir)


class GoogleFlowBrowserBridge:
    """Small Playwright/CDP wrapper around the Google Flow UI."""

    def __init__(
        self,
        *,
        profile_dir: str | Path | None = None,
        flow_url: str | None = None,
        cdp_url: str | None = None,
        headless: bool | None = None,
        timeout_seconds: int = 900,
    ) -> None:
        self.profile_dir = Path(profile_dir or os.environ.get("GOOGLE_FLOW_BROWSER_PROFILE_DIR") or DEFAULT_PROFILE_DIR).expanduser()
        self.flow_url = self._validate_flow_url(flow_url or os.environ.get("GOOGLE_FLOW_URL") or DEFAULT_FLOW_URL)
        self.cdp_url = self._validate_cdp_url(cdp_url or os.environ.get("GOOGLE_FLOW_CDP_URL") or None)
        self.headless = _env_bool("GOOGLE_FLOW_HEADLESS", False) if headless is None else headless
        self.timeout_seconds = int(timeout_seconds)
        self._playwright: Any = None
        self._context: Any = None
        self._browser: Any = None
        self._owns_context = False

    @staticmethod
    def _validate_flow_url(flow_url: str) -> str:
        parsed = urlparse(flow_url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or host not in ALLOWED_FLOW_HOSTS:
            allowed = ", ".join(sorted(ALLOWED_FLOW_HOSTS))
            raise GoogleFlowBridgeError(
                f"GOOGLE_FLOW_URL must use https and one of these hosts: {allowed}.",
                code="validation",
            )
        return flow_url

    @staticmethod
    def _validate_cdp_url(cdp_url: str | None) -> str | None:
        if not cdp_url:
            return None
        parsed = urlparse(cdp_url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in {"http", "https", "ws", "wss"} or host not in {"localhost", "127.0.0.1", "::1"}:
            raise GoogleFlowBridgeError(
                "GOOGLE_FLOW_CDP_URL must point to a localhost browser debugging endpoint.",
                code="validation",
            )
        return cdp_url

    def close(self) -> None:
        """Close only resources owned by this bridge."""
        if self._context is not None and self._owns_context:
            try:
                self._context.close()
            except Exception:
                pass
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
        self._context = None
        self._browser = None
        self._playwright = None
        self._owns_context = False

    def open_login(self, *, keep_open: bool = True) -> dict[str, Any]:
        page = self._new_page()
        self._goto_flow(page)
        status = self._auth_state(page)
        return redact_payload(
            {
                "flow_url": page.url,
                "authenticated": status["authenticated"],
                "browser_open": keep_open,
                "profile_configured": True,
                "message": "Sign in to Google Flow in the opened browser profile, then rerun check_auth.",
            },
            profile_dir=self.profile_dir,
        )

    def check_auth(self) -> dict[str, Any]:
        page = self._new_page()
        self._goto_flow(page)
        return redact_payload(self._auth_state(page), profile_dir=self.profile_dir)

    def generate_video(
        self,
        *,
        prompt: str,
        output_path: str | Path,
        operation: str = "text_to_video",
        image_paths: list[str | Path] | None = None,
        aspect_ratio: str | None = None,
        duration: str | int | None = None,
        model_variant: str | None = None,
    ) -> dict[str, Any]:
        if not prompt.strip():
            raise GoogleFlowBridgeError("Google Flow prompt is required.", code="validation")

        output = Path(output_path).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)

        normalized_images = [Path(p).expanduser() for p in image_paths or []]
        missing = [str(path) for path in normalized_images if not path.exists()]
        if missing:
            raise GoogleFlowBridgeError(
                f"Reference image file not found: {missing[0]}",
                code="validation",
            )

        page = self._new_page()
        self._goto_flow(page)
        auth = self._auth_state(page)
        if not auth["authenticated"]:
            raise GoogleFlowBridgeError(
                "Google Flow browser session is logged out. Run open_login first.",
                code="logged_out",
            )

        try:
            self._submit_prompt(
                page,
                prompt=prompt,
                operation=operation,
                image_paths=normalized_images,
                aspect_ratio=aspect_ratio,
                duration=duration,
                model_variant=model_variant,
            )
            downloaded = self._wait_for_download(page, output)
        except GoogleFlowBridgeError:
            raise
        except Exception as exc:
            raise GoogleFlowBridgeError(
                f"Google Flow UI automation failed: {redact_text(exc, profile_dir=self.profile_dir)}",
                code="ui_changed",
                retryable=True,
            ) from exc

        return redact_payload(
            {
                "output_path": str(downloaded),
                "source": "google_flow_ui_download",
                "flow_url": page.url,
                "browser_profile": "dedicated_google_flow_profile",
            },
            profile_dir=self.profile_dir,
        )

    def _start_playwright(self) -> Any:
        if self._playwright is not None:
            return self._playwright
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise GoogleFlowBridgeError(
                "Playwright is not installed. Install optional browser dependencies with requirements-browser.txt.",
                code="missing_dependency",
            ) from exc
        self._playwright = sync_playwright().start()
        return self._playwright

    def _ensure_context(self) -> Any:
        if self._context is not None:
            return self._context

        pw = self._start_playwright()
        if self.cdp_url:
            try:
                self._browser = pw.chromium.connect_over_cdp(self.cdp_url)
                if self._browser.contexts:
                    self._context = self._browser.contexts[0]
                    self._owns_context = False
                else:
                    self._context = self._browser.new_context(accept_downloads=True)
                    self._owns_context = True
            except Exception as exc:
                raise GoogleFlowBridgeError(
                    f"Failed to connect to GOOGLE_FLOW_CDP_URL: {redact_text(exc, profile_dir=self.profile_dir)}",
                    code="browser_start_failed",
                    retryable=True,
                ) from exc
        else:
            try:
                self.profile_dir.mkdir(parents=True, exist_ok=True)
                self._context = pw.chromium.launch_persistent_context(
                    str(self.profile_dir),
                    accept_downloads=True,
                    headless=self.headless,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                self._owns_context = True
            except Exception as exc:
                raise GoogleFlowBridgeError(
                    f"Failed to launch dedicated Google Flow browser profile: {redact_text(exc, profile_dir=self.profile_dir)}",
                    code="browser_start_failed",
                    retryable=True,
                ) from exc

        try:
            self._context.set_default_timeout(15_000)
        except Exception:
            pass
        return self._context

    def _new_page(self) -> Any:
        context = self._ensure_context()
        try:
            if context.pages:
                return context.pages[0]
        except Exception:
            pass
        return context.new_page()

    def _goto_flow(self, page: Any) -> None:
        try:
            page.goto(self.flow_url, wait_until="domcontentloaded", timeout=60_000)
        except Exception as exc:
            raise GoogleFlowBridgeError(
                f"Failed to open Google Flow: {redact_text(exc, profile_dir=self.profile_dir)}",
                code="navigation_failed",
                retryable=True,
            ) from exc

    def _auth_state(self, page: Any) -> dict[str, Any]:
        logged_out = False
        try:
            logged_out = "accounts.google." in page.url or "ServiceLogin" in page.url
        except Exception:
            logged_out = False

        sign_in_re = re.compile(r"sign\s*in|log\s*in", re.I)
        for locator_factory in (
            lambda: page.get_by_role("button", name=sign_in_re),
            lambda: page.get_by_role("link", name=sign_in_re),
            lambda: page.get_by_text(sign_in_re),
        ):
            try:
                if locator_factory().first.is_visible(timeout=1000):
                    logged_out = True
                    break
            except Exception:
                continue

        return {
            "authenticated": not logged_out,
            "flow_url": redact_text(page.url, profile_dir=self.profile_dir),
            "auth_mode": "browser_session",
        }

    def _submit_prompt(
        self,
        page: Any,
        *,
        prompt: str,
        operation: str,
        image_paths: list[Path],
        aspect_ratio: str | None,
        duration: str | int | None,
        model_variant: str | None,
    ) -> None:
        if operation == "image_to_video":
            self._upload_images(page, image_paths)

        prompt_box = self._first_visible(
            page,
            [
                lambda: page.get_by_role("textbox", name=re.compile(r"prompt|describe|idea", re.I)),
                lambda: page.locator("textarea"),
                lambda: page.locator('[contenteditable="true"]'),
                lambda: page.locator('input[type="text"]'),
            ],
            description="prompt box",
        )
        try:
            prompt_box.first.fill(prompt)
        except Exception:
            prompt_box.first.click()
            page.keyboard.insert_text(prompt)

        for value in (aspect_ratio, duration, model_variant):
            if value:
                self._click_text_if_available(page, str(value))

        generate_button = self._first_visible(
            page,
            [
                lambda: page.get_by_role("button", name=re.compile(r"generate|create|make", re.I)),
                lambda: page.get_by_text(re.compile(r"generate|create|make video", re.I)),
            ],
            description="generate button",
        )
        generate_button.first.click()

    def _upload_images(self, page: Any, image_paths: list[Path]) -> None:
        if not image_paths:
            raise GoogleFlowBridgeError("image_to_video requires a local image path.", code="validation")

        file_inputs = page.locator('input[type="file"]')
        try:
            if file_inputs.count() == 0:
                self._click_text_if_available(page, "Image")
                file_inputs = page.locator('input[type="file"]')
            file_inputs.first.set_input_files([str(path) for path in image_paths])
        except Exception as exc:
            raise GoogleFlowBridgeError(
                f"Could not upload local image to Google Flow UI: {redact_text(exc, profile_dir=self.profile_dir)}",
                code="ui_changed",
                retryable=True,
            ) from exc

    def _wait_for_download(self, page: Any, output_path: Path) -> Path:
        deadline = time.time() + self.timeout_seconds
        download_re = re.compile(r"download|save", re.I)
        failure_re = re.compile(r"failed|error|try again|unable", re.I)

        while time.time() < deadline:
            try:
                error_text = page.get_by_text(failure_re).first
                if error_text.is_visible(timeout=1000):
                    raise GoogleFlowBridgeError(
                        f"Google Flow reported a generation/download error: {error_text.inner_text(timeout=1000)}",
                        code="download_failed",
                        retryable=True,
                    )
            except GoogleFlowBridgeError:
                raise
            except Exception:
                pass

            try:
                download_button = page.get_by_role("button", name=download_re).first
                if not download_button.is_visible(timeout=1000):
                    download_button = page.get_by_text(download_re).first
                if download_button.is_visible(timeout=1000):
                    try:
                        with page.expect_download(timeout=30_000) as download_info:
                            download_button.click()
                        download = download_info.value
                    except Exception as exc:
                        raise GoogleFlowBridgeError(
                            f"Google Flow download action failed: {redact_text(exc, profile_dir=self.profile_dir)}",
                            code="download_failed",
                            retryable=True,
                        ) from exc
                    download.save_as(str(output_path))
                    return output_path
            except GoogleFlowBridgeError:
                raise
            except Exception:
                pass

            try:
                page.wait_for_timeout(5000)
            except Exception:
                time.sleep(5)

        raise GoogleFlowBridgeError(
            "Timed out waiting for Google Flow to finish generation and expose a download button.",
            code="timeout",
            retryable=True,
        )

    def _first_visible(self, page: Any, factories: list[Any], *, description: str) -> Any:
        last_error: Exception | None = None
        for factory in factories:
            try:
                locator = factory()
                if locator.first.is_visible(timeout=2000):
                    return locator
            except Exception as exc:
                last_error = exc
                continue
        detail = f": {last_error}" if last_error else ""
        raise GoogleFlowBridgeError(
            f"Google Flow UI changed; could not find {description}{redact_text(detail, profile_dir=self.profile_dir)}",
            code="ui_changed",
            retryable=True,
        )

    def _click_text_if_available(self, page: Any, value: str) -> bool:
        escaped = re.escape(value)
        candidates = [
            lambda: page.get_by_role("button", name=re.compile(escaped, re.I)),
            lambda: page.get_by_text(re.compile(escaped, re.I)),
        ]
        for factory in candidates:
            try:
                locator = factory().first
                if locator.is_visible(timeout=1000):
                    locator.click()
                    return True
            except Exception:
                continue
        return False
