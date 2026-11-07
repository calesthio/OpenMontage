#!/usr/bin/env python3
"""Upload a finished render to S3-compatible object storage (MinIO).

Reads MinIO connection from env (MINIO_ENDPOINT, MINIO_ACCESS_KEY,
MINIO_SECRET_KEY, MINIO_SECURE). Used by the worker entrypoint after
render_tutorial.py so the render-api can hand back a presigned download URL.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--file", default=None, help="override the source file path")
    args = ap.parse_args()

    projects_dir = os.environ.get("OPENMONTAGE_PROJECTS_DIR", "/work/projects")
    src = Path(args.file) if args.file else Path(projects_dir) / args.project_id / "renders" / "final.mp4"
    if not src.exists():
        print(f"ERROR: render not found: {src}", file=sys.stderr)
        return 2

    try:
        from minio import Minio
    except ImportError:
        print("ERROR: minio package not installed in the worker image", file=sys.stderr)
        return 3

    endpoint = os.environ["MINIO_ENDPOINT"]  # host:port (no scheme)
    secure = os.environ.get("MINIO_SECURE", "false").lower() in ("1", "true", "yes")
    client = Minio(
        endpoint,
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=secure,
    )
    if not client.bucket_exists(args.bucket):
        client.make_bucket(args.bucket)
    client.fput_object(args.bucket, args.key, str(src), content_type="video/mp4")
    print(f"OK uploaded s3://{args.bucket}/{args.key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
