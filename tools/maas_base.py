"""Shared plumbing for the DolphinLitePark MaaS gateway tools.

maas_tts, maas_video, and maas_image all talk to the same gateway
(https://api.aiapbot.com, overridable via MAAS_API_BASE) using the same
Bearer-token auth (MAAS_API_KEY). _api_key()/_base_url()/get_status() used to
be copy-pasted verbatim across all three — centralized here so a change to
the gateway's auth/base-url convention only needs to happen once.
"""

from __future__ import annotations

import os

from tools.base_tool import BaseTool, ToolStatus


class MaasBaseTool(BaseTool):
    """Common env-based auth/config for DolphinLitePark MaaS gateway tools."""

    def _api_key(self) -> str | None:
        return os.environ.get("MAAS_API_KEY")

    def _base_url(self) -> str:
        return os.environ.get("MAAS_API_BASE", "https://api.aiapbot.com").rstrip("/")

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if self._api_key() else ToolStatus.UNAVAILABLE
