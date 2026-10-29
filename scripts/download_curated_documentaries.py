import os
import sys
import subprocess
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent

DOWNLOADS = [
    # Non-BBC: Honey Badger
    {
        "url": "https://www.youtube.com/watch?v=DkvLCjFiODw",
        "output": ROOT_DIR / "assets" / "documentaries" / "honey_badger" / "smithsonian_honey_badger_snake_01.mp4"
    },
    {
        "url": "https://www.youtube.com/watch?v=Wpt1jQMbw3I",
        "output": ROOT_DIR / "assets" / "documentaries" / "honey_badger" / "smithsonian_honey_badger_bee_stings_01.mp4"
    },
    # BBC: Honey Badger (5:30)
    {
        "url": "https://www.youtube.com/watch?v=bskDDjCjNVQ",
        "output": ROOT_DIR / "assets" / "documentaries" / "honey_badger" / "bbc_honey_badger_big_brained_01.mp4"
    },
    # Non-BBC: Mantis Shrimp (3:25)
    {
        "url": "https://www.youtube.com/watch?v=E0Li1k5hGBE",
        "output": ROOT_DIR / "assets" / "documentaries" / "mantis_shrimp" / "natgeo_mantis_shrimp_punch_01.mp4"
    },
    # Non-BBC: Electric Eel (4:35)
    {
        "url": "https://www.youtube.com/watch?v=jaWpDWbY5ik",
        "output": ROOT_DIR / "assets" / "documentaries" / "electric_eel" / "smithsonian_electric_eel_01.mp4"
    },
    # Non-BBC: Glass Frog (1:45)
    {
        "url": "https://www.youtube.com/watch?v=4YzR-3wAgIA",
        "output": ROOT_DIR / "assets" / "documentaries" / "glass_frog" / "smithsonian_glass_frog_01.mp4"
    },
    # Non-BBC: Peregrine Falcon (3:44)
    {
        "url": "https://www.youtube.com/watch?v=ovocT91G1ww",
        "output": ROOT_DIR / "assets" / "documentaries" / "peregrine_falcon" / "smithsonian_peregrine_falcon_01.mp4"
    }
]

for item in DOWNLOADS:
    out_path = item["output"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and out_path.stat().st_size > 1024 * 1024:
        print(f"⏩ Already exists: {out_path.name}")
        continue
    
    print(f"\n⬇️ Downloading: {item['url']} -> {out_path.name}")
    cmd = [
        "yt-dlp",
        item["url"],
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "-o", str(out_path),
        "--merge-output-format", "mp4",
        "--no-playlist"
    ]
    try:
        subprocess.run(cmd, check=True)
        print(f"✅ Downloaded: {out_path.name} ({out_path.stat().st_size / (1024*1024):.1f} MB)")
    except Exception as e:
        print(f"❌ Failed: {e}")
