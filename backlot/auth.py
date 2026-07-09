"""Small auth layer for the hosted Backlot app.

The preferred path is iKawn OS OAuth. The session cookie held by this app is
local to ikawn-ray.fly.dev and only proves that a user completed the iKawn OS
OAuth flow.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests
from fastapi import Request
from fastapi.responses import RedirectResponse, Response


SESSION_COOKIE = "ikawn_ray_session"
OAUTH_STATE_COOKIE = "ikawn_ray_oauth"
MCP_OAUTH_STATE_COOKIE = "ikawn_ray_mcp_oauth"
DEFAULT_SESSION_SECONDS = 12 * 60 * 60


def _env_int(name: str, default: int, *, minimum: int = 60) -> int:
    try:
        return max(minimum, int(os.environ.get(name) or default))
    except (TypeError, ValueError):
        return default


MCP_TOKEN_SECONDS = _env_int("RAY_MCP_TOKEN_SECONDS", 30 * 24 * 60 * 60)
MCP_REFRESH_TOKEN_SECONDS = _env_int("RAY_MCP_REFRESH_TOKEN_SECONDS", 90 * 24 * 60 * 60)

PUBLIC_PATH_PREFIXES = (
    "/.well-known/",
    "/api/health",
    "/auth/",
    "/oauth/",
    "/ui/",
)
PUBLIC_PATHS = {
    "/auth",
    "/favicon.ico",
    "/mcp",
}


def auth_enabled() -> bool:
    return os.environ.get("RAY_AUTH_DISABLED", "").lower() not in {"1", "true", "yes"}


def public_base_url(request: Request) -> str:
    configured = os.environ.get("RAY_PUBLIC_URL")
    if configured:
        return configured.rstrip("/")
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", "localhost"))
    return f"{proto}://{host}".rstrip("/")


def os_base_url() -> str:
    return os.environ.get("IKAWN_OS_BASE_URL", "https://os.ikawn.com").rstrip("/")


def _secret() -> bytes:
    value = os.environ.get("RAY_SESSION_SECRET")
    if not value:
        value = "dev-only-ray-session-secret-change-me"
    return value.encode("utf-8")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def sign_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    body = _b64(raw)
    sig = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64(sig)}"


def unsign_payload(value: str | None) -> dict[str, Any] | None:
    if not value or "." not in value:
        return None
    body, sig = value.rsplit(".", 1)
    expected = _b64(hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        payload = json.loads(_unb64(body))
    except Exception:
        return None
    exp = payload.get("exp")
    if isinstance(exp, (int, float)) and exp < time.time():
        return None
    return payload


def get_session(request: Request) -> dict[str, Any] | None:
    if not auth_enabled():
        return {"sub": "local-dev", "provider": "disabled"}
    return unsign_payload(request.cookies.get(SESSION_COOKIE))


def bearer_token(request: Request) -> str | None:
    value = request.headers.get("authorization") or ""
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def get_mcp_session(request: Request) -> dict[str, Any] | None:
    if not auth_enabled():
        return {"sub": "local-dev", "provider": "disabled", "scope": "mcp:ray"}
    token = bearer_token(request)
    if not token:
        return None
    dev_token = os.environ.get("RAY_MCP_BEARER_TOKEN")
    if dev_token and hmac.compare_digest(token, dev_token):
        return {"sub": "mcp-static-token", "provider": "static", "scope": "mcp:ray"}
    payload = unsign_payload(token)
    if payload and payload.get("typ") == "mcp_access":
        scope = str(payload.get("scope") or "")
        if "mcp:ray" in scope.split():
            return payload
    return None


def mcp_www_authenticate(request: Request) -> str:
    base = public_base_url(request)
    metadata = f"{base}/.well-known/oauth-protected-resource"
    return f'Bearer realm="ikawn-ray", resource_metadata="{metadata}"'


def is_public_path(path: str) -> bool:
    return path in PUBLIC_PATHS or any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES)


async def auth_middleware(request: Request, call_next):
    if not auth_enabled() or is_public_path(request.url.path):
        return await call_next(request)

    if get_session(request):
        return await call_next(request)

    if request.url.path.startswith("/api/"):
        return Response(
            json.dumps({"error": "unauthorized"}),
            status_code=401,
            media_type="application/json",
        )

    wants_html = "text/html" in request.headers.get("accept", "")
    if wants_html or request.method == "GET":
        next_path = request.url.path
        if request.url.query:
            next_path += f"?{request.url.query}"
        return RedirectResponse(f"/auth/login?next={next_path}", status_code=303)

    return Response(
        json.dumps({"error": "unauthorized"}),
        status_code=401,
        media_type="application/json",
    )


def _oauth_client_path() -> Path:
    return Path(os.environ.get("IKAWN_OS_CLIENT_PATH", "/data/oauth-client.json"))


def _mcp_clients_path() -> Path:
    return Path(os.environ.get("RAY_MCP_CLIENTS_PATH", "/data/mcp-oauth-clients.json"))


def _mcp_codes_path() -> Path:
    return Path(os.environ.get("RAY_MCP_CODES_PATH", "/data/mcp-oauth-codes.json"))


def _read_store(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_store(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def ensure_oauth_client(request: Request) -> str:
    env_client = os.environ.get("IKAWN_OS_CLIENT_ID")
    if env_client:
        return env_client

    client_path = _oauth_client_path()
    if client_path.exists():
        data = json.loads(client_path.read_text(encoding="utf-8"))
        if data.get("client_id"):
            return str(data["client_id"])

    base = public_base_url(request)
    redirect_uri = f"{base}/auth/callback"
    response = requests.post(
        f"{os_base_url()}/oauth/register",
        json={
            "client_name": "iKawn Ray",
            "client_uri": base,
            "logo_uri": f"{base}/ui/ikawn-ray.svg",
            "redirect_uris": [redirect_uri],
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
            "scope": "mcp",
        },
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    client_path.parent.mkdir(parents=True, exist_ok=True)
    client_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return str(data["client_id"])


def register_mcp_client(payload: dict[str, Any]) -> dict[str, Any]:
    redirect_uris = payload.get("redirect_uris")
    if not isinstance(redirect_uris, list) or not redirect_uris:
        raise ValueError("redirect_uris is required")
    clean_redirects = [str(uri) for uri in redirect_uris if str(uri).startswith(("https://", "http://localhost", "http://127.0.0.1"))]
    if not clean_redirects:
        raise ValueError("at least one valid redirect URI is required")
    client_id = f"ray_mcp_{secrets.token_urlsafe(24)}"
    client = {
        "client_id": client_id,
        "client_name": str(payload.get("client_name") or "Claude MCP Client")[:120],
        "redirect_uris": clean_redirects,
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
        "scope": "mcp:ray",
        "created_at": int(time.time()),
    }
    path = _mcp_clients_path()
    data = _read_store(path)
    data[client_id] = client
    _write_store(path, data)
    return client


def get_mcp_client(client_id: str | None) -> dict[str, Any] | None:
    if not client_id:
        return None
    return _read_store(_mcp_clients_path()).get(client_id)


def validate_mcp_redirect(client: dict[str, Any], redirect_uri: str | None) -> bool:
    return bool(redirect_uri and redirect_uri in set(client.get("redirect_uris") or []))


def issue_mcp_authorization_code(payload: dict[str, Any]) -> str:
    code = secrets.token_urlsafe(32)
    path = _mcp_codes_path()
    data = _read_store(path)
    data[code] = {**payload, "exp": int(time.time()) + 600}
    _write_store(path, data)
    return code


def consume_mcp_authorization_code(code: str | None) -> dict[str, Any] | None:
    if not code:
        return None
    path = _mcp_codes_path()
    data = _read_store(path)
    payload = data.pop(code, None)
    _write_store(path, data)
    if not payload or int(payload.get("exp") or 0) < int(time.time()):
        return None
    return payload


def pkce_challenge(verifier: str) -> str:
    return _b64(hashlib.sha256(verifier.encode("ascii")).digest())


def issue_mcp_access_token(sub: str, client_id: str, scope: str = "mcp:ray") -> tuple[str, int]:
    now = int(time.time())
    payload = {
        "typ": "mcp_access",
        "sub": sub,
        "client_id": client_id,
        "provider": "ikawn-os",
        "scope": scope,
        "iat": now,
        "exp": now + MCP_TOKEN_SECONDS,
    }
    return sign_payload(payload), MCP_TOKEN_SECONDS


def issue_mcp_refresh_token(sub: str, client_id: str, scope: str = "mcp:ray") -> tuple[str, int]:
    now = int(time.time())
    payload = {
        "typ": "mcp_refresh",
        "sub": sub,
        "client_id": client_id,
        "provider": "ikawn-os",
        "scope": scope,
        "iat": now,
        "exp": now + MCP_REFRESH_TOKEN_SECONDS,
    }
    return sign_payload(payload), MCP_REFRESH_TOKEN_SECONDS


def read_mcp_refresh_token(token: str | None, client_id: str | None) -> dict[str, Any] | None:
    payload = unsign_payload(token)
    if not payload or payload.get("typ") != "mcp_refresh":
        return None
    if client_id and payload.get("client_id") != client_id:
        return None
    scope = str(payload.get("scope") or "")
    if "mcp:ray" not in scope.split():
        return None
    return payload


def redirect_with_params(base_url: str, params: dict[str, str]) -> RedirectResponse:
    separator = "&" if "?" in base_url else "?"
    return RedirectResponse(f"{base_url}{separator}{urlencode(params)}", status_code=303)


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return verifier, _b64(digest)


def set_cookie(response: Response, name: str, value: str, max_age: int) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


def clear_cookie(response: Response, name: str) -> None:
    response.delete_cookie(name, path="/")


def issue_session(response: Response, token: str, expires_in: int | None = None) -> None:
    ttl = min(int(expires_in or DEFAULT_SESSION_SECONDS), DEFAULT_SESSION_SECONDS)
    payload = {
        "sub": hashlib.sha256(token.encode("utf-8")).hexdigest()[:32],
        "provider": "ikawn-os",
        "iat": int(time.time()),
        "exp": int(time.time()) + ttl,
    }
    set_cookie(response, SESSION_COOKIE, sign_payload(payload), ttl)
