"""Tests for the upload_post_publisher tool.

No network: a fake Upload-Post API is patched over ``requests``. Covers the tool
contract, registry discovery, status, validation, the deterministic request id,
a schema-valid publish_log, and the interruption cases the design exists for —
including an interrupted create followed by a corrected cover (the stale-input
failure mode described in #410).
"""

import json
import sys
from pathlib import Path

import pytest
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from schemas.artifacts import validate_artifact
from tools.base_tool import ToolRuntime, ToolStatus, ToolTier
from tools.publishers import upload_post_publisher as upp
from tools.publishers.upload_post_publisher import UploadPostPublisher
from tools.tool_registry import ToolRegistry


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body
        self.text = json.dumps(body)

    def json(self):
        return self._body


class FakeUploadPost:
    """Minimal in-memory Upload-Post: remembers uploads by request id."""

    def __init__(self, connected=("tiktok", "youtube", "instagram")):
        self.connected = set(connected)
        self.requests = {}  # request_id -> status payload
        self.posts = []  # (headers, form) of every POST /api/upload
        self.drop_connection = False  # raise after "receiving" the upload
        self.lose_upload = False  # raise without receiving it
        self.result_for = {}  # platform -> per-platform result override
        self.reply_status = None  # answer POST with this HTTP status (e.g. 503)
        self.reply_body = None  # override the POST body (e.g. "" for an empty 2xx)
        self.accept = True  # whether the fake records the upload before replying
        self.connect_timeout = False

    def get(self, url, headers=None, params=None, timeout=None):
        if url.endswith("/api/uploadposts/status"):
            status = self.requests.get(params["request_id"])
            if status is None:
                return FakeResponse(404, {"status": "not_found", "message": "No upload request found with this ID"})
            return FakeResponse(200, status)
        if "/api/uploadposts/users/" in url:
            accounts = {p: ({"handle": p} if p in self.connected else None) for p in upp.VIDEO_PLATFORMS}
            return FakeResponse(200, {"success": True, "profile": {"social_accounts": accounts}})
        raise AssertionError(f"unexpected GET {url}")

    def post(self, url, headers=None, data=None, files=None, timeout=None):
        assert url.endswith("/api/upload")
        form = list(data)
        self.posts.append((headers, form))
        if self.connect_timeout:
            raise requests.exceptions.ConnectTimeout("could not connect")
        if self.lose_upload:
            raise requests.ConnectionError("connection reset before the body was sent")
        request_id = dict(form)["request_id"]
        platforms = [v for k, v in form if k == "platform[]"]
        results = []
        for p in platforms:
            if p not in self.connected:
                results.append({"platform": p, "success": False, "skipped": True})
            else:
                results.append(self.result_for.get(p) or {
                    "platform": p,
                    "success": True,
                    "platform_post_id": f"{p}-id",
                    "post_url": f"https://{p}.example/post/{p}-id" if p != "youtube" else
                    "Post uploaded as Private. No public URL available.",
                })
        if self.accept:
            self.requests[request_id] = {"status": "completed", "completed": len(results), "total": len(results),
                                         "results": results}
        if self.drop_connection:
            raise requests.ConnectionError("connection reset after the upload was received")
        if self.reply_status is not None:
            return FakeResponse(self.reply_status, {"message": "Service Unavailable"})
        if self.reply_body is not None:
            return EmptyResponse()
        return FakeResponse(200, {"success": True, "request_id": request_id})


class EmptyResponse:
    status_code = 200
    text = ""

    def json(self):
        raise ValueError("no JSON body")


@pytest.fixture
def api(monkeypatch):
    fake = FakeUploadPost()
    monkeypatch.setattr(requests, "get", fake.get)
    monkeypatch.setattr(requests, "post", fake.post)
    monkeypatch.setattr(upp.time, "sleep", lambda s: None)
    monkeypatch.setenv(upp.API_KEY_ENV, "test-key")
    monkeypatch.setenv(upp.PROFILE_ENV, "creator")
    return fake


@pytest.fixture
def render(tmp_path):
    video = tmp_path / "projects" / "demo" / "renders" / "final.mp4"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42final-cut")
    cover = tmp_path / "cover_ink.png"
    cover.write_bytes(b"\x89PNG ink cover")
    return video, cover


def _inputs(video, **extra):
    return {"video_path": str(video), "title": "Vector DBs in 60s", "platforms": ["tiktok", "youtube"], **extra}


# ---- Contract ----

def test_contract_metadata():
    tool = UploadPostPublisher()
    info = tool.get_info()
    assert info["name"] == "upload_post_publisher"
    assert info["tier"] == ToolTier.PUBLISH.value
    assert info["capability"] == "publish"
    assert info["provider"] == "upload_post"
    assert info["runtime"] == ToolRuntime.API.value
    assert info["resource_profile"]["network_required"] is True
    assert tool.retry_policy.max_retries == 0  # a blind retry is how double posts happen
    assert f"env:{upp.API_KEY_ENV}" in tool.dependencies
    assert tool.estimate_cost({}) == 0.0


def test_registry_discovers_it_under_publish():
    registry = ToolRegistry()
    registry.discover("tools.publishers")
    assert "upload_post_publisher" in registry.list_all()
    assert registry.get("upload_post_publisher").capability == "publish"


def test_status_follows_api_key(monkeypatch):
    monkeypatch.delenv(upp.API_KEY_ENV, raising=False)
    assert UploadPostPublisher().get_status() == ToolStatus.UNAVAILABLE
    monkeypatch.setenv(upp.API_KEY_ENV, "k")
    assert UploadPostPublisher().get_status() == ToolStatus.AVAILABLE


def test_missing_key_is_reported_not_raised(monkeypatch, render):
    monkeypatch.delenv(upp.API_KEY_ENV, raising=False)
    monkeypatch.setenv(upp.PROFILE_ENV, "creator")
    result = UploadPostPublisher().execute(_inputs(render[0]))
    assert result.success is False and upp.API_KEY_ENV in result.error


# ---- Validation (no network) ----

@pytest.mark.parametrize("extra, message", [
    ({"platforms": ["myspace"]}, "unsupported platform"),
    ({"platforms": ["instagram"], "visibility": "private"}, "can't be honoured on instagram"),
    ({"platforms": ["tiktok"], "visibility": "unlisted"}, "can't be honoured on tiktok"),
    ({"platforms": ["pinterest"]}, "pinterest_board_id"),
    ({"title": "x" * 101}, "YouTube allows 100"),
    ({"thumbnail_path": "/nope.png"}, "thumbnail_path provided but not found"),
])
def test_validation(api, render, extra, message):
    result = UploadPostPublisher().execute(_inputs(render[0], **extra))
    assert result.success is False and message in result.error
    assert api.posts == []


# ---- Request identity ----

def test_request_id_is_a_hash_of_what_goes_live(api, render, tmp_path):
    video, cover = render
    tool = UploadPostPublisher()
    base = tool._plan(_inputs(video, thumbnail_path=str(cover)))["request_id"]
    assert tool._plan(_inputs(video, thumbnail_path=str(cover)))["request_id"] == base

    other_cover = tmp_path / "cover_bone.png"
    other_cover.write_bytes(b"\x89PNG bone cover")
    assert tool._plan(_inputs(video, thumbnail_path=str(other_cover)))["request_id"] != base
    assert tool._plan(_inputs(video, thumbnail_path=str(cover), title="New caption"))["request_id"] != base
    assert tool._plan(_inputs(video, thumbnail_path=str(cover), attempt=2))["request_id"] != base


# ---- Publishing ----

def test_publish_returns_schema_valid_log(api, render):
    video, cover = render
    result = UploadPostPublisher().execute(
        _inputs(video, thumbnail_path=str(cover), hashtags=["ai", "#explainer"], tags=["vector db"])
    )
    assert result.success, result.error
    log = result.data["publish_log"]
    validate_artifact("publish_log", log)

    headers, form = api.posts[0]
    fields = dict(form)
    assert headers["Idempotency-Key"] == fields["request_id"] == result.data["request_id"]
    assert headers["Authorization"] == "Apikey test-key"
    assert fields["title"] == "Vector DBs in 60s #ai #explainer"
    assert fields["privacyStatus"] == "private"  # YouTube defaults to private
    assert "privacy_level" not in fields  # TikTok keeps the account's own default
    assert ("tags[]", "vector db") in form

    entries = {e["platform"]: e for e in log["entries"]}
    assert entries["tiktok"]["status"] == "published"
    assert entries["tiktok"]["url"] == "https://tiktok.example/post/tiktok-id"
    assert entries["youtube"]["url"] == "https://www.youtube.com/watch?v=youtube-id"
    assert entries["youtube"]["visibility"] == "private"
    meta = log["metadata"]
    assert meta["input_hashes"]["video_sha256"] and meta["input_hashes"]["thumbnail_sha256"]
    assert meta["caption_sent"] == fields["title"]
    assert meta["notes"]["youtube"].startswith("Post uploaded as Private")


def test_skipped_failed_and_inbox_are_reported_per_platform(api, render):
    api.connected = {"tiktok", "youtube"}
    api.result_for["youtube"] = {"platform": "youtube", "success": False, "error_message": "token expired"}
    api.result_for["tiktok"] = {"platform": "tiktok", "success": True, "fallback_to_inbox": True}
    result = UploadPostPublisher().execute(_inputs(render[0], platforms=["tiktok", "youtube", "instagram"]))
    entries = {e["platform"]: e for e in result.data["publish_log"]["entries"]}
    assert entries["tiktok"]["status"] == "draft"
    assert entries["youtube"] == {**entries["youtube"], "status": "failed", "error": "token expired"}
    assert entries["instagram"]["status"] == "failed" and "skipped" in entries["instagram"]["error"]
    assert result.success is False
    validate_artifact("publish_log", result.data["publish_log"])


# ---- Interruptions ----

def test_dropped_connection_polls_instead_of_resending(api, render):
    api.drop_connection = True
    result = UploadPostPublisher().execute(_inputs(render[0]))
    assert result.success, result.error
    assert len(api.posts) == 1


def test_rerun_after_interruption_resumes_without_uploading(api, render):
    api.drop_connection = True
    first = UploadPostPublisher().execute(_inputs(render[0]))
    api.drop_connection = False
    second = UploadPostPublisher().execute(_inputs(render[0]))
    assert second.success and second.data["resumed"] is True
    assert second.data["request_id"] == first.data["request_id"]
    assert len(api.posts) == 1  # the re-run never uploaded again


def test_dropped_upload_with_no_record_is_ambiguous_not_resent(api, render):
    api.lose_upload = True
    result = UploadPostPublisher().execute(_inputs(render[0], wait_seconds=0))
    assert result.success is False and result.data["ambiguous"] is True
    assert "NOT sent again" in result.error
    api.lose_upload = False
    again = UploadPostPublisher().execute(_inputs(render[0]))
    assert again.success is False and again.data["ambiguous"] is True
    assert len(api.posts) == 1
    confirmed = UploadPostPublisher().execute(_inputs(render[0], confirm_not_published=True))
    assert confirmed.success and len(api.posts) == 2
    assert api.posts[0][1] == api.posts[1][1]  # same request, same id


@pytest.mark.parametrize("mode", ["http_503", "empty_2xx"])
def test_ambiguous_submit_is_never_resent(api, render, mode):
    """A 5xx or an empty 2xx doesn't prove the upload was rejected. With no record on
    Upload-Post, a re-run — even from a fresh process reading the ledger — must not upload again."""
    api.accept = False
    if mode == "http_503":
        api.reply_status = 503
    else:
        api.reply_body = ""
    first = UploadPostPublisher().execute(_inputs(render[0], wait_seconds=0))
    assert first.success is False and first.data["ambiguous"] is True
    ledger = json.loads(Path(first.data["ledger_path"]).read_text())
    assert ledger["submissions"][0]["state"] == "ambiguous"

    api.reply_status = api.reply_body = None
    api.accept = True
    rerun = UploadPostPublisher().execute(_inputs(render[0]))  # new instance: state comes from disk
    assert rerun.success is False and rerun.data["ambiguous"] is True
    assert len(api.posts) == 1


def test_503_after_acceptance_is_tracked_not_failed(api, render):
    api.reply_status = 503  # accepted server-side, then the proxy answered 503
    result = UploadPostPublisher().execute(_inputs(render[0]))
    assert result.success, result.error
    again = UploadPostPublisher().execute(_inputs(render[0]))
    assert again.data["resumed"] is True and len(api.posts) == 1


def test_crash_mid_upload_blocks_rerun_after_restart(api, render):
    """The process died between recording 'submitting' and learning the outcome."""
    tool = UploadPostPublisher()
    plan = tool._plan(_inputs(render[0]))
    tool._record(plan, "submitting")
    result = UploadPostPublisher().execute(_inputs(render[0]))
    assert result.success is False and result.data["ambiguous"] is True
    assert api.posts == []


@pytest.mark.parametrize("status", [400, 401, 403, 422])
def test_definitive_rejection_allows_resend(api, render, status):
    api.accept = False
    api.reply_status = status
    first = UploadPostPublisher().execute(_inputs(render[0]))
    assert first.success is False and "rejected" in first.error
    api.reply_status = None
    api.accept = True
    again = UploadPostPublisher().execute(_inputs(render[0]))
    assert again.success and len(api.posts) == 2


def test_connect_timeout_allows_resend(api, render):
    api.connect_timeout = True
    first = UploadPostPublisher().execute(_inputs(render[0]))
    assert first.success is False and "nothing was sent" in first.error
    api.connect_timeout = False
    assert UploadPostPublisher().execute(_inputs(render[0])).success and len(api.posts) == 2


def test_corrected_cover_after_interrupted_create_is_blocked(api, render, tmp_path):
    """#410: a create with the old cover is interrupted, but the upload arrives and goes
    live; the user re-runs with a corrected cover. That must not silently post twice."""
    video, ink = render
    api.drop_connection = True
    stale = UploadPostPublisher().execute(_inputs(video, thumbnail_path=str(ink)))
    assert stale.data["request_id"]
    api.drop_connection = False

    bone = tmp_path / "cover_bone.png"
    bone.write_bytes(b"\x89PNG bone cover")
    corrected = UploadPostPublisher().execute(_inputs(video, thumbnail_path=str(bone)))
    assert corrected.success is False
    assert "second post" in corrected.error
    assert corrected.data["conflicts"][0]["request_id"] == stale.data["request_id"]
    assert len(api.posts) == 1

    explicit = UploadPostPublisher().execute(
        _inputs(video, thumbnail_path=str(bone), allow_additional_post=True)
    )
    assert explicit.success and len(api.posts) == 2


def test_failed_attempt_does_not_block_a_retry(api, render):
    api.result_for["tiktok"] = {"platform": "tiktok", "success": False, "error_message": "boom"}
    api.result_for["youtube"] = {"platform": "youtube", "success": False, "error_message": "boom"}
    api.requests.clear()
    first = UploadPostPublisher().execute(_inputs(render[0]))
    assert first.success is False
    api.result_for.clear()
    retry = UploadPostPublisher().execute(_inputs(render[0], attempt=2))
    assert retry.success, retry.error
    assert retry.data["request_id"] != first.data["request_id"]


def test_dry_run_checks_account_and_never_uploads(api, render):
    api.connected = {"tiktok"}
    report = UploadPostPublisher().dry_run(_inputs(render[0]))
    assert report["missing_platforms"] == ["youtube"]
    assert report["already_submitted"] is False and report["conflicts"] == []
    assert UploadPostPublisher().execute(_inputs(render[0], dry_run=True)).success
    assert api.posts == []


# ---- Restart cases: the ledger is the durable evidence ----


def test_completed_publish_is_not_resent_after_remote_record_expires(api, render):
    """Completed locally, then Upload-Post forgets the request (status/idempotency
    retention expired, status returns 404). A re-run must answer from the ledger,
    never upload again."""
    first = UploadPostPublisher().execute(_inputs(render[0]))
    assert first.success and len(api.posts) == 1
    api.requests.clear()  # remote retention expired: GET status -> 404

    rerun = UploadPostPublisher().execute(_inputs(render[0]))  # new instance, state from disk
    assert rerun.success, rerun.error
    assert rerun.data["resumed"] is True and rerun.data["resumed_from"] == "ledger"
    assert rerun.data["request_id"] == first.data["request_id"]
    assert [r["platform"] for r in rerun.data["results"]] == [r["platform"] for r in first.data["results"]]
    assert rerun.data["publish_log"]["entries"] == first.data["publish_log"]["entries"]
    assert len(api.posts) == 1

    # A second post of the same publish needs deliberate authorization.
    again = UploadPostPublisher().execute(_inputs(render[0], allow_additional_post=True))
    assert again.success and again.data["resumed"] is False
    assert len(api.posts) == 2


def test_completed_publish_with_a_platform_failure_replays_the_failure(api, render):
    api.result_for["youtube"] = {"platform": "youtube", "success": False, "error_message": "quota"}
    first = UploadPostPublisher().execute(_inputs(render[0]))
    assert first.success is False and "youtube" in first.error
    api.requests.clear()
    rerun = UploadPostPublisher().execute(_inputs(render[0]))
    assert rerun.success is False and "youtube" in rerun.error
    assert rerun.data["resumed_from"] == "ledger" and len(api.posts) == 1


def test_corrupt_ledger_blocks_publishing(api, render):
    """A damaged ledger may be the only record of an accepted upload: fail closed."""
    tool = UploadPostPublisher()
    plan = tool._plan(_inputs(render[0]))
    plan["ledger"].parent.mkdir(parents=True, exist_ok=True)
    plan["ledger"].write_text("{\"version\": 1, \"submissions\": [{\"request_id\": ", encoding="utf-8")

    result = UploadPostPublisher().execute(_inputs(render[0]))
    assert result.success is False and result.data["ledger_unreadable"] is True
    assert "ledger" in result.error and "nothing was sent" in result.error
    assert api.posts == []
    assert plan["ledger"].read_text(encoding="utf-8").startswith("{\"version\": 1")  # untouched

    dry = UploadPostPublisher().execute(_inputs(render[0], dry_run=True))
    assert "ledger" in (dry.data["dry_run"].get("error") or "")

    plan["ledger"].write_text(json.dumps({"version": 1, "submissions": "not-a-list"}), encoding="utf-8")
    result = UploadPostPublisher().execute(_inputs(render[0]))
    assert result.success is False and result.data["ledger_unreadable"] is True and api.posts == []


@pytest.mark.skipif(not hasattr(Path, "chmod") or __import__("os").geteuid() == 0, reason="needs a non-root user")
def test_unreadable_ledger_blocks_publishing(api, render):
    tool = UploadPostPublisher()
    plan = tool._plan(_inputs(render[0]))
    tool._record(plan, "completed")
    plan["ledger"].chmod(0)
    try:
        result = UploadPostPublisher().execute(_inputs(render[0]))
    finally:
        plan["ledger"].chmod(0o600)
    assert result.success is False and result.data["ledger_unreadable"] is True
    assert "cannot read" in result.error and api.posts == []


def test_missing_ledger_is_an_empty_history(api, render):
    tool = UploadPostPublisher()
    plan = tool._plan(_inputs(render[0]))
    assert not plan["ledger"].exists()
    assert tool._read_ledger(plan["ledger"]) == []
    result = UploadPostPublisher().execute(_inputs(render[0]))
    assert result.success and len(api.posts) == 1
