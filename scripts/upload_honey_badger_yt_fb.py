import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.publishers.youtube_uploader import YouTubeUploader
from tools.publishers.facebook_uploader import FacebookReelsUploader

VIDEO_PATH = ROOT_DIR / "projects" / "honey_badger_snake_battle" / "renders" / "honey_badger_snake_battle_master.mp4"
THUMB_PATH = ROOT_DIR / "projects" / "honey_badger_snake_battle" / "renders" / "honey_badger_snake_battle_thumbnail.jpg"

TITLE = "Why Venomous Snakes Cannot Kill A Honey Badger 🐍 #shorts #wildlife"
DESCRIPTION = """Witness the fearless biological armor and venom-neutralizing receptors of the Honey Badger in an epic battle against a deadly snake!

🔔 Follow Wild Mechanics for daily wildlife micro-stories and predator breakdowns.

#shorts #wildlife #honeybadger #nature #animals #documentary #wildmechanics #predator #snake"""

TAGS = ["shorts", "honey badger", "snake", "wildlife", "nature", "documentary", "animals", "wild mechanics", "predator", "safari"]

print("=================================================================")
print("🚀 WILD MECHANICS MULTI-PLATFORM PUBLISHER")
print("=================================================================")
print(f"🎬 Video: {VIDEO_PATH.name} ({VIDEO_PATH.stat().st_size / (1024*1024):.1f} MB)")

results = {}

# 1. YouTube Shorts Upload
print("\n📺 Step 1: Uploading to YouTube Shorts...")
try:
    yt_uploader = YouTubeUploader()
    yt_res = yt_uploader.execute({
        "video_path": str(VIDEO_PATH),
        "title": TITLE,
        "description": DESCRIPTION,
        "tags": TAGS,
        "privacy_status": "public",
        "category_id": "15",
        "thumbnail_path": str(THUMB_PATH)
    })
    if yt_res.success:
        yt_url = yt_res.data.get("video_url")
        yt_id = yt_res.data.get("video_id")
        results["youtube"] = {"status": "success", "url": yt_url, "id": yt_id}
        print(f"✅ YouTube Shorts Published: {yt_url}")
    else:
        results["youtube"] = {"status": "failed", "error": yt_res.error}
        print(f"❌ YouTube Upload Failed: {yt_res.error}")
except Exception as e:
    results["youtube"] = {"status": "error", "error": str(e)}
    print(f"❌ YouTube Exception: {e}")

# 2. Facebook Page Reels Upload
print("\n📘 Step 2: Uploading to Facebook Page Reels...")
try:
    fb_uploader = FacebookReelsUploader()
    if fb_uploader.is_configured():
        fb_res = fb_uploader.upload_reel(
            video_path=str(VIDEO_PATH),
            title=TITLE,
            description=DESCRIPTION
        )
        if fb_res and fb_res.get("success"):
            fb_id = fb_res.get("video_id")
            results["facebook"] = {"status": "success", "id": fb_id}
            print(f"✅ Facebook Reel Published! Video ID: {fb_id}")
        else:
            results["facebook"] = {"status": "failed", "details": fb_res}
            print(f"⚠️ Facebook Upload Result: {fb_res}")
    else:
        results["facebook"] = {"status": "skipped", "reason": "Credentials missing"}
        print("⚠️ Facebook credentials not configured.")
except Exception as e:
    results["facebook"] = {"status": "error", "error": str(e)}
    print(f"❌ Facebook Exception: {e}")

print("\n=================================================================")
print("📊 FINAL PUBLISHING SUMMARY:")
print(f"📺 YouTube: {results.get('youtube', {})}")
print(f"📘 Facebook: {results.get('facebook', {})}")
print("=================================================================")
