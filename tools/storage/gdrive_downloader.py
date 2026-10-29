"""
tools/storage/gdrive_downloader.py
Automated Google Drive downloader for OpenMontage Wildlife Documentary footage.
Supports:
1. Direct Google Drive Shareable File URLs & File IDs
2. Automated confirmation token handling for large video files (>100MB)
3. Google Drive Folder batch sync via gdown / Google Drive API
"""

import os
import re
import sys
import json
import logging
import requests
from pathlib import Path
from typing import Optional, Dict, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("GDriveDownloader")


def extract_gdrive_id(url_or_id: str) -> str:
    """Extracts the clean Google Drive file ID from full URLs or bare IDs."""
    if not url_or_id:
        return ""
    
    url_or_id = str(url_or_id).strip()
    # Match /file/d/<id>/ or id=<id>
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", url_or_id)
    if match:
        return match.group(1)
    
    match_id = re.search(r"id=([a-zA-Z0-9_-]+)", url_or_id)
    if match_id:
        return match_id.group(1)
    
    # If already a plain ID
    if re.match(r"^[a-zA-Z0-9_-]{20,}$", url_or_id):
        return url_or_id
        
    return url_or_id


def download_file_from_google_drive(id_or_url: str, destination: Path) -> bool:
    """
    Downloads a public or shareable Google Drive file with large-file chunking and virus-scan token handling.
    """
    file_id = extract_gdrive_id(id_or_url)
    if not file_id:
        logger.error(f"[GDRIVE] Invalid Google Drive file ID/URL: {id_or_url}")
        return False

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists() and destination.stat().st_size > 1024 * 1024:
        logger.info(f"[GDRIVE] File already exists: {destination.name} ({destination.stat().st_size / (1024*1024):.1f} MB)")
        return True

    logger.info(f"[GDRIVE] Downloading Google Drive file ID '{file_id}' -> {destination.name}...")

    # Method 1: Try via gdown if installed
    try:
        import gdown
        url = f"https://drive.google.com/uc?id={file_id}"
        output = gdown.download(url, str(destination), quiet=False, fuzzy=True)
        if output and Path(output).exists() and Path(output).stat().st_size > 1024:
            logger.info(f"[GDRIVE] Download complete via gdown: {destination.name} ({destination.stat().st_size / (1024*1024):.1f} MB)")
            return True
    except Exception as e:
        logger.debug(f"[GDRIVE] gdown attempt failed or not available ({e}), falling back to direct stream...")

    # Method 2: Direct HTTP streaming with session & cookie bypass
    URL = "https://docs.google.com/uc?export=download"
    session = requests.Session()

    response = session.get(URL, params={"id": file_id, "confirm": "t"}, stream=True)
    
    # Check for confirmation token if required
    token = None
    for key, value in response.cookies.items():
        if key.startswith("download_warning"):
            token = value
            break

    if token:
        params = {"id": file_id, "confirm": token}
        response = session.get(URL, params=params, stream=True)

    if response.status_code != 200:
        logger.error(f"[GDRIVE] HTTP Error {response.status_code} while downloading file {file_id}")
        return False

    CHUNK_SIZE = 32768
    total_bytes = 0
    with open(destination, "wb") as f:
        for chunk in response.iter_content(CHUNK_SIZE):
            if chunk:
                f.write(chunk)
                total_bytes += len(chunk)

    if total_bytes < 10000:
        # Check if Google returned an HTML error page instead of video binary
        with open(destination, "r", encoding="utf-8", errors="ignore") as f:
            content_preview = f.read(500)
            if "<html" in content_preview.lower():
                logger.error(f"[GDRIVE] Download failed: Google Drive returned HTML error instead of video binary: {content_preview[:200]}")
                destination.unlink(missing_ok=True)
                return False

    logger.info(f"[GDRIVE] Successfully downloaded {destination.name} ({total_bytes / (1024*1024):.1f} MB)")
    return True


def sync_from_gdrive_folder(folder_url_or_id: str, output_dir: Path) -> list:
    """
    Syncs all media files from a Google Drive folder into the specified output directory.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    folder_id = extract_gdrive_id(folder_url_or_id)
    folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
    
    logger.info(f"[GDRIVE] Syncing folder: {folder_url} -> {output_dir}")
    try:
        import gdown
        downloaded = gdown.download_folder(folder_url, output=str(output_dir), quiet=False, use_cookies=False)
        return downloaded or []
    except Exception as e:
        logger.error(f"[GDRIVE] Failed to sync folder via gdown: {e}")
        return []


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python gdrive_downloader.py <GDRIVE_URL_OR_ID> <OUTPUT_PATH>")
        sys.exit(1)
    
    url_arg = sys.argv[1]
    out_arg = Path(sys.argv[2])
    success = download_file_from_google_drive(url_arg, out_arg)
    sys.exit(0 if success else 1)
