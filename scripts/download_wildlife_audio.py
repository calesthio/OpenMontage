"""
download_wildlife_audio.py
Audio Asset Harvester & Synthesizer for OpenMontage.

Creates assets/audio/sfx/ and assets/audio/bgm/ with royalty-free cinematic sound effects
and background music beds for wildlife shorts.
"""

import os
import sys
import subprocess
from pathlib import Path

# Ensure UTF-8 output
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

ROOT_DIR = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT_DIR / "assets" / "audio"
SFX_DIR = AUDIO_DIR / "sfx"
BGM_DIR = AUDIO_DIR / "bgm"


def create_synth_sfx(output_path: Path, freq_start: int, freq_end: int, duration: float, type_name: str):
    """Synthesizes high-impact cinematic sound effects using FFmpeg lavfi filters."""
    if output_path.exists() and output_path.stat().st_size > 1000:
        print(f"⏩ [SFX Exists] {output_path.name}")
        return

    print(f"🔊 Synthesizing SFX: {output_path.name} ({type_name})...")
    if type_name == "whoosh":
        filter_str = f"anoisesrc=d={duration}:c=white:r=44100, lowpass=f=800, volume=3.0, afade=t=in:ss=0:d=0.2, afade=t=out:st=0.3:d=0.3"
    elif type_name == "roar":
        filter_str = f"anoisesrc=d={duration}:c=pink:r=44100, lowpass=f=400, vibrato=f=6:d=0.5, volume=4.0, afade=t=in:ss=0:d=0.3, afade=t=out:st=1.2:d=0.8"
    elif type_name == "impact":
        filter_str = f"sine=frequency={freq_start}:duration={duration}, lowpass=f=200, volume=5.0, afade=t=out:st=0.1:d=0.4"
    else:  # howl / ambient
        filter_str = f"sine=frequency={freq_start}:duration={duration}, vibrato=f=3:d=0.3, volume=2.5, afade=t=in:ss=0:d=0.5, afade=t=out:st=1.5:d=0.5"

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", filter_str,
        "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
        str(output_path)
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)


def create_synth_bgm(output_path: Path, duration: float = 60.0):
    """Synthesizes a suspenseful background music drone bed."""
    if output_path.exists() and output_path.stat().st_size > 5000:
        print(f"⏩ [BGM Exists] {output_path.name}")
        return

    print(f"🎵 Synthesizing BGM Bed: {output_path.name}...")
    filter_str = (
        f"sine=frequency=65:duration={duration},"
        f"volume=0.3,tremolo=f=0.5:d=0.4,"
        f"afade=t=in:ss=0:d=3.0,afade=t=out:st={duration-3.0}:d=3.0"
    )
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", filter_str,
        "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
        str(output_path)
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)


def main():
    print("=" * 60)
    print("🔊 OpenMontage Sound & SFX Asset Harvester")
    print("=" * 60)

    SFX_DIR.mkdir(parents=True, exist_ok=True)
    BGM_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Synthesize SFX library
    sfx_specs = [
        (SFX_DIR / "whoosh_01.wav", 100, 800, 0.6, "whoosh"),
        (SFX_DIR / "roar_tiger_01.wav", 80, 300, 2.0, "roar"),
        (SFX_DIR / "roar_lion_01.wav", 70, 280, 2.0, "roar"),
        (SFX_DIR / "sub_impact_01.wav", 60, 40, 0.6, "impact"),
        (SFX_DIR / "wolf_howl_01.wav", 300, 600, 2.0, "howl"),
    ]

    for path, f1, f2, dur, stype in sfx_specs:
        create_synth_sfx(path, f1, f2, dur, stype)

    # 2. Synthesize BGM bed
    create_synth_bgm(BGM_DIR / "nature_suspense_bgm.wav", duration=60.0)

    print("\n✅ Audio asset library populated successfully!")
    print(f"SFX Directory: {SFX_DIR}")
    print(f"BGM Directory: {BGM_DIR}")


if __name__ == "__main__":
    main()
