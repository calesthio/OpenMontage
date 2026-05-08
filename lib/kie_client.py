"""Shared KIE.AI HTTP client.

Used by tools/graphics/kie_*.py and tools/video/kie_*.py.

Reference: ~/.claude/projects/-Users-abalioglu/memory/reference_kieai_models.md
- Pattern A (Unified Market API): POST /api/v1/jobs/createTask + GET /api/v1/jobs/recordInfo
- Pattern B (Dedicated APIs): each model family has its own create+query endpoints

This client implements Pattern A (covers ~80% of the catalog) plus thin helpers
for the dedicated endpoints we use (Veo, 4o Image).

Auth: `Authorization: Bearer <KIE_AI_API_KEY>`
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests


KIE_BASE = "https://api.kie.ai/api/v1"
KIE_FILE_BASE = "https://kieai.redpandaai.co/api"


class KIEError(RuntimeError):
    """Raised on KIE API errors."""


def get_api_key() -> str | None:
    return os.environ.get("KIE_AI_API_KEY") or os.environ.get("KIEAI_API_KEY")


def is_configured() -> bool:
    return bool(get_api_key())


def _headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    api_key = get_api_key()
    if not api_key:
        raise KIEError("KIE_AI_API_KEY not set")
    h = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


# ── Pattern A: Unified Market API ────────────────────────────────────────


def create_task(model: str, input_payload: dict[str, Any], *, timeout: int = 30) -> str:
    """POST /api/v1/jobs/createTask — returns taskId.

    `model` is the KIE model identifier, e.g.:
      - "google/nano-banana"
      - "nano-banana-2"
      - "openai/gpt-image-2"
      - "bytedance/seedance-2-fast"
      - "kling-2.6/image-to-video"
      - "kling-3.0/video"
    """
    body = {"model": model, "input": input_payload}
    r = requests.post(f"{KIE_BASE}/jobs/createTask", json=body, headers=_headers(), timeout=timeout)
    if r.status_code >= 400:
        raise KIEError(f"createTask {r.status_code}: {r.text[:500]}")
    j = r.json()
    if not j.get("data") and not j.get("taskId"):
        raise KIEError(f"createTask response missing taskId: {j}")
    return j.get("data", {}).get("taskId") or j.get("taskId")


def poll_record(task_id: str, *, timeout: int = 30) -> dict[str, Any]:
    """GET /api/v1/jobs/recordInfo?taskId=… — returns the record dict.

    States: waiting → queuing → generating → success | fail
    """
    r = requests.get(
        f"{KIE_BASE}/jobs/recordInfo",
        params={"taskId": task_id},
        headers=_headers(),
        timeout=timeout,
    )
    if r.status_code >= 400:
        raise KIEError(f"recordInfo {r.status_code}: {r.text[:500]}")
    j = r.json()
    return j.get("data") or j


def wait_for_completion(
    task_id: str,
    *,
    poll_interval_s: float = 4.0,
    max_wait_s: float = 600.0,
) -> dict[str, Any]:
    """Block until task is `success` or `fail`. Returns the final record.

    Raises KIEError on `fail` or timeout.
    """
    deadline = time.time() + max_wait_s
    while time.time() < deadline:
        rec = poll_record(task_id)
        state = (rec.get("state") or rec.get("status") or "").lower()
        if state == "success":
            return rec
        if state == "fail" or state == "failed":
            err = rec.get("failMsg") or rec.get("error") or rec.get("message") or "unknown"
            raise KIEError(f"task {task_id} failed: {err}")
        time.sleep(poll_interval_s)
    raise KIEError(f"task {task_id} timed out after {max_wait_s}s")


def run_unified(model: str, input_payload: dict[str, Any], **wait_kwargs) -> dict[str, Any]:
    """Convenience: createTask + wait_for_completion in one call.

    Returns the final record dict; result URLs/data are typically inside
    `record["resultUrls"]`, `record["output"]`, or `record["data"]` —
    structure varies by model family. Caller should know what to extract.
    """
    task_id = create_task(model, input_payload)
    return wait_for_completion(task_id, **wait_kwargs)


# ── Pattern B: Dedicated 4o Image API (alternative GPT image entry) ──────


def gpt4o_image_generate(prompt: str, *, n: int = 1, size: str = "1024x1024", **extra) -> str:
    """POST /api/v1/gpt4o-image/generate — alternative to Pattern-A `openai/gpt-image-2`.

    Returns taskId.
    """
    body = {"prompt": prompt, "n": n, "size": size, **extra}
    r = requests.post(
        f"{KIE_BASE}/gpt4o-image/generate",
        json=body,
        headers=_headers(),
        timeout=30,
    )
    if r.status_code >= 400:
        raise KIEError(f"gpt4o-image/generate {r.status_code}: {r.text[:500]}")
    j = r.json()
    return j.get("data", {}).get("taskId") or j.get("taskId")


def gpt4o_image_record(task_id: str) -> dict[str, Any]:
    r = requests.get(
        f"{KIE_BASE}/gpt4o-image/record-info",
        params={"taskId": task_id},
        headers=_headers(),
        timeout=30,
    )
    if r.status_code >= 400:
        raise KIEError(f"gpt4o-image/record-info {r.status_code}: {r.text[:500]}")
    return r.json().get("data") or r.json()


# ── Helpers: download artifact + upload local file ────────────────────────


def download_to(url: str, dest: Path, *, timeout: int = 120) -> Path:
    """Stream-download a result URL to local disk."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=timeout) as r:
        if r.status_code >= 400:
            raise KIEError(f"download {url} → {r.status_code}")
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=64 * 1024):
                if chunk:
                    f.write(chunk)
    return dest


def upload_file_url(url: str, *, timeout: int = 60) -> str:
    """POST kieai.redpandaai.co/api/file-url-upload — returns hosted URL.

    Useful when KIE expects a public URL but you have a local file already
    uploaded somewhere (S3/R2/etc). For raw local files use `upload_file_stream`.
    """
    r = requests.post(
        f"{KIE_FILE_BASE}/file-url-upload",
        json={"url": url},
        headers=_headers(),
        timeout=timeout,
    )
    if r.status_code >= 400:
        raise KIEError(f"file-url-upload {r.status_code}: {r.text[:500]}")
    j = r.json()
    return j.get("data", {}).get("url") or j.get("url")


def upload_file_stream(path: str | Path, *, timeout: int = 300) -> str:
    """POST kieai.redpandaai.co/api/file-stream-upload — multipart, returns hosted URL.

    Max 100MB. Files are kept for 3 days.
    """
    path = Path(path)
    if not path.exists():
        raise KIEError(f"local file not found: {path}")
    api_key = get_api_key()
    if not api_key:
        raise KIEError("KIE_AI_API_KEY not set")
    with open(path, "rb") as f:
        r = requests.post(
            f"{KIE_FILE_BASE}/file-stream-upload",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (path.name, f)},
            timeout=timeout,
        )
    if r.status_code >= 400:
        raise KIEError(f"file-stream-upload {r.status_code}: {r.text[:500]}")
    j = r.json()
    return j.get("data", {}).get("url") or j.get("url")


def maybe_upload(path_or_url: str) -> str:
    """If `path_or_url` is a URL, return as-is. If it's a local path, upload + return hosted URL."""
    parsed = urlparse(path_or_url)
    if parsed.scheme in ("http", "https"):
        return path_or_url
    return upload_file_stream(path_or_url)


# ── Result extraction (varies by model family) ───────────────────────────


def extract_result_urls(record: dict[str, Any]) -> list[str]:
    """Extract result URLs from a completed KIE record.

    KIE puts artifacts under different keys depending on the model family:
    - Most unified-API models (nano-banana, seedance, kling, etc.) return them
      inside `resultJson` as a JSON-encoded STRING containing `{"resultUrls": [...]}`.
    - Some return `resultUrls` directly at the top level.
    - Some put them under `output` / `data` / `urls`.

    This function tries all known shapes.
    """
    import json as _json

    # 1. resultJson — JSON-encoded string (most common for unified API)
    rj = record.get("resultJson")
    if isinstance(rj, str) and rj.strip():
        try:
            parsed = _json.loads(rj)
            if isinstance(parsed, dict):
                for key in ("resultUrls", "result_urls", "urls", "image_urls", "video_urls", "output_urls"):
                    v = parsed.get(key)
                    if v:
                        return [str(u) for u in (v if isinstance(v, list) else [v]) if u]
        except _json.JSONDecodeError:
            pass
    elif isinstance(rj, dict):
        # already-parsed shape
        for key in ("resultUrls", "result_urls", "urls", "image_urls", "video_urls", "output_urls"):
            v = rj.get(key)
            if v:
                return [str(u) for u in (v if isinstance(v, list) else [v]) if u]

    # 2. Top-level fields
    for key in ("resultUrls", "result_urls", "outputUrls", "output_urls", "urls"):
        v = record.get(key)
        if v:
            return [str(u) for u in (v if isinstance(v, list) else [v]) if u]

    # 3. Nested 'output' or 'data'
    nested = record.get("output") or record.get("data") or {}
    if isinstance(nested, dict):
        for key in ("urls", "result_urls", "resultUrls", "image_urls", "video_urls"):
            v = nested.get(key)
            if v:
                return [str(u) for u in (v if isinstance(v, list) else [v]) if u]
    elif isinstance(nested, list):
        return [str(u) for u in nested if u]

    return []
