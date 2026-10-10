"""HTTP primitives for media adapters. Never retry a paid submission automatically."""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from urllib.parse import urlparse

import requests


def request_json(method, url, *, headers=None, **kwargs):
    response = requests.request(method, url, headers=headers, timeout=60, **kwargs)
    response.raise_for_status()
    return response.json()


def download(url: str, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if url.startswith("data:"):
        head, body = url.split(",", 1)
        if ";base64" not in head:
            raise ValueError("Only base64 media data URIs are supported")
        content = base64.b64decode(body, validate=True)
    else:
        if urlparse(url).scheme != "https":
            raise ValueError("Media output must be an HTTPS URL or base64 data URI")
        response = requests.get(url, timeout=120)
        response.raise_for_status()
        content = response.content
    if not content:
        raise ValueError("Provider returned empty media")
    temp = path.with_name(path.name + ".part")
    temp.write_bytes(content)
    temp.replace(path)
    return str(path)


def save_job(path, data):
    if path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".part")
        temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temporary.replace(target)


def poll(fetch, *, timeout=600, interval=2):
    if timeout <= 0 or interval <= 0:
        raise ValueError("poll_timeout and poll_interval must be positive")
    deadline = time.monotonic() + timeout
    while True:
        result = fetch()
        state = str(result.get("status", "")).lower()
        if state in {"completed", "succeeded", "success"}:
            return result
        if state in {"failed", "cancelled", "canceled", "error"}:
            raise RuntimeError(
                f"Provider job {state}: {result.get('error', 'no detail')}"
            )
        if time.monotonic() >= deadline:
            raise TimeoutError(
                "Job is still pending; resume with the returned job metadata, do not resubmit"
            )
        time.sleep(min(interval, max(0, deadline - time.monotonic())))
