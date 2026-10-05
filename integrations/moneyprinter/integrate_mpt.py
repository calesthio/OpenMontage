#!/usr/bin/env python3

"""Bridge MoneyPrinterTurbo generation into the local YouTube Shorts workflow.

This is a lightweight adapter for generating a short from a prompt, then uploading the
produced MP4 to YouTube using OAuth credentials.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
except Exception:  # pragma: no cover - optional runtime dependency for upload flow
    InstalledAppFlow = None
    build = None
    MediaFileUpload = None

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def run_moneyprinter(subject: str, extra_args: list[str] | None = None) -> dict:
    repo_root = Path(__file__).resolve().parents[2]
    mpt_dir = repo_root / "external_repos" / "MoneyPrinterTurbo"
    if not mpt_dir.exists():
        raise FileNotFoundError(f"MoneyPrinterTurbo checkout not found at {mpt_dir}")

    cmd = [
        sys.executable,
        str(mpt_dir / "cli.py"),
        "--video-subject",
        subject,
        "--stop-at",
        "video",
    ]
    if extra_args:
        cmd.extend(extra_args)

    print(f"Running MoneyPrinterTurbo: {' '.join(cmd)}")
    proc = subprocess.run(
        cmd,
        cwd=str(mpt_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"MoneyPrinterTurbo failed: {proc.stderr.strip() or proc.stdout.strip()}")

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        start = proc.stdout.find("{")
        end = proc.stdout.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise RuntimeError(
                "MoneyPrinterTurbo did not return parseable JSON. Raw stdout:\n"
                + proc.stdout
            )
        return json.loads(proc.stdout[start : end + 1])


def find_rendered_video(result: dict) -> str | None:
    seen = set()

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in seen:
                    continue
                seen.add(key)
                match = walk(value)
                if match:
                    return match
        elif isinstance(node, list):
            for item in node:
                match = walk(item)
                if match:
                    return match
        elif isinstance(node, str) and node.lower().endswith(".mp4"):
            return node
        return None

    discovered = walk(result)
    if discovered:
        return discovered

    tasks_dir = Path(__file__).resolve().parents[2] / "external_repos" / "MoneyPrinterTurbo" / "storage" / "tasks"
    if tasks_dir.exists():
        for candidate in sorted(tasks_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            final_video = candidate / "renders" / "final.mp4"
            if final_video.exists():
                return str(final_video)
    return None


def upload_to_youtube(video_path: str, title: str, description: str, privacy: str, client_secrets_path: str | None) -> dict:
    if InstalledAppFlow is None or build is None or MediaFileUpload is None:
        raise RuntimeError(
            "Google upload dependencies are missing. Install: pip install google-auth-oauthlib google-api-python-client"
        )

    if client_secrets_path is None:
        client_secrets_path = str(Path.cwd() / "client_secrets.json")
    client_secrets = Path(client_secrets_path)
    if not client_secrets.exists():
        raise FileNotFoundError(
            "OAuth client_secrets.json not found. Place your Google OAuth client JSON next to this script or pass --client-secrets."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), SCOPES)
    credentials = flow.run_local_server(port=0)
    youtube = build("youtube", "v3", credentials=credentials)

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": [],
            "categoryId": "22",
        },
        "status": {"privacyStatus": privacy},
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/*")
    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    response = None
    print("Uploading to YouTube ...")
    while response is None:
        status, response = request.next_chunk()
        if status is not None:
            print(f"Upload progress: {int(status.progress() * 100)}%")
    return response


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a MoneyPrinterTurbo short and upload it to YouTube.")
    parser.add_argument("--subject", required=True, help="Short topic or keyword to generate")
    parser.add_argument("--privacy", choices=["public", "unlisted", "private"], default="public")
    parser.add_argument(
        "--client-secrets",
        default=None,
        help="Path to a Google OAuth client_secrets.json file. Defaults to ./client_secrets.json.",
    )
    parser.add_argument(
        "--video-title",
        default=None,
        help="Override generated title for YouTube upload.",
    )
    parser.add_argument(
        "--description",
        default="",
        help="Optional description to include on the YouTube upload.",
    )
    args = parser.parse_args()

    pipeline_result = run_moneyprinter(args.subject)
    render_path = find_rendered_video(pipeline_result)
    if render_path is None:
        raise RuntimeError("No MP4 output was found in the MoneyPrinterTurbo result payload.")

    title = args.video_title or pipeline_result.get("title") or f"{args.subject} - Spyderlabs Short"
    description = args.description or pipeline_result.get("caption") or "Generated with MoneyPrinterTurbo"

    upload_result = upload_to_youtube(render_path, title, description, args.privacy, args.client_secrets)
    print(json.dumps(upload_result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
