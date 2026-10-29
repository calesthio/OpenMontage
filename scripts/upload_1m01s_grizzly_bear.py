"""
upload_1m01s_grizzly_bear.py
Uploads the 1:01 (61.2s) Master Grizzly Bear Short with 0:17 Battle Hook & Thumbnail to YouTube.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# UTF-8 stdout
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.publishers.youtube_uploader import YouTubeUploader
from lib.notifier import NotificationDispatcher

uploader = YouTubeUploader()
video_file = ROOT / "projects" / "grizzly_bear" / "renders" / "grizzly_bear_1m01s_master.mp4"
thumb_file = ROOT / "projects" / "grizzly_bear" / "assets" / "bear_battle_1m01s_thumbnail.jpg"

print(f"🚀 Uploading 1:01 Master Short ({video_file.stat().st_size / (1024*1024):.1f} MB, Duration: 61.2s) with Battle Thumbnail to YouTube Shorts...")

title = "Why Salmon Willingly Jump Into A Bear's Mouth 😱 #shorts #wildlife"
description = (
    "Why do thousands of migrating salmon leap directly into the jaws of waiting grizzly bears? "
    "Discover the brutal biological mechanics of the river apex predator!\n\n"
    "🔔 Follow Wild Mechanics for daily wildlife micro-stories and predator breakdowns.\n\n"
    "#shorts #wildlife #grizzlybear #nature #animals #documentary #wildmechanics #predator #survival"
)
tags = ["shorts", "grizzly bear", "salmon run", "wildlife", "nature", "documentary", "animals", "wild mechanics", "predator", "hunt"]

inputs = {
    "video_path": str(video_file),
    "title": title,
    "description": description,
    "tags": tags,
    "privacy_status": "public",
    "category_id": "15",  # Pets & Animals
    "thumbnail_path": str(thumb_file)
}

res = uploader.execute(inputs)

if res.success:
    video_url = res.data.get("video_url")
    video_id = res.data.get("video_id")
    print(f"\n🎉 UPLOAD SUCCESSFUL!")
    print(f"🔗 YouTube Video URL: {video_url}")
    print(f"🆔 Video ID: {video_id}")
    
    # Send Telegram notification
    dispatcher = NotificationDispatcher()
    tg_msg = (
        f"🎬 *New 1:01 Wildlife Short Published\\!*\n\n"
        f"🐻 *Title:* Why Salmon Willingly Jump Into A Bear's Mouth\n"
        f"⏱️ *Duration:* 1:01 \\(61\\.2s\\) — Matching Scarface Jaguar & Poison Frog\\!\n"
        f"🎣 *Hook:* 0:17 Bear Battle Clash with Authentic Audio \\(No TTS\\)\n"
        f"🖼️ *Thumbnail:* High\\-CTR Jaw Lock Freeze Frame\n"
        f"🔗 [Watch on YouTube]({video_url})"
    )
    dispatcher.send_telegram_notification(tg_msg)
else:
    print(f"❌ Upload Failed: {res.error}")
