"""HTTP execution engine for relay providers.

Guarantees (the reasons this module exists):

* **A paid submission is never repeated automatically.** Before the submit
  request goes out, a job file is written next to ``output_path``
  (``<output>.relay-job.json``). Any later call for the same output resumes
  that job — polls the existing task id and downloads — instead of paying
  again. A submit whose outcome is unknown (read timeout, gateway 502/504)
  is recorded as ``submit_unknown`` and refuses to resubmit unless the caller
  passes ``confirm_resubmit: true`` after checking the relay dashboard.
* **Polling timeouts are resumable.** A timeout returns ``status: pending``
  with ``job_path`` / ``resume_job``; calling the tool again continues.
* **Results land on disk immediately.** The remote URL is only provenance; the
  file is downloaded the moment the task succeeds (with free retries), and a
  failed download keeps the job in ``succeeded`` so the next call re-downloads
  without resubmitting.
* **Keys stay home.** The key is read from the env var at call time, sent only
  to the relay's own origin (never to CDN result URLs, never across a
  redirect), never written to job files, and redacted from error text.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import mimetypes
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urljoin, urlsplit

from tools.relay.config import RelayModel, is_loopback_url

JOB_VERSION = 1
JOB_SUFFIX = ".relay-job.json"

# Status words relays use. Comparison is case-insensitive.
DEFAULT_SUCCESS = ["succeeded", "success", "completed", "complete", "done", "finished"]
DEFAULT_FAILURE = ["failed", "failure", "error", "cancelled", "canceled", "expired", "rejected"]

# HTTP statuses after which a submit *may* have been accepted and billed.
_AMBIGUOUS_STATUS = {408, 499, 502, 504, 520, 522, 524}
_MODEL_MISSING = re.compile(
    r"model_not_found|not available for this group|model .* does not exist|no available channel|无可用渠道",
    re.I,
)

_IMAGE_MAGIC = (
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"GIF87a", "image/gif", "gif"),
    (b"GIF89a", "image/gif", "gif"),
    (b"BM", "image/bmp", "bmp"),
)


class RelayError(RuntimeError):
    """A relay call failed in a way the caller should see verbatim."""

    def __init__(self, message: str, *, code: str = "relay_error", data: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.data = data or {}


class SubmitUnknown(RelayError):
    """The submit may or may not have been accepted (and billed)."""


class SubmitRejected(RelayError):
    """The relay definitively refused the submission (not billed)."""


# ---------------------------------------------------------------------------
# small utilities
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_path(obj: Any, spec: Optional[str]) -> Any:
    """Read ``a.b.0.c`` from nested JSON; ``|`` separates fallbacks."""
    if not spec:
        return None
    for alternative in str(spec).split("|"):
        node = obj
        ok = True
        for part in alternative.strip().split("."):
            if part == "":
                continue
            if isinstance(node, dict) and part in node:
                node = node[part]
            elif isinstance(node, list) and part.lstrip("-").isdigit() and -len(node) <= int(part) < len(node):
                node = node[int(part)]
            else:
                ok = False
                break
        if ok and node not in (None, ""):
            return node
    return None


_WHOLE_VAR = re.compile(r"^\{\{\s*([a-z_][a-z0-9_]*)\s*\}\}$")
_INLINE_VAR = re.compile(r"\{\{\s*([a-z_][a-z0-9_]*)\s*\}\}")
_DROP = object()


def render_template(node: Any, variables: dict[str, Any]) -> Any:
    """Fill ``{{var}}`` placeholders.

    A string that is exactly one placeholder takes the variable's native type
    (int stays int, list stays list). A key/item whose variable is missing or
    None is dropped, so optional parameters disappear instead of being sent as
    ``null``.
    """

    def walk(value: Any) -> Any:
        if value is None:  # an override of `null` removes a preset field
            return _DROP
        if isinstance(value, dict):
            out = {}
            for k, v in value.items():
                rendered = walk(v)
                if rendered is not _DROP:
                    out[k] = rendered
            return out
        if isinstance(value, list):
            return [r for r in (walk(v) for v in value) if r is not _DROP]
        if isinstance(value, str):
            whole = _WHOLE_VAR.match(value)
            if whole:
                resolved = variables.get(whole.group(1))
                return _DROP if resolved is None else resolved
            missing = False

            def sub(match: re.Match[str]) -> str:
                nonlocal missing
                resolved = variables.get(match.group(1))
                if resolved is None:
                    missing = True
                    return ""
                return str(resolved)

            text = _INLINE_VAR.sub(sub, value)
            return _DROP if missing else text
        return value

    rendered = walk(copy.deepcopy(node))
    return {} if rendered is _DROP else rendered


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fingerprint(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


# ---------------------------------------------------------------------------
# media inputs (first frame, reference images)
# ---------------------------------------------------------------------------


@dataclass
class ImageInput:
    source: str  # original reference (path or URL) — never the bytes
    data: Optional[bytes] = None
    mime: str = "image/png"
    filename: str = "image.png"
    url: Optional[str] = None  # set when the reference was already a URL

    @property
    def digest(self) -> str:
        if self.data is not None:
            return hashlib.sha256(self.data).hexdigest()[:24]
        return hashlib.sha256((self.url or self.source).encode()).hexdigest()[:24]

    def data_uri(self) -> str:
        assert self.data is not None
        return f"data:{self.mime};base64,{base64.b64encode(self.data).decode('ascii')}"

    def b64(self) -> str:
        assert self.data is not None
        return base64.b64encode(self.data).decode("ascii")


def sniff_image(data: bytes) -> Optional[tuple[str, str]]:
    for magic, mime, ext in _IMAGE_MAGIC:
        if data.startswith(magic):
            return mime, ext
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None


def load_image_input(ref: Any, *, max_mb: float = 10.0) -> ImageInput:
    """Accept a local file path, data URI, or http(s) URL."""
    value = str(ref or "").strip()
    if not value:
        raise RelayError("empty image reference", code="bad_image")
    if value.startswith(("http://", "https://")):
        return ImageInput(source=value, url=value)
    if value.startswith("data:"):
        head, _, body = value.partition(",")
        if ";base64" not in head:
            raise RelayError("image data URI must be base64", code="bad_image")
        data = base64.b64decode(body, validate=True)
        source = f"data-uri:{hashlib.sha256(data).hexdigest()[:12]}"
    else:
        path = Path(value).expanduser()
        if not path.is_file():
            raise RelayError(f"image file not found: {value}", code="bad_image")
        data = path.read_bytes()
        source = str(path.resolve())
    if len(data) > max_mb * 1024 * 1024:
        raise RelayError(f"image exceeds {max_mb} MB limit: {source}", code="bad_image")
    sniffed = sniff_image(data)
    if not sniffed:
        raise RelayError(f"not a PNG/JPEG/WEBP/GIF/BMP image: {source}", code="bad_image")
    mime, ext = sniffed
    return ImageInput(source=source, data=data, mime=mime, filename=f"image.{ext}")


def encode_image(image: ImageInput, mode: str) -> Any:
    """Encode an image for a JSON body according to the model's image_input."""
    if mode == "url":
        if not image.url:
            raise RelayError(
                "this model only accepts image URLs (image_input: url); a local file "
                f"({image.source}) cannot be sent. OpenMontage will not upload it to a "
                "third-party host on its own — host it yourself or change image_input.",
                code="image_url_required",
            )
        return image.url
    if image.url:
        # A URL is forwarded as-is; fetching and re-encoding it would hide the
        # dependency on a remote file.
        return image.url
    if mode == "base64":
        return image.b64()
    return image.data_uri()


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------


class RelayHTTP:
    def __init__(self, model: RelayModel, *, session: Any = None):
        import requests

        self.model = model
        self.relay = model.relay
        self.endpoint = model.endpoint
        self._requests = requests
        self.session = session or requests.Session()
        self.session.trust_env = self.relay.trust_env_proxy
        if is_loopback_url(self.endpoint):
            # A loopback relay (mock) must never be routed through a proxy.
            self.session.trust_env = False

    # -- auth -----------------------------------------------------------------
    def api_key(self) -> str:
        key = self.relay.api_key()
        if not key:
            raise RelayError(
                f"environment variable {self.relay.api_key_env} is not set "
                f"(relay {self.relay.name}). Add it to .env — never to the config file.",
                code="missing_key",
            )
        return key

    def auth_headers(self) -> dict[str, str]:
        import os

        key = self.api_key()
        scheme = self.relay.auth_scheme.strip()
        headers = {self.relay.auth_header: f"{scheme} {key}" if scheme else key}
        headers.update(self.relay.extra_headers)
        for header, env in self.relay.extra_headers_env.items():
            value = os.environ.get(env)
            if value:
                headers[header] = value
        return headers

    def redact(self, text: str) -> str:
        import os

        out = str(text)
        secrets = [self.relay.api_key() or ""]
        secrets += [os.environ.get(env, "") for env in self.relay.extra_headers_env.values()]
        for secret in secrets:
            if secret and len(secret) >= 4:
                out = out.replace(secret, "[REDACTED]")
        return out

    # -- urls -----------------------------------------------------------------
    def url(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            if not self.same_origin(path):
                raise RelayError(f"refusing to send credentials to a foreign URL: {path}", code="foreign_url")
            return path
        return self.endpoint.rstrip("/") + "/" + path.lstrip("/")

    def same_origin(self, url: str) -> bool:
        a, b = urlsplit(url), urlsplit(self.endpoint)
        return (a.scheme, a.hostname, a.port) == (b.scheme, b.hostname, b.port)

    def _check_scheme(self, url: str) -> None:
        if urlsplit(url).scheme == "http" and not (
            self.relay.allow_insecure_http or is_loopback_url(url)
        ):
            raise RelayError(f"refusing plain-http URL from a non-local host: {url}", code="insecure_url")

    # -- requests -------------------------------------------------------------
    def call(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        data: Any = None,
        files: Any = None,
        timeout: float = 60.0,
    ) -> Any:
        url = self.url(path)
        self._check_scheme(url)
        return self.session.request(
            method.upper(),
            url,
            headers=self.auth_headers(),
            json=json_body,
            data=data,
            files=files,
            timeout=(15, timeout),
            allow_redirects=False,
        )

    def submit(self, method: str, path: str, **kwargs: Any) -> Any:
        """POST a billable request; classify failures as rejected vs unknown."""
        req = self._requests
        try:
            response = self.call(method, path, **kwargs)
        except req.exceptions.ConnectTimeout as exc:
            raise SubmitRejected(f"could not connect to relay: {self.redact(exc)}", code="connect_failed") from exc
        except req.exceptions.ConnectionError as exc:
            # NewConnectionError = never reached the server; anything else
            # (reset mid-request, ReadTimeout) may have been accepted.
            if "NewConnectionError" in repr(exc) or "Failed to establish" in str(exc):
                raise SubmitRejected(f"could not connect to relay: {self.redact(exc)}", code="connect_failed") from exc
            raise SubmitUnknown(
                "the connection dropped after the request was sent; the relay may "
                "already have accepted and billed it. Check the relay dashboard, then "
                "call again with confirm_resubmit=true only if no task exists.",
                code="submit_unknown",
            ) from exc
        except req.exceptions.Timeout as exc:
            raise SubmitUnknown(
                "submit timed out; the relay may already have accepted and billed it. "
                "Check the relay dashboard, then call again with confirm_resubmit=true "
                "only if no task exists.",
                code="submit_unknown",
            ) from exc
        if response.status_code in _AMBIGUOUS_STATUS:
            raise SubmitUnknown(
                f"relay gateway answered HTTP {response.status_code}; the upstream task "
                "may still have been created. Check the relay dashboard before resubmitting.",
                code="submit_unknown",
            )
        if response.status_code >= 400:
            detail = self.redact(response.text[:600])
            hint = ""
            if _MODEL_MISSING.search(detail):
                hint = (
                    f" — model {self.model.model!r} is not served to this key. "
                    "Run `python -m tools.relay models --relay "
                    f"{self.relay.name}` to list what the key can use."
                )
            raise SubmitRejected(
                f"relay rejected the request: HTTP {response.status_code} {detail}{hint}",
                code="model_not_found" if hint else f"http_{response.status_code}",
            )
        return response

    def get_json(self, path: str, *, timeout: float = 30.0) -> Any:
        response = self.call("GET", path, timeout=timeout)
        if response.status_code == 404:
            raise RelayError(f"task not found on relay (HTTP 404) at {path}", code="task_not_found")
        if response.status_code >= 400:
            raise RelayError(
                f"poll failed: HTTP {response.status_code} {self.redact(response.text[:300])}",
                code=f"http_{response.status_code}",
            )
        return response.json()

    # -- downloads ------------------------------------------------------------
    def download(self, url: str, dest: Path, *, attempts: int = 3) -> dict[str, Any]:
        """Download a result to ``dest`` atomically. Retries are free."""
        last: Optional[Exception] = None
        for attempt in range(attempts):
            try:
                return self._download_once(url, dest)
            except RelayError as exc:
                if exc.code in {"insecure_url", "bad_media", "provider_error_body"}:
                    raise
                last = exc
            except Exception as exc:  # noqa: BLE001
                last = exc
            if attempt + 1 < attempts:
                time.sleep(min(2 * (attempt + 1), 5))
        raise RelayError(f"download failed after {attempts} attempts: {self.redact(last)}", code="download_failed")

    def _download_once(self, url: str, dest: Path) -> dict[str, Any]:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if url.startswith("data:"):
            head, _, body = url.partition(",")
            if ";base64" not in head:
                raise RelayError("result data URI must be base64", code="bad_media")
            content = base64.b64decode(body, validate=True)
            if not content:
                raise RelayError("relay returned empty media", code="bad_media")
            partial = dest.with_name(dest.name + ".part")
            partial.write_bytes(content)
            partial.replace(dest)
            return {"bytes": len(content), "content_type": head[5:].split(";")[0]}

        if url.startswith("/"):
            url = urljoin(self.endpoint + "/", url)
        current = url
        for _ in range(5):
            self._check_scheme(current)
            with_auth = self.same_origin(current)
            response = self.session.get(
                current,
                headers=self.auth_headers() if with_auth else {},
                timeout=(15, 300),
                stream=True,
                allow_redirects=False,
            )
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("Location")
                if not location:
                    raise RelayError("redirect without Location", code="download_failed")
                current = urljoin(current, location)
                continue
            break
        else:
            raise RelayError("too many redirects while downloading", code="download_failed")

        if response.status_code >= 400:
            raise RelayError(f"download HTTP {response.status_code}", code="download_failed")
        ctype = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype in {"application/json", "text/html", "text/plain"}:
            body = response.content[:400].decode("utf-8", "replace")
            raise RelayError(
                f"expected media but the relay returned {ctype}: {self.redact(body)}",
                code="provider_error_body",
            )
        partial = dest.with_name(dest.name + ".part")
        size = 0
        with open(partial, "wb") as fh:
            for chunk in response.iter_content(1 << 16):
                if chunk:
                    fh.write(chunk)
                    size += len(chunk)
        if size == 0:
            partial.unlink(missing_ok=True)
            raise RelayError("relay returned empty media", code="download_failed")
        partial.replace(dest)
        return {"bytes": size, "content_type": ctype}


# ---------------------------------------------------------------------------
# job files
# ---------------------------------------------------------------------------


def default_job_path(output_path: Path) -> Path:
    return output_path.with_name(output_path.name + JOB_SUFFIX)


def load_job(path: Path) -> Optional[dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RelayError(f"job file is unreadable: {path} ({exc})", code="bad_job_file") from exc


def save_job(path: Path, job: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    job["updated_at"] = _now()
    partial = path.with_name(path.name + ".part")
    partial.write_text(json.dumps(job, indent=2, ensure_ascii=False), encoding="utf-8")
    partial.replace(path)


def validate_video_file(path: Path) -> dict[str, Any]:
    """Return probe info; raise if ffprobe says the file has no video stream."""
    info: dict[str, Any] = {"file_size_bytes": path.stat().st_size}
    if not shutil.which("ffprobe"):
        return info
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        raise RelayError(f"downloaded file is not a readable video: {proc.stderr.strip()[:200]}", code="bad_media")
    probe = json.loads(proc.stdout or "{}")
    video = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), None)
    if not video:
        raise RelayError("downloaded file has no video stream", code="bad_media")
    info.update(
        {
            "width": video.get("width"),
            "height": video.get("height"),
            "codec": video.get("codec_name"),
            "has_audio": any(s.get("codec_type") == "audio" for s in probe.get("streams", [])),
        }
    )
    try:
        info["duration_seconds"] = round(float(probe.get("format", {}).get("duration")), 3)
    except (TypeError, ValueError):
        pass
    return info


# ---------------------------------------------------------------------------
# declarative async protocol (generic + OpenAI video presets)
# ---------------------------------------------------------------------------

_OPENAI_VIDEO_POLL = {
    "method": "GET",
    "path": "/videos/{task_id}",
    "status": "status|data.status|task_status",
    "success": ["completed", "succeeded", "success"],
    "failure": ["failed", "cancelled", "canceled", "error", "expired"],
    "error": "error.message|error|fail_reason|data.fail_reason|message",
    "result_url": "video_url|url|data.url|data.video_url|output.video_url|content.video_url|result.url",
}

PRESETS: dict[str, dict[str, Any]] = {
    # OpenAI Videos API (Sora-style): multipart create, auth'd /content download.
    "openai_videos": {
        "submit": {
            "method": "POST",
            "path": "/videos",
            "body_format": "multipart",
            "body": {
                "model": "{{model}}",
                "prompt": "{{prompt}}",
                "seconds": "{{duration_str}}",
                "size": "{{size}}",
            },
            "files": {"input_reference": "{{first_frame_file}}"},
        },
        "response": {"task_id": "id|task_id|data.id|data.task_id"},
        "poll": _OPENAI_VIDEO_POLL,
        "download": {"path": "/videos/{task_id}/content"},
    },
    # JSON variant served by many new-api / one-api relays.
    "openai_video_generations": {
        "submit": {
            "method": "POST",
            "path": "/video/generations",
            "body_format": "json",
            "body": {
                "model": "{{model}}",
                "prompt": "{{prompt}}",
                "seconds": "{{duration_str}}",
                "size": "{{size}}",
                "input_reference": "{{first_frame}}",
            },
        },
        "response": {"task_id": "id|task_id|data.id|data.task_id"},
        "poll": _OPENAI_VIDEO_POLL,
        "download": {"path": "/videos/{task_id}/content"},
    },
}


def protocol_spec(model: RelayModel) -> dict[str, Any]:
    base = PRESETS.get(model.protocol, {})
    return deep_merge(base, model.request or {})


@dataclass
class PollOutcome:
    state: str  # pending | succeeded | failed
    raw: Any = None
    status: Optional[str] = None
    error: Optional[str] = None
    result_url: Optional[str] = None


def interpret_poll(spec: dict[str, Any], payload: Any) -> PollOutcome:
    poll = spec.get("poll") or {}
    status = get_path(payload, poll.get("status", "status"))
    status_text = str(status).strip().lower() if status is not None else None
    success = {s.lower() for s in poll.get("success", DEFAULT_SUCCESS)}
    failure = {s.lower() for s in poll.get("failure", DEFAULT_FAILURE)}
    result_url = get_path(payload, poll.get("result_url"))
    if isinstance(result_url, list):
        result_url = result_url[0] if result_url else None
    if status_text in success:
        return PollOutcome("succeeded", payload, status_text, result_url=result_url)
    if status_text in failure:
        error = get_path(payload, poll.get("error", "error.message|error|message"))
        return PollOutcome("failed", payload, status_text, error=str(error) if error else None)
    return PollOutcome("pending", payload, status_text)


# ---------------------------------------------------------------------------
# job runner
# ---------------------------------------------------------------------------


@dataclass
class JobRequest:
    """Everything needed to submit (once) and finish one generation."""

    tool_name: str
    operation: str
    output_path: Path
    job_path: Path
    fingerprint: str
    estimated_cost_usd: Optional[float]
    variables: dict[str, Any]
    files: dict[str, ImageInput] = field(default_factory=dict)
    media_kind: str = "video"  # video | image
    summary: dict[str, Any] = field(default_factory=dict)  # non-secret provenance


@dataclass
class JobResult:
    success: bool
    data: dict[str, Any]
    error: Optional[str] = None
    cost_usd: Optional[float] = 0.0
    artifacts: list[str] = field(default_factory=list)


def _result(success: bool, job: dict[str, Any], job_path: Path, *, error: Optional[str] = None,
            cost: Optional[float] = 0.0, extra: Optional[dict] = None,
            artifacts: Optional[list[str]] = None) -> JobResult:
    data = {
        "status": job.get("state"),
        "task_id": job.get("task_id"),
        "job_path": str(job_path),
        "resume_job": {"job_path": str(job_path), "task_id": job.get("task_id")},
        "relay": job.get("relay"),
        "hosting_provider": job.get("relay"),
        "model": job.get("model"),
        "protocol": job.get("protocol"),
        "operation": job.get("operation"),
        "remote_url": job.get("result_url"),
        "committed_cost_usd": job.get("estimated_cost_usd"),
    }
    data.update(extra or {})
    return JobResult(success, data, error=error, cost_usd=cost, artifacts=artifacts or [])


class JobRunner:
    """Submit-once / poll / resume / download for one relay model."""

    def __init__(self, model: RelayModel, http: Optional[RelayHTTP] = None,
                 sleep: Callable[[float], None] = time.sleep):
        self.model = model
        self.http = http or RelayHTTP(model)
        self.sleep = sleep
        self._inline: Optional[bytes] = None

    # -- public ---------------------------------------------------------------
    def run(self, req: JobRequest, inputs: dict[str, Any],
            submit_fn: Optional[Callable[[JobRequest], dict[str, Any]]] = None,
            poll_fn: Optional[Callable[[str], PollOutcome]] = None,
            download_fn: Optional[Callable[[dict[str, Any], Path], dict[str, Any]]] = None) -> JobResult:
        submit_fn = submit_fn or self._generic_submit
        poll_fn = poll_fn or self._generic_poll
        download_fn = download_fn or self._generic_download

        job = load_job(req.job_path)
        previous = job
        if job is not None:
            decision = self._resume_decision(job, req, inputs)
            if isinstance(decision, JobResult):
                return decision
            job = decision
        if job is None:
            job = self._new_job(req)
            if previous is not None:  # approved resubmission: keep the old receipt
                job["previous_attempts"] = list(previous.get("previous_attempts") or []) + [
                    {k: previous.get(k) for k in ("task_id", "state", "error", "submitted_at", "fingerprint")}
                ]
            save_job(req.job_path, job)  # recorded BEFORE the paid request leaves
            try:
                submitted = submit_fn(req)
            except SubmitUnknown as exc:
                job.update(state="submit_unknown", error=str(exc))
                save_job(req.job_path, job)
                return _result(False, job, req.job_path, error=str(exc),
                               extra={"recovery_action": "verify_on_relay_then_confirm_resubmit"})
            except (SubmitRejected, RelayError) as exc:
                job.update(state="failed", error=str(exc), billed=False)
                save_job(req.job_path, job)
                return _result(False, job, req.job_path, error=str(exc), extra={"error_code": exc.code})
            job["submitted_at"] = _now()
            inline = submitted.get("inline")
            result_url = submitted.get("result_url")
            if isinstance(result_url, str) and result_url.startswith("data:"):
                # Never park base64 media in the job file; write it straight to disk.
                head, _, body = result_url.partition(",")
                inline = base64.b64decode(body, validate=True)
                result_url = None
            if submitted.get("task_id"):
                job.update(state="submitted", task_id=str(submitted["task_id"]))
            elif inline is not None:
                job.update(state="succeeded", result_url="inline")
                self._inline = inline
            elif result_url:
                job.update(state="succeeded", result_url=result_url)
            else:
                job.update(state="submit_unknown",
                           error="relay accepted the request but returned neither a task id nor a result")
                save_job(req.job_path, job)
                return _result(False, job, req.job_path, error=job["error"],
                               extra={"raw_response_keys": submitted.get("raw_keys")})
            save_job(req.job_path, job)

        if job["state"] == "submitted":
            job = self._poll_until_done(job, req, inputs, poll_fn)
            if job["state"] == "submitted":
                return _result(
                    False, job, req.job_path,
                    error=(
                        "task still running when polling stopped (not a failure, nothing was "
                        "resubmitted). Call the same tool again with the same output_path, or "
                        f"pass resume_job/job_path={req.job_path}, to continue."
                    ),
                    extra={"status": "pending", "recovery_action": "resume"},
                )
            if job["state"] == "failed":
                return _result(False, job, req.job_path,
                               error=f"relay task failed: {job.get('error') or job.get('last_status')}",
                               extra={"error_code": "task_failed"})

        # state == succeeded → download now
        try:
            inline = getattr(self, "_inline", None)
            if inline is not None:
                info = self._write_inline(inline, req.output_path)
                self._inline = None
            else:
                info = download_fn(job, req.output_path)
        except RelayError as exc:
            job["download_error"] = str(exc)
            save_job(req.job_path, job)
            return _result(False, job, req.job_path,
                           error=f"task succeeded but download failed: {exc}. Call again to retry the download (no resubmission).",
                           extra={"recovery_action": "resume"})
        cost = job.get("estimated_cost_usd") if not job.get("cost_reported") else 0.0
        job.update(state="downloaded", local_path=str(req.output_path), downloaded_at=_now(),
                   cost_reported=True, download_error=None)
        save_job(req.job_path, job)
        extra = {"output": str(req.output_path), "output_path": str(req.output_path), **info,
                 "cost_status": "estimated_from_config" if job.get("estimated_cost_usd") is not None else "unpriced",
                 "remote_url_note": "remote URLs from relays expire; the local file is the canonical asset"}
        return _result(True, job, req.job_path, cost=cost, extra=extra, artifacts=[str(req.output_path)])

    # -- resume logic ---------------------------------------------------------
    def _resume_decision(self, job: dict[str, Any], req: JobRequest, inputs: dict[str, Any]):
        explicit_resume = bool(inputs.get("resume_job") or inputs.get("job_path"))
        if job.get("tool") != req.tool_name:
            raise RelayError(
                f"job file {req.job_path} belongs to tool {job.get('tool')}, not {req.tool_name}",
                code="job_mismatch",
            )
        if job.get("fingerprint") != req.fingerprint and not explicit_resume:
            if job.get("state") in {"failed"} and inputs.get("confirm_resubmit"):
                return None
            return _result(
                False, job, req.job_path,
                error=(
                    "output_path already has a job for a DIFFERENT request "
                    f"({job.get('state')}). Use a new output_path, or pass resume_job to "
                    "continue the recorded task. Nothing was submitted."
                ),
                extra={"error_code": "job_conflict"},
            )
        state = job.get("state")
        if state == "downloaded" and req.output_path.is_file():
            return _result(True, job, req.job_path, cost=0.0,
                           extra={"output": str(req.output_path), "output_path": str(req.output_path),
                                  "from_job_file": True},
                           artifacts=[str(req.output_path)])
        if state == "downloaded":
            job["state"] = "succeeded"  # local file gone → re-download, never resubmit
            return job
        if state == "succeeded" and job.get("result_url") == "inline":
            # A synchronous result was returned but the process stopped before
            # it reached disk. It cannot be fetched again from the relay.
            if inputs.get("confirm_resubmit"):
                return None
            return _result(
                False, job, req.job_path,
                error=(
                    "the relay returned this result synchronously but it was never saved "
                    "(process interrupted). Regenerating is a new paid request — call again "
                    "with confirm_resubmit=true after the user approves."
                ),
                extra={"error_code": "inline_result_lost"},
            )
        if state in {"submitted", "succeeded"}:
            return job
        if state in {"submit_unknown", "submitting"}:
            if inputs.get("confirm_resubmit"):
                return None
            return _result(
                False, job, req.job_path,
                error=(
                    "a previous submit for this output has an UNKNOWN outcome and may already "
                    "be billed. Check the relay's task list; if no task exists, call again "
                    "with confirm_resubmit=true. Nothing was submitted."
                ),
                extra={"error_code": "submit_unknown", "recovery_action": "verify_on_relay_then_confirm_resubmit"},
            )
        if state == "failed":
            if inputs.get("confirm_resubmit"):
                return None
            return _result(
                False, job, req.job_path,
                error=(
                    f"the recorded task failed: {job.get('error')}. A new attempt is a new paid "
                    "request — call again with confirm_resubmit=true after the user approves."
                ),
                extra={"error_code": "previous_failure"},
            )
        return _result(
            False, job, req.job_path,
            error=f"job file has an unrecognised state {state!r}; refusing to submit. Inspect {req.job_path}.",
            extra={"error_code": "bad_job_state"},
        )

    def _new_job(self, req: JobRequest) -> dict[str, Any]:
        m = self.model
        return {
            "version": JOB_VERSION,
            "tool": req.tool_name,
            "relay": m.relay.name,
            "endpoint": m.endpoint,
            "model": m.model,
            "protocol": m.protocol,
            "operation": req.operation,
            "fingerprint": req.fingerprint,
            "state": "submitting",
            "created_at": _now(),
            "task_id": None,
            "result_url": None,
            "output_path": str(req.output_path),
            "estimated_cost_usd": req.estimated_cost_usd,
            "cost_reported": False,
            "request_summary": req.summary,
            "poll_count": 0,
        }

    # -- polling --------------------------------------------------------------
    def _poll_until_done(self, job, req, inputs, poll_fn) -> dict[str, Any]:
        interval = float(inputs.get("poll_interval_seconds") or self.model.poll_setting("interval_seconds", 5))
        timeout = float(inputs.get("poll_timeout_seconds") or self.model.poll_setting("timeout_seconds", 900))
        max_errors = int(self.model.poll_setting("max_consecutive_errors", 5))
        deadline = time.monotonic() + timeout
        errors = 0
        while True:
            try:
                outcome = poll_fn(job["task_id"])
                errors = 0
            except RelayError as exc:
                if exc.code == "task_not_found":
                    job.update(state="failed", error=str(exc))
                    save_job(req.job_path, job)
                    return job
                errors += 1
                job["last_poll_error"] = str(exc)
                outcome = None
            except Exception as exc:  # noqa: BLE001 — network blips are not task failures
                errors += 1
                job["last_poll_error"] = self.http.redact(str(exc))
                outcome = None
            job["poll_count"] = int(job.get("poll_count", 0)) + 1
            job["last_polled_at"] = _now()
            if outcome is not None:
                job["last_status"] = outcome.status
                if outcome.state == "succeeded":
                    job.update(state="succeeded", result_url=outcome.result_url, completed_at=_now())
                    save_job(req.job_path, job)
                    return job
                if outcome.state == "failed":
                    job.update(state="failed", error=outcome.error or outcome.status, billed="unknown")
                    save_job(req.job_path, job)
                    return job
            save_job(req.job_path, job)
            if errors >= max_errors or time.monotonic() >= deadline:
                return job  # still "submitted" → resumable
            self.sleep(max(0.0, min(interval, deadline - time.monotonic())))

    # -- generic protocol -----------------------------------------------------
    def _generic_submit(self, req: JobRequest) -> dict[str, Any]:
        spec = protocol_spec(self.model)
        submit = spec.get("submit") or {}
        body = render_template(submit.get("body") or {}, req.variables)
        extra = req.variables.get("extra_params") or {}
        if isinstance(body, dict) and isinstance(extra, dict):
            body = deep_merge(body, extra)
        path = render_template(submit.get("path", ""), req.variables)
        method = submit.get("method", "POST")
        timeout = self.model.submit_timeout_seconds
        if submit.get("body_format", "json") == "multipart":
            files = []
            for field_name, placeholder in (submit.get("files") or {}).items():
                var = _WHOLE_VAR.match(str(placeholder))
                image = req.files.get(var.group(1)) if var else None
                if image is not None:
                    if image.data is None:
                        raise SubmitRejected(
                            f"multipart field {field_name} needs a local image, got URL {image.url}",
                            code="bad_image",
                        )
                    files.append((field_name, (image.filename, image.data, image.mime)))
            form = {k: (json.dumps(v) if isinstance(v, (dict, list)) else str(v)) for k, v in body.items()}
            # Text fields go in as (None, value) parts so the request is always
            # multipart/form-data — with no file attached, requests would
            # otherwise silently fall back to x-www-form-urlencoded.
            parts = [(k, (None, v)) for k, v in form.items()] + files
            response = self.http.submit(method, path, files=parts, timeout=timeout)
        else:
            response = self.http.submit(method, path, json_body=body, timeout=timeout)
        try:
            payload = response.json()
        except ValueError as exc:
            raise SubmitUnknown(
                f"relay answered HTTP {response.status_code} with a non-JSON body; the task may exist",
                code="submit_unknown",
            ) from exc
        response_spec = spec.get("response") or {}
        task_id = get_path(payload, response_spec.get("task_id", "task_id|id|data.task_id|data.id"))
        result_url = get_path(payload, response_spec.get("result_url"))
        b64 = get_path(payload, response_spec.get("result_b64"))
        if b64 and not result_url:
            mime = "image/png" if req.media_kind == "image" else "video/mp4"
            result_url = f"data:{mime};base64,{b64}"
        if isinstance(result_url, list):
            result_url = result_url[0] if result_url else None
        error = get_path(payload, response_spec.get("error", "error.message|error"))
        if not task_id and not result_url and error:
            raise SubmitRejected(f"relay returned an error: {self.http.redact(str(error))}", code="relay_error")
        return {"task_id": task_id, "result_url": result_url,
                "raw_keys": sorted(payload.keys()) if isinstance(payload, dict) else None}

    def _generic_poll(self, task_id: str) -> PollOutcome:
        spec = protocol_spec(self.model)
        poll = spec.get("poll") or {}
        path = str(poll.get("path", "")).replace("{task_id}", task_id)
        if not path:
            raise RelayError("protocol has no poll.path", code="bad_protocol")
        if str(poll.get("method", "GET")).upper() == "GET":
            payload = self.http.get_json(path)
        else:
            response = self.http.call(poll["method"], path,
                                      json_body=render_template(poll.get("body") or {}, {"task_id": task_id}))
            if response.status_code >= 400:
                raise RelayError(f"poll failed: HTTP {response.status_code}", code=f"http_{response.status_code}")
            payload = response.json()
        return interpret_poll(spec, payload)

    def _write_inline(self, content: bytes, dest: Path) -> dict[str, Any]:
        if not content:
            raise RelayError("relay returned empty media", code="bad_media")
        if content[:1] in (b"{", b"<"):
            raise RelayError(
                f"expected media but got: {self.http.redact(content[:200].decode('utf-8', 'replace'))}",
                code="provider_error_body",
            )
        dest.parent.mkdir(parents=True, exist_ok=True)
        partial = dest.with_name(dest.name + ".part")
        partial.write_bytes(content)
        partial.replace(dest)
        info: dict[str, Any] = {"bytes": len(content)}
        if self.model.kind == "video":
            info.update(validate_video_file(dest))
        elif self.model.kind == "image" and not sniff_image(content[:16]):
            raise RelayError("relay result is not an image", code="bad_media")
        return info

    def _generic_download(self, job: dict[str, Any], dest: Path) -> dict[str, Any]:
        spec = protocol_spec(self.model)
        download = spec.get("download") or {}
        url = job.get("result_url")
        if not url and download.get("path"):
            url = self.http.url(str(download["path"]).replace("{task_id}", str(job.get("task_id"))))
        if not url:
            raise RelayError("task succeeded but the relay returned no result URL", code="no_result")
        info = self.http.download(str(url), dest)
        if self.model.kind == "video":
            info.update(validate_video_file(dest))
        elif self.model.kind == "image":
            head = dest.read_bytes()[:16]
            if not sniff_image(head):
                dest.unlink(missing_ok=True)
                raise RelayError("downloaded file is not an image", code="bad_media")
        return info


def guess_extension(mime: str, fallback: str) -> str:
    ext = mimetypes.guess_extension(mime or "") or ""
    return ext.lstrip(".") or fallback
