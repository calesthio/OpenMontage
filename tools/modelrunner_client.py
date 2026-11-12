"""Shared ModelRunner API plumbing for the video, image, TTS, and music tools.

ModelRunner (https://modelrunner.ai) is a multi-model inference platform: one
key and one async queue contract in front of hosted video, image, speech, and
music model families (Wan, Seedance, Seedream, Recraft, Stable Diffusion,
Kokoro, Gemini TTS, ElevenLabs, Lyria, Stable Audio, ...).

Every generation follows the same three-step queue shape:

    POST https://queue.modelrunner.run/{owner}/{alias}
        -> {"request_id", "status_url", "response_url", "status", ...}
    GET  {status_url}
        -> {"status": "IN_QUEUE" | "IN_PROGRESS" | "COMPLETED" | "FAILED" | "CANCELLED", ...}
    GET  {response_url}
        -> {"output": <url or [urls]>, "error": ..., ...}

A request can report COMPLETED and still carry a non-empty `error` (a failure
normalized for billing); the result endpoint surfaces those as HTTP 422. Treat
any non-empty final `error` as failure — never as output.

The API key is attached ONLY to https URLs on the two first-party hosts
(queue.modelrunner.run and api.modelrunner.run). Authenticated calls never
follow redirects. Output downloads and storage PUTs are unauthenticated by
design, and download redirects are re-validated hop by hop.

`requests` is imported lazily inside functions so registry discovery stays fast
(see tests/contracts — the lazy-import convention is enforced by the suite).
"""

from __future__ import annotations

import ipaddress
import mimetypes
import os
import re
import secrets
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

QUEUE_BASE_URL = "https://queue.modelrunner.run"
API_BASE_URL = "https://api.modelrunner.run"
STORAGE_INITIATE_ENDPOINT = f"{API_BASE_URL}/storage/upload/initiate"

# Every submit carries a fresh per-attempt key. A retry of the SAME attempt
# (same key, byte-identical body) gets the original request back instead of
# starting — and billing — a second job; a different body under the same key
# is refused with 409 rather than silently replayed.
IDEMPOTENCY_HEADER = "X-Idempotency-Key"
# The same id is written into the request's metadata, so an attempt whose
# outcome is unknown can be found in the account's request history:
#   GET /requests?metadata={"openmontage_attempt": "<attempt_id>"}
ATTEMPT_METADATA_KEY = "openmontage_attempt"
# Waits between re-sends of one attempt after a lost or 5xx response. The
# first attempt may still be running server-side (a submit can take minutes on
# slow routes), so the server answers "in progress" until it finishes.
_SUBMIT_RETRY_DELAYS = (2.0, 5.0, 10.0, 20.0, 30.0)
# While the server reports the first send still running, keep asking for this
# long. A synchronous route holds the create open for the whole generation.
_IN_PROGRESS_WAIT_S = 600.0
_IN_PROGRESS_POLL_S = 30.0
# 409 codes that describe the key itself, never the request.
_KEY_IN_PROGRESS = "idempotency_key_in_progress"
_KEY_STATE_CODES = {_KEY_IN_PROGRESS, "idempotency_outcome_unknown", "idempotency_key_reused"}
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# The API documents COMPLETED as the only success status. FAILED and CANCELLED
# are terminal failures. Anything else (IN_QUEUE, IN_PROGRESS, or a status
# introduced later) is treated as in-flight so a new intermediate state can't
# be mistaken for a failure.
TERMINAL_SUCCESS = {"COMPLETED"}
TERMINAL_FAILURE = {"FAILED", "CANCELLED"}

# MODELRUNNER_KEY is the name the official SDKs read; the other two are the
# names ModelRunner's own queue-API code examples use.
ENV_KEYS = ("MODELRUNNER_KEY", "MODELRUNNER_API_KEY", "MRUN_API_KEY")

INSTALL_INSTRUCTIONS = (
    "Set MODELRUNNER_KEY to your ModelRunner API key.\n"
    "  Get one at https://modelrunner.ai -> Settings -> API Keys"
)

# Hosts the API key may be sent to. Everything else (media CDNs, presigned S3
# PUT URLs) must never see the credential.
_AUTHORIZED_HOSTS = {
    urlparse(QUEUE_BASE_URL).hostname,
    urlparse(API_BASE_URL).hostname,
}

_UPLOAD_MAX_BYTES = 512 * 1024 * 1024  # storage accepts large media; refuse absurdity

_MIME_FALLBACK = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".webp": "image/webp", ".bmp": "image/bmp", ".gif": "image/gif",
    ".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm",
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4",
    ".aac": "audio/aac", ".flac": "audio/flac", ".ogg": "audio/ogg",
}


class ModelRunnerError(RuntimeError):
    """Raised for any ModelRunner API or transport failure."""


class ModelRunnerSubmitError(ModelRunnerError):
    """Submission failed after the queue may already have accepted the job.

    `queue` carries whatever sanitized coordinates are known so tools can
    report honest billing provenance: `request_id` when the response exposed
    one, or `attempt_id` + `submit_outcome="ambiguous"` when no response ever
    arrived and the job may or may not exist.
    """

    def __init__(self, message: str, queue: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.queue = dict(queue or {})


def get_api_key() -> str | None:
    """Return the first configured ModelRunner key."""
    for key in ENV_KEYS:
        value = os.environ.get(key)
        if value:
            return value
    return None


def _headers(api_key: str, json_body: bool = True) -> dict[str, str]:
    headers = {"Authorization": f"Key {api_key}"}
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


def _assert_api_url(url: str, context: str) -> None:
    """Refuse to attach the API key to any URL off the first-party hosts."""
    parsed = urlparse(str(url))
    if parsed.scheme != "https" or parsed.hostname not in _AUTHORIZED_HOSTS:
        raise ModelRunnerError(
            f"{context} URL {url!r} is not on a ModelRunner API host; "
            f"refusing to send the API key to it."
        )


def validate_media_url(url: str, context: str = "output") -> str:
    """Validate a URL is safe to download from: https, real public hostname."""
    parsed = urlparse(str(url))
    if parsed.scheme != "https":
        raise ModelRunnerError(f"ModelRunner {context} URL is not https: {url!r}")
    host = parsed.hostname
    if not host:
        raise ModelRunnerError(f"ModelRunner {context} URL has no hostname: {url!r}")
    if host == "localhost" or host.endswith(".local"):
        raise ModelRunnerError(f"ModelRunner {context} URL points at a local host: {url!r}")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return str(url)  # a normal DNS name
    if not address.is_global:
        raise ModelRunnerError(f"ModelRunner {context} URL points at a private address: {url!r}")
    return str(url)


def _error_detail(response: Any) -> str:
    """Extract the most useful error text from an API error response."""
    try:
        body = response.json()
    except Exception:  # noqa: BLE001 - fall back to raw text
        body = None
    if isinstance(body, dict):
        message = body.get("message") or body.get("error")
        if message:
            return str(message)[:500]
    return str(getattr(response, "text", ""))[:500]


def _error_code(response: Any) -> str | None:
    """The API's machine-readable `details.code`, when the error body has one."""
    try:
        body = response.json()
    except Exception:  # noqa: BLE001
        return None
    details = body.get("details") if isinstance(body, dict) else None
    code = details.get("code") if isinstance(details, dict) else None
    return str(code) if code else None


def _raise_for_status(response: Any, context: str) -> None:
    status = getattr(response, "status_code", 200)
    if 300 <= status < 400:
        # Authenticated calls never follow redirects — a redirect from a
        # first-party host is unexpected and following it could carry the
        # credential somewhere it must not go.
        raise ModelRunnerError(f"{context} answered a redirect (HTTP {status}); refusing to follow it.")
    if status >= 400:
        raise ModelRunnerError(f"{context} failed with HTTP {status}: {_error_detail(response)}")


def _json_of(response: Any, context: str) -> dict[str, Any]:
    try:
        body = response.json()
    except Exception as exc:  # noqa: BLE001 - surface the raw text, not a parse trace
        text = str(getattr(response, "text", ""))[:500]
        raise ModelRunnerError(f"{context} returned a non-JSON response: {text}") from exc
    if not isinstance(body, dict):
        raise ModelRunnerError(f"{context} returned an unexpected payload: {str(body)[:500]}")
    return body


def parse_poll_controls(
    inputs: dict[str, Any], default_interval: float, default_timeout: float
) -> tuple[float, float]:
    """Parse and range-check poll_interval/poll_timeout BEFORE any paid submit.

    A malformed polling control must fail the call while it still costs
    nothing — not after the job is already queued and billing.
    """
    try:
        interval = float(inputs.get("poll_interval", default_interval))
        timeout = float(inputs.get("poll_timeout", default_timeout))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"poll_interval and poll_timeout must be numbers: {exc}") from exc
    if interval <= 0 or timeout <= 0:
        raise ValueError(
            f"poll_interval ({interval}) and poll_timeout ({timeout}) must be positive seconds"
        )
    return interval, timeout


def merge_extra_params(payload: dict[str, Any], extra: Any) -> dict[str, Any]:
    """Overlay caller extra_params without letting them override validated fields.

    Anything the route builder already validated (duration, resolution, size,
    prompt, ...) is protected — silently replacing it would bill a different
    job than the one that was validated and estimated.
    """
    if not isinstance(extra, dict):
        return payload
    if "metadata" in extra:
        raise ValueError(
            "extra_params may not set `metadata`: it carries the submit attempt id "
            "used to find a request whose submit outcome is unknown."
        )
    overlap = sorted(set(extra) & set(payload))
    if overlap:
        raise ValueError(
            f"extra_params may not override validated fields: {', '.join(overlap)}. "
            f"Pass those through their first-class inputs instead."
        )
    payload.update(extra)
    return payload


def _never_sent(exc: BaseException, requests_module: Any) -> bool:
    """True only when a POST provably never reached the network.

    That is a refused or unresolvable connection, a connect timeout, or a
    local error raised before any I/O (body encoding, a blocked socket).
    Transport failures surface as `requests` exceptions or OSError; any of
    those other than a failed connect may have been sent, so they count as
    possibly sent.
    """
    exceptions = getattr(requests_module, "exceptions", None)
    if exceptions is not None:
        if isinstance(exc, exceptions.ConnectTimeout):
            return True
        if isinstance(exc, exceptions.ConnectionError):
            try:
                from urllib3.exceptions import NewConnectionError
            except ImportError:  # pragma: no cover - urllib3 ships with requests
                return False
            reason = exc.args[0] if exc.args else None
            return isinstance(getattr(reason, "reason", reason), NewConnectionError)
        local = tuple(
            getattr(exceptions, name)
            for name in ("InvalidJSONError", "InvalidHeader", "InvalidURL", "MissingSchema", "InvalidSchema")
            if hasattr(exceptions, name)
        )
        if local and isinstance(exc, local):
            return True  # raised while preparing the request, before any socket
        if isinstance(exc, exceptions.RequestException):
            return False
    return not isinstance(exc, OSError)


def new_attempt_id() -> str:
    """A fresh idempotency key / `openmontage_attempt` tag for one submission."""
    return secrets.token_urlsafe(16)


def submit(
    endpoint_id: str, payload: dict[str, Any], api_key: str, timeout: int = 60,
    attempt_id: str | None = None,
) -> dict[str, Any]:
    """Submit a generation request.

    Returns {request_id, status_url, response_url, attempt_id}. Pass
    `attempt_id` to use a key the caller has already written down.

    The POST carries a per-attempt `X-Idempotency-Key`. If the response is
    lost (transport error) or the edge answers 5xx, the identical request is
    re-sent under the same key, so an accepted job is returned rather than
    started twice. If no attempt yields an answer, a ModelRunnerSubmitError
    with `submit_outcome="ambiguous"` and the `attempt_id` is raised: the job
    may exist, and resubmitting would risk paying twice.

    If the POST succeeded but the queue envelope is unusable (incomplete, or
    pointing off the first-party hosts), the job may already exist server-side
    — the ModelRunnerSubmitError carries the request_id.
    """
    import requests

    url = f"{QUEUE_BASE_URL}/{endpoint_id}"
    attempt_id = attempt_id or new_attempt_id()
    body = {**payload, "metadata": {ATTEMPT_METADATA_KEY: attempt_id}}
    headers = {**_headers(api_key), IDEMPOTENCY_HEADER: attempt_id}
    ambiguous = {"attempt_id": attempt_id, "submit_outcome": "ambiguous"}

    # The status code of a refusal cannot say whether the server released the
    # key (nothing dispatched) or kept it (the job may exist): both can be a
    # 400. So a refusal is re-sent once under the same key, and the answer to
    # that settles it: the same refusal means the key was released, a 409 key
    # state means the first attempt may have dispatched.
    delays = iter(_SUBMIT_RETRY_DELAYS)
    in_progress_deadline: float | None = None
    refusal_status: int | None = None
    response = None
    last_problem = ""
    maybe_sent = False
    while True:
        try:
            candidate = requests.post(url, headers=headers, json=body, timeout=timeout, allow_redirects=False)
        except Exception as exc:  # noqa: BLE001 - no answer: the job may or may not exist
            last_problem = f"could not reach ModelRunner at {url}: {exc}"
            if not maybe_sent and _never_sent(exc, requests):
                # Nothing has left this machine, so nothing can bill and a
                # plain rerun is safe: fail now, without a queue.
                raise ModelRunnerError(last_problem) from exc
            maybe_sent = True
            wait = None if refusal_status is not None else next(delays, None)
        else:
            maybe_sent = True
            status = getattr(candidate, "status_code", 200)
            code = _error_code(candidate) if status == 409 else None
            last_problem = f"HTTP {status}: {_error_detail(candidate)}"
            if status < 300:
                response = candidate
                break
            if refusal_status is not None:
                if status == refusal_status and code not in _KEY_STATE_CODES:
                    response = candidate  # the key was released: a definite refusal
                break
            if code == _KEY_IN_PROGRESS:
                if in_progress_deadline is None:
                    in_progress_deadline = time.monotonic() + _IN_PROGRESS_WAIT_S
                wait = _IN_PROGRESS_POLL_S if time.monotonic() < in_progress_deadline else None
            elif status >= 500 or status == 429:
                wait = next(delays, None)
            elif status < 400 or code in _KEY_STATE_CODES:
                break  # a redirect, or a key whose first attempt may have dispatched
            else:
                refusal_status, wait = status, 0.0
        if wait is None:
            break
        if wait:
            time.sleep(wait)

    if response is None:
        raise ModelRunnerSubmitError(
            f"ModelRunner submission to {endpoint_id} got no definite answer ({last_problem}). "
            f"The job may have started and may bill; find it by metadata "
            f"{ATTEMPT_METADATA_KEY}={attempt_id} before resubmitting.",
            queue=ambiguous,
        )

    _raise_for_status(response, f"ModelRunner submission to {endpoint_id}")
    try:
        data = _json_of(response, "ModelRunner submission")
    except ModelRunnerError as exc:
        # A 2xx is sent only after the request row exists.
        raise ModelRunnerSubmitError(str(exc), queue=ambiguous) from exc

    request_id = data.get("request_id")
    status_url = data.get("status_url")
    response_url = data.get("response_url")
    accepted = {"request_id": str(request_id), "attempt_id": attempt_id} if request_id else dict(ambiguous)
    if not (request_id and status_url and response_url):
        raise ModelRunnerSubmitError(
            f"ModelRunner submission returned an incomplete queue envelope: {str(data)[:500]}",
            queue=accepted,
        )
    try:
        _assert_api_url(status_url, "status_url")
        _assert_api_url(response_url, "response_url")
    except ModelRunnerError as exc:
        raise ModelRunnerSubmitError(str(exc), queue=accepted) from exc
    return {
        "request_id": str(request_id),
        "status_url": str(status_url),
        "response_url": str(response_url),
        "attempt_id": attempt_id,
    }


def queue_urls_for(endpoint_id: str, request_id: str) -> dict[str, str]:
    """Status and result URLs for an already-submitted request (no network)."""
    request_id = str(request_id)
    if not _REQUEST_ID_RE.match(request_id):
        raise ValueError(f"request_id {request_id!r} is not a ModelRunner request id")
    base = f"{QUEUE_BASE_URL}/{endpoint_id}/requests/{request_id}"
    return {"request_id": request_id, "status_url": f"{base}/status", "response_url": base}


def get_request_record(request_id: str, api_key: str, timeout: int = 30) -> dict[str, Any]:
    """Read the account's own record of a request: what it was actually charged.

    Returns {"status", "billing_status", "total_price"} (any of them None when
    unreadable). Never raises — billing provenance is best-effort and must not
    turn a delivered result into a failure. `billing_status` is one of
    pending / partial / charged / failed; `total_price` is the charged USD.
    """
    empty: dict[str, Any] = {"status": None, "billing_status": None, "total_price": None}
    if not _REQUEST_ID_RE.match(str(request_id or "")):
        return empty
    try:
        import requests

        url = f"{QUEUE_BASE_URL}/requests/{request_id}"
        _assert_api_url(url, "request record")
        response = requests.get(
            url, headers=_headers(api_key, json_body=False), timeout=timeout, allow_redirects=False
        )
        if getattr(response, "status_code", 200) != 200:
            return empty
        body = response.json()
    except Exception:  # noqa: BLE001 - provenance only
        return empty
    if not isinstance(body, dict):
        return empty
    try:
        total = float(body["totalPrice"]) if body.get("totalPrice") is not None else None
    except (TypeError, ValueError):
        total = None
    billing = body.get("billingStatus")
    return {
        "status": body.get("status"),
        "billing_status": billing if billing in ("pending", "partial", "charged", "failed") else None,
        "total_price": total,
    }


def poll(
    status_url: str,
    api_key: str,
    interval: float = 3.0,
    timeout: float = 600.0,
    request_timeout: int = 30,
) -> dict[str, Any]:
    """Poll a queued request until it reaches COMPLETED.

    Raises ModelRunnerError on FAILED/CANCELLED or when `timeout` seconds
    elapse (measured with a monotonic clock; each sleep is capped to the
    remaining budget so the deadline is honored).
    """
    import requests

    _assert_api_url(status_url, "status_url")
    deadline = time.monotonic() + max(float(timeout), 0.0)
    last_status = "unknown"
    consecutive_transport_errors = 0

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ModelRunnerError(
                f"ModelRunner request did not finish within {float(timeout):.0f}s "
                f"(last status: {last_status}). The job may still complete and bill — "
                f"check {status_url}"
            )
        try:
            response = requests.get(
                status_url,
                headers=_headers(api_key, json_body=False),
                # Each GET is also capped to the remaining budget so a short
                # overall timeout can't be blown by one slow request.
                timeout=min(float(request_timeout), max(remaining, 1.0)),
                allow_redirects=False,
            )
        except Exception as exc:  # noqa: BLE001
            consecutive_transport_errors += 1
            if consecutive_transport_errors >= 5:
                raise ModelRunnerError(
                    f"Polling {status_url} failed after "
                    f"{consecutive_transport_errors} consecutive transport errors: {exc}"
                ) from exc
        else:
            _raise_for_status(response, f"ModelRunner poll of {status_url}")
            consecutive_transport_errors = 0
            data = _json_of(response, "ModelRunner poll")
            last_status = str(data.get("status", "unknown")).upper()

            if last_status in TERMINAL_SUCCESS:
                return data
            if last_status in TERMINAL_FAILURE:
                error = data.get("error") or "no error detail provided"
                raise ModelRunnerError(f"ModelRunner generation {last_status.lower()}: {error}")

        time.sleep(min(interval, max(deadline - time.monotonic(), 0.0)))


def get_result(response_url: str, api_key: str, timeout: int = 60) -> dict[str, Any]:
    """Fetch the final result envelope, rejecting failed-but-normalized runs.

    A COMPLETED request can still carry a non-empty `error` (the provider
    failed and the failure was normalized for billing; the API answers 422).
    That is a failure, never output.
    """
    import requests

    _assert_api_url(response_url, "response_url")
    try:
        response = requests.get(
            response_url,
            headers=_headers(api_key, json_body=False),
            timeout=timeout,
            allow_redirects=False,
        )
    except Exception as exc:  # noqa: BLE001
        raise ModelRunnerError(f"Fetching the ModelRunner result failed: {exc}") from exc

    status_code = getattr(response, "status_code", 200)
    if status_code == 410:
        raise ModelRunnerError(
            "ModelRunner reports this request's payloads were purged under its retention policy."
        )
    data = _json_of(response, "ModelRunner result") if status_code in (200, 422) else None
    if data is None:
        _raise_for_status(response, "ModelRunner result fetch")
        data = _json_of(response, "ModelRunner result")

    error = data.get("error")
    if error:
        raise ModelRunnerError(f"ModelRunner generation failed: {str(error)[:500]}")
    if status_code >= 400:
        _raise_for_status(response, "ModelRunner result fetch")
    return data


def extract_outputs(result: dict[str, Any], cardinality: str) -> list[str]:
    """Normalize the model-specific `output` field to a list of hosted URLs.

    `cardinality` is "single" (a scalar URL — video, speech, music routes) or
    "list" (a list of URLs — image routes). Every URL is validated before use.
    """
    output = result.get("output")
    if cardinality == "single":
        values = [output] if isinstance(output, str) and output else []
    else:
        values = [v for v in output if isinstance(v, str) and v] if isinstance(output, list) else []
    if not values:
        raise ModelRunnerError(
            f"ModelRunner returned COMPLETED but no usable output: {str(output)[:300]}"
        )
    return [validate_media_url(value) for value in values]


def upload_media(file_path: str | Path, api_key: str, timeout: int = 120) -> str:
    """Upload a local file to ModelRunner storage and return its hosted URL.

    Two steps: an authenticated initiate that returns a presigned PUT URL and
    the final file URL, then an unauthenticated PUT of the raw bytes with the
    same Content-Type. Type and size are validated before initiate so an
    invalid file never creates an orphaned upload slot.
    """
    import requests

    path = Path(file_path)
    if not path.is_file():
        raise ModelRunnerError(f"Cannot upload — file not found: {path}")
    size = path.stat().st_size
    if size == 0:
        raise ModelRunnerError(f"Cannot upload an empty file: {path}")
    if size > _UPLOAD_MAX_BYTES:
        raise ModelRunnerError(
            f"Refusing to upload {path.name}: {size} bytes exceeds the "
            f"{_UPLOAD_MAX_BYTES // (1024 * 1024)}MB limit."
        )

    content_type, _ = mimetypes.guess_type(path.name)
    if not content_type:
        content_type = _MIME_FALLBACK.get(path.suffix.lower())
    if not content_type:
        raise ModelRunnerError(
            f"Cannot determine the media type of {path.name!r}; rename it with a standard extension."
        )

    try:
        response = requests.post(
            STORAGE_INITIATE_ENDPOINT,
            headers=_headers(api_key),
            json={"file_name": path.name, "content_type": content_type, "size": size},
            timeout=timeout,
            allow_redirects=False,
        )
    except Exception as exc:  # noqa: BLE001
        raise ModelRunnerError(f"Initiating the ModelRunner upload failed: {exc}") from exc
    _raise_for_status(response, "ModelRunner upload initiate")
    data = _json_of(response, "ModelRunner upload initiate")

    upload_url = data.get("upload_url")
    file_url = data.get("file_url")
    if not upload_url or not file_url:
        raise ModelRunnerError(f"ModelRunner upload initiate returned no URLs: {str(data)[:500]}")
    # The initiate response controls where the file bytes go — hold it to the
    # same https/public-host bar as every other destination.
    upload_url = validate_media_url(upload_url, "upload destination")
    file_url = validate_media_url(file_url, "uploaded file")

    try:
        # The presigned PUT must carry the exact Content-Type from initiate and
        # no Authorization header (the URL itself is the credential). The file
        # is streamed from disk rather than read into memory.
        with path.open("rb") as handle:
            put_response = requests.put(
                str(upload_url),
                headers={"Content-Type": content_type},
                data=handle,
                timeout=timeout,
                allow_redirects=False,
            )
    except Exception as exc:  # noqa: BLE001
        raise ModelRunnerError(f"Uploading {path.name} to ModelRunner storage failed: {exc}") from exc
    _raise_for_status(put_response, "ModelRunner storage upload")
    return str(file_url)


def download(url: str, output_path: str | Path, timeout: int = 300) -> Path:
    """Download a generated asset to disk (no auth header) and return the path.

    Redirects are followed manually so every hop passes the same
    https/public-host validation as the original URL.
    """
    import requests
    from urllib.parse import urljoin

    current = validate_media_url(url)
    for _ in range(5):
        try:
            response = requests.get(current, timeout=timeout, allow_redirects=False)
        except Exception as exc:  # noqa: BLE001
            raise ModelRunnerError(f"Downloading ModelRunner output failed: {exc}") from exc

        status = getattr(response, "status_code", 200)
        if 300 <= status < 400:
            headers = getattr(response, "headers", {}) or {}
            location = headers.get("location") or headers.get("Location")
            if not location:
                raise ModelRunnerError(
                    f"ModelRunner output download redirected (HTTP {status}) without a Location header."
                )
            current = validate_media_url(urljoin(current, str(location)), "redirected output")
            continue
        _raise_for_status(response, "ModelRunner output download")

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.content)
        return path
    raise ModelRunnerError("ModelRunner output download followed too many redirects (limit 5).")
