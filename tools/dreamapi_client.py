"""DreamAPI HTTP client.

``requests`` is imported inside functions so tool discovery stays cheap.
The API key is read from ``DREAMAPI_API_KEY`` and is never logged.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

BASE_URL = "https://api.newportai.com"
ENV_KEY = "DREAMAPI_API_KEY"
INSTALL_INSTRUCTIONS = (
    "Set DREAMAPI_API_KEY to a key from the DreamAPI dashboard "
    "(https://api.newportai.com/). Register and top up there. "
    "The key stays in your environment and is not written by OpenMontage."
)


class DreamApiError(RuntimeError):
    pass


def get_api_key() -> str:
    return os.environ.get(ENV_KEY, "").strip()


def _requests():
    import requests
    return requests


def _check(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("code") != 0:
        raise DreamApiError(payload.get("message") or "DreamAPI request failed")
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        raise DreamApiError("DreamAPI response did not contain a data object")
    return data


def post_json(path: str, body: dict[str, Any], api_key: str, timeout: float = 60) -> dict[str, Any]:
    response = _requests().post(
        f"{BASE_URL}{path}",
        json=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=timeout,
    )
    response.raise_for_status()
    return _check(response.json())


def is_remote(value: str) -> bool:
    lowered = value.strip().lower()
    return lowered.startswith(("http://", "https://", "data:"))


def upload_local(path: str, api_key: str) -> str:
    file_path = Path(path)
    if not file_path.is_file():
        raise DreamApiError(f"DreamAPI media file not found: {path}")
    policy = post_json("/api/file/v1/get_policy", {"scene": "Dream-CN"}, api_key)
    host = str(policy.get("host") or "")
    access_id = str(policy.get("accessId") or policy.get("OSSAccessKeyId") or "")
    policy_text = str(policy.get("policy") or "")
    signature = str(policy.get("signature") or "")
    object_key = str(policy.get("key") or "")
    if not object_key and policy.get("dir"):
        object_key = f"{policy['dir']}{file_path.name}"
    if not all((host, access_id, policy_text, signature, object_key)):
        raise DreamApiError("DreamAPI upload policy is incomplete")
    with file_path.open("rb") as handle:
        uploaded = _requests().post(
            host,
            data={
                "key": object_key,
                "policy": policy_text,
                "OSSAccessKeyId": access_id,
                "signature": signature,
                "callback": str(policy.get("callback") or ""),
                "success_action_status": "200",
            },
            files={"file": (file_path.name, handle)},
            timeout=300,
        )
    uploaded.raise_for_status()
    uploaded_json = uploaded.json()
    req_id = ((uploaded_json.get("data") or {}).get("reqId")) or policy.get("reqId")
    if not req_id:
        raise DreamApiError("DreamAPI upload did not return reqId")
    finished = post_json("/api/file/v1/policy_upload_finish", {"reqId": req_id}, api_key)
    url = str(finished.get("url") or "")
    if not url:
        raise DreamApiError("DreamAPI upload did not return a URL")
    return url


def resolve_media(value: str, api_key: str) -> str:
    if is_remote(value):
        return value
    return upload_local(value, api_key)


def resolve_body_media(spec: dict[str, Any], inputs: dict[str, Any], api_key: str) -> dict[str, Any]:
    resolved = dict(inputs)
    for field in spec["fields"]:
        value = resolved.get(field["key"])
        if field["kind"] == "media" and isinstance(value, str):
            resolved[field["key"]] = resolve_media(value, api_key)
        elif field["kind"] == "media_list" and isinstance(value, list):
            resolved[field["key"]] = [resolve_media(item, api_key) for item in value if isinstance(item, str)]
    return resolved


def collect_outputs(data: dict[str, Any]) -> tuple[list[str], str | None]:
    urls: list[str] = []
    for collection, key in (("images", "imageUrl"), ("videos", "videoUrl"), ("audios", "audioUrl")):
        for item in data.get(collection) or []:
            if isinstance(item, dict) and isinstance(item.get(key), str):
                urls.append(item[key])
    matting = data.get("mattingResult")
    if isinstance(matting, dict):
        for key in ("mattingFileUrl", "mattingAlphaFileUrl", "compositeFileUrl"):
            if isinstance(matting.get(key), str):
                urls.append(matting[key])
    clone_id = data.get("cloneId") if isinstance(data.get("cloneId"), str) else None
    return list(dict.fromkeys(urls)), clone_id


def run_task(
    endpoint: str,
    body: dict[str, Any],
    api_key: str,
    *,
    task_id: str = "",
    interval: float = 3.0,
    timeout: float = 900.0,
) -> dict[str, Any]:
    import time
    current = task_id.strip()
    if not current:
        submitted = post_json(endpoint, body, api_key)
        current = str(submitted.get("taskId") or "")
        if not current:
            raise DreamApiError("DreamAPI did not return a taskId")
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = post_json("/api/getAsyncResult", {"taskId": current}, api_key, timeout=30)
        task = data.get("task") if isinstance(data.get("task"), dict) else {}
        status = task.get("status")
        if status == 3:
            urls, clone_id = collect_outputs(data)
            if not urls and not clone_id:
                raise DreamApiError("DreamAPI succeeded without a media URL")
            return {"task_id": current, "urls": urls, "clone_id": clone_id}
        if status == 4:
            raise DreamApiError(str(task.get("reason") or "DreamAPI generation failed"))
        time.sleep(interval)
    raise DreamApiError("DreamAPI generation timed out")


def execute_catalog(capability: str, inputs: dict[str, Any], default_name: str) -> dict[str, Any]:
    """Validate, submit or resume, download, and return tool data. Raises DreamApiError or ValueError."""
    from tools.dreamapi_models import MODELS, build_body

    api_key = get_api_key()
    if not api_key:
        raise DreamApiError("DREAMAPI_API_KEY not set. " + INSTALL_INSTRUCTIONS)
    model_id = str(inputs.get("model") or "")
    spec, _ = build_body(model_id, inputs, capability)
    task_id = str(inputs.get("task_id") or "")
    if task_id:
        body: dict[str, Any] = {}
        endpoint = spec["endpoint"]
    else:
        resolved = resolve_body_media(spec, inputs, api_key)
        spec, body = build_body(model_id, resolved, capability)
        endpoint = spec["endpoint"]
    result = run_task(
        endpoint,
        body,
        api_key,
        task_id=task_id,
        interval=float(inputs.get("poll_interval", 3.0)),
        timeout=float(inputs.get("poll_timeout", 900.0)),
    )
    requested = Path(inputs.get("output_path") or default_name)
    paths: list[str] = []
    for index, url in enumerate(result["urls"]):
        output = requested if index == 0 else requested.with_name(f"{requested.stem}_{index + 1}{requested.suffix or '.bin'}")
        download(url, output)
        paths.append(str(output))
    return {
        "provider": "dreamapi",
        "model": model_id,
        "note": MODELS[model_id]["note"],
        "output": paths[0] if paths else "",
        "outputs": paths,
        "task_id": result["task_id"],
        "source_urls": result["urls"],
        "clone_id": result["clone_id"],
        "cost_note": "DreamAPI bills the account that owns DREAMAPI_API_KEY. Confirm the price in the dashboard before a batch.",
    }


def download(url: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    response = _requests().get(url, timeout=300)
    response.raise_for_status()
    output_path.write_bytes(response.content)
