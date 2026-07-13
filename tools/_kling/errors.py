"""Error types and retry policy for Kling official API calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class KlingAPIError(Exception):
    """Structured error returned by the Kling official API."""

    message: str
    code: str | int | None = None
    request_id: str | None = None
    http_status: int | None = None
    response: dict[str, Any] | None = None

    def __str__(self) -> str:
        parts = [self.message]
        if self.code is not None:
            parts.append(f"code={self.code}")
        if self.request_id:
            parts.append(f"request_id={self.request_id}")
        if self.http_status is not None:
            parts.append(f"http_status={self.http_status}")
        return " | ".join(parts)


_RETRYABLE_CODES = {"1302", "1303", "5000", "5001", "5002"}
_RETRYABLE_HTTP = {500, 503, 504}


def _code_str(code: str | int | None) -> str | None:
    if code is None:
        return None
    return str(code)


def is_retryable_kling_error(error: KlingAPIError) -> bool:
    """Return whether an official Kling error is safe for limited retry."""

    code = _code_str(error.code)
    if code in _RETRYABLE_CODES:
        return True
    return error.http_status in _RETRYABLE_HTTP
