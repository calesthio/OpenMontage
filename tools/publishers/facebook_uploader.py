"""
Facebook Reels Uploader using Meta Graph API.
Uploads 1080x1920 MP4 Shorts directly to Facebook Page Reels.
"""

import os
import sys
import json
import logging
import requests
from pathlib import Path
from typing import Optional, Dict, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FacebookUploader")

GRAPH_API_VERSION = "v19.0"
GRAPH_BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

class FacebookReelsUploader:
    def __init__(self, page_id: Optional[str] = None, access_token: Optional[str] = None):
        self.page_id = page_id or os.environ.get("FB_PAGE_ID") or os.environ.get("FACEBOOK_PAGE_ID")
        self.access_token = access_token or os.environ.get("FB_PAGE_ACCESS_TOKEN") or os.environ.get("FACEBOOK_ACCESS_TOKEN")

    def is_configured(self) -> bool:
        return bool(self.page_id and self.access_token)

    def upload_reel(self, video_path: str, title: str, description: str = "") -> Optional[Dict[str, Any]]:
        """
        Uploads a video to Facebook Reels using the 3-step Graph API flow.
        """
        if not self.is_configured():
            logger.warning("[FB_UPLOADER] Facebook Page ID or Access Token not configured. Skipping FB upload.")
            return None

        video_file = Path(video_path)
        if not video_file.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        file_size = video_file.stat().st_size
        caption = f"{title}\n\n{description}".strip()

        logger.info(f"[FB_UPLOADER] Starting Reels upload for '{title}' ({file_size / (1024*1024):.2f} MB)...")

        # Step 1: Initialize Upload Session
        init_url = f"{GRAPH_BASE_URL}/{self.page_id}/video_reels"
        init_payload = {
            "upload_phase": "start",
            "access_token": self.access_token
        }
        init_resp = requests.post(init_url, data=init_payload)
        if init_resp.status_code != 200:
            logger.error(f"[FB_UPLOADER] Init failed: {init_resp.text}")
            return None

        init_data = init_resp.json()
        video_id = init_data.get("video_id")
        upload_url = init_data.get("upload_url")

        if not video_id or not upload_url:
            logger.error(f"[FB_UPLOADER] Invalid init response: {init_data}")
            return None

        logger.info(f"[FB_UPLOADER] Upload session initialized. Video ID: {video_id}")

        # Step 2: Upload Binary Bytes
        upload_headers = {
            "Authorization": f"OAuth {self.access_token}",
            "offset": "0",
            "file_size": str(file_size)
        }
        with open(video_file, "rb") as f:
            upload_resp = requests.post(upload_url, headers=upload_headers, data=f)

        if upload_resp.status_code != 200:
            logger.error(f"[FB_UPLOADER] Binary upload failed: {upload_resp.text}")
            return None

        logger.info(f"[FB_UPLOADER] Video binary transferred successfully.")

        # Step 3: Publish Reel
        publish_url = f"{GRAPH_BASE_URL}/{self.page_id}/video_reels"
        publish_payload = {
            "upload_phase": "finish",
            "video_id": video_id,
            "video_state": "PUBLISHED",
            "description": caption,
            "access_token": self.access_token
        }
        publish_resp = requests.post(publish_url, data=publish_payload)
        if publish_resp.status_code != 200:
            logger.error(f"[FB_UPLOADER] Publishing failed: {publish_resp.text}")
            return None

        publish_data = publish_resp.json()
        logger.info(f"[FB_UPLOADER] ✅ Published Reel successfully! Video ID: {video_id}")

        return {
            "video_id": video_id,
            "success": publish_data.get("success", True),
            "fb_url": f"https://www.facebook.com/reel/{video_id}"
        }

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python facebook_uploader.py <video_path> <title> [description]")
        sys.exit(1)

    v_path = sys.argv[1]
    v_title = sys.argv[2]
    v_desc = sys.argv[3] if len(sys.argv) > 3 else ""

    uploader = FacebookReelsUploader()
    res = uploader.upload_reel(v_path, v_title, v_desc)
    if res:
        print(json.dumps(res, indent=2))
