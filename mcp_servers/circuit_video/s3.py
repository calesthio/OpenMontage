"""AWS S3 upload + presign using SigV4 (stdlib only).

Talks to real AWS S3, not the in-cluster MinIO the k8s worker uses.
Credentials come from the MCP config (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY).
"""

from __future__ import annotations

import hashlib
import hmac
import xml.etree.ElementTree as ET
import http.client
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import quote


def object_key(prefix: str, render_id: str, filename: str = "final.mp4") -> str:
    prefix = (prefix or "").lstrip("/")
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    return f"{prefix}{render_id}/{filename}"


def public_url(bucket: str, region: str, key: str, public_base: str = "") -> str:
    if public_base:
        return f"{public_base.rstrip('/')}/{key}"
    return f"https://{bucket}.s3.{region}.amazonaws.com/{_encode_path(key)}"


def _encode_path(path: str) -> str:
    return quote(path, safe="/-_.~")


def _uri_encode(value: str, encode_slash: bool = True) -> str:
    safe = "-_.~" if encode_slash else "/-_.~"
    return quote(value, safe=safe)


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256_hex(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret: str, datestamp: str, region: str, service: str) -> bytes:
    k_date = _sign(("AWS4" + secret).encode("utf-8"), datestamp)
    k_region = hmac.new(k_date, region.encode("utf-8"), hashlib.sha256).digest()
    k_service = hmac.new(k_region, service.encode("utf-8"), hashlib.sha256).digest()
    return hmac.new(k_service, b"aws4_request", hashlib.sha256).digest()


def _host(bucket: str, region: str) -> str:
    return f"{bucket}.s3.{region}.amazonaws.com"


def _amz_now(now: Optional[datetime] = None) -> tuple[str, str]:
    now = now or datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    return amz_date, amz_date[:8]


def _canonical_query(params: dict[str, str]) -> str:
    return "&".join(
        f"{_uri_encode(k)}={_uri_encode(v)}"
        for k, v in sorted(params.items())
    )


def _authorization(
    *,
    method: str,
    host: str,
    canonical_uri: str,
    query: str,
    headers: dict[str, str],
    payload_hash: str,
    amz_date: str,
    datestamp: str,
    region: str,
    access_key: str,
    secret_key: str,
    extra_signed: tuple[str, ...] = (),
) -> str:
    signed = ["host", "x-amz-content-sha256", "x-amz-date", *extra_signed]
    signed = sorted(set(signed))
    canonical_headers = "".join(f"{k}:{headers[k]}\n" for k in signed)
    signed_headers = ";".join(signed)
    canonical = (
        f"{method}\n{canonical_uri}\n{query}\n"
        f"{canonical_headers}\n{signed_headers}\n{payload_hash}"
    )
    scope = f"{datestamp}/{region}/s3/aws4_request"
    string_to_sign = (
        f"AWS4-HMAC-SHA256\n{amz_date}\n{scope}\n{_sha256_hex(canonical.encode('utf-8'))}"
    )
    signature = hmac.new(
        _signing_key(secret_key, datestamp, region, "s3"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return (
        "AWS4-HMAC-SHA256 "
        f"Credential={access_key}/{scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )


def _parse_s3_error(body: bytes, status: int) -> str:
    text = body.decode("utf-8", "replace")
    try:
        root = ET.fromstring(text)
        code = (root.findtext("Code") or "").strip()
        msg = (root.findtext("Message") or "").strip()
        if code or msg:
            return f"S3 HTTP {status} {code}: {msg}".strip()
    except ET.ParseError:
        pass
    return f"S3 HTTP {status}: {text[:400]}"


def upload_file(
    path: Path,
    *,
    bucket: str,
    key: str,
    region: str,
    access_key: str,
    secret_key: str,
    content_type: str = "video/mp4",
) -> str:
    """PUT the file to s3://bucket/key. Returns the s3 URI."""
    if not path.exists():
        raise FileNotFoundError(f"upload source not found: {path}")
    host = _host(bucket, region)
    canonical_uri = "/" + _encode_path(key)
    payload_hash = _file_sha256_hex(path)
    amz_date, datestamp = _amz_now()
    content_type = content_type or "video/mp4"
    headers = {
        "host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
        "content-type": content_type,
    }
    auth = _authorization(
        method="PUT",
        host=host,
        canonical_uri=canonical_uri,
        query="",
        headers=headers,
        payload_hash=payload_hash,
        amz_date=amz_date,
        datestamp=datestamp,
        region=region,
        access_key=access_key,
        secret_key=secret_key,
        extra_signed=("content-type",),
    )
    http_headers = {
        "Host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
        "Content-Type": content_type,
        "Content-Length": str(path.stat().st_size),
        "Authorization": auth,
    }
    conn = http.client.HTTPSConnection(host, timeout=300)
    try:
        with path.open("rb") as body:
            conn.request("PUT", canonical_uri, body=body, headers=http_headers)
            resp = conn.getresponse()
            data = resp.read()
            if resp.status not in (200, 204):
                raise RuntimeError(_parse_s3_error(data, resp.status))
    finally:
        conn.close()
    return f"s3://{bucket}/{key}"


def presign_get(
    *,
    bucket: str,
    key: str,
    region: str,
    access_key: str,
    secret_key: str,
    expires: int = 86400,
    now: Optional[datetime] = None,
) -> str:
    """Return a presigned GET URL (default 24h, matching the k8s render-api)."""
    expires = max(1, min(int(expires), 7 * 24 * 3600))
    host = _host(bucket, region)
    canonical_uri = "/" + _encode_path(key)
    amz_date, datestamp = _amz_now(now)
    scope = f"{datestamp}/{region}/s3/aws4_request"
    params = {
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
        "X-Amz-Credential": f"{access_key}/{scope}",
        "X-Amz-Date": amz_date,
        "X-Amz-Expires": str(expires),
        "X-Amz-SignedHeaders": "host",
    }
    query = _canonical_query(params)
    payload_hash = "UNSIGNED-PAYLOAD"
    headers = {"host": host, "x-amz-content-sha256": payload_hash, "x-amz-date": amz_date}
    # Presigned URLs sign only the headers listed in X-Amz-SignedHeaders (host).
    signed = ["host"]
    canonical_headers = "".join(f"{k}:{headers[k]}\n" for k in signed)
    canonical = (
        f"GET\n{canonical_uri}\n{query}\n{canonical_headers}\n"
        f"{';'.join(signed)}\n{payload_hash}"
    )
    string_to_sign = (
        f"AWS4-HMAC-SHA256\n{amz_date}\n{scope}\n{_sha256_hex(canonical.encode('utf-8'))}"
    )
    signature = hmac.new(
        _signing_key(secret_key, datestamp, region, "s3"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"https://{host}{canonical_uri}?{query}&X-Amz-Signature={signature}"


def upload_render(cfg: dict, render_id: str, file_path: Path) -> dict:
    """Upload a finished MP4 and return s3_uri + download_url."""
    key = object_key(cfg["s3_prefix"], render_id, file_path.name)
    s3_uri = upload_file(
        file_path,
        bucket=cfg["s3_bucket"],
        key=key,
        region=cfg["s3_region"],
        access_key=cfg["aws_access_key_id"],
        secret_key=cfg["aws_secret_access_key"],
    )
    if cfg.get("s3_public_base"):
        download_url = public_url(cfg["s3_bucket"], cfg["s3_region"], key, cfg["s3_public_base"])
    else:
        download_url = presign_get(
            bucket=cfg["s3_bucket"],
            key=key,
            region=cfg["s3_region"],
            access_key=cfg["aws_access_key_id"],
            secret_key=cfg["aws_secret_access_key"],
        )
    return {"s3_uri": s3_uri, "s3_key": key, "download_url": download_url}
