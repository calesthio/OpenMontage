"""
download_more_animals.py
Downloads Honey Badger, Mongoose vs Cobra, and Bengal Tiger using robust yt-dlp remuxing.
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

MORE_TARGETS = [
    {
        "id": "honey_badger",
        "animal": "honey_badger",
        "query": "ytsearch1:honey badger vs puff adder cobra bbc earth wildlife",
        "filename": "honey_badger_doc_source_01.mp4",
    },
    {
        "id": "mongoose",
        "animal": "mongoose",
        "query": "ytsearch1:mongoose vs cobra snake fight wildlife bbc earth",
        "filename": "mongoose_doc_source_01.mp4",
    },
    {
        "id": "tiger",
        "animal": "tiger",
        "query": "ytsearch1:bengal tiger stalks deer hunt bbc dynasties wildlife",
        "filename": "tiger_doc_source_01.mp4",
    }
]

for target in MORE_TARGETS:
    animal_dir = DOC_DIR / target["animal"]
    animal_dir.mkdir(parents=True, exist_ok=True)
    out_file = animal_dir / target["filename"]
    
    print(f"\n📥 Downloading {target['animal']}...")
    cmd = [
        "yt-dlp",
        "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "--merge-output-format", "mp4",
        "--no-playlist",
        "-o", str(out_file),
        target["query"]
    ]
    try:
        subprocess.run(cmd, check=True)
        print(f"🎉 Downloaded: {out_file} ({out_file.stat().st_size / (1024*1024):.1f} MB)")
    except Exception as e:
        print(f"❌ Failed: {e}")

