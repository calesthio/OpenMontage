"""Shared Google service-account authentication for OpenMontage tools.

Lets the Google provider tools (``google_tts``, ``google_imagen``)
authenticate with a service-account JSON key file via OAuth Bearer tokens —
in addition to the existing API-key path. This is what makes
``GOOGLE_APPLICATION_CREDENTIALS`` actually work end to end.

The ``google-auth`` package is imported lazily so this module never adds an
import-time cost for tools that only use API keys, and so a missing dependency
surfaces as an actionable runtime error rather than a hard import failure.
"""

from __future__ import annotations

import os
from typing import Any

# Broad scope that covers Cloud Text-to-Speech and Vertex AI prediction.
CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"

# Shared constants for long-running Google/Vertex AI generation calls (e.g. music, video)
GOOGLE_API_TIMEOUT_SECONDS = 600
GOOGLE_API_TIMEOUT_MS = GOOGLE_API_TIMEOUT_SECONDS * 1000


def service_account_configured() -> bool:
    """True when GOOGLE_APPLICATION_CREDENTIALS points to an existing file."""
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    return bool(path and os.path.exists(path))


def has_google_credentials() -> bool:
    """True when GOOGLE_API_KEY, GEMINI_API_KEY, or service account is configured."""
    return bool(
        os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or service_account_configured()
    )


def get_genai_client(http_options: Any | None = None) -> Any:
    """Lazily import and initialize the Google GenAI Client based on configured credentials."""
    from google import genai

    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    use_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in (
        "true",
        "1",
    ) or os.environ.get("GOOGLE_GENAI_USE_ENTERPRISE", "").lower() in ("true", "1")

    if use_vertex or (not api_key and service_account_configured()):
        kwargs = {
            "vertexai": True,
            "location": os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
            "http_options": http_options,
        }
        project_id = resolve_project_id()
        if project_id:
            kwargs["project"] = project_id
        return genai.Client(**kwargs)
    else:
        if api_key:
            return genai.Client(api_key=api_key, http_options=http_options)
        return genai.Client(http_options=http_options)


def resolve_project_id(creds_project_id: str | None = None) -> str | None:
    """Resolve the GCP project id from env vars, falling back to the key file's.

    Vertex AI needs an explicit project id; TTS does not. We prefer an explicit
    env override so users can target a project other than the key's own.
    """
    return (
        os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("GOOGLE_CLOUD_PROJECT_ID")
        or os.environ.get("GCLOUD_PROJECT")
        or creds_project_id
    )


def get_access_token(scopes: list[str] | None = None) -> tuple[str, str | None]:
    """Mint an OAuth access token from the service-account JSON.

    Returns ``(access_token, project_id)``. ``project_id`` is the one embedded
    in the key file (callers should still prefer :func:`resolve_project_id`).

    Raises:
        RuntimeError: if ``google-auth`` is missing or the credentials cannot
            be loaded/refreshed — with a message the agent can surface verbatim.
    """
    if scopes is None:
        scopes = [CLOUD_PLATFORM_SCOPE]

    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
    except ImportError as exc:  # pragma: no cover - depends on optional dep
        raise RuntimeError(
            "Service-account auth requires the 'google-auth' package. "
            "Install it with: pip install google-auth"
        ) from exc

    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not path or not os.path.exists(path):
        raise RuntimeError(
            "GOOGLE_APPLICATION_CREDENTIALS is not set or points to a missing "
            "file; cannot use service-account authentication."
        )

    try:
        creds = service_account.Credentials.from_service_account_file(
            path, scopes=scopes
        )
        creds.refresh(Request())
    except Exception as exc:  # noqa: BLE001 - re-raised as actionable message
        raise RuntimeError(
            f"Failed to load/refresh service-account credentials from {path}: {exc}"
        ) from exc

    token = creds.token
    if not token or not isinstance(token, str):
        raise RuntimeError(
            "Service-account credentials did not yield a valid access token."
        )

    project_id = getattr(creds, "project_id", None)
    ret_project_id = str(project_id) if project_id is not None else None
    return token, ret_project_id
