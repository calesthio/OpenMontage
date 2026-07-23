"""Callback validation helpers for Kling official providers."""

from __future__ import annotations

from urllib.parse import urlparse


def validate_callback_url(callback_url: str | None) -> str | None:
    """Return a normalized callback URL or raise for obviously invalid input."""

    if not callback_url:
        return None
    value = str(callback_url).strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("callback_url must be an absolute http(s) URL")
    return value
