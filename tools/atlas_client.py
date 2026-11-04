"""Shared Atlas Cloud API plumbing for the image and video provider tools.

Atlas Cloud (https://www.atlascloud.ai) is a multi-model gateway: one key and one
async prediction contract in front of 400+ third-party models (Seedream, FLUX,
Nano Banana, Kling, Seedance, Hailuo, ...).

Every non-LLM generation follows the same three-step shape:

    POST /api/v1/model/generateImage  ->  {"data": {"id": ...}}
    POST /api/v1/model/generateVideo  ->  {"data": {"id": ...}}
    GET  /api/v1/model/prediction/{id} -> {"data": {"status", "outputs", "error"}}

`requests` is imported lazily inside functions so registry discovery stays fast
(see tests/contracts — the lazy-import convention is enforced by the suite).
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

BASE_URL = "https://api.atlascloud.ai/api/v1"

GENERATE_IMAGE_ENDPOINT = f"{BASE_URL}/model/generateImage"
GENERATE_VIDEO_ENDPOINT = f"{BASE_URL}/model/generateVideo"
PREDICTION_ENDPOINT = f"{BASE_URL}/model/prediction"
UPLOAD_MEDIA_ENDPOINT = f"{BASE_URL}/model/uploadMedia"

# Atlas documents `created`/`processing` as in-flight and both `completed` and
# `succeeded` as terminal success. Treat any unrecognised status as in-flight so a
# newly introduced intermediate state can't be mistaken for a failure.
TERMINAL_SUCCESS = {"completed", "succeeded"}
TERMINAL_FAILURE = {"failed", "canceled", "cancelled"}

ENV_KEYS = ("ATLASCLOUD_API_KEY", "ATLAS_CLOUD_API_KEY", "ATLAS_API_KEY")

INSTALL_INSTRUCTIONS = (
    "Set ATLASCLOUD_API_KEY to your Atlas Cloud API key.\n"
    "  Get one at https://www.atlascloud.ai/ -> Dashboard -> API Keys"
)


class AtlasError(RuntimeError):
    """Raised for any Atlas Cloud API or transport failure."""


def get_api_key() -> str | None:
    """Return the first configured Atlas Cloud key.

    ATLASCLOUD_API_KEY is the name Atlas uses in its own docs and CLI; the other
    two are accepted because they are the names people reach for by habit.
    """
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


def _payload_of(response: Any) -> dict[str, Any]:
    """Parse an Atlas envelope, raising AtlasError with the body on any problem.

    Atlas wraps results as {"code": 200, "data": {...}}. A non-200 `code` can ride
    along with HTTP 200, so the envelope is checked even on a successful request.
    """
    try:
        body = response.json()
    except Exception as exc:  # noqa: BLE001 - surface the raw text, not a parse trace
        text = getattr(response, "text", "")
        raise AtlasError(f"Atlas Cloud returned a non-JSON response: {text[:500]}") from exc

    if not isinstance(body, dict):
        raise AtlasError(f"Atlas Cloud returned an unexpected payload: {str(body)[:500]}")

    code = body.get("code")
    if code is not None and int(code) != 200:
        message = body.get("message") or body.get("error") or str(body)[:500]
        raise AtlasError(f"Atlas Cloud error (code {code}): {message}")

    data = body.get("data")
    if data is None:
        # uploadMedia historically answered with a bare {"url": ...}.
        return body
    if not isinstance(data, dict):
        raise AtlasError(f"Atlas Cloud returned an unexpected 'data' field: {str(data)[:500]}")
    return data


def _raise_for_status(response: Any, context: str) -> None:
    status = getattr(response, "status_code", 200)
    if status >= 400:
        text = getattr(response, "text", "")
        raise AtlasError(f"{context} failed with HTTP {status}: {text[:500]}")


def submit(endpoint: str, payload: dict[str, Any], api_key: str, timeout: int = 60) -> str:
    """Submit a generation request and return its prediction id."""
    import requests

    try:
        response = requests.post(
            endpoint, headers=_headers(api_key), json=payload, timeout=timeout
        )
    except AtlasError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise AtlasError(f"Could not reach Atlas Cloud at {endpoint}: {exc}") from exc

    _raise_for_status(response, "Atlas Cloud submission")
    data = _payload_of(response)

    prediction_id = data.get("id")
    if not prediction_id:
        raise AtlasError(f"Atlas Cloud did not return a prediction id: {str(data)[:500]}")
    return str(prediction_id)


def poll(
    prediction_id: str,
    api_key: str,
    interval: float = 3.0,
    timeout: float = 600.0,
    request_timeout: int = 30,
) -> dict[str, Any]:
    """Poll a prediction until it terminates. Returns the final `data` object.

    Raises AtlasError on reported failure or when `timeout` seconds elapse.
    """
    import requests

    url = f"{PREDICTION_ENDPOINT}/{prediction_id}"
    elapsed = 0.0
    last_status = "unknown"
    consecutive_transport_errors = 0

    while elapsed < timeout:
        try:
            response = requests.get(
                url, headers=_headers(api_key, json_body=False), timeout=request_timeout
            )
        except Exception as exc:  # noqa: BLE001
            consecutive_transport_errors += 1
            if consecutive_transport_errors >= 5:
                raise AtlasError(
                    f"Polling prediction {prediction_id} failed after "
                    f"{consecutive_transport_errors} consecutive transport errors: {exc}"
                ) from exc
            time.sleep(interval)
            elapsed += interval
            continue

        _raise_for_status(response, f"Atlas Cloud poll for {prediction_id}")
        consecutive_transport_errors = 0
        data = _payload_of(response)
        last_status = str(data.get("status", "unknown")).lower()

        if last_status in TERMINAL_SUCCESS:
            outputs = data.get("outputs") or []
            if not outputs:
                raise AtlasError(
                    f"Prediction {prediction_id} reported '{last_status}' but returned no outputs."
                )
            return data
        if last_status in TERMINAL_FAILURE:
            error = data.get("error") or "no error detail provided"
            raise AtlasError(f"Atlas Cloud generation failed ({last_status}): {error}")

        time.sleep(interval)
        elapsed += interval

    raise AtlasError(
        f"Prediction {prediction_id} did not finish within {timeout:.0f}s "
        f"(last status: {last_status}). The job may still complete — "
        f"check {PREDICTION_ENDPOINT}/{prediction_id}"
    )


def upload_media(file_path: str | Path, api_key: str, timeout: int = 120) -> str:
    """Upload a local file and return the hosted URL Atlas assigns to it.

    Used to turn a local reference image into the `image_url` that image-to-video
    models expect. Atlas has answered this endpoint with both {"data":
    {"download_url": ...}} and a bare {"url": ...}, so both shapes are accepted.
    """
    import requests

    path = Path(file_path)
    if not path.exists():
        raise AtlasError(f"Cannot upload — file not found: {path}")

    try:
        with path.open("rb") as handle:
            response = requests.post(
                UPLOAD_MEDIA_ENDPOINT,
                headers=_headers(api_key, json_body=False),
                files={"file": (path.name, handle)},
                timeout=timeout,
            )
    except Exception as exc:  # noqa: BLE001
        raise AtlasError(f"Uploading {path.name} to Atlas Cloud failed: {exc}") from exc

    _raise_for_status(response, "Atlas Cloud upload")
    data = _payload_of(response)

    url = data.get("download_url") or data.get("url")
    if not url:
        raise AtlasError(f"Atlas Cloud upload returned no URL: {str(data)[:500]}")
    return str(url)


def download(url: str, output_path: str | Path, timeout: int = 300) -> Path:
    """Download a generated asset to disk and return the written path."""
    import requests

    try:
        response = requests.get(url, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        raise AtlasError(f"Downloading Atlas Cloud output failed: {exc}") from exc

    _raise_for_status(response, "Atlas Cloud output download")

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    return path


def aspect_ratio_from_size(width: int, height: int, allowed: list[str]) -> str:
    """Pick the closest ratio in `allowed` to width/height.

    OpenMontage's canonical params are width/height, but many Atlas models only
    accept a ratio enum. Snapping to the nearest supported ratio beats sending a
    value the model will reject.
    """
    if not allowed:
        return "16:9"
    if height <= 0 or width <= 0:
        return allowed[0]

    target = width / height
    best = allowed[0]
    best_delta = float("inf")
    for ratio in allowed:
        if ratio == "auto" or ":" not in ratio:
            continue
        left, _, right = ratio.partition(":")
        try:
            candidate = float(left) / float(right)
        except (ValueError, ZeroDivisionError):
            continue
        delta = abs(candidate - target)
        if delta < best_delta:
            best_delta = delta
            best = ratio
    return best
