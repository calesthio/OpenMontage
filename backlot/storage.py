"""R2 storage helpers for hosted Ray workspaces."""

from __future__ import annotations

import mimetypes
import os
import time
from pathlib import Path
from typing import Any


def configured() -> bool:
    required = ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET", "R2_ENDPOINT")
    return all(os.environ.get(key) for key in required)


def public_url_for(key: str) -> str | None:
    base = os.environ.get("R2_PUBLIC_URL")
    if not base:
        return None
    return f"{base.rstrip('/')}/{key.lstrip('/')}"


def key_for(project_id: str, rel_path: str) -> str:
    prefix = os.environ.get("R2_PREFIX", "ikawn-v1/workspaces").strip("/")
    clean_rel = rel_path.strip("/").replace("\\", "/")
    return f"{prefix}/{project_id}/{clean_rel}"


def _client():
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name=os.environ.get("R2_REGION", "auto"),
    )


def upload_file(path: Path, project_id: str, rel_path: str | None = None) -> dict[str, Any]:
    if not configured():
        return {"uploaded": False, "reason": "r2_not_configured"}
    path = Path(path)
    rel = rel_path or path.name
    key = key_for(project_id, rel)
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    _client().upload_file(
        str(path),
        os.environ["R2_BUCKET"],
        key,
        ExtraArgs={"ContentType": content_type},
    )
    return {
        "uploaded": True,
        "bucket": os.environ["R2_BUCKET"],
        "key": key,
        "url": public_url_for(key),
        "content_type": content_type,
        "size": path.stat().st_size,
    }


def presigned_put(project_id: str, rel_path: str, content_type: str, expires_in: int = 900) -> dict[str, Any]:
    if not configured():
        raise RuntimeError("R2 is not configured")
    key = key_for(project_id, rel_path)
    url = _client().generate_presigned_url(
        "put_object",
        Params={
            "Bucket": os.environ["R2_BUCKET"],
            "Key": key,
            "ContentType": content_type or "application/octet-stream",
        },
        ExpiresIn=expires_in,
        HttpMethod="PUT",
    )
    return {
        "put_url": url,
        "key": key,
        "url": public_url_for(key),
        "bucket": os.environ["R2_BUCKET"],
        "content_type": content_type or "application/octet-stream",
        "expires_at": int(time.time()) + expires_in,
        "required_headers": {"Content-Type": content_type or "application/octet-stream"},
    }


def object_info(key: str) -> dict[str, Any]:
    if not configured():
        raise RuntimeError("R2 is not configured")
    response = _client().head_object(Bucket=os.environ["R2_BUCKET"], Key=key)
    return {
        "bucket": os.environ["R2_BUCKET"],
        "key": key,
        "url": public_url_for(key),
        "content_type": response.get("ContentType") or "application/octet-stream",
        "size": int(response.get("ContentLength") or 0),
    }
