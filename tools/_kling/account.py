"""Account usage diagnostics for Kling official API.

This module is a low-frequency helper, not an OpenMontage registry tool.
"""

from __future__ import annotations

import time
from hashlib import sha256
from typing import Any

from .client import KlingClient
from .errors import KlingAPIError

_CACHE: dict[tuple[tuple[str, str], ...], dict[str, Any]] = {}
_LAST_QUERY_AT = 0.0


def reset_account_usage_cache() -> None:
    """Clear in-process account usage cache. Intended for tests."""

    global _LAST_QUERY_AT
    _CACHE.clear()
    _LAST_QUERY_AT = 0.0


def get_account_costs(
    *,
    start_time: str | None = None,
    end_time: str | None = None,
    resource_pack_name: str | None = None,
    client: KlingClient | None = None,
    ttl_seconds: float = 300.0,
    min_interval_seconds: float = 10.0,
    now: float | None = None,
) -> dict[str, Any]:
    """Read `/account/costs` with in-process cache and throttle protection."""

    global _LAST_QUERY_AT

    timestamp = time.time() if now is None else now
    params = {
        key: value
        for key, value in {
            "start_time": start_time,
            "end_time": end_time,
            "resource_pack_name": resource_pack_name,
        }.items()
        if value
    }
    api = client or KlingClient()
    key = _cache_key(api, params)
    cached = _CACHE.get(key)
    if cached and timestamp - float(cached["fetched_at"]) <= ttl_seconds:
        return {**cached["payload"], "cached": True, "throttle_status": "cache_hit"}

    if _LAST_QUERY_AT and timestamp - _LAST_QUERY_AT < min_interval_seconds:
        if cached:
            return {**cached["payload"], "cached": True, "throttle_status": "throttled_cache"}
        return {
            "provider": "kling_official",
            "queried_range": {
                "start_time": start_time,
                "end_time": end_time,
                "resource_pack_name": resource_pack_name,
            },
            "cached": False,
            "throttle_status": "throttled_no_cache",
            "message": "Account Usage is rate-limited; retry after the local throttle window.",
        }

    raw = api.get("/account/costs", params=params)
    data = raw.get("data") if isinstance(raw, dict) else {}
    if not isinstance(data, dict):
        data = {}
    payload = {
        "provider": "kling_official",
        "queried_range": {
            "start_time": start_time,
            "end_time": end_time,
            "resource_pack_name": resource_pack_name,
        },
        "resource_pack_subscribe_infos": data.get("resource_pack_subscribe_infos", []),
        "raw": raw,
        "cached": False,
        "throttle_status": "fresh",
    }
    _CACHE[key] = {"fetched_at": timestamp, "payload": payload}
    _LAST_QUERY_AT = timestamp
    return payload


def _cache_key(client: Any, params: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    """Scope Account Usage cache by request params and account endpoint identity."""

    api_key = getattr(client, "api_key", None) or ""
    api_key_hash = sha256(str(api_key).encode("utf-8")).hexdigest() if api_key else ""
    scope = {
        "base_url": getattr(client, "base_url", ""),
        "api_key_sha256": api_key_hash,
        **{name: str(value) for name, value in params.items()},
    }
    return tuple(sorted((name, str(value)) for name, value in scope.items()))


def account_usage_hint_for_error(error: KlingAPIError) -> dict[str, Any]:
    """Return a diagnostic hint for balance/resource-pack related errors."""

    code = str(error.code) if error.code is not None else ""
    if code not in {"1101", "1102"}:
        return {}
    return {
        "provider": "kling_official",
        "reason": "account_balance_or_resource_pack",
        "message": (
            "Kling returned an account/resource-pack error. Use tools._kling.account.get_account_costs() "
            "for a low-frequency account usage diagnostic, or check the Kling Open Platform console."
        ),
        "error_code": error.code,
        "request_id": error.request_id,
    }
