"""Authentication provider seam.

The default PassphraseAuth matches the v1 team-passphrase cookie. A future
OAuthProvider (GitHub / enterprise SSO) implements the same login()/verify()
contract — no call-site changes (see interfaces/__init__.get_auth_provider).
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any


class AuthProvider(ABC):
    """Abstract authentication provider."""

    name: str = "abstract"

    @abstractmethod
    def login(self, credentials: dict[str, Any]) -> str | None:
        """Validate credentials; return a session token, or None on failure."""

    @abstractmethod
    def verify(self, token: str | None) -> bool:
        """Return True if the session token is valid."""


class PassphraseAuth(AuthProvider):
    """Single shared team passphrase → an opaque 'authenticated' cookie (v1)."""

    name = "passphrase"

    def __init__(self, passphrase: str | None = None) -> None:
        # Falls back to the env var the web login route already uses.
        self._passphrase = passphrase if passphrase is not None else os.environ.get("OM_TEAM_PASSPHRASE", "")
        self._token = "authenticated"

    def login(self, credentials: dict[str, Any]) -> str | None:
        supplied = str(credentials.get("passphrase", ""))
        if self._passphrase and supplied == self._passphrase:
            return self._token
        return None

    def verify(self, token: str | None) -> bool:
        return token == self._token
