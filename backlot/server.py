"""Backlot server — FastAPI app: board state API, SSE change feed, media.

The watcher observes ``projects/`` with watchfiles; on any change it bumps a
per-project version and wakes SSE subscribers, who tell the browser to
refetch state. The server never writes to project directories.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from pathlib import Path
from typing import Optional

import requests
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from backlot import auth, jobs, mcp, storage
from backlot.state import PROJECTS_DIR, REPO_ROOT, list_projects, load_board_state, summarize_project

UI_DIR = Path(__file__).resolve().parent / "ui"
THUMB_CACHE_DIR = REPO_ROOT / ".backlot" / "thumbs"
THUMB_WIDTHS = (320, 640, 960)

# Paths inside a project whose changes are pure noise for the board.
_IGNORE_PARTS = {"node_modules", ".git", "__pycache__", ".cache"}

SSE_HEARTBEAT_SECONDS = 15


class ChangeHub:
    """Fan-out of project-change notifications to SSE subscribers.

    Subscriptions are filtered: a board subscribed to one project only ever
    receives that project's ids, so unrelated-project bursts can't flood its
    queue and starve out the one notification it actually needs.
    """

    def __init__(self) -> None:
        self._subscribers: dict[asyncio.Queue, Optional[str]] = {}

    def subscribe(self, project_id: Optional[str] = None) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=64)
        self._subscribers[q] = project_id
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.pop(q, None)

    def publish(self, project_id: str) -> None:
        for q, only in list(self._subscribers.items()):
            if only is not None and only != project_id:
                continue
            try:
                q.put_nowait(project_id)
            except asyncio.QueueFull:
                # Queue holds only THIS subscriber's relevant ids, so a full
                # queue already guarantees a pending wake-up → safe to drop.
                pass


hub = ChangeHub()

# Library summaries are expensive to derive (full state parse per project);
# cache per project and invalidate from the watcher.
_summary_cache: dict[str, dict] = {}


def _invalidate_summary(project_id: str) -> None:
    _summary_cache.pop(project_id, None)


def _cached_summaries() -> list[dict]:
    if not PROJECTS_DIR.is_dir():
        return []
    summaries = []
    for entry in sorted(PROJECTS_DIR.iterdir()):
        if not entry.is_dir() or entry.name.startswith(("_", ".")):
            continue
        cached = _summary_cache.get(entry.name)
        if cached is None:
            try:
                cached = summarize_project(entry)
            except Exception:
                cached = {
                    "project_id": entry.name, "title": entry.name,
                    "pipeline_type": "unknown", "has_pipeline_state": False,
                    "poster": None, "live": False, "last_activity": 0,
                    "active_stage": None, "awaiting_human": False,
                    "stage_states": [], "completed_count": 0,
                    "render_count": 0, "scene_count": 0, "error": "unreadable",
                }
            _summary_cache[entry.name] = cached
        summaries.append(cached)
    summaries.sort(key=lambda s: (not s["live"], -(s["last_activity"] or 0)))
    return summaries


# Watch-loop hot path: pure string comparison, no per-path filesystem calls
# (change batches can be thousands of paths during a render).
import os as _os

_PROJECTS_ROOT_STR = _os.path.normcase(str(PROJECTS_DIR.resolve()))


def _project_of_change(path_str: str) -> Optional[str]:
    """Map a changed filesystem path to a project id (None = irrelevant)."""
    norm = _os.path.normcase(_os.path.normpath(path_str))
    if not norm.startswith(_PROJECTS_ROOT_STR):
        return None
    rel = norm[len(_PROJECTS_ROOT_STR):].lstrip("\\/")
    if not rel:
        return None
    parts = rel.replace("\\", "/").split("/")
    if _IGNORE_PARTS.intersection(parts):
        return None
    return parts[0]


async def _watch_projects() -> None:
    """Background task: watch projects/ and publish debounced changes."""
    try:
        from watchfiles import awatch
    except ImportError:
        return  # watcher unavailable → board still works via manual refresh
    if not PROJECTS_DIR.is_dir():
        return
    async for changes in awatch(PROJECTS_DIR, recursive=True, step=400):
        touched: set[str] = set()
        for _change, path_str in changes:
            pid = _project_of_change(path_str)
            if pid:
                touched.add(pid)
        for pid in touched:
            _invalidate_summary(pid)
            hub.publish(pid)


def create_app() -> FastAPI:
    app = FastAPI(title="Backlot", docs_url=None, redoc_url=None)
    app.middleware("http")(auth.auth_middleware)

    @app.on_event("startup")
    async def _startup() -> None:
        app.state.watch_task = asyncio.create_task(_watch_projects())

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        task = getattr(app.state, "watch_task", None)
        if task:
            task.cancel()

    # ---- API ----------------------------------------------------------

    @app.get("/api/health")
    async def health() -> dict:
        return {"ok": True, "app": "backlot"}

    @app.get("/api/config")
    async def config() -> dict:
        return {
            "auth_enabled": auth.auth_enabled(),
            "auth_provider": "ikawn-os" if auth.auth_enabled() else "disabled",
            "llm_configured": bool(_os.environ.get("OPENROUTER_API_KEY") or _os.environ.get("OPENAI_API_KEY")),
            "fal_configured": bool(_os.environ.get("FAL_KEY") or _os.environ.get("FAL_AI_API_KEY")),
            "grok_configured": bool(_os.environ.get("FAL_KEY") or _os.environ.get("FAL_AI_API_KEY") or _os.environ.get("XAI_API_KEY")),
            "xai_configured": bool(_os.environ.get("XAI_API_KEY")),
            "r2_configured": storage.configured(),
            "video_models": jobs.video_model_options(),
        }

    # ---- OAuth + MCP --------------------------------------------------

    @app.get("/.well-known/oauth-protected-resource")
    @app.get("/.well-known/oauth-protected-resource/mcp")
    async def oauth_protected_resource(request: Request) -> dict:
        base = auth.public_base_url(request)
        brand = mcp.brand_metadata(base)
        return {
            "resource": f"{base}/mcp",
            "authorization_servers": [base],
            "scopes_supported": ["mcp:ray"],
            "bearer_methods_supported": ["header"],
            "resource_name": mcp.BRAND_NAME,
            "resource_documentation": base,
            "resource_policy_uri": base,
            "logo_uri": brand["logo_url"],
            "brand_color": mcp.BRAND_COLOR,
            "theme_color": mcp.BRAND_COLOR,
            "_meta": brand,
        }

    @app.get("/.well-known/oauth-authorization-server")
    @app.get("/.well-known/openid-configuration")
    async def oauth_authorization_server(request: Request) -> dict:
        base = auth.public_base_url(request)
        brand = mcp.brand_metadata(base)
        return {
            "issuer": base,
            "authorization_endpoint": f"{base}/oauth/authorize",
            "token_endpoint": f"{base}/oauth/token",
            "registration_endpoint": f"{base}/oauth/register",
            "service_documentation": base,
            "logo_uri": brand["logo_url"],
            "brand_color": mcp.BRAND_COLOR,
            "theme_color": mcp.BRAND_COLOR,
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
            "scopes_supported": ["mcp:ray"],
            "_meta": brand,
        }

    @app.post("/oauth/register")
    async def oauth_register(request: Request):
        try:
            body = await request.json()
            client = auth.register_mcp_client(body)
        except Exception as exc:
            return JSONResponse({"error": "invalid_client_metadata", "error_description": str(exc)}, status_code=400)
        return JSONResponse({**client, "client_id_issued_at": int(time.time())}, status_code=201)

    @app.get("/oauth/authorize")
    async def oauth_authorize(request: Request):
        q = request.query_params
        if q.get("response_type") != "code":
            return JSONResponse({"error": "unsupported_response_type"}, status_code=400)
        client = auth.get_mcp_client(q.get("client_id"))
        if not client or not auth.validate_mcp_redirect(client, q.get("redirect_uri")):
            return JSONResponse({"error": "invalid_client"}, status_code=400)
        if q.get("code_challenge_method") != "S256" or not q.get("code_challenge"):
            return JSONResponse({"error": "invalid_request", "error_description": "PKCE S256 is required"}, status_code=400)

        try:
            upstream_client_id = await asyncio.to_thread(auth.ensure_oauth_client, request)
        except Exception as exc:
            return JSONResponse({"error": "upstream_oauth_client", "error_description": str(exc)}, status_code=500)

        verifier, challenge = auth.pkce_pair()
        upstream_state = _os.urandom(24).hex()
        saved = {
            "state": upstream_state,
            "verifier": verifier,
            "next": "/",
            "exp": time.time() + 600,
            "mcp_oauth": {
                "client_id": q.get("client_id"),
                "redirect_uri": q.get("redirect_uri"),
                "client_state": q.get("state") or "",
                "code_challenge": q.get("code_challenge"),
                "scope": q.get("scope") or "mcp:ray",
            },
        }
        redirect_uri = f"{auth.public_base_url(request)}/auth/callback"
        url = requests.Request(
            "GET",
            f"{auth.os_base_url()}/oauth/authorize",
            params={
                "client_id": upstream_client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "mcp",
                "state": upstream_state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            },
        ).prepare().url
        response = RedirectResponse(url, status_code=303)
        auth.set_cookie(response, auth.OAUTH_STATE_COOKIE, auth.sign_payload(saved), 600)
        return response

    @app.post("/oauth/token")
    async def oauth_token(request: Request):
        form = await _oauth_request_data(request)
        grant_type = form.get("grant_type")
        if grant_type == "refresh_token":
            refresh_data = auth.read_mcp_refresh_token(form.get("refresh_token"), form.get("client_id"))
            if not refresh_data:
                return JSONResponse({"error": "invalid_grant"}, status_code=400)
            token, expires_in = auth.issue_mcp_access_token(
                str(refresh_data.get("sub")),
                str(refresh_data.get("client_id")),
                str(refresh_data.get("scope") or "mcp:ray"),
            )
            refresh_token, refresh_expires_in = auth.issue_mcp_refresh_token(
                str(refresh_data.get("sub")),
                str(refresh_data.get("client_id")),
                str(refresh_data.get("scope") or "mcp:ray"),
            )
            return {
                "access_token": token,
                "token_type": "Bearer",
                "expires_in": expires_in,
                "refresh_token": refresh_token,
                "refresh_token_expires_in": refresh_expires_in,
                "scope": refresh_data.get("scope") or "mcp:ray",
            }
        if grant_type != "authorization_code":
            return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)
        code_data = auth.consume_mcp_authorization_code(form.get("code"))
        if not code_data:
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        if code_data.get("client_id") != form.get("client_id") or code_data.get("redirect_uri") != form.get("redirect_uri"):
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        if auth.pkce_challenge(str(form.get("code_verifier") or "")) != code_data.get("code_challenge"):
            return JSONResponse({"error": "invalid_grant", "error_description": "PKCE verification failed"}, status_code=400)
        token, expires_in = auth.issue_mcp_access_token(
            str(code_data.get("sub")),
            str(code_data.get("client_id")),
            str(code_data.get("scope") or "mcp:ray"),
        )
        refresh_token, refresh_expires_in = auth.issue_mcp_refresh_token(
            str(code_data.get("sub")),
            str(code_data.get("client_id")),
            str(code_data.get("scope") or "mcp:ray"),
        )
        return {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": expires_in,
            "refresh_token": refresh_token,
            "refresh_token_expires_in": refresh_expires_in,
            "scope": code_data.get("scope") or "mcp:ray",
        }

    @app.api_route("/mcp", methods=["GET", "POST", "DELETE"])
    async def mcp_endpoint(request: Request):
        session = auth.get_mcp_session(request)
        if not session:
            return JSONResponse(
                {"error": "unauthorized"},
                status_code=401,
                headers={"WWW-Authenticate": auth.mcp_www_authenticate(request)},
            )
        if request.method != "POST":
            return JSONResponse({"ok": True, "server": mcp.SERVER_NAME, "transport": "streamable-http"})
        try:
            body = await request.json()
        except Exception:
            return _mcp_error_response(None, -32700, "Invalid JSON")
        base = auth.public_base_url(request)
        if isinstance(body, list):
            replies = []
            for item in body:
                if isinstance(item, dict):
                    reply = await mcp.dispatch(item, base_url=base, session=session, publish_project=_publish_project)
                    if reply is not None:
                        replies.append(reply)
            if not replies:
                return Response(status_code=202)
            return JSONResponse(replies)
        if not isinstance(body, dict):
            return _mcp_error_response(None, -32600, "Invalid JSON-RPC request")
        reply = await mcp.dispatch(body, base_url=base, session=session, publish_project=_publish_project)
        if reply is None:
            return Response(status_code=202)
        return JSONResponse(reply)

    @app.get("/api/projects")
    async def projects() -> list:
        return await asyncio.to_thread(_cached_summaries)

    @app.post("/api/jobs")
    async def create_job(request: Request):
        body = await request.json()
        try:
            job = await asyncio.to_thread(jobs.create_job, body, auth.get_session(request))
        except jobs.JobError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        _invalidate_summary(job["project_id"])
        hub.publish(job["project_id"])
        return job

    @app.post("/api/jobs/{project_id}/start")
    async def start_job(project_id: str) -> dict:
        _safe_project_dir(project_id)
        asyncio.create_task(asyncio.to_thread(_plan_job_and_publish, project_id))
        return {"ok": True, "project_id": project_id, "status": "planning", "url": f"/p/{project_id}"}

    @app.post("/api/jobs/{project_id}/plan")
    async def plan_job(project_id: str) -> dict:
        _safe_project_dir(project_id)
        asyncio.create_task(asyncio.to_thread(_plan_job_and_publish, project_id))
        return {"ok": True, "project_id": project_id, "status": "planning", "url": f"/p/{project_id}"}

    @app.post("/api/jobs/{project_id}/revise-plan")
    async def revise_plan(project_id: str, request: Request):
        _safe_project_dir(project_id)
        body = await request.json()
        try:
            result = await asyncio.to_thread(jobs.revise_plan, project_id, body)
        except jobs.JobError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        _invalidate_summary(project_id)
        hub.publish(project_id)
        return result

    @app.post("/api/jobs/{project_id}/approve-paid-generation")
    async def approve_paid_generation(project_id: str, request: Request) -> dict:
        _safe_project_dir(project_id)
        try:
            body = await request.json()
        except Exception:
            body = {}
        if body.get("confirm_paid_generation") is not True:
            raise HTTPException(status_code=400, detail="confirm_paid_generation=true is required")
        override_no_references = body.get("override_no_references") is True
        confirm_seedance_risk = body.get("confirm_seedance_risk") is True
        try:
            await asyncio.to_thread(
                jobs.validate_paid_generation_allowed,
                project_id,
                override_no_references,
                confirm_seedance_risk,
            )
        except jobs.JobError as exc:
            return JSONResponse({"error": str(exc)}, status_code=409)
        asyncio.create_task(asyncio.to_thread(_run_job_and_publish, project_id, override_no_references, confirm_seedance_risk))
        return {"ok": True, "project_id": project_id, "status": "paid_generation_started", "url": f"/p/{project_id}"}

    @app.post("/api/jobs/{project_id}/retry-paid-generation")
    async def retry_paid_generation(project_id: str, request: Request) -> dict:
        _safe_project_dir(project_id)
        try:
            body = await request.json()
        except Exception:
            body = {}
        if body.get("confirm_paid_generation") is not True:
            raise HTTPException(status_code=400, detail="confirm_paid_generation=true is required")
        video_model = str(body.get("video_model") or "grok-imagine-video")
        confirm_seedance_risk = body.get("confirm_seedance_risk") is True
        try:
            normalized_model = jobs._normalize_video_model(video_model)
            selected_model = jobs.VIDEO_MODELS[normalized_model]
        except jobs.JobError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        if selected_model.get("requires_explicit_paid_approval") and not confirm_seedance_risk:
            return JSONResponse(
                {"error": "Seedance retry requires confirm_seedance_risk=true after explicit user approval."},
                status_code=409,
            )
        asyncio.create_task(asyncio.to_thread(_retry_job_and_publish, project_id, normalized_model, confirm_seedance_risk))
        return {"ok": True, "project_id": project_id, "status": "paid_generation_retry_started", "url": f"/p/{project_id}"}

    @app.post("/api/jobs/{project_id}/approve-asset-review")
    async def approve_asset_review(project_id: str, request: Request) -> dict:
        _safe_project_dir(project_id)
        try:
            body = await request.json()
        except Exception:
            body = {}
        if body.get("confirm_asset_review_passed") is not True:
            raise HTTPException(status_code=400, detail="confirm_asset_review_passed=true is required")
        try:
            result = await asyncio.to_thread(jobs.approve_asset_review, project_id)
        except jobs.JobError as exc:
            return JSONResponse({"error": str(exc)}, status_code=409)
        _invalidate_summary(project_id)
        hub.publish(project_id)
        return result

    @app.post("/api/jobs/{project_id}/references")
    async def add_job_references(project_id: str, request: Request) -> dict:
        project_dir = _safe_project_dir(project_id)
        body = await request.json()
        req_path = project_dir / "artifacts" / "job_request.json"
        try:
            data = json.loads(req_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        data["reference_assets"] = body.get("reference_assets") or []
        req_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return {"ok": True, "reference_assets": data["reference_assets"]}

    @app.post("/api/project/{project_id}/uploads")
    async def upload_project_files(project_id: str, files: list[UploadFile] = File(...)) -> dict:
        _safe_project_dir(project_id)
        saved = []
        for file in files:
            content = await file.read()
            saved.append(await asyncio.to_thread(jobs.save_upload, project_id, file.filename or "upload.bin", content))
        _invalidate_summary(project_id)
        hub.publish(project_id)
        return {"files": saved}

    @app.get("/api/project/{project_id}/state")
    async def project_state(project_id: str) -> dict:
        project_dir = _safe_project_dir(project_id)
        return await asyncio.to_thread(load_board_state, project_dir)

    @app.get("/api/project/{project_id}/events")
    async def project_events(project_id: str, request: Request) -> StreamingResponse:
        _safe_project_dir(project_id)  # 404 early for unknown projects

        async def stream():
            q = hub.subscribe(project_id)
            try:
                yield _sse({"type": "hello", "project_id": project_id})
                while True:
                    if await request.is_disconnected():
                        return
                    try:
                        await asyncio.wait_for(q.get(), timeout=SSE_HEARTBEAT_SECONDS)
                    except asyncio.TimeoutError:
                        yield _sse({"type": "heartbeat", "ts": time.time()})
                        continue
                    # Coalesce bursts: drain anything else queued.
                    while not q.empty():
                        try:
                            q.get_nowait()
                        except asyncio.QueueEmpty:
                            break
                    yield _sse({"type": "change", "project_id": project_id})
            finally:
                hub.unsubscribe(q)

        return StreamingResponse(stream(), media_type="text/event-stream", headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        })

    @app.get("/api/library/events")
    async def library_events(request: Request) -> StreamingResponse:
        async def stream():
            q = hub.subscribe()
            try:
                yield _sse({"type": "hello"})
                while True:
                    if await request.is_disconnected():
                        return
                    try:
                        changed = await asyncio.wait_for(q.get(), timeout=SSE_HEARTBEAT_SECONDS)
                    except asyncio.TimeoutError:
                        yield _sse({"type": "heartbeat", "ts": time.time()})
                        continue
                    while not q.empty():
                        try:
                            q.get_nowait()
                        except asyncio.QueueEmpty:
                            break
                    yield _sse({"type": "change", "project_id": changed})
            finally:
                hub.unsubscribe(q)

        return StreamingResponse(stream(), media_type="text/event-stream", headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        })

    # ---- Thumbnails (downscaled, cached on disk) ------------------------

    @app.get("/thumb/{project_id}/{file_path:path}")
    async def thumb(project_id: str, file_path: str, w: int = 640) -> FileResponse:
        project_dir = _safe_project_dir(project_id)
        target = (project_dir / file_path).resolve()
        try:
            target.relative_to(project_dir.resolve())
        except ValueError:
            raise HTTPException(status_code=403, detail="path escapes project")
        if not target.is_file():
            raise HTTPException(status_code=404, detail="media not found")
        width = min(THUMB_WIDTHS, key=lambda x: abs(x - w))
        cached = await asyncio.to_thread(_thumbnail_for, target, width)
        if cached is None:
            # Never fall back to raw video bytes for an <img> consumer (F-03);
            # non-thumbable images are safe to serve as-is.
            if target.suffix.lower() in {".mp4", ".webm", ".mov"}:
                raise HTTPException(status_code=404, detail="no poster frame available")
            return FileResponse(target)
        return FileResponse(cached, media_type="image/jpeg")

    # ---- Media (range requests handled by FileResponse) ---------------

    @app.get("/media/{project_id}/{file_path:path}")
    async def media(project_id: str, file_path: str) -> FileResponse:
        project_dir = _safe_project_dir(project_id)
        target = (project_dir / file_path).resolve()
        try:
            target.relative_to(project_dir.resolve())
        except ValueError:
            raise HTTPException(status_code=403, detail="path escapes project")
        if not target.is_file():
            raise HTTPException(status_code=404, detail="media not found")
        return FileResponse(target)

    # ---- UI ------------------------------------------------------------

    @app.get("/p/{project_id}")
    async def board_page(project_id: str) -> FileResponse:
        _safe_project_dir(project_id)
        return FileResponse(UI_DIR / "board.html")

    @app.get("/p/{project_path:path}")
    async def board_page_path(project_path: str) -> FileResponse:
        return FileResponse(UI_DIR / "board.html")

    @app.get("/")
    async def library_page() -> FileResponse:
        return FileResponse(UI_DIR / "index.html")

    @app.get("/auth")
    async def auth_page() -> FileResponse:
        return FileResponse(UI_DIR / "login.html")

    @app.get("/auth/login")
    async def auth_login(request: Request):
        if not auth.auth_enabled():
            return RedirectResponse("/", status_code=303)
        if request.query_params.get("start") != "1" and "text/html" in request.headers.get("accept", ""):
            return FileResponse(UI_DIR / "login.html")

        next_path = request.query_params.get("next") or "/"
        try:
            client_id = await asyncio.to_thread(auth.ensure_oauth_client, request)
        except Exception as exc:
            return RedirectResponse(f"/auth?error=oauth_client&detail={str(exc)[:80]}", status_code=303)

        verifier, challenge = auth.pkce_pair()
        state = _os.urandom(24).hex()
        payload = {"state": state, "verifier": verifier, "next": next_path, "exp": time.time() + 600}
        redirect_uri = f"{auth.public_base_url(request)}/auth/callback"
        url = requests.Request(
            "GET",
            f"{auth.os_base_url()}/oauth/authorize",
            params={
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "mcp",
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            },
        ).prepare().url
        response = RedirectResponse(url, status_code=303)
        auth.set_cookie(response, auth.OAUTH_STATE_COOKIE, auth.sign_payload(payload), 600)
        return response

    @app.get("/auth/callback")
    async def auth_callback(request: Request) -> RedirectResponse:
        saved = auth.unsign_payload(request.cookies.get(auth.OAUTH_STATE_COOKIE))
        if not saved or saved.get("state") != request.query_params.get("state"):
            return RedirectResponse("/auth?error=state", status_code=303)
        if request.query_params.get("error"):
            return RedirectResponse(f"/auth?error={request.query_params.get('error')}", status_code=303)
        code = request.query_params.get("code")
        if not code:
            return RedirectResponse("/auth?error=missing_code", status_code=303)
        client_id = await asyncio.to_thread(auth.ensure_oauth_client, request)
        token_resp = requests.post(
            f"{auth.os_base_url()}/oauth/token",
            json={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": f"{auth.public_base_url(request)}/auth/callback",
                "client_id": client_id,
                "code_verifier": saved["verifier"],
            },
            timeout=20,
        )
        if not token_resp.ok:
            return RedirectResponse("/auth?error=token", status_code=303)
        token_data = token_resp.json()
        if saved.get("mcp_oauth"):
            mcp_oauth = saved["mcp_oauth"]
            sub = hashlib.sha256(str(token_data["access_token"]).encode("utf-8")).hexdigest()[:32]
            code = auth.issue_mcp_authorization_code({
                "sub": sub,
                "client_id": mcp_oauth["client_id"],
                "redirect_uri": mcp_oauth["redirect_uri"],
                "code_challenge": mcp_oauth["code_challenge"],
                "scope": mcp_oauth.get("scope") or "mcp:ray",
            })
            params = {"code": code}
            if mcp_oauth.get("client_state"):
                params["state"] = mcp_oauth["client_state"]
            response = auth.redirect_with_params(mcp_oauth["redirect_uri"], params)
            auth.clear_cookie(response, auth.OAUTH_STATE_COOKIE)
            return response
        response = RedirectResponse(str(saved.get("next") or "/"), status_code=303)
        auth.clear_cookie(response, auth.OAUTH_STATE_COOKIE)
        auth.issue_session(response, token_data["access_token"], token_data.get("expires_in"))
        return response

    @app.post("/auth/logout")
    async def auth_logout() -> RedirectResponse:
        response = RedirectResponse("/auth", status_code=303)
        auth.clear_cookie(response, auth.SESSION_COOKIE)
        auth.clear_cookie(response, auth.OAUTH_STATE_COOKIE)
        return response

    if UI_DIR.is_dir():
        app.mount("/ui", StaticFiles(directory=UI_DIR), name="ui")

    return app


async def _oauth_request_data(request: Request) -> dict[str, str]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            data = await request.json()
        except Exception:
            return {}
        return {str(k): str(v) for k, v in data.items()}
    form = await request.form()
    return {str(k): str(v) for k, v in form.items()}


def _mcp_error_response(msg_id, code: int, message: str) -> JSONResponse:
    return JSONResponse({
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": code, "message": message},
    })


def _publish_project(project_id: str) -> None:
    _invalidate_summary(project_id)
    hub.publish(project_id)


def _safe_project_dir(project_id: str) -> Path:
    # ':' rejects Windows drive-relative ids like "C:" (PROJECTS_DIR / "C:"
    # collapses back to PROJECTS_DIR itself).
    if any(c in project_id for c in "/\\:") or project_id in (".", ".."):
        raise HTTPException(status_code=400, detail="invalid project id")
    project_dir = PROJECTS_DIR / project_id
    if not project_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"unknown project: {project_id}")
    return project_dir


def _run_job_and_publish(
    project_id: str,
    override_no_references: bool = False,
    confirm_seedance_risk: bool = False,
) -> None:
    jobs.approve_paid_generation(
        project_id,
        override_no_references=override_no_references,
        confirm_seedance_risk=confirm_seedance_risk,
    )
    _invalidate_summary(project_id)
    hub.publish(project_id)


def _retry_job_and_publish(project_id: str, video_model: str, confirm_seedance_risk: bool = False) -> None:
    jobs.retry_paid_generation(project_id, video_model, confirm_seedance_risk=confirm_seedance_risk)
    _invalidate_summary(project_id)
    hub.publish(project_id)


def _plan_job_and_publish(project_id: str) -> None:
    jobs.plan_job(project_id)
    _invalidate_summary(project_id)
    hub.publish(project_id)


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _thumbnail_for(source: Path, width: int) -> Optional[Path]:
    """Downscale an image (or extract a video poster frame) to a cached JPEG."""
    suffix = source.suffix.lower()
    is_image = suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    is_video = suffix in {".mp4", ".webm", ".mov"}
    if not (is_image or is_video):
        return None
    try:
        import hashlib
        stat = source.stat()
        key = hashlib.sha1(
            f"{source}|{stat.st_mtime_ns}|{stat.st_size}|{width}".encode()
        ).hexdigest()[:20]
        cached = THUMB_CACHE_DIR / f"{key}.jpg"
        if cached.is_file():
            return cached
        THUMB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        # Unique temp per request — concurrent misses for the same source
        # must not write (and replace from) the same temp file.
        import uuid
        tmp = THUMB_CACHE_DIR / f"{key}.{uuid.uuid4().hex[:8]}.tmp.jpg"
        if is_video:
            import subprocess
            result = subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-ss", "1.5",
                 "-i", str(source), "-frames:v", "1",
                 "-vf", f"scale={width}:-2", str(tmp)],
                capture_output=True, timeout=30,
            )
            if result.returncode != 0 or not tmp.is_file():
                return None
        else:
            from PIL import Image
            with Image.open(source) as img:
                img = img.convert("RGB")
                img.thumbnail((width, width * 3))
                img.save(tmp, "JPEG", quality=82)
        tmp.replace(cached)
        return cached
    except Exception:
        return None


app = create_app()
