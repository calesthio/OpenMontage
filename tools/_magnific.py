"""Shared client and base tool for the Magnific API (https://api.magnific.com).

Every Magnific AI endpoint follows the same async contract:

    POST <path>            -> {"data": {"task_id": ..., "status": "CREATED"}}
    GET  <status>/<task>   -> {"data": {"task_id": ..., "status": ..., "generated": [url, ...]}}

Status is one of CREATED / IN_PROGRESS / COMPLETED / FAILED. `MagnificTool` owns
submit + poll + download + ToolResult so the six Magnific tools only describe
their endpoint and payload.

Auth is a single ``MAGNIFIC_API_KEY`` sent as the ``x-magnific-api-key`` header.
Docs: https://docs.magnific.com/llms.txt
"""

from __future__ import annotations

import base64
import mimetypes
import os
import threading
import time
from pathlib import Path
from typing import Any, NamedTuple, Optional

from tools.base_tool import (
    BaseTool,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
)

API_BASE = "https://api.magnific.com"
ENV_KEY = "MAGNIFIC_API_KEY"

INSTALL_INSTRUCTIONS = (
    "Set MAGNIFIC_API_KEY to a Magnific API key.\n"
    "  Create one at https://www.magnific.com/user/organization/api-keys\n"
    "  (paid plan required; the key and secret are shown only once.)\n"
    "  Prefer chat-driven use instead? Magnific also runs an official MCP server\n"
    "  at https://mcp.magnific.com which signs in with OAuth and needs no key:\n"
    "    claude mcp add --transport http magnific https://mcp.magnific.com"
)

TERMINAL_OK = "COMPLETED"
TERMINAL_FAIL = "FAILED"

# Base64-inlining a large file bloats the JSON body (1.33x encoded, then copied
# again by json.dumps) and usually times out; a public URL is the documented path.
MAX_INLINE_BYTES = 20 * 1024 * 1024

# Poll cadence: check immediately, then ramp so a 6-second task is not charged a
# flat 5-second floor while a 3-minute video keeps the same steady-state cadence.
_POLL_START = 1.0
_POLL_FACTOR = 1.5
_POLL_CAP = 5.0
_MAX_POLL_ERRORS = 5


class MagnificError(RuntimeError):
    """Raised when the Magnific API rejects a request or a task fails."""


class _FatalPoll(Exception):
    """A 4xx during polling — retrying will not help, so stop immediately."""


class Downloaded(NamedTuple):
    """A saved asset plus the content type the server actually served."""

    path: Path
    content_type: str


def api_key() -> Optional[str]:
    return os.environ.get(ENV_KEY) or None


# Two sessions, deliberately. Both keep connections alive across a generation's
# dozens of polls, but the API key must never leave api.magnific.com: generated
# assets live on a separate CDN host, and requests only strips `Authorization`
# on a cross-host redirect (see SessionRedirectMixin.rebuild_auth) — a custom
# auth header would follow the redirect and leak. `_ASSET_SESSION` carries no
# credentials, matching how every other tool here fetches results.
_API_SESSION: Any = None
_ASSET_SESSION: Any = None
_SESSION_LOCK = threading.Lock()


def _make_session() -> Any:
    import requests

    return requests.Session()


def session() -> Any:
    """Authenticated session for api.magnific.com. Never use it for asset URLs."""
    global _API_SESSION
    key = api_key()
    if not key:
        raise MagnificError(f"{ENV_KEY} not set. {INSTALL_INSTRUCTIONS}")
    with _SESSION_LOCK:
        if _API_SESSION is None:
            _API_SESSION = _make_session()
        _API_SESSION.headers.update(
            {"x-magnific-api-key": key, "Content-Type": "application/json"}
        )
        return _API_SESSION


def asset_session() -> Any:
    """Credential-free session for downloading generated assets from the CDN."""
    global _ASSET_SESSION
    with _SESSION_LOCK:
        if _ASSET_SESSION is None:
            _ASSET_SESSION = _make_session()
        return _ASSET_SESSION


_MEDIA_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff",
    ".mp4", ".mov", ".webm", ".avi", ".mkv",
    ".wav", ".mp3", ".flac", ".ogg", ".m4a",
}


def _looks_like_path(value: str) -> bool:
    """True when a non-existent value was clearly meant to be a file path."""
    return "/" in value or "\\" in value or Path(value).suffix.lower() in _MEDIA_SUFFIXES


def as_input(value: str, *, max_bytes: int = MAX_INLINE_BYTES) -> str:
    """Normalize an image/audio/video input for a Magnific request body.

    Magnific accepts either a public https URL or a raw (unprefixed) base64
    string. A URL is passed through untouched — the docs are explicit that a URL
    preserves more quality than a re-encoded local copy. A local path is read and
    base64-encoded; a ``data:`` URI is stripped down to its payload.

    Raises ValueError for a local file too large to inline.
    """
    if value.startswith(("http://", "https://")):
        return value
    if value.startswith("data:"):
        head, comma, payload = value.partition(",")
        if not comma:
            raise ValueError(f"Malformed data: URI (no comma): {head[:60]}")
        return payload
    path = Path(value)
    if path.is_file():
        size = path.stat().st_size
        if size > max_bytes:
            raise ValueError(
                f"{path.name} is {size / 1e6:.1f} MB — too large to base64-inline. "
                "Upload it and pass a public https URL instead."
            )
        return base64.b64encode(path.read_bytes()).decode("ascii")
    if _looks_like_path(value):
        # Fail here rather than POSTing the literal string and getting back an
        # opaque HTTP 400 from the API.
        raise ValueError(f"File not found: {value}")
    # Already-encoded base64 handed in directly.
    return value


def normalize_ratio(value: Optional[str], allowed: list[str]) -> Optional[str]:
    """Accept a plain "16:9"/"16x9" ratio and resolve it to Magnific's own name.

    The selectors pass `aspect_ratio` as a free-form hint (image_selector.py
    declares it as an untyped string), so a caller routed through one would
    otherwise send "16:9" and get an HTTP 400. Magnific's names all end in
    `_<w>_<h>`, so the mapping is derived from the enum rather than duplicated
    in a table that could drift from it.
    """
    if not value or value in allowed:
        return value
    normalized = value.strip().lower().replace("x", ":").replace("/", ":")
    if ":" not in normalized:
        return value
    w, _, h = normalized.partition(":")
    matches = [name for name in allowed if name.endswith(f"_{w.strip()}_{h.strip()}")]
    return matches[0] if len(matches) == 1 else value


def submit(path: str, payload: dict[str, Any], *, timeout: int = 60) -> str:
    """POST a generation request and return its task_id.

    None values are dropped here so every caller keeps the server-side defaults
    without having to remember a prune step.
    """
    body = {k: v for k, v in payload.items() if v is not None}
    resp = session().post(f"{API_BASE}{path}", json=body, timeout=timeout)
    if resp.status_code >= 400:
        raise MagnificError(f"POST {path} -> HTTP {resp.status_code}: {resp.text[:400]}")
    data = (resp.json() or {}).get("data") or {}
    task_id = data.get("task_id")
    if not task_id:
        raise MagnificError(f"POST {path} returned no task_id: {resp.text[:400]}")
    return task_id


def poll(status_path: str, task_id: str, *, max_wait: float = 900.0) -> list[str]:
    """Poll a task to completion and return its generated asset URLs.

    The generation is already paid for by the time polling starts, so a blip —
    a reset connection, a 5xx from the edge, a truncated body — must not throw
    the task away. Transient failures are tolerated until `_MAX_POLL_ERRORS` of
    them happen back to back, matching `atlas_client.poll`.
    """
    deadline = time.monotonic() + max_wait
    url = f"{API_BASE}{status_path}/{task_id}"
    interval = _POLL_START
    last_status = "UNKNOWN"
    errors = 0
    while True:
        try:
            resp = session().get(url, timeout=30)
            if resp.status_code >= 500:
                raise MagnificError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            if resp.status_code >= 400:
                raise _FatalPoll(
                    f"GET {status_path}/{task_id} -> HTTP {resp.status_code}: {resp.text[:400]}"
                )
            data = (resp.json() or {}).get("data") or {}
        except _FatalPoll as exc:
            raise MagnificError(str(exc)) from None
        except Exception as exc:  # noqa: BLE001 — transient until proven otherwise
            errors += 1
            if errors >= _MAX_POLL_ERRORS:
                raise MagnificError(
                    f"Task {task_id} polling failed {errors}x in a row; "
                    f"the task may still be running. Last error: {exc}"
                ) from exc
            time.sleep(interval)
            interval = min(interval * _POLL_FACTOR, _POLL_CAP)
            continue
        errors = 0
        last_status = data.get("status", "UNKNOWN")
        if last_status == TERMINAL_OK:
            generated = data.get("generated") or []
            if not generated:
                raise MagnificError(f"Task {task_id} completed but returned no assets.")
            return list(generated)
        if last_status == TERMINAL_FAIL:
            raise MagnificError(f"Task {task_id} failed: {data.get('error') or resp.text[:300]}")
        if time.monotonic() + interval >= deadline:
            raise MagnificError(
                f"Task {task_id} timed out after {max_wait:.0f}s (last status: {last_status})."
            )
        time.sleep(interval)
        interval = min(interval * _POLL_FACTOR, _POLL_CAP)


def run(
    path: str,
    payload: dict[str, Any],
    *,
    status_path: Optional[str] = None,
    max_wait: float = 900.0,
) -> list[str]:
    """Submit a task and block until it produces assets.

    ``status_path`` defaults to ``path``; pass it explicitly for the endpoints
    whose GET differs from their POST (e.g. Seedance posts to
    ``/v1/ai/video/seedance-2-pro-720p`` but polls ``/v1/ai/video/seedance-2-pro``).
    """
    return poll(status_path or path, submit(path, payload), max_wait=max_wait)


def suffix_for(content_type: str, default: str = ".bin") -> str:
    """Map a Content-Type to a file suffix, matching _kling/media.py's approach."""
    if not content_type:
        return default
    return mimetypes.guess_extension(content_type.split(";", 1)[0].strip()) or default


def download(url: str, dest: str | Path, *, timeout: int = 300) -> Downloaded:
    """Download a generated asset. Magnific URLs expire ~24h after creation.

    A caller-supplied suffix is authoritative and left alone, matching the rest of
    the repo (`_kling/media.py:output_path_with_suffix`, `seedream_image`,
    `openai_image`). A suffix is only derived when the destination has none. The
    served content type is returned alongside so callers can report the real
    format even when it differs from the extension they chose.
    """
    resp = asset_session().get(url, timeout=timeout)
    resp.raise_for_status()
    content_type = resp.headers.get("Content-Type", "")
    out = Path(dest)
    if not out.suffix:
        out = out.with_suffix(suffix_for(content_type))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(resp.content)
    return Downloaded(out, content_type.split(";", 1)[0].strip())


class MagnificTool(BaseTool):
    """Shared contract for every Magnific-backed tool.

    Abstract (no ``execute``), so ToolRegistry skips it during discovery.
    """

    provider = "magnific"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.ASYNC
    runtime = ToolRuntime.API

    dependencies = ["env:MAGNIFIC_API_KEY", "python:requests"]
    install_instructions = INSTALL_INSTRUCTIONS

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=256, disk_mb=200, network_required=True)
    retry_policy = RetryPolicy(max_retries=2, backoff_seconds=3.0, retryable_errors=["rate_limit", "timeout"])

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if api_key() else ToolStatus.UNAVAILABLE

    def default_output(self) -> str:
        """The schema's advertised output_path, so code and schema cannot drift."""
        return self.input_schema["properties"]["output_path"]["default"]

    def _unconfigured(self) -> ToolResult:
        return ToolResult(success=False, error=f"Magnific not configured. {INSTALL_INSTRUCTIONS}")

    def _max_wait(self, inputs: dict[str, Any]) -> float:
        """Generous ceiling around the tool's own runtime estimate."""
        return self.estimate_runtime(inputs) * 8 + 120

    def _generate(
        self,
        inputs: dict[str, Any],
        endpoint: str,
        payload: dict[str, Any],
        *,
        model: str,
        status_path: Optional[str] = None,
        data_extra: Optional[dict[str, Any]] = None,
        saves: Optional[int] = 1,
    ) -> ToolResult:
        """Submit, poll, download, and build the standard ToolResult.

        ``saves`` caps how many returned assets are written; None writes all of
        them. Extras go alongside the first with a -2, -3 suffix. Returns a
        failed ToolResult rather than raising.
        """
        if not api_key():
            return self._unconfigured()

        start = time.time()
        payload = {**payload, "webhook_url": inputs.get("webhook_url")}
        base = Path(inputs.get("output_path") or self.default_output())
        try:
            urls = run(endpoint, payload, status_path=status_path, max_wait=self._max_wait(inputs))
            saved = self._save(urls if saves is None else urls[:saves], base)
        except Exception as e:
            return ToolResult(success=False, error=f"{self.name} failed: {e}")

        return ToolResult(
            success=True,
            data={
                "provider": "magnific",
                "model": model,
                "source_urls": urls,
                "source_url": urls[0],
                "format": saved[0].content_type,
                "output": str(saved[0].path),
                "output_path": str(saved[0].path),
                "output_paths": [str(d.path) for d in saved],
                **(data_extra or {}),
            },
            artifacts=[str(d.path) for d in saved],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )

    @staticmethod
    def _save(urls: list[str], base: Path) -> list[Downloaded]:
        """Download assets to base (and base-2, base-3, …), in parallel past one."""
        def dest(i: int) -> Path:
            return base if i == 0 else base.with_name(f"{base.stem}-{i + 1}{base.suffix}")

        if len(urls) == 1:
            return [download(urls[0], dest(0))]
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=min(len(urls), 8)) as pool:
            return list(pool.map(lambda iu: download(iu[1], dest(iu[0])), enumerate(urls)))
