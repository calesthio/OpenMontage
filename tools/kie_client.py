"""Shared KIE AI API plumbing for the image and video provider tools.

KIE AI (https://kie.ai) is a multi-model gateway: one key and one unified async
task contract in front of hundreds of third-party models (Veo, Kling, Runway,
Seedream, Nano Banana, GPT Image, Suno, ...). Every Market model follows the
same shape:

    POST /api/v1/jobs/createTask      -> {"code": 200, "data": {"taskId": ...}}
    GET  /api/v1/jobs/recordInfo?taskId=... -> {"code": 200, "data": {"state", "resultJson", ...}}

Uploads (for turning a local file into the hosted URL most Market models
expect as input) go through a separate host:

    POST https://kieai.redpandaai.co/api/file-stream-upload -> {"data": {"downloadUrl": ...}}

`requests` is imported lazily inside functions so registry discovery stays
fast and offline-safe.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

BASE_URL = "https://api.kie.ai"
CREATE_TASK_ENDPOINT = f"{BASE_URL}/api/v1/jobs/createTask"
RECORD_INFO_ENDPOINT = f"{BASE_URL}/api/v1/jobs/recordInfo"
CREDIT_ENDPOINT = f"{BASE_URL}/api/v1/chat/credit"

UPLOAD_BASE_URL = "https://kieai.redpandaai.co"
UPLOAD_STREAM_ENDPOINT = f"{UPLOAD_BASE_URL}/api/file-stream-upload"

# Documented task states (market/common/get-task-detail).
TERMINAL_SUCCESS = {"success"}
TERMINAL_FAILURE = {"fail"}

ENV_KEYS = ("KIE_API_KEY", "KIEAI_API_KEY")

INSTALL_INSTRUCTIONS = (
    "Set KIE_API_KEY to your KIE AI API key.\n"
    "  Get one at https://kie.ai/api-key"
)


class KieError(RuntimeError):
    """Raised for any KIE AI API or transport failure."""


def get_api_key() -> str | None:
    for key in ENV_KEYS:
        value = os.environ.get(key)
        if value:
            return value
    return None


def _headers(api_key: str, json_body: bool = True) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {api_key}"}
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


def _raise_for_status(response: Any, context: str) -> None:
    status = getattr(response, "status_code", 200)
    if status >= 400:
        text = getattr(response, "text", "")
        raise KieError(f"{context} failed with HTTP {status}: {text[:500]}")


def _envelope(response: Any, context: str) -> dict[str, Any]:
    """Parse a KIE {"code", "msg", "data"} envelope.

    KIE returns HTTP 200 even for application-level errors, so `code` must
    always be checked regardless of the HTTP status.
    """
    try:
        body = response.json()
    except Exception as exc:  # noqa: BLE001
        text = getattr(response, "text", "")
        raise KieError(f"{context} returned a non-JSON response: {text[:500]}") from exc

    if not isinstance(body, dict):
        raise KieError(f"{context} returned an unexpected payload: {str(body)[:500]}")

    code = body.get("code")
    if code is not None and int(code) != 200:
        message = body.get("msg") or str(body)[:500]
        raise KieError(f"{context} error (code {code}): {message}")

    return body.get("data") or {}


def create_task(
    model: str,
    input_payload: dict[str, Any],
    api_key: str,
    callback_url: str | None = None,
    timeout: int = 60,
) -> str:
    """Submit a Market generation task and return its taskId."""
    import requests

    body: dict[str, Any] = {"model": model, "input": input_payload}
    if callback_url:
        body["callBackUrl"] = callback_url

    try:
        response = requests.post(
            CREATE_TASK_ENDPOINT, headers=_headers(api_key), json=body, timeout=timeout
        )
    except KieError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise KieError(f"Could not reach KIE AI at {CREATE_TASK_ENDPOINT}: {exc}") from exc

    _raise_for_status(response, "KIE AI task creation")
    data = _envelope(response, "KIE AI task creation")
    task_id = data.get("taskId")
    if not task_id:
        raise KieError(f"KIE AI did not return a taskId: {str(data)[:500]}")
    return str(task_id)


def poll_task(
    task_id: str,
    api_key: str,
    interval: float = 3.0,
    timeout: float = 600.0,
    request_timeout: int = 30,
) -> list[str]:
    """Poll a task until it terminates. Returns the list of result URLs.

    Raises KieError on reported failure or when `timeout` seconds elapse.
    """
    import requests

    elapsed = 0.0
    last_state = "unknown"
    consecutive_transport_errors = 0

    while elapsed < timeout:
        try:
            response = requests.get(
                RECORD_INFO_ENDPOINT,
                headers=_headers(api_key, json_body=False),
                params={"taskId": task_id},
                timeout=request_timeout,
            )
        except Exception as exc:  # noqa: BLE001
            consecutive_transport_errors += 1
            if consecutive_transport_errors >= 5:
                raise KieError(
                    f"Polling task {task_id} failed after "
                    f"{consecutive_transport_errors} consecutive transport errors: {exc}"
                ) from exc
            time.sleep(interval)
            elapsed += interval
            continue

        _raise_for_status(response, f"KIE AI poll for {task_id}")
        consecutive_transport_errors = 0
        data = _envelope(response, f"KIE AI poll for {task_id}")
        last_state = str(data.get("state", "unknown")).lower()

        if last_state in TERMINAL_SUCCESS:
            result_json = data.get("resultJson")
            if not result_json:
                raise KieError(f"Task {task_id} reported 'success' but returned no resultJson.")
            try:
                parsed = json.loads(result_json) if isinstance(result_json, str) else result_json
            except Exception as exc:  # noqa: BLE001
                raise KieError(f"Task {task_id} returned unparsable resultJson: {exc}") from exc
            urls = parsed.get("resultUrls") or []
            if not urls:
                raise KieError(f"Task {task_id} succeeded but resultJson had no resultUrls: {parsed}")
            return [str(url) for url in urls]
        if last_state in TERMINAL_FAILURE:
            error = data.get("failMsg") or "no error detail provided"
            raise KieError(f"KIE AI generation failed ({last_state}): {error}")

        time.sleep(interval)
        elapsed += interval

    raise KieError(
        f"Task {task_id} did not finish within {timeout:.0f}s "
        f"(last state: {last_state}). The job may still complete -- "
        f"check {RECORD_INFO_ENDPOINT}?taskId={task_id}"
    )


def upload_file(file_path: str | Path, api_key: str, upload_path: str = "openmontage", timeout: int = 120) -> str:
    """Upload a local file and return the hosted download URL KIE assigns to it.

    Used to turn a local reference image/audio file into the `image_urls`
    (or similar) field most Market models expect. Uploaded files are
    retained for 24 hours only -- the generation call must happen promptly.
    """
    import requests

    path = Path(file_path)
    if not path.exists():
        raise KieError(f"Cannot upload -- file not found: {path}")

    try:
        with path.open("rb") as handle:
            response = requests.post(
                UPLOAD_STREAM_ENDPOINT,
                headers=_headers(api_key, json_body=False),
                files={"file": (path.name, handle)},
                data={"uploadPath": upload_path},
                timeout=timeout,
            )
    except Exception as exc:  # noqa: BLE001
        raise KieError(f"Uploading {path.name} to KIE AI failed: {exc}") from exc

    _raise_for_status(response, "KIE AI upload")
    data = _envelope(response, "KIE AI upload")
    url = data.get("downloadUrl")
    if not url:
        raise KieError(f"KIE AI upload returned no downloadUrl: {str(data)[:500]}")
    return str(url)


def download(url: str, output_path: str | Path, timeout: int = 300) -> Path:
    """Download a generated asset to disk and return the written path."""
    import requests

    try:
        response = requests.get(url, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        raise KieError(f"Downloading KIE AI output failed: {exc}") from exc

    _raise_for_status(response, "KIE AI output download")

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    return path


def resolve_media(value: str, api_key: str) -> str:
    """Return `value` unchanged if it is already a URL, else upload it."""
    text = str(value).strip()
    if text.lower().startswith(("http://", "https://", "data:")):
        return text
    return upload_file(text, api_key)
