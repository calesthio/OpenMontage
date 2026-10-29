"""
upload_grizzly_bear_short.py
Uploads the Grizzly Bear 98.0s Master Short to YouTube Shorts.
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
video_file = Path("projects/grizzly_bear/renders/grizzly_bear_ghost_4_5_master.mp4")

print(f"🚀 Uploading {video_file} ({video_file.stat().st_size / (1024*1024):.1f} MB) to YouTube Shorts...")

title = "Why Salmon Willingly Jump Into A Bear's Mouth 😱 #shorts #wildlife"
description = (
    "Along the roaring rapids, hungry grizzly bears hold the ultimate high ground as thousands "
    "of migrating salmon make fatal leaps upstream. Discover the brutal biological mechanics of the river apex predator!\n\n"
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
    "category_id": "15"  # Pets & Animals
}

res = uploader.execute(inputs)

if res.success:
    video_url = res.data.get("video_url")
    video_id = res.data.get("video_id")
    print(f"🎉 UPLOAD SUCCESSFUL!")
    print(f"🔗 YouTube Video URL: {video_url}")
    print(f"🆔 Video ID: {video_id}")
    
    # Send Telegram notification if configured
    dispatcher = NotificationDispatcher()
    tg_msg = (
        f"🎬 *New Wild Mechanics Short Published\\!*\n\n"
        f"🐻 *Title:* Why Salmon Willingly Jump Into A Bear's Mouth\n"
        f"⏱️ *Duration:* 98\\.0s \\(Love Nature 4K \\+ 4:5 Ghost Blur\\)\n"
        f"🔗 [Watch on YouTube]({video_url})"
    )
    dispatcher.send_telegram_notification(tg_msg)
else:
    print(f"❌ Upload Failed: {res.error}")
