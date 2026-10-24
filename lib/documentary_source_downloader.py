"""
documentary_source_downloader.py
Automated 1080p/4K Documentary Video Downloader for OpenMontage.
Supports Direct GitHub Releases Assets, direct CDN MP4s, and yt-dlp fallback.
"""

import json
import subprocess
import urllib.request
import os
import sys
from pathlib import Path
from typing import Any, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
DOCUMENTS_DIR = ROOT_DIR / "assets" / "documentaries"


class DocumentarySourceDownloader:
    def __init__(self, output_base_dir: Optional[Path] = None):
        self.output_base_dir = output_base_dir or DOCUMENTS_DIR
        self.output_base_dir.mkdir(parents=True, exist_ok=True)

    def download_from_url(
        self,
        url: str,
        animal: str,
        resolution: str = "1080p",
        force: bool = False,
    ) -> Path:
        animal_clean = animal.lower().strip().replace(" ", "_")
        animal_dir = self.output_base_dir / animal_clean
        animal_dir.mkdir(parents=True, exist_ok=True)
        target_file = animal_dir / f"{animal_clean}_doc_source_01.mp4"

        if not force and target_file.exists() and target_file.stat().st_size > 5_000_000:
            print(f"[DOWNLOADER] Using cached source file: {target_file} ({target_file.stat().st_size} bytes)")
            return target_file

        # Strategy 1: Direct URL Download (GitHub Release Asset / CDN / Direct MP4)
        if ("github.com" in url and "/releases/download/" in url) or url.endswith(".mp4") or "raw.githubusercontent.com" in url:
            print(f"[DOWNLOADER] Fast-Path: Downloading direct release asset from {url}...")
            try:
                opener = urllib.request.build_opener()
                opener.addheaders = [("User-Agent", "OpenMontage/1.0")]
                urllib.request.install_opener(opener)
                urllib.request.urlretrieve(url, str(target_file))
                if target_file.exists() and target_file.stat().st_size > 1_000_000:
                    print(f"[DOWNLOADER] Successfully downloaded release asset: {target_file} ({target_file.stat().st_size} bytes)")
                    return target_file
            except Exception as e:
                print(f"[DOWNLOADER] Direct URL download failed: {e}")

        # Strategy 2: yt-dlp with android_vr / web_embedded client (no PO token required)
        print(f"[DOWNLOADER] Running yt-dlp download...")
        cmd_ytdlp = [
            "yt-dlp",
            "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
            "--merge-output-format", "mp4",
            "--no-playlist",
            "--no-warnings",
            "--extractor-args", "youtube:player_client=android_vr,web_embedded",
            "-o", str(target_file),
            url,
        ]
        res = subprocess.run(cmd_ytdlp, capture_output=True, text=True)
        if target_file.exists() and target_file.stat().st_size > 500_000:
            print(f"[DOWNLOADER] Success via yt-dlp: {target_file} ({target_file.stat().st_size} bytes)")
            return target_file

        raise RuntimeError(f"Failed to download source footage from {url}. Error: {res.stderr}")
