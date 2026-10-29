"""
generate_wild_mechanics_short.py
Universal CLI to generate any animal Short following the Wild Mechanics Master Pipeline:
- 4:5 Ghost Blur Framing (zero black bars, 100% watermark elimination)
- Authentic Master Documentary Footage & Narrator Voice
- Audio Pitch Modulation (anti-Content-ID) & 0.8s smooth black fade-out
- Word-Level Kinetic Karaoke in Electric Yellow (#FFFF00) at Safe Zone (MarginV=460)
- Top Branding Header (WILD MECHANICS at Y=105, Curiosity Hook Title at Y=165)
- Dynamic Mid-Screen Action Badges
- Dynamic Outro CTA: ElevenLabs Voice ID from .env + Boosted Background Music Bed (volume=0.35)

Usage:
  python scripts/generate_wild_mechanics_short.py --animal grizzly_bear --target 95
  python scripts/generate_wild_mechanics_short.py --animal cheetah --mode bbc
  python scripts/generate_wild_mechanics_short.py --animal wolf --target 80
"""

import os
import sys
import argparse
import subprocess
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

from faster_whisper import WhisperModel
from lib.wild_mechanics_engine import (
    ghost_blur_filter,
    audio_pitch_and_fade_filter,
    build_ass_subtitles,
    generate_dynamic_cta_clip,
    is_bbc_source,
    get_target_durations
)
from tools.publishers.youtube_uploader import YouTubeUploader
from lib.notifier import NotificationDispatcher

# Animal Themes, Curiosity Hooks & Dynamic Action Badges
ANIMAL_CONFIGS = {
    "grizzly_bear": {
        "name": "Grizzly Bear",
        "title_hook": "WHY SALMON JUMP INTO A BEAR'S MOUTH 😱",
        "yt_title": "Why Salmon Willingly Jump Into A Bear's Mouth 😱 #shorts #wildlife",
        "source_dir": "grizzly_bear",
        "default_start": 19.0,
        "default_duration": 95.0,
        "badges": [
            {"start": 5.0, "end": 11.0, "text": "🐟 THE SALMON GAUNTLET 🐟"},
            {"start": 34.0, "end": 40.0, "text": "🎯 THE HIGH GROUND 🎯"},
            {"start": 47.0, "end": 55.0, "text": "💥 AIRBORNE STRIKE 💥"},
            {"start": 70.0, "end": 77.0, "text": "👑 RIVER APEX PREDATOR 👑"},
        ]
    },
    "jaguar": {
        "name": "Jaguar",
        "title_hook": "THE DEADLIEST AMBUSH IN THE AMAZON 🐆",
        "yt_title": "The Deadliest 1-Second Ambush in the Amazon 🐆 #shorts #wildlife",
        "source_dir": "jaguar",
        "default_start": 0.0,
        "default_duration": 58.0,
        "badges": [
            {"start": 3.0, "end": 8.0, "text": "👀 THE SILENT STALK 👀"},
            {"start": 20.0, "end": 26.0, "text": "🎯 TARGET LOCKED 🎯"},
            {"start": 42.0, "end": 50.0, "text": "💥 SKULL-CRUSHING BITE 💥"},
        ]
    },
    "great_grey_owl": {
        "name": "Great Grey Owl",
        "title_hook": "HOW THIS BIRD HEARS THROUGH 2 FEET OF SNOW 🦉",
        "yt_title": "How This Bird Hears Heartbeats Under 2 Feet of Snow 🦉 #shorts #wildlife",
        "source_dir": "great_grey_owl",
        "default_start": 0.0,
        "default_duration": 70.0,
        "badges": [
            {"start": 4.0, "end": 10.0, "text": "📡 ACOUSTIC RADAR DISH 📡"},
            {"start": 28.0, "end": 35.0, "text": "🎯 TARGET UNDER SNOW 🎯"},
            {"start": 50.0, "end": 58.0, "text": "💥 THE SNOW PLUNGE 💥"},
        ]
    },
    "cheetah": {
        "name": "Cheetah",
        "title_hook": "WHY CHEETAHS SPRINT AT 120 KM/H BUT CAN STILL LOSE 🤯",
        "yt_title": "Why Cheetahs Sprint At 120 KM/H But Can Still Lose 🤯 #shorts #wildlife",
        "source_dir": "cheetah",
        "default_start": 0.0,
        "default_duration": 58.0,
        "badges": [
            {"start": 4.0, "end": 10.0, "text": "⚡ ZERO TO 60 IN 3 SECONDS ⚡"},
            {"start": 25.0, "end": 32.0, "text": "🎯 HEAT EXHAUSTION LIMIT 🎯"},
            {"start": 44.0, "end": 52.0, "text": "💥 CLAW TRIP STRIKE 💥"},
        ]
    },
    "wolf": {
        "name": "Wolf",
        "title_hook": "THE DEADLIEST COORDINATED PACK HUNT ON EARTH 🐺",
        "yt_title": "The Deadliest Coordinated Pack Hunt on Earth 🐺 #shorts #wildlife",
        "source_dir": "wolf",
        "default_start": 0.0,
        "default_duration": 75.0,
        "badges": [
            {"start": 4.0, "end": 10.0, "text": "🐾 THE FLANKING MANEUVER 🐾"},
            {"start": 30.0, "end": 37.0, "text": "🎯 RUNNING PREY TO EXHAUSTION 🎯"},
            {"start": 55.0, "end": 64.0, "text": "💥 PACK LOCKDOWN 💥"},
        ]
    },
    "great_white_shark": {
        "name": "Great White Shark",
        "title_hook": "WHY SHARKS SENSE A SINGLE DROP OF BLOOD 2 MILES AWAY 🦈",
        "yt_title": "Why Sharks Sense A Single Drop of Blood 2 Miles Away 🦈 #shorts #wildlife",
        "source_dir": "great_white_shark",
        "default_start": 0.0,
        "default_duration": 75.0,
        "badges": [
            {"start": 4.0, "end": 10.0, "text": "⚡ AMPULLAE OF LORENZINI ⚡"},
            {"start": 30.0, "end": 37.0, "text": "🎯 BLIND SPOT LAUNCH 🎯"},
            {"start": 52.0, "end": 60.0, "text": "💥 VERTICAL BREACH STRIKE 💥"},
        ]
    },
    "peregrine_falcon": {
        "name": "Peregrine Falcon",
        "title_hook": "THE ONLY LIVING ANIMAL FASTER THAN A BULLET 🦅",
        "yt_title": "The Only Living Animal Faster Than A Bullet 🦅 #shorts #wildlife",
        "source_dir": "peregrine_falcon",
        "default_start": 0.0,
        "default_duration": 75.0,
        "badges": [
            {"start": 4.0, "end": 10.0, "text": "🚀 390 KM/H GRAVITY DIVE 🚀"},
            {"start": 30.0, "end": 37.0, "text": "🎯 TEARDROP AERODYNAMICS 🎯"},
            {"start": 52.0, "end": 60.0, "text": "💥 MID-AIR IMPACT 💥"},
        ]
    }
}


def render_animal_short(animal_key: str, target_duration: float = 95.0, upload_yt: bool = False):
    config = ANIMAL_CONFIGS.get(animal_key)
    if not config:
        raise ValueError(f"Unknown animal key: {animal_key}. Available: {list(ANIMAL_CONFIGS.keys())}")
        
    project_dir = ROOT / "projects" / animal_key
    assets_dir = project_dir / "assets"
    renders_dir = project_dir / "renders"
    assets_dir.mkdir(parents=True, exist_ok=True)
    renders_dir.mkdir(parents=True, exist_ok=True)
    
    # Locate documentary source
    source_dir = ROOT / "assets" / "documentaries" / config["source_dir"]
    doc_files = list(source_dir.glob("*.mp4"))
    if not doc_files:
        raise FileNotFoundError(f"No documentary file found in {source_dir}")
    source_video = doc_files[0]
    
    story_duration, cta_duration = get_target_durations(source_video, requested_target=target_duration)
    total_expected = story_duration + cta_duration
    
    print(f"🎬 Processing {config['name']} Short...")
    print(f"📂 Source: {source_video.name}")
    print(f"🏷️ Source Provider: {'BBC (Content-ID Safe <= 60s)' if is_bbc_source(source_video) else 'Non-BBC (Extended 90s-100s)'}")
    print(f"⏱️ Story Duration: {story_duration:.1f}s | CTA: {cta_duration:.1f}s | Total: {total_expected:.1f}s")
    
    # 1. Trim & Pitch Shift Story
    trimmed_video = assets_dir / f"{animal_key}_story_{int(story_duration)}s.mp4"
    fade_start = story_duration - 0.8
    audio_filt = audio_pitch_and_fade_filter(fade_out_start=fade_start, fade_duration=0.8, pitch_factor=0.97)
    
    start_time = config["default_start"]
    cmd_trim = [
        "ffmpeg", "-y",
        "-ss", str(start_time),
        "-t", str(story_duration),
        "-i", str(source_video),
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-filter:a", audio_filt,
        "-c:a", "aac", "-b:a", "320k",
        str(trimmed_video)
    ]
    subprocess.run(cmd_trim, check=True)
    
    # 2. Faster-Whisper Word Sync
    print("🎙️ Transcribing for ASS word-level kinetic karaoke...")
    whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = whisper_model.transcribe(str(trimmed_video), word_timestamps=True)
    
    ass_path = assets_dir / f"{animal_key}_karaoke.ass"
    build_ass_subtitles(
        segments=list(segments),
        output_path=ass_path,
        title_hook=config["title_hook"],
        action_badges=config["badges"],
        max_duration=fade_start
    )
    
    # 3. Render 4:5 Ghost Blur Story
    story_rendered = renders_dir / f"part1_{animal_key}_ghost_story.mp4"
    fg_filter = ghost_blur_filter(ass_file=str(ass_path), fade_out_start=fade_start, fade_duration=0.8)
    cmd_story = [
        "ffmpeg", "-y",
        "-i", str(trimmed_video),
        "-filter_complex", fg_filter,
        "-map", "[v]", "-map", "0:a",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-c:a", "aac", "-b:a", "320k",
        str(story_rendered)
    ]
    subprocess.run(cmd_story, check=True, cwd=str(assets_dir))
    
    # 4. Generate Dynamic Outro CTA (ElevenLabs + Boosted BGM)
    cta_clip = renders_dir / f"part2_{animal_key}_cta.mp4"
    cta_bg = assets_dir / "clean_cta_bg.mp4"
    if not cta_bg.exists():
        # Fallback to bear CTA bg or download matching stock clip
        fallback_bg = ROOT / "projects" / "grizzly_bear" / "assets" / "clean_bear_cta_bg.mp4"
        if fallback_bg.exists():
            cta_bg = fallback_bg
            
    generate_dynamic_cta_clip(
        animal_name=animal_key,
        stock_bg_video=cta_bg,
        output_clip_path=cta_clip,
        whisper_model=whisper_model,
        bgm_volume=0.35  # Boosted volume as requested
    )
    
    # 5. Master Stitch
    master_video = renders_dir / f"{animal_key}_wild_mechanics_master.mp4"
    cmd_stitch = [
        "ffmpeg", "-y",
        "-i", str(story_rendered),
        "-i", str(cta_clip),
        "-filter_complex", "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-c:a", "aac", "-b:a", "320k",
        str(master_video)
    ]
    subprocess.run(cmd_stitch, check=True)
    print(f"🎉 MASTER SHORT CREATED: {master_video} ({master_video.stat().st_size / (1024*1024):.1f} MB)")
    
    # 6. Optional YouTube Upload
    if upload_yt:
        uploader = YouTubeUploader()
        desc = (
            f"{config['title_hook']}\n\n"
            f"Discover the brutal biological mechanics of the {config['name']}!\n\n"
            f"🔔 Follow Wild Mechanics for daily wildlife micro-stories.\n\n"
            f"#shorts #wildlife #{animal_key.replace('_','')} #nature #animals #documentary #wildmechanics"
        )
        res = uploader.execute({
            "video_path": str(master_video),
            "title": config["yt_title"],
            "description": desc,
            "tags": ["shorts", config["name"], "wildlife", "nature", "animals", "documentary", "wild mechanics"],
            "privacy_status": "public",
            "category_id": "15"
        })
        if res.success:
            print(f"🚀 Published to YouTube: {res.data.get('video_url')}")
            
    return master_video


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wild Mechanics Master Video Generator")
    parser.add_argument("--animal", type=str, default="grizzly_bear", choices=list(ANIMAL_CONFIGS.keys()))
    parser.add_argument("--target", type=float, default=95.0, help="Story duration in seconds (60 for BBC, 70-95 for non-BBC)")
    parser.add_argument("--upload", action="store_true", help="Upload directly to YouTube upon completion")
    args = parser.parse_args()
    
    render_animal_short(args.animal, target_duration=args.target, upload_yt=args.upload)
