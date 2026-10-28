"""YouTube Data API v3 uploader — the networked PUBLISH-tier tool.

Uploads a finished render to the creator's own channel with their own OAuth client
(client_secret.json from Google Cloud Console). It never publishes directly: the
video goes up as ``private`` (or ``unlisted``), optionally with a ``publishAt``
time so YouTube itself flips it to public later. ``public`` is refused.

A real upload needs an explicit go-ahead: ``confirm=True`` in the tool API, or
``--yes`` / typing YES at the prompt on the command line. ``--dry-run`` validates
everything and prints the exact request without touching the network.

CLI:
    python -m tools.publishers.youtube_upload --metadata out/metadata.json --dry-run
    python -m tools.publishers.youtube_upload --metadata out/metadata.json \\
        --publish-at "2026-10-20 18:00"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

if __package__ in (None, ""):  # allow `python tools/publishers/youtube_upload.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CONFIG_DIR = Path(os.environ.get("OPENMONTAGE_YOUTUBE_DIR", Path.home() / ".openmontage" / "youtube"))
DEFAULT_CLIENT_SECRET = CONFIG_DIR / "client_secret.json"
DEFAULT_TOKEN = CONFIG_DIR / "token.json"
ALLOWED_PRIVACY = ("private", "unlisted")
TITLE_MAX, DESC_MAX_BYTES, TAGS_MAX = 100, 5000, 500
CHUNK = 8 * 1024 * 1024
RETRY_STATUS = {500, 502, 503, 504}


class UploadInputError(ValueError):
    pass


def _tags_length(tags: list[str]) -> int:
    # YouTube counts the comma separators and wraps tags containing spaces in quotes
    return sum(len(t) + (2 if " " in t else 0) for t in tags) + max(len(tags) - 1, 0)


def parse_publish_at(value: str, now: Optional[datetime] = None) -> str:
    """'2026-10-20 18:00' (local time) or full ISO-8601 -> RFC 3339 UTC string."""
    v = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(v)
    except ValueError as exc:
        raise UploadInputError(f"publish_at: не понимаю дату {value!r}, нужен формат 2026-10-20 18:00") from exc
    if dt.tzinfo is None:
        dt = dt.astimezone()  # naive = the computer's local time
    now = now or datetime.now(timezone.utc)
    if dt <= now + timedelta(minutes=15):
        raise UploadInputError("publish_at должен быть минимум на 15 минут в будущем")
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def build_request(inputs: dict[str, Any], now: Optional[datetime] = None) -> dict[str, Any]:
    """Validate inputs and return {"body", "video", "thumbnail"} for videos.insert."""
    meta: dict[str, Any] = {}
    if inputs.get("metadata_path"):
        p = Path(inputs["metadata_path"]).expanduser()
        if not p.is_file():
            raise UploadInputError(f"metadata_path не найден: {p}")
        meta = json.loads(p.read_text(encoding="utf-8"))
    get = lambda k, d=None: inputs.get(k) if inputs.get(k) not in (None, "") else meta.get(k, d)  # noqa: E731

    video = get("video_path") or meta.get("video")
    if not video or not Path(video).expanduser().is_file():
        raise UploadInputError(f"видео не найдено: {video}")
    thumb = get("thumbnail_path") or meta.get("thumbnail")
    if thumb and not Path(thumb).expanduser().is_file():
        raise UploadInputError(f"превью не найдено: {thumb}")

    title = (get("title") or "").strip()
    desc = get("description", "") or ""
    tags = list(get("tags", []) or [])
    if not title:
        raise UploadInputError("нет title")
    if len(title) > TITLE_MAX:
        raise UploadInputError(f"title длиннее {TITLE_MAX} символов ({len(title)})")
    if any(ch in title + desc for ch in "<>"):
        raise UploadInputError("YouTube не принимает символы < и > в title/description")
    if len(desc.encode("utf-8")) > DESC_MAX_BYTES:
        raise UploadInputError(f"description длиннее {DESC_MAX_BYTES} байт")
    if _tags_length(tags) > TAGS_MAX:
        raise UploadInputError(f"теги в сумме длиннее {TAGS_MAX} символов")

    privacy = (inputs.get("privacy") or "private").lower()
    if privacy not in ALLOWED_PRIVACY:
        raise UploadInputError(f"privacy={privacy!r} запрещён: только {', '.join(ALLOWED_PRIVACY)} (публикация — через publish_at)")
    status: dict[str, Any] = {
        "privacyStatus": privacy,
        "selfDeclaredMadeForKids": bool(get("madeForKids", False)),
        "embeddable": True,
    }
    if inputs.get("publish_at"):
        status["privacyStatus"] = "private"  # API requirement for scheduled videos
        status["publishAt"] = parse_publish_at(inputs["publish_at"], now)

    snippet: dict[str, Any] = {"title": title, "description": desc, "tags": tags,
                               "categoryId": str(get("categoryId", "20"))}
    if get("defaultLanguage"):
        snippet["defaultLanguage"] = get("defaultLanguage")
    return {"body": {"snippet": snippet, "status": status},
            "video": str(Path(video).expanduser().resolve()),
            "thumbnail": str(Path(thumb).expanduser().resolve()) if thumb else None}


def _credentials(client_secret: Path, token: Path):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if token.is_file():
        creds = Credentials.from_authorized_user_file(str(token), SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:  # revoked / expired refresh token (7 days in Testing mode)
            creds = None
    if not creds or not creds.valid:
        if not client_secret.is_file():
            raise UploadInputError(f"нет {client_secret} — см. docs/YOUTUBE_UPLOAD.md")
        flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
        creds = flow.run_local_server(port=0, prompt="consent")
    token.parent.mkdir(parents=True, exist_ok=True)
    token.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _resumable(request, log=print):
    from googleapiclient.errors import HttpError

    response, retries = None, 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                log(f"  загружено {int(status.progress() * 100)}%")
        except HttpError as e:
            if e.resp.status not in RETRY_STATUS or retries >= 8:
                raise
            retries += 1
            time.sleep(min(2 ** retries, 60))
        except (ConnectionError, TimeoutError, OSError):
            if retries >= 8:
                raise
            retries += 1
            time.sleep(min(2 ** retries, 60))
    return response


class YouTubeUpload(BaseTool):
    name = "youtube_upload"
    version = "0.1.0"
    tier = ToolTier.PUBLISH
    capability = "publish"
    provider = "youtube"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API

    dependencies = ["python:googleapiclient", "python:google_auth_oauthlib"]
    install_instructions = (
        "pip install google-api-python-client google-auth-oauthlib google-auth-httplib2; "
        f"put your OAuth client_secret.json in {DEFAULT_CLIENT_SECRET} "
        "(see docs/YOUTUBE_UPLOAD.md)."
    )
    capabilities = ["upload_video", "set_thumbnail", "schedule_publish"]
    supports = {"local_offline": False, "free": True, "uploads": True, "public_direct": False}
    best_for = ["uploading a finished render to the creator's own channel as private or scheduled"]
    not_good_for = ["publishing public immediately (refused by design)", "other platforms"]

    input_schema = {
        "type": "object",
        "properties": {
            "metadata_path": {"type": "string", "description": "metadata.json with title/description/tags/video/thumbnail"},
            "video_path": {"type": "string"},
            "thumbnail_path": {"type": "string"},
            "title": {"type": "string"},
            "description": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "privacy": {"type": "string", "enum": list(ALLOWED_PRIVACY), "default": "private"},
            "publish_at": {"type": "string", "description": "Scheduled public time; local time or ISO-8601"},
            "client_secret": {"type": "string"},
            "token_path": {"type": "string"},
            "dry_run": {"type": "boolean", "default": False},
            "confirm": {"type": "boolean", "default": False,
                        "description": "Must be true for a real upload (the user said yes)."},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {"publish_log": {"type": "object"}, "request": {"type": "object"},
                       "video_id": {"type": "string"}, "url": {"type": "string"}},
    }
    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=0, network_required=True)
    side_effects = ["uploads a private or scheduled video (and thumbnail) to the user's YouTube channel",
                    "stores an OAuth token in ~/.openmontage/youtube/token.json"]
    user_visible_verification = ["Open YouTube Studio and check the video is Private/Scheduled with the right title"]

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        req = build_request(inputs)
        return {"tool": self.name, "would_execute": False, "request": req,
                "status": self.get_status().value, "estimated_cost_usd": 0.0}

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        try:
            req = build_request(inputs)
        except UploadInputError as exc:
            return ToolResult(success=False, error=str(exc))
        if inputs.get("dry_run"):
            return ToolResult(success=True, data={"dry_run": True, "request": req})
        if not inputs.get("confirm"):
            return ToolResult(success=False, error="Загрузка требует явного подтверждения (confirm=True).")

        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        stamp = datetime.now(timezone.utc).isoformat()
        try:
            creds = _credentials(Path(inputs.get("client_secret") or DEFAULT_CLIENT_SECRET).expanduser(),
                                 Path(inputs.get("token_path") or DEFAULT_TOKEN).expanduser())
            yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
            media = MediaFileUpload(req["video"], chunksize=CHUNK, resumable=True, mimetype="video/*")
            resp = _resumable(yt.videos().insert(part="snippet,status", body=req["body"], media_body=media))
            vid = resp["id"]
            thumb_err = None
            if req["thumbnail"]:
                try:
                    yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(req["thumbnail"])).execute()
                except Exception as exc:  # e.g. channel not verified for custom thumbnails
                    thumb_err = str(exc)
        except Exception as exc:
            return ToolResult(success=False, error=f"YouTube upload failed: {exc}")

        url = f"https://youtu.be/{vid}"
        snip = req["body"]["snippet"]
        entry = {"platform": "youtube", "status": "draft", "url": url, "video_id": vid,
                 "visibility": req["body"]["status"]["privacyStatus"], "timestamp": stamp,
                 "metadata_used": {"title": snip["title"], "description": snip["description"]}}
        if thumb_err:
            entry["error"] = f"thumbnail not set: {thumb_err}"
        return ToolResult(success=True, data={"publish_log": {"version": "1.0", "entries": [entry]},
                                              "video_id": vid, "url": url,
                                              "publish_at": req["body"]["status"].get("publishAt"),
                                              "thumbnail_error": thumb_err},
                          artifacts=[url])


def main(argv: Optional[list[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Upload to YouTube as private/scheduled (never public directly)")
    ap.add_argument("--metadata", help="metadata.json with title/description/tags/video/thumbnail")
    ap.add_argument("--video")
    ap.add_argument("--thumbnail")
    ap.add_argument("--title")
    ap.add_argument("--privacy", default="private", choices=ALLOWED_PRIVACY)
    ap.add_argument("--publish-at", help='scheduled public time, local: "2026-10-20 18:00"')
    ap.add_argument("--client-secret", default=str(DEFAULT_CLIENT_SECRET))
    ap.add_argument("--token", default=str(DEFAULT_TOKEN))
    ap.add_argument("--dry-run", action="store_true", help="validate and print the request, no network")
    ap.add_argument("--yes", action="store_true", help="skip the YES prompt")
    a = ap.parse_args(argv)

    inputs = {"metadata_path": a.metadata, "video_path": a.video, "thumbnail_path": a.thumbnail,
              "title": a.title, "privacy": a.privacy, "publish_at": a.publish_at,
              "client_secret": a.client_secret, "token_path": a.token}
    try:
        req = build_request(inputs)
    except UploadInputError as exc:
        print(f"ОШИБКА: {exc}")
        return 2
    st, sn = req["body"]["status"], req["body"]["snippet"]
    size = Path(req["video"]).stat().st_size / 2 ** 20
    when = st.get("publishAt")
    if when:
        local = datetime.fromisoformat(when.replace("Z", "+00:00")).astimezone()
        mode = f"ОТЛОЖЕННО: станет публичным {local:%Y-%m-%d %H:%M} (местное время)"
    else:
        mode = f"{st['privacyStatus'].upper()} (никто не увидит, пока вы сами не откроете в Studio)"
    print(f"Видео:   {req['video']} ({size:.0f} МБ)\nПревью:  {req['thumbnail'] or '—'}\n"
          f"Название: {sn['title']}\nТеги:    {len(sn['tags'])} шт.\nРежим:   {mode}")
    if a.dry_run:
        print("\n--dry-run: в YouTube ничего не отправлено. Тело запроса videos.insert:")
        print(json.dumps(req["body"], indent=2, ensure_ascii=False))
        missing = [d for d in YouTubeUpload.dependencies if not _importable(d.split(":", 1)[1])]
        if missing:
            print("\nДля реальной загрузки установите: pip install google-api-python-client google-auth-oauthlib")
        if not Path(a.client_secret).expanduser().is_file():
            print(f"Для реальной загрузки положите client_secret.json в {a.client_secret}")
        return 0
    if not a.yes:
        if not sys.stdin.isatty():
            print("Нет подтверждения: запустите с --yes или в терминале.")
            return 3
        if input("\nЗагрузить на YouTube? Введите YES: ").strip() != "YES":
            print("Отменено.")
            return 1
    res = YouTubeUpload().execute({**inputs, "confirm": True})
    if not res.success:
        print(f"ОШИБКА: {res.error}")
        return 1
    print(f"Загружено: {res.data['url']}  (статус: {st['privacyStatus']}{', запланировано' if when else ''})")
    if res.data.get("thumbnail_error"):
        print(f"Превью не установлено: {res.data['thumbnail_error']}")
    return 0


def _importable(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except ImportError:
        return False


if __name__ == "__main__":
    sys.exit(main())
