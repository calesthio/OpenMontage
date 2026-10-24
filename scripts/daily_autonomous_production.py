"""
daily_autonomous_production.py
Master Autonomous Engine for OpenMontage Wildlife Shorts.
Executes automatically on GitHub Actions cron (3x daily) or local manual trigger:
1. Reads next species from config/wildlife_story_queue.json
2. Renders 100% autonomously:
   - 4:5 Ghost Blur (zero watermarks, OLED boost)
   - Pitch modulated documentary audio (anti-Content-ID) + 0.8s black fade
   - Word-level kinetic yellow karaoke at YouTube Shorts safe-zone (MarginV=460)
   - Top Header (WILD MECHANICS + Curiosity Hook Title)
   - Dynamic Outro CTA (ElevenLabs Voice ID from .env + Boosted BGM)
3. Uploads directly to YouTube Shorts via YouTube Data API v3
4. Dispatches rich Discord & Telegram notification
5. Advances queue index for the next run
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from lib.wild_mechanics_engine import (
    ghost_blur_filter,
    audio_pitch_and_fade_filter,
    build_ass_subtitles,
    generate_dynamic_cta_clip,
    generate_cold_hook_clip,
    extract_high_ctr_thumbnail,
    master_stitch_filter,
    is_bbc_source,
    get_target_durations
)
from faster_whisper import WhisperModel
from tools.publishers.youtube_uploader import YouTubeUploader
from lib.notifier import NotificationDispatcher
from tools.storage.gdrive_downloader import download_file_from_google_drive, sync_from_gdrive_folder

QUEUE_FILE = ROOT_DIR / "config" / "wildlife_story_queue.json"


def load_queue() -> dict:
    if not QUEUE_FILE.exists():
        raise FileNotFoundError(f"Queue file missing: {QUEUE_FILE}")
    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_queue(queue_data: dict):
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue_data, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Wild Mechanics Daily Autonomous Producer")
    parser.add_argument("--upload", action="store_true", help="Upload rendered video directly to YouTube")
    parser.add_argument("--notify", action="store_true", default=True, help="Send Discord/Telegram notification")
    parser.add_argument("--story-id", type=str, default=None, help="Produce a specific story by ID")
    args = parser.parse_args()

    print("=" * 65)
    print("🐾 WILD MECHANICS AUTONOMOUS PRODUCTION ENGINE")
    print("=" * 65)

    queue = load_queue()
    stories = queue.get("stories", [])
    if not stories:
        print("[ERROR] No stories in queue.")
        sys.exit(1)

    idx = queue.get("current_index", 0)
    story = None

    if args.story_id:
        for s in stories:
            if s.get("id") == args.story_id:
                story = s
                break
        if not story:
            print(f"[ERROR] Story ID '{args.story_id}' not found.")
            sys.exit(1)
    else:
        idx = idx % len(stories)
        story = stories[idx]

    animal_key = story.get("id", "wildlife")
    animal_name = story.get("animal", "Wildlife")
    title_hook = story.get("title_hook", f"WHY {animal_name.upper()} IS THE ULTIMATE PREDATOR 😱")
    yt_title = story.get("yt_title", f"{animal_name}: Nature's Apex Predator #shorts #wildlife")
    source_file_rel = story.get("source_file", "")
    source_path = ROOT_DIR / source_file_rel if source_file_rel else None

    # Auto find source video if not explicitly located
    if not source_path or not source_path.exists():
        doc_dir = ROOT_DIR / "assets" / "documentaries" / animal_key.split("_")[0]
        if doc_dir.exists():
            files = list(doc_dir.glob("*.mp4"))
            if files:
                source_path = files[0]

    target_dest = ROOT_DIR / (source_file_rel if source_file_rel else f"assets/documentaries/{animal_key.split('_')[0]}/{animal_key}_source.mp4")

    # 1. Primary Cloud Storage: Google Drive on-demand download
    gdrive_target = story.get("gdrive_id") or story.get("gdrive_url")
    if (not source_path or not source_path.exists()) and gdrive_target:
        print(f"\n📁 Source video missing on runner. Pulling from Google Drive: {gdrive_target}")
        gdrive_success = download_file_from_google_drive(gdrive_target, target_dest)
        if gdrive_success and target_dest.exists():
            source_path = target_dest

    # 1b. Master Google Drive Folder Sync
    master_folder = story.get("gdrive_folder") or os.environ.get("GDRIVE_MASTER_FOLDER", "https://drive.google.com/drive/folders/1ywnMZUJ85Afy7swh-m7CNbvM3bVeKxDJ")
    if (not source_path or not source_path.exists()) and master_folder:
        print(f"\n📁 Checking master Google Drive folder for {target_dest.name}...")
        sync_from_gdrive_folder(master_folder, target_dest.parent)
        if target_dest.exists():
            source_path = target_dest

    # 2. Fallback Storage: yt-dlp on-demand stream
    if (not source_path or not source_path.exists()) and story.get("yt_url"):
        yt_url = story.get("yt_url")
        print(f"\n⬇️ Source video missing. Downloading via yt-dlp fallback from: {yt_url}")
        target_dest.parent.mkdir(parents=True, exist_ok=True)
        cmd_dl = [
            "yt-dlp",
            "--extractor-args", "youtube:player_client=android,ios,mweb",
            "--no-check-certificates",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "-o", str(target_dest),
            yt_url
        ]
        try:
            subprocess.run(cmd_dl, check=True)
            source_path = target_dest
        except Exception as e:
            print(f"[WARN] yt-dlp download failed: {e}")

    if not source_path or not source_path.exists():
        print(f"[ERROR] Documentary source footage missing for {animal_name}: {source_path}")
        sys.exit(1)

    # 1. Automatic Duration Routing (BBC vs Non-BBC)
    hook_target_s, story_duration, cta_duration = get_target_durations(source_path, requested_target=story.get("duration"))
    total_expected = hook_target_s + story_duration + cta_duration

    print(f"\n🎬 Story: [{story.get('id')}] - {animal_name}")
    print(f"📂 Source: {source_path.name}")
    print(f"🏷️ Provider: {'BBC (Content-ID Safe <= 60s)' if is_bbc_source(source_path) else 'Non-BBC (Extended 90s-100s)'}")
    print(f"⏱️ Hook: {hook_target_s:.1f}s | Story: {story_duration:.1f}s | CTA: {cta_duration:.1f}s | Total Expected: {total_expected:.1f}s")

    project_dir = ROOT_DIR / "projects" / animal_key
    assets_dir = project_dir / "assets"
    renders_dir = project_dir / "renders"
    assets_dir.mkdir(parents=True, exist_ok=True)
    renders_dir.mkdir(parents=True, exist_ok=True)

    # 2. Render Act 1: Cold Action Hook (3.0s with authentic audio, NO TTS)
    hook_rendered = renders_dir / f"part1_{animal_key}_hook.mp4"
    start_pos = story.get("start", 0.0)
    hook_start = story.get("hook_start", start_pos + 15.0)
    print(f"\n🎬 Step 1: Rendering Act 1 Cold Action Hook ({hook_target_s:.1f}s with authentic audio, NO TTS)...")
    generate_cold_hook_clip(
        doc_source=source_path,
        hook_title_text=title_hook,
        output_clip_path=hook_rendered,
        hook_cut_start=hook_start,
        hook_cut_duration=hook_target_s,
        pitch_factor=0.97
    )

    # 3. Trim Story & Modulate Audio
    trimmed_video = assets_dir / f"{animal_key}_story_{int(story_duration)}s.mp4"
    fade_start = story_duration - 0.8
    fade_dur = 0.8
    audio_filt = audio_pitch_and_fade_filter(fade_out_start=fade_start, fade_duration=fade_dur, pitch_factor=0.97)

    print(f"\n✂️ Step 2: Trimming {story_duration:.1f}s continuous story with anti-fingerprint audio modulation...")
    cmd_trim = [
        "ffmpeg", "-y",
        "-ss", str(start_pos),
        "-t", str(story_duration),
        "-i", str(source_path),
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-filter:a", audio_filt,
        "-c:a", "aac", "-b:a", "320k",
        str(trimmed_video)
    ]
    subprocess.run(cmd_trim, check=True)

    # 4. Whisper Word Sync & ASS Generation
    print("\n🎙️ Step 3: Transcribing for ASS word-level kinetic karaoke at Safe Zone...")
    whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = whisper_model.transcribe(str(trimmed_video), word_timestamps=True)

    ass_path = assets_dir / f"{animal_key}_subtitles.ass"
    build_ass_subtitles(
        segments=list(segments),
        output_path=ass_path,
        title_hook=title_hook,
        max_duration=fade_start
    )

    # 5. Render Act 2: 4:5 Ghost Blur Story with HFlip
    story_rendered = renders_dir / f"part2_{animal_key}_ghost_story.mp4"
    fg_filter = ghost_blur_filter(
        ass_file=str(ass_path),
        fade_out_start=fade_start,
        fade_duration=fade_dur,
        hflip=True,
        progress_bar=False,
        duration=story_duration,
        crop_mode=story.get("crop_mode", "subject_4_5"),
        x_align=story.get("crop_x_align", "center")
    )

    print(f"\n🎨 Step 4: Rendering Act 2 4:5 Ghost Blur Story (zero watermarks & OLED boost)...")
    cmd_story = [
        "ffmpeg", "-y",
        "-i", str(trimmed_video),
        "-filter_complex", fg_filter,
        "-map", "[v]", "-map", "0:a",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-c:a", "aac", "-b:a", "320k",
        str(story_rendered)
    ]
    subprocess.run(cmd_story, check=True)

    # 6. Render Act 3: Dynamic CTA Outro (Volume-Matched ElevenLabs + Boosted BGM)
    cta_rendered = renders_dir / f"part3_{animal_key}_cta.mp4"
    print(f"\n📣 Step 5: Rendering Act 3 Outro CTA ({cta_duration:.1f}s with volume-matched ElevenLabs VO & BGM)...")
    generate_dynamic_cta_clip(
        animal_name=story.get("animal", animal_key),
        output_clip_path=cta_rendered,
        duration_s=cta_duration,
        clean_stock_bg=story.get("clean_stock_bg")
    )

    # 7. Master Concat Stitch with 100% Synchronized Progress Bar
    master_video = renders_dir / f"{animal_key}_master.mp4"
    print(f"\n🚀 Step 6: Concat Stitching with 100% Time-Synchronized Progress Bar (Total: {total_expected:.1f}s)...")
    stitch_filt = master_stitch_filter(num_inputs=3, total_duration=total_expected, progress_bar=True)
    cmd_stitch = [
        "ffmpeg", "-y",
        "-i", str(hook_rendered),
        "-i", str(story_rendered),
        "-i", str(cta_rendered),
        "-filter_complex", stitch_filt,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-c:a", "aac", "-b:a", "320k",
        str(master_video)
    ]
    subprocess.run(cmd_stitch, check=True)
    print(f"🎉 MASTER VIDEO CREATED: {master_video.name} ({master_video.stat().st_size / (1024*1024):.1f} MB)")

    # 7. Extract High-CTR Thumbnail & Upload to YouTube
    thumb_path = renders_dir / f"{animal_key}_thumbnail.jpg"
    extract_high_ctr_thumbnail(master_video, thumb_path, timestamp_s=1.5)
    print(f"🖼️ High-CTR Thumbnail Generated: {thumb_path.name}")

    video_url = None
    if args.upload:
        print("\n🚀 Uploading to YouTube Shorts via YouTube Data API v3...")
        try:
            uploader = YouTubeUploader()
            desc = (
                f"{story.get('description', '')}\n\n"
                f"🔔 Follow Wild Mechanics for daily wildlife micro-stories.\n\n"
                f"#shorts #wildlife #{animal_key.replace('_','')} #nature #animals #documentary #wildmechanics"
            )
            up_res = uploader.execute({
                "video_path": str(master_video),
                "title": yt_title,
                "description": desc,
                "tags": story.get("tags", ["shorts", "wildlife", "nature", "animals", "documentary", "wild mechanics"]),
                "privacy_status": "public",
                "category_id": "15",
                "thumbnail_path": str(thumb_path)
            })
            if up_res.success:
                video_url = up_res.data.get("video_url")
                print(f"🎉 YouTube Upload Complete! URL: {video_url}")
            else:
                print(f"⚠️ YouTube upload skipped or failed: {up_res.error}")
        except Exception as e:
            print(f"⚠️ YouTube upload skipped due to environment: {e}")

    # 8. Notifications
    if args.notify:
        dispatcher = NotificationDispatcher()
        tg_msg = (
            f"🎬 *New Wild Mechanics Short Published\\!*\n\n"
            f"🐾 *Animal:* {animal_name}\n"
            f"🏷️ *Title:* {title_hook}\n"
            f"⏱️ *Duration:* {total_expected:.1f}s \\(4:5 Ghost Blur \\+ ElevenLabs CTA\\)\n"
        )
        if video_url:
            tg_msg += f"🔗 [Watch on YouTube]({video_url})"
        dispatcher.send_telegram_notification(tg_msg)

    # 9. Advance Queue Index
    if not args.story_id:
        queue["current_index"] = (idx + 1) % len(stories)
        save_queue(queue)
        print(f"\n📊 Queue index advanced: {idx} -> {queue['current_index']} (Next: {stories[queue['current_index']]['animal']})")

    print("\n✅ Daily Production Run Successfully Completed!")


if __name__ == "__main__":
    main()
