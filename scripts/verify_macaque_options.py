import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
out1 = ROOT / "projects" / "macaque" / "renders" / "macaque_option1_original_sound.mp4"
out2 = ROOT / "projects" / "macaque" / "renders" / "macaque_option2_custom_voiceover.mp4"

def verify(p):
    print("="*60)
    print(f"FILE: {p.name}")
    print(f"PATH: {p}")
    print(f"EXISTS: {p.exists()}")
    if not p.exists():
        return
    print(f"SIZE: {p.stat().st_size / (1024*1024):.2f} MB")
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration,size,bit_rate",
        "-show_entries", "stream=codec_type,codec_name,width,height,sample_rate,channels",
        "-of", "json", str(p)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, check=True)
    d = json.loads(r.stdout)
    dur = float(d["format"]["duration"])
    print(f"DURATION: {dur:.2f} seconds")
    for s in d["streams"]:
        stype = s["codec_type"]
        cname = s["codec_name"]
        if stype == "video":
            print(f"  VIDEO: {cname.upper()} | {s['width']}x{s['height']}")
        elif stype == "audio":
            print(f"  AUDIO: {cname.upper()} | {s['sample_rate']}Hz | {s['channels']} channels")

verify(out1)
verify(out2)
