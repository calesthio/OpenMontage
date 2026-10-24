"""
run_auto_short.py
CLI launcher for OpenMontage Automated Wildlife Short Production Pipeline.

Demonstrates end-to-end B-roll analysis, narration matching, and 9:16 vertical video compilation.
"""

import sys
import json
from pathlib import Path

# Ensure UTF-8 output
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from lib.wildlife_broll_analyzer import WildlifeBrollAnalyzer
from lib.auto_short_engine import AutoShortEngine

# Multi-animal short narrative script
SAMPLE_WILDLIFE_SCRIPT = {
    "title": "Apex Predators of the Wild 🐅🦁🐺 #wildlife #shorts",
    "hook_banner": "APEX PREDATORS OF THE WILD 🐅",
    "voice": "en-US-ChristopherNeural",
    "scenes": [
        {
            "scene_num": 1,
            "animal": "tiger",
            "text": "Deep in the dense jungles, the tiger stalks silently through the shadows. A master of camouflage, it waits for the perfect moment to strike."
        },
        {
            "scene_num": 2,
            "animal": "lion",
            "text": "Across the open savanna, the lion pride rules through power and strategy. Together, these apex hunters defend their territory with explosive speed."
        },
        {
            "scene_num": 3,
            "animal": "wolf",
            "text": "In frozen northern forests, the wolf pack hunts with endless endurance and relentless teamwork, outsmarting prey in harsh terrain."
        },
        {
            "scene_num": 4,
            "animal": "cheetah",
            "text": "This is the untamed law of the wild. Power, precision, and survival define the greatest predators on Earth."
        }
    ]
}


def main():
    print("=" * 60)
    print("🚀 OpenMontage Wildlife AutoShort Pipeline Launcher")
    print("=" * 60)

    # Step 1: Run B-roll analyzer to index all clips
    print("\n🔍 Step 1: Analyzing Wildlife B-Roll Library...")
    analyzer = WildlifeBrollAnalyzer()
    analyzer.analyze_all()

    # Step 2: Initialize AutoShort engine and render short video
    print("\n🎬 Step 2: Rendering AutoShort with Matched B-Roll & Narration...")
    engine = AutoShortEngine()
    output_mp4 = engine.generate_short(SAMPLE_WILDLIFE_SCRIPT)

    print("\n" + "=" * 60)
    print(f"🎉 AutoShort production complete!")
    print(f"📹 Deliverable MP4: {output_mp4}")
    print("=" * 60)


if __name__ == "__main__":
    main()
