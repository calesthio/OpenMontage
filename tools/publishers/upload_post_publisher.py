"""Upload-Post publisher — a networked PUBLISH-tier provider.

Publishes one finished render to TikTok, Instagram (Reels), YouTube, LinkedIn,
Facebook, X, Threads, Pinterest and Bluesky through the Upload-Post API
(https://docs.upload-post.com), and returns the same schema-valid
``publish_log`` shape ``export_bundle`` produces — one entry per platform.

Scope is deliberately narrow: video only, publish now. No scheduling, photos,
text posts, comments or DMs.

Publishing is irreversible (most platforms can't unpublish or swap a cover
through their APIs), so the design centres on never posting twice and never
posting stale inputs:

* **Deterministic request id.** The id sent to Upload-Post (as both
  ``request_id`` and ``Idempotency-Key``) is a hash of the exact bytes and text
  being published: video, thumbnail, caption, description, tags, platforms,
  profile, visibility and an ``attempt`` counter. Re-running the same publish
  after an interruption resolves to the same id; changing the cover or caption
  is, by construction, a different publish.
* **Resume before upload.** Before sending anything the tool asks Upload-Post
  whether that id already exists. If it does, it resumes polling instead of
  uploading again — so an interrupted run can never create a second post, even
  outside the server's 24 h idempotency window.
* **No re-send on network errors.** If the connection drops mid-upload the tool
  polls the same id to learn whether the upload arrived.
* **Stale-publish guard.** A small ledger next to the export bundle records
  every submission. If an earlier submission of the same render with *different*
  inputs is still in flight or already live on an overlapping platform, the tool
  refuses to publish again unless ``allow_additional_post`` is set — the
  corrected version and the stale one can't both go out silently. The ledger is
  also the durable evidence of a completed publish: once Upload-Post has
  forgotten the request (status retention expired), a re-run answers from the
  ledger instead of uploading again, and a ledger that exists but cannot be
  read or parsed blocks publishing rather than being treated as empty.
* **Auditable log.** ``publish_log.metadata`` records the request id and the
  SHA-256 of the video, thumbnail and caption that were actually sent.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import time
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)

API_BASE = "https://api.upload-post.com"
API_KEY_ENV = "UPLOAD_POST_API_KEY"
PROFILE_ENV = "UPLOAD_POST_USER"
LEDGER_NAME = "upload_post_ledger.json"

VIDEO_PLATFORMS = (
    "tiktok",
    "instagram",
    "youtube",
    "linkedin",
    "facebook",
    "x",
    "threads",
    "pinterest",
    "bluesky",
)
# Platforms that honour a per-post "private" setting through Upload-Post.
PRIVATE_CAPABLE = {"youtube", "tiktok"}
TIKTOK_PRIVACY = {"public": "PUBLIC_TO_EVERYONE", "private": "SELF_ONLY"}
TIKTOK_PRIVACY_LEVELS = (
    "PUBLIC_TO_EVERYONE",
    "MUTUAL_FOLLOW_FRIENDS",
    "FOLLOWER_OF_CREATOR",
    "SELF_ONLY",
)

FINAL_STATES = {"completed", "failed"}
# Only these statuses prove Upload-Post rejected the upload before accepting it, so
# re-sending is safe. Anything else (5xx, 408/409, transport errors, timeouts, a 2xx
# without a JSON body) is ambiguous: the upload may have been accepted.
DEFINITIVE_REJECTIONS = {400, 401, 402, 403, 404, 413, 422, 429}
# Ledger states in which the same request id must not be uploaded again without a
# status check proving it never arrived, or explicit user confirmation.
UNRESOLVED_STATES = {"submitting", "submitted", "ambiguous", "in_flight"}
POLL_INTERVAL_SECONDS = 10
# After a dropped connection, how long an unknown request id may stay unknown before
# we conclude the upload never arrived (nothing was published).
ARRIVAL_GRACE_SECONDS = 60
DEFAULT_WAIT_SECONDS = 600
UPLOAD_TIMEOUT = (30, 900)  # (connect, read); the read covers sending the file
API_TIMEOUT = (15, 60)


class UploadPostError(Exception):
    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


class LedgerError(UploadPostError):
    """The submission ledger exists but cannot be trusted (unreadable or corrupt).

    It may hold the only record of an upload Upload-Post already accepted, so the
    publisher fails closed instead of treating it as empty history."""

    def __init__(self, path: Path, reason: str):
        super().__init__(
            f"The submission ledger {path} is unreadable or corrupt ({reason}). It may be the only record "
            "of an earlier accepted upload, so nothing was sent. Repair it or move it aside after checking "
            "the target accounts, then re-run."
        )
        self.path = path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class UploadPostPublisher(BaseTool):
    name = "upload_post_publisher"
    version = "0.1.0"
    tier = ToolTier.PUBLISH
    capability = "publish"
    provider = "upload_post"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = [f"env:{API_KEY_ENV}", "python:requests"]
    install_instructions = (
        "Create an account at https://upload-post.com (free plan: 10 uploads/month; "
        "TikTok needs a paid plan), connect your social accounts to a profile, create "
        f"an API key, then set {API_KEY_ENV} (and optionally {PROFILE_ENV}) in .env. "
        "See docs/PROVIDERS.md#upload-post--social-publishing."
    )

    agent_skills = []

    capabilities = ["social_publish", "write_publish_log"]
    supports = {
        "uploads": True,
        "multi_platform": True,
        "video": True,
        "photos": False,
        "scheduling": False,
        "free_tier": True,
        "idempotent": True,
        "local_offline": False,
    }
    best_for = [
        "publishing a finished render to TikTok, Instagram Reels, YouTube (incl. Shorts), "
        "LinkedIn, Facebook, X, Threads, Pinterest and Bluesky in one call",
        "cross-posting vertical shorts from clip-factory / explainer runs",
        "publishing without registering a developer app or OAuth client per platform",
    ]
    not_good_for = [
        "offline hand-off without an account (use export_bundle)",
        "scheduling, photo carousels or text-only posts (out of scope for this tool)",
    ]

    input_schema = {
        "type": "object",
        "required": ["video_path", "title", "platforms"],
        "properties": {
            "video_path": {
                "type": "string",
                "description": "Final rendered video (render_report.outputs[].path, or export_bundle's video/output.mp4).",
            },
            "title": {
                "type": "string",
                "description": "Caption on TikTok/Instagram/X/Threads/Bluesky, title on YouTube (max 100 chars there).",
            },
            "platforms": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "enum": list(VIDEO_PLATFORMS)},
            },
            "description": {
                "type": "string",
                "description": "Longer text for YouTube, LinkedIn, Facebook and Pinterest.",
            },
            "tags": {"type": "array", "items": {"type": "string"}, "description": "YouTube tags."},
            "hashtags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Appended to the caption (a missing '#' is added).",
            },
            "thumbnail_path": {"type": "string", "description": "Cover for YouTube / LinkedIn."},
            "visibility": {
                "type": "string",
                "enum": ["public", "private", "unlisted"],
                "description": (
                    "Default: YouTube private, TikTok the account's own default, other platforms public. "
                    "'private'/'unlisted' are rejected for platforms that have no such mode."
                ),
            },
            "tiktok_privacy_level": {"type": "string", "enum": list(TIKTOK_PRIVACY_LEVELS)},
            "ai_generated": {
                "type": "boolean",
                "description": "Self-disclose AI-generated content (TikTok, Instagram, YouTube and X labels).",
            },
            "pinterest_board_id": {"type": "string", "description": "Required when publishing to Pinterest."},
            "profile": {
                "type": "string",
                "description": f"Upload-Post profile to post from. Defaults to ${PROFILE_ENV}.",
            },
            "confirm_not_published": {
                "type": "boolean",
                "description": (
                    "Only after an 'ambiguous' result: the user checked the platforms and nothing went out, "
                    "so the same publish may be sent again."
                ),
            },
            "attempt": {
                "type": "integer",
                "minimum": 1,
                "description": "Bump to deliberately retry a publish whose previous attempt failed.",
            },
            "allow_additional_post": {
                "type": "boolean",
                "description": "Publish even if a different version of this render is already live or in flight.",
            },
            "ledger_path": {"type": "string", "description": "Override the submission ledger location."},
            "wait_seconds": {"type": "integer", "minimum": 0, "description": "How long to poll for results."},
            "dry_run": {"type": "boolean", "description": "Validate and check the account; never uploads."},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "publish_log": {"type": "object"},
            "request_id": {"type": "string"},
            "resumed": {"type": "boolean"},
            "results": {"type": "array", "items": {"type": "object"}},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=0, network_required=True)
    # Never retried by the framework: a blind retry of a publish is exactly the failure
    # mode this tool exists to prevent. Resumption goes through the request id instead.
    retry_policy = RetryPolicy(max_retries=0)
    idempotency_key_fields = ["video_path", "title", "platforms", "profile", "attempt"]

    def idempotency_key(self, inputs: dict[str, Any]) -> str:
        # The real key hashes the bytes and text being published (see _plan).
        try:
            return self._plan(inputs)["request_id"]
        except (ValueError, KeyError, OSError):
            return super().idempotency_key(inputs)
    side_effects = [
        "uploads the video to Upload-Post and publishes it to the requested social accounts",
        f"writes {LEDGER_NAME} next to the export bundle",
    ]
    user_visible_verification = [
        "Open each URL in the publish_log and confirm the right cut, cover and caption went live",
        "For private posts, check the platform's creator dashboard (no public URL exists)",
    ]

    # ---- Cost ----

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Subscription-priced (free plan: 10 uploads/month); no per-call charge.
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 60.0 + 20.0 * len(inputs.get("platforms") or [])

    # ---- HTTP ----

    @staticmethod
    def _api_key() -> Optional[str]:
        return os.environ.get(API_KEY_ENV) or None

    @staticmethod
    def _headers(api_key: str) -> dict[str, str]:
        # Upload-Post API keys use the "Apikey" scheme, not "Bearer".
        return {"Authorization": f"Apikey {api_key}"}

    @staticmethod
    def _raise_for(resp: Any) -> dict[str, Any]:
        try:
            body = resp.json()
        except ValueError:
            body = {}
        if resp.status_code >= 400:
            message = body.get("message") or body.get("error") if isinstance(body, dict) else None
            raise UploadPostError(f"HTTP {resp.status_code}: {message or resp.text[:200]}", resp.status_code)
        return body if isinstance(body, dict) else {}

    def _get(self, api_key: str, path: str, params: Optional[dict] = None) -> dict[str, Any]:
        import requests

        resp = requests.get(f"{API_BASE}{path}", headers=self._headers(api_key), params=params, timeout=API_TIMEOUT)
        return self._raise_for(resp)

    def _get_status(self, api_key: str, request_id: str) -> Optional[dict[str, Any]]:
        """Status for a request id, or None if Upload-Post has never seen it."""
        try:
            return self._get(api_key, "/api/uploadposts/status", {"request_id": request_id})
        except UploadPostError as exc:
            if exc.status == 404:
                return None
            raise

    def _connected_platforms(self, api_key: str, profile: str) -> list[str]:
        body = self._get(api_key, f"/api/uploadposts/users/{profile}")
        accounts = (body.get("profile") or body).get("social_accounts") or {}
        return sorted(p for p, account in accounts.items() if account)

    def _submit(self, api_key: str, request_id: str, form: list, video: Path, thumbnail: Optional[Path]) -> dict:
        import requests

        headers = {**self._headers(api_key), "Idempotency-Key": request_id}
        with ExitStack() as stack:
            files = [("video", (video.name, stack.enter_context(open(video, "rb")), "video/mp4"))]
            if thumbnail:
                mime = mimetypes.guess_type(thumbnail.name)[0] or "image/png"
                files.append(("thumbnail", (thumbnail.name, stack.enter_context(open(thumbnail, "rb")), mime)))
            resp = requests.post(
                f"{API_BASE}/api/upload", headers=headers, data=form, files=files, timeout=UPLOAD_TIMEOUT
            )
        return self._raise_for(resp)

    def _wait(self, api_key: str, request_id: str, wait_seconds: int) -> dict[str, Any]:
        start = time.monotonic()
        deadline = start + wait_seconds
        while True:
            status = self._get_status(api_key, request_id)
            if status is None:
                if time.monotonic() - start >= min(ARRIVAL_GRACE_SECONDS, wait_seconds):
                    return {"status": "not_found", "results": []}
                status = {"status": "pending", "results": []}
            elif status.get("status") in FINAL_STATES:
                return status
            if time.monotonic() >= deadline:
                return status
            time.sleep(POLL_INTERVAL_SECONDS)

    # ---- Request construction ----

    @staticmethod
    def _caption(title: str, hashtags: list[str]) -> str:
        tags = [h if h.startswith("#") else f"#{h}" for h in hashtags if h]
        missing = [t for t in tags if t.lower() not in title.lower()]
        return " ".join([title, *missing]) if missing else title

    def _plan(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Validate inputs and derive everything the publish depends on. No network."""
        video = Path(inputs["video_path"]).expanduser()
        if not video.is_file():
            raise ValueError(f"video_path not found: {video}")
        if video.stat().st_size == 0:
            raise ValueError(f"video_path is empty: {video}")

        thumbnail = None
        if inputs.get("thumbnail_path"):
            thumbnail = Path(inputs["thumbnail_path"]).expanduser()
            if not thumbnail.is_file():
                raise ValueError(f"thumbnail_path provided but not found: {thumbnail}")

        platforms: list[str] = []
        for p in inputs.get("platforms") or []:
            p = "x" if p == "twitter" else p
            if p not in VIDEO_PLATFORMS:
                raise ValueError(f"unsupported platform {p!r}; choose from {', '.join(VIDEO_PLATFORMS)}")
            if p not in platforms:
                platforms.append(p)
        if not platforms:
            raise ValueError("platforms must list at least one target")

        title = (inputs.get("title") or "").strip()
        if not title:
            raise ValueError("title is required")
        if "youtube" in platforms and len(title) > 100:
            raise ValueError(f"title is {len(title)} chars; YouTube allows 100")
        if "pinterest" in platforms and not inputs.get("pinterest_board_id"):
            raise ValueError("pinterest_board_id is required for Pinterest")

        visibility = inputs.get("visibility")
        if visibility in ("private", "unlisted"):
            no_mode = [p for p in platforms if p not in PRIVATE_CAPABLE or (p == "tiktok" and visibility == "unlisted")]
            if no_mode:
                raise ValueError(
                    f"visibility={visibility!r} can't be honoured on {', '.join(no_mode)} — those posts would be "
                    "public. Drop them or publish publicly."
                )

        profile = inputs.get("profile") or os.environ.get(PROFILE_ENV)
        if not profile:
            raise ValueError(f"profile is required (or set {PROFILE_ENV})")

        hashtags = list(inputs.get("hashtags") or [])
        caption = self._caption(title, hashtags)
        description = inputs.get("description") or ""
        tags = list(inputs.get("tags") or [])
        attempt = int(inputs.get("attempt") or 1)

        form: list[tuple[str, str]] = [
            ("user", profile),
            ("title", caption),
            ("async_upload", "true"),
            *[("platform[]", p) for p in platforms],
        ]
        if description:
            form.append(("description", description))
        if inputs.get("ai_generated"):
            form.append(("is_ai_generated", "true"))
        youtube_privacy = None
        if "youtube" in platforms:
            youtube_privacy = visibility or "private"
            form.append(("privacyStatus", youtube_privacy))
            form += [("tags[]", t) for t in tags]
        tiktok_privacy = None
        if "tiktok" in platforms:
            tiktok_privacy = inputs.get("tiktok_privacy_level") or TIKTOK_PRIVACY.get(visibility or "")
            if tiktok_privacy:
                form.append(("privacy_level", tiktok_privacy))
        if "pinterest" in platforms:
            form.append(("pinterest_board_id", inputs["pinterest_board_id"]))

        hashes = {
            "video_sha256": _sha256_file(video),
            "thumbnail_sha256": _sha256_file(thumbnail) if thumbnail else None,
            "caption_sha256": _sha256_text(caption),
        }
        # Everything that changes what goes live is part of the id; nothing else is.
        fingerprint = {
            **hashes,
            "form": sorted(form),
            "attempt": attempt,
        }
        request_id = "om-" + hashlib.sha256(json.dumps(fingerprint, sort_keys=True).encode()).hexdigest()[:32]
        form.append(("request_id", request_id))

        return {
            "video": video,
            "thumbnail": thumbnail,
            "platforms": platforms,
            "profile": profile,
            "title": title,
            "caption": caption,
            "description": description,
            "hashtags": hashtags,
            "youtube_privacy": youtube_privacy,
            "tiktok_privacy": tiktok_privacy,
            "visibility": visibility,
            "attempt": attempt,
            "hashes": hashes,
            "request_id": request_id,
            "form": form,
            "ledger": self._ledger_path(inputs, video),
        }

    # ---- Ledger (stale-publish guard) ----

    @staticmethod
    def _ledger_path(inputs: dict[str, Any], video: Path) -> Path:
        if inputs.get("ledger_path"):
            return Path(inputs["ledger_path"]).expanduser()
        from tools.publishers.export_bundle import ExportBundle

        project = ExportBundle._infer_project_name(video)
        return ExportBundle._default_export_dir(video, project) / LEDGER_NAME

    @staticmethod
    def _read_ledger(path: Path) -> list[dict[str, Any]]:
        """Submissions recorded so far. A missing ledger is an empty history; an
        existing one that cannot be read or parsed is NOT — see LedgerError."""
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return []
        except OSError as exc:
            raise LedgerError(path, f"cannot read: {exc}") from exc
        try:
            doc = json.loads(text)
        except ValueError as exc:
            raise LedgerError(path, f"invalid JSON: {exc}") from exc
        submissions = doc.get("submissions") if isinstance(doc, dict) else None
        if not isinstance(submissions, list) or not all(isinstance(s, dict) for s in submissions):
            raise LedgerError(path, "unexpected structure")
        return submissions

    @staticmethod
    def _write_ledger(path: Path, submissions: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": 1, "submissions": submissions}, indent=2), encoding="utf-8")
        tmp.replace(path)

    def _record(self, plan: dict[str, Any], state: str, **extra: Any) -> None:
        submissions = self._read_ledger(plan["ledger"])
        entry = next((s for s in submissions if s.get("request_id") == plan["request_id"]), None)
        if entry is None:
            entry = {
                "request_id": plan["request_id"],
                "profile": plan["profile"],
                "platforms": plan["platforms"],
                "video_path": str(plan["video"].resolve()),
                **plan["hashes"],
                "submitted_at": datetime.now(timezone.utc).isoformat(),
            }
            submissions.append(entry)
        entry["state"] = state
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()
        entry.update(extra)
        self._write_ledger(plan["ledger"], submissions)

    def _conflicts(self, api_key: Optional[str], plan: dict[str, Any]) -> list[dict[str, Any]]:
        """Earlier submissions of this render (same bytes or same file) with different inputs
        that are live or may still go live on an overlapping platform."""
        video_path = str(plan["video"].resolve())
        conflicts = []
        for sub in self._read_ledger(plan["ledger"]):
            if sub.get("request_id") == plan["request_id"] or sub.get("profile") != plan["profile"]:
                continue
            if sub.get("video_sha256") != plan["hashes"]["video_sha256"] and sub.get("video_path") != video_path:
                continue
            overlap = sorted(set(sub.get("platforms") or []) & set(plan["platforms"]))
            if not overlap or sub.get("state") == "failed":
                continue
            state = sub.get("state") or "unknown"
            if api_key:
                remote = self._get_status(api_key, sub["request_id"])
                if remote is None:
                    # Never reached Upload-Post: only a risk while the ledger says it may be in flight.
                    if state == "failed":
                        continue
                    state = "unknown"
                else:
                    results = self._normalize(remote)
                    alive = {r["platform"] for r in results if r["status"] not in ("failed", "skipped")}
                    if remote.get("status") in FINAL_STATES and not alive & set(overlap):
                        continue
                    state = remote.get("status") or state
            conflicts.append({"request_id": sub["request_id"], "state": state, "platforms": overlap})
        return conflicts

    # ---- Results ----

    @staticmethod
    def _normalize(status: dict[str, Any]) -> list[dict[str, Any]]:
        out = []
        for r in status.get("results") or []:
            if r.get("skipped"):
                state = "skipped"
            elif r.get("status") in ("queued", "processing", "retryable"):
                state = r["status"]
            else:
                state = "completed" if r.get("success") else "failed"
            post_id = r.get("platform_post_id") or r.get("video_id")
            raw_url = r.get("post_url") or r.get("url")
            url = raw_url if isinstance(raw_url, str) and raw_url.startswith("http") else None
            if not url and r.get("platform") == "youtube" and post_id:
                url = f"https://www.youtube.com/watch?v={post_id}"  # also valid for private videos
            out.append({
                "platform": r.get("platform"),
                "status": state,
                "url": url,
                "post_id": post_id,
                # Platforms return prose instead of a URL for private posts, e.g.
                # "Post uploaded as Private. No public URL available."
                "note": raw_url if isinstance(raw_url, str) and not raw_url.startswith("http") else None,
                "error": (r.get("error_message") or r.get("error")) if state not in ("completed",) else None,
                "inbox": bool(r.get("fallback_to_inbox")),
            })
        return out

    def _publish_log(self, plan: dict[str, Any], status: dict[str, Any], resumed: bool) -> dict[str, Any]:
        timestamp = datetime.now(timezone.utc).isoformat()
        by_platform = {r["platform"]: r for r in self._normalize(status)}
        entries = []
        for platform in plan["platforms"]:
            r = by_platform.get(platform)
            entry: dict[str, Any] = {
                "platform": platform,
                "timestamp": timestamp,
                "metadata_used": {
                    "title": plan["caption"],
                    "description": plan["description"],
                    "hashtags": plan["hashtags"],
                },
            }
            if r is None or r["status"] in ("queued", "processing", "retryable"):
                entry["status"] = "pending_review"
                entry["error"] = "still processing on Upload-Post — re-run the same publish to resume"
            elif r["status"] == "skipped":
                entry["status"] = "failed"
                entry["error"] = f"skipped: profile '{plan['profile']}' has no {platform} account connected"
            elif r["status"] == "failed":
                entry["status"] = "failed"
                entry["error"] = r["error"] or "failed"
            elif r["inbox"]:
                entry["status"] = "draft"
                entry["error"] = "delivered to the TikTok inbox; publish it from the TikTok app"
            else:
                entry["status"] = "published"
            if r and r["url"]:
                entry["url"] = r["url"]
            if r and r["post_id"]:
                entry["video_id"] = str(r["post_id"])
            visibility = self._effective_visibility(plan, platform)
            if visibility:
                entry["visibility"] = visibility
            entries.append(entry)

        return {
            "version": "1.0",
            "entries": entries,
            "metadata": {
                "provider": "upload_post",
                "request_id": plan["request_id"],
                "profile": plan["profile"],
                "attempt": plan["attempt"],
                "resumed_existing_request": resumed,
                "upload_post_status": status.get("status"),
                "caption_sent": plan["caption"],
                "input_hashes": plan["hashes"],
                "notes": {r["platform"]: r["note"] for r in by_platform.values() if r.get("note")},
            },
        }

    @staticmethod
    def _effective_visibility(plan: dict[str, Any], platform: str) -> Optional[str]:
        if platform == "youtube":
            return plan["youtube_privacy"]
        if platform == "tiktok":
            return {"SELF_ONLY": "private", "PUBLIC_TO_EVERYONE": "public"}.get(plan["tiktok_privacy"] or "")
        return "public"

    # ---- Preflight ----

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Validate, fingerprint and check the account. Never uploads."""
        result: dict[str, Any] = {
            "tool": self.name,
            "status": self.get_status().value,
            "estimated_cost_usd": self.estimate_cost(inputs),
            "would_execute": False,
        }
        try:
            plan = self._plan(inputs)
        except ValueError as exc:
            result["error"] = str(exc)
            return result

        result.update({
            "request_id": plan["request_id"],
            "platforms": plan["platforms"],
            "profile": plan["profile"],
            "caption": plan["caption"],
            "input_hashes": plan["hashes"],
            "ledger_path": str(plan["ledger"]),
        })
        api_key = self._api_key()
        if not api_key:
            result["error"] = f"{API_KEY_ENV} is not set"
            return result
        try:
            connected = self._connected_platforms(api_key, plan["profile"])
            existing = self._get_status(api_key, plan["request_id"])
            conflicts = self._conflicts(api_key, plan)
        except Exception as exc:  # network / auth — report, don't raise
            result["error"] = str(exc)
            return result
        missing = [p for p in plan["platforms"] if p not in connected]
        result.update({
            "connected_platforms": connected,
            "missing_platforms": missing,
            "already_submitted": existing is not None,
            "ledger_state": self._ledger_state(plan),
            "conflicts": conflicts,
            "would_execute": not conflicts or bool(inputs.get("allow_additional_post")),
        })
        return result

    # ---- Ambiguity handling ----

    def _ledger_entry(self, plan: dict[str, Any]) -> Optional[dict[str, Any]]:
        for sub in self._read_ledger(plan["ledger"]):
            if sub.get("request_id") == plan["request_id"]:
                return sub
        return None

    def _ledger_state(self, plan: dict[str, Any]) -> Optional[str]:
        entry = self._ledger_entry(plan)
        return entry.get("state") if entry else None

    def _completed_result(self, plan: dict[str, Any], entry: dict[str, Any], started: float) -> ToolResult:
        """This exact publish already completed according to the ledger, and Upload-Post
        no longer has the request (status/idempotency retention expired). The local
        record is the durable evidence: return it instead of inferring "never
        published" from the missing remote record and uploading again."""
        results = entry.get("results") or []
        failed = [r for r in results if r.get("status") == "failed"]
        return ToolResult(
            success=not failed,
            data={
                "publish_log": entry.get("publish_log"),
                "request_id": plan["request_id"],
                "resumed": True,
                "resumed_from": "ledger",
                "recorded_at": entry.get("updated_at"),
                "results": results,
                "ledger_path": str(plan["ledger"]),
            },
            error=None if not failed else "; ".join(f"{r['platform']}: {r.get('error')}" for r in failed),
            duration_seconds=round(time.monotonic() - started, 2),
        )

    def _submit_classified(self, api_key: str, plan: dict[str, Any]) -> Any:
        """Send the upload once. Returns the ledger state to record ("submitted" or
        "ambiguous"), or a ToolResult for a definitive rejection (safe to re-send)."""
        import requests

        try:
            body = self._submit(api_key, plan["request_id"], plan["form"], plan["video"], plan["thumbnail"])
        except UploadPostError as exc:
            if exc.status in DEFINITIVE_REJECTIONS:
                self._record(plan, "failed")
                return ToolResult(
                    success=False, error=f"Upload-Post rejected the upload: {exc}",
                    data={"request_id": plan["request_id"]},
                )
            return "ambiguous"  # 5xx and friends: it may have been accepted — poll, never re-send
        except requests.exceptions.ConnectTimeout:
            self._record(plan, "failed")  # never connected, so nothing was sent
            return ToolResult(
                success=False, error="Could not connect to Upload-Post; nothing was sent. Re-running is safe.",
                data={"request_id": plan["request_id"]},
            )
        except requests.RequestException:
            return "ambiguous"  # dropped mid-request: it may have arrived — poll, never re-send
        if not body:
            return "ambiguous"  # 2xx without a JSON body: can't confirm acceptance
        return "submitted"

    def _ambiguous_result(self, plan: dict[str, Any], previous_state: Optional[str]) -> ToolResult:
        detail = (
            f"A previous run of this exact publish ended in state {previous_state!r}"
            if previous_state else "The upload was sent but its outcome could not be confirmed"
        )
        return ToolResult(
            success=False,
            error=(
                f"{detail} and Upload-Post has no record of request {plan['request_id']} yet. It may still have "
                "been accepted, so it was NOT sent again. Check the target accounts: if it went live, you're done; "
                "if nothing went out, re-run with confirm_not_published=true."
            ),
            data={"request_id": plan["request_id"], "ambiguous": True, "ledger_path": str(plan["ledger"])},
        )

    # ---- Execution ----

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if inputs.get("dry_run"):
            return ToolResult(success=True, data={"dry_run": self.dry_run(inputs)})

        try:
            plan = self._plan(inputs)
        except ValueError as exc:
            return ToolResult(success=False, error=str(exc))

        api_key = self._api_key()
        if not api_key:
            return ToolResult(success=False, error=f"{API_KEY_ENV} is not set. {self.install_instructions}")

        started = time.monotonic()
        try:
            existing = self._get_status(api_key, plan["request_id"])
            resumed = existing is not None
            if not resumed:
                conflicts = self._conflicts(api_key, plan)
                if conflicts and not inputs.get("allow_additional_post"):
                    detail = "; ".join(
                        f"{c['request_id']} ({c['state']}) on {', '.join(c['platforms'])}" for c in conflicts
                    )
                    return ToolResult(
                        success=False,
                        error=(
                            "A different version of this render was already submitted and is live or in flight: "
                            f"{detail}. Publishing now would create a second post. Check those posts first; set "
                            "allow_additional_post=true only if a second post is intended."
                        ),
                        data={"conflicts": conflicts, "request_id": plan["request_id"]},
                    )
                # Same request id seen before but unknown to Upload-Post: a previous run may have
                # been accepted without us learning it (5xx, dropped connection, crash). Never
                # upload it again on our own.
                entry = self._ledger_entry(plan)
                previous = entry.get("state") if entry else None
                # Completed locally but gone from the status endpoint: the remote record
                # expired, not the publication. Only an explicit allow_additional_post
                # sends the same publish again.
                if previous == "completed" and not inputs.get("allow_additional_post"):
                    return self._completed_result(plan, entry, started)
                if previous in UNRESOLVED_STATES and not inputs.get("confirm_not_published"):
                    return self._ambiguous_result(plan, previous_state=previous)
                # Recorded before the upload so an interruption mid-request is still visible next run.
                self._record(plan, "submitting")
                outcome = self._submit_classified(api_key, plan)
                if isinstance(outcome, ToolResult):
                    return outcome
                self._record(plan, outcome)

            status = self._wait(api_key, plan["request_id"], int(inputs.get("wait_seconds", DEFAULT_WAIT_SECONDS)))
        except LedgerError as exc:
            return ToolResult(
                success=False, error=str(exc),
                data={"request_id": plan["request_id"], "ledger_path": str(exc.path), "ledger_unreadable": True},
            )
        except UploadPostError as exc:
            return ToolResult(success=False, error=f"Upload-Post: {exc}", data={"request_id": plan["request_id"]})
        except Exception as exc:
            import requests

            if not isinstance(exc, requests.RequestException):
                raise
            return ToolResult(
                success=False,
                error=(
                    f"Network error talking to Upload-Post ({exc}). Nothing was re-sent; re-run the same "
                    "publish to resume it."
                ),
                data={"request_id": plan["request_id"]},
            )

        final = status.get("status")
        if final == "not_found":
            # Sent (or possibly sent) but not visible on the status endpoint: we can't prove
            # either way, so block re-sending until the user checks.
            self._record(plan, "ambiguous")
            return self._ambiguous_result(plan, previous_state=None)
        publish_log = self._publish_log(plan, status, resumed)
        if final in FINAL_STATES:
            # Keep the outcome with the record: a later run can answer from the
            # ledger once Upload-Post has forgotten the request.
            self._record(plan, final, results=self._normalize(status), publish_log=publish_log)
        else:
            self._record(plan, "in_flight")

        try:
            from schemas.artifacts import validate_artifact

            validate_artifact("publish_log", publish_log)
        except Exception as exc:  # pragma: no cover - defensive
            return ToolResult(success=False, error=f"publish_log failed schema validation: {exc}")

        results = self._normalize(status)
        failed = [r for r in results if r["status"] == "failed"]
        published = [e for e in publish_log["entries"] if e["status"] in ("published", "draft")]
        return ToolResult(
            success=bool(published) and not failed,
            data={
                "publish_log": publish_log,
                "request_id": plan["request_id"],
                "resumed": resumed,
                "results": results,
            },
            error=None if published and not failed else "; ".join(
                f"{e['platform']}: {e.get('error')}" for e in publish_log["entries"] if e["status"] != "published"
            ) or None,
            duration_seconds=round(time.monotonic() - started, 2),
        )
