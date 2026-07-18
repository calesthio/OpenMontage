"""Shared plumbing for the DolphinLitePark MaaS gateway tools.

maas_tts, maas_video, and maas_image all talk to the same gateway
(https://api.aiapbot.com, overridable via MAAS_API_BASE) using the same
Bearer-token auth (MAAS_API_KEY). _api_key()/_base_url()/get_status() used to
be copy-pasted verbatim across all three — centralized here so a change to
the gateway's auth/base-url convention only needs to happen once.

_poll_job() extends that to the third copy-pasted block: the tolerant
submit→poll loop (deadline + transient-error budget). It deliberately does
NOT unify the tools' PARAMETERS — the 60/300/600s timeouts are
model-specific and doc-cited, and the success-status sets differ — nor their
error messages, which operators read at 2am. It raises typed exceptions so
each tool formats its own ToolResult.
"""

from __future__ import annotations

import os
import time
from typing import Any, Callable

from tools.base_tool import BaseTool, ToolStatus

# Transient poll blips (502/504/reset/timeout) are tolerated because the job
# is already submitted AND BILLED — abandoning a paid generation on the first
# hiccup wastes money. But cap them so a persistently broken poll endpoint
# fails fast instead of spinning to the deadline.
MAX_POLL_ERRORS = 5


class MaasPollError(Exception):
    """Base for poll-loop outcomes that end the job."""


class MaasPollTimeout(MaasPollError):
    """Deadline passed with the job still in a non-terminal state.

    Carries no duration: each caller knows its own timeout constant and
    words the message itself.
    """


class MaasPollUnreachable(MaasPollError):
    """The poll endpoint failed MAX_POLL_ERRORS times in a row."""

    def __init__(self, attempts: int, last_error: Exception):
        super().__init__(f"poll failed {attempts}x (last: {last_error})")
        self.attempts = attempts
        self.last_error = last_error


class MaasJobFailed(MaasPollError):
    """The gateway reported a terminal failure status."""

    def __init__(self, status: str, payload: dict[str, Any]):
        super().__init__(f"job {status}")
        self.status = status
        self.payload = payload


class MaasBaseTool(BaseTool):
    """Common env-based auth/config for DolphinLitePark MaaS gateway tools."""

    # The MaaS gateway bills internally in CNY (see maas_video.py's
    # estimate_cost docstring) — every subclass's cost_usd is deliberately
    # already a CNY amount, not a currency-conversion bug. See BaseTool.
    cost_currency: str = "CNY"

    def _api_key(self) -> str | None:
        return os.environ.get("MAAS_API_KEY")

    def _base_url(self) -> str:
        return os.environ.get("MAAS_API_BASE", "https://api.aiapbot.com").rstrip("/")

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if self._api_key() else ToolStatus.UNAVAILABLE

    @staticmethod
    def _poll_job(
        url: str,
        headers: dict[str, str],
        *,
        deadline: float,
        interval: float,
        success_statuses: tuple[str, ...] = ("succeeded",),
        failure_statuses: tuple[str, ...] = ("failed", "cancelled"),
        request_timeout: int = 15,
        sleep: Callable[[float], None] | None = None,
    ) -> dict[str, Any]:
        """Poll `url` until a terminal status. Returns the final payload.

        Raises MaasPollTimeout / MaasPollUnreachable / MaasJobFailed — the
        caller owns the ToolResult wording (each gateway surface words its
        failures differently, and those strings are what operators read).

        `deadline` is an absolute time.time() value, and `interval`/timeouts
        stay per-call: maas_tts polls a 2-15s model on a 60s budget per its
        documented profile, while video renders for minutes on 600s. Sleeps
        BEFORE the first poll — a job is never ready the instant it is
        submitted, and the tests pin this call order.
        """
        import requests

        _sleep = sleep or time.sleep
        poll_errors = 0
        while time.time() < deadline:
            _sleep(interval)
            try:
                resp = requests.get(url, headers=headers, timeout=request_timeout)
                resp.raise_for_status()
            except Exception as e:  # noqa: BLE001 — any transport blip is transient
                poll_errors += 1
                if poll_errors >= MAX_POLL_ERRORS:
                    raise MaasPollUnreachable(poll_errors, e) from e
                continue  # transient — retry on the next interval
            poll_errors = 0

            payload = resp.json()
            status = payload.get("status", "unknown")
            if status in success_statuses:
                return payload
            if status in failure_statuses:
                raise MaasJobFailed(status, payload)
            # still processing — keep polling

        raise MaasPollTimeout()
