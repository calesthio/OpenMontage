"""
download_pure_wildlife_stories.py
Downloads pristine 1080p wildlife documentary clips with ZERO humans for autonomous short production.
"""

import sys
import subprocess
from pathlib import Path

# Fix Windows cp1252 stdout encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
DOC_DIR = ROOT / "assets" / "documentaries"
DOC_DIR.mkdir(parents=True, exist_ok=True)

TARGETS = [
    {
        "id": "honey_badger_fearless",
        "animal": "honey_badger",
        "query": "ytsearch1:honey badger cobra fight venom bbc wildlife",
        "filename": "honey_badger_doc_source_01.mp4",
        "title": "The Fearless Honey Badger | Nature #shorts #wildlife",
    },
    {
        "id": "orca_wave_wash",
        "animal": "orca",
        "query": "ytsearch1:killer whales hunt seal ice wave wash bbc frozen planet",
        "filename": "orca_doc_source_01.mp4",
        "title": "Orcas Tactical Wave Attack | Frozen Planet #shorts #wildlife",
    },
    {
        "id": "golden_eagle_cliff",
        "animal": "golden_eagle",
        "query": "ytsearch1:golden eagle hunting mountain bbc planet earth wildlife",
        "filename": "golden_eagle_doc_source_01.mp4",
        "title": "The Apex Raptor | Golden Eagle #shorts #wildlife",
    },
    {
        "id": "komodo_dragon_hunt",
        "animal": "komodo_dragon",
        "query": "ytsearch1:komodo dragon hunting deer bbc life wildlife",
        "filename": "komodo_dragon_doc_source_01.mp4",
        "title": "The Living Dinosaur | Komodo Dragon #shorts #wildlife",
    },
    {
        "id": "electric_eel_shock",
        "animal": "electric_eel",
        "query": "ytsearch1:electric eel shock river monster wildlife bbc",
        "filename": "electric_eel_doc_source_01.mp4",
        "title": "Bio-Electric Superpower | Electric Eel #shorts #wildlife",
    },
    {
        "id": "mongoose_vs_cobra",
        "animal": "mongoose",
        "query": "ytsearch1:mongoose vs king cobra fight bbc earth wildlife",
        "filename": "mongoose_doc_source_01.mp4",
        "title": "Lightning Reflexes | Mongoose vs Cobra #shorts #wildlife",
    }
]

def download_target(target):
    animal_dir = DOC_DIR / target["animal"]
    animal_dir.mkdir(parents=True, exist_ok=True)
    out_file = animal_dir / target["filename"]
    
    if out_file.exists() and out_file.stat().st_size > 10_000_000:
        print(f"✅ Already downloaded: {out_file} ({out_file.stat().st_size / (1024*1024):.1f} MB)")
        return out_file

    print(f"\n📥 Downloading {target['animal']} from query: '{target['query']}'...")
    cmd = [
        "yt-dlp",
        "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--no-playlist",
        "-o", str(out_file),
        target["query"]
    ]
    try:
        subprocess.run(cmd, check=True)
        print(f"🎉 Downloaded: {out_file} ({out_file.stat().st_size / (1024*1024):.1f} MB)")
        return out_file
    except Exception as e:
        print(f"❌ Failed to download {target['animal']}: {e}")
        return None

if __name__ == "__main__":
    for t in TARGETS:
        download_target(t)
