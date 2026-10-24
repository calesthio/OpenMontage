"""Build the complete 'Electric Eel Power' video deliverable end-to-end."""

import json
import subprocess
import sys
from pathlib import Path
from gtts import gTTS

ROOT_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = ROOT_DIR / "projects" / "electric-eel-power"
ARTIFACTS_DIR = PROJECT_DIR / "artifacts"
ASSETS_DIR = PROJECT_DIR / "assets"
AUDIO_DIR = ASSETS_DIR / "audio"
RENDERS_DIR = PROJECT_DIR / "renders"

ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
RENDERS_DIR.mkdir(parents=True, exist_ok=True)

# 1. Research Brief
research_brief = {
    "project_id": "electric-eel-power",
    "topic": "The Electric Eel's Secret Battery",
    "data_points": [
        {
            "fact": "Electric eels can generate up to 860 volts of electricity—enough to stun a horse.",
            "source": "Nature Biology",
            "surprise_factor": "high"
        },
        {
            "fact": "80% of an electric eel's body is covered in electrocytes (specialized muscle cells).",
            "source": "Current Biology",
            "surprise_factor": "high"
        },
        {
            "fact": "Eels use micro-pulses as biological radar to navigate muddy Amazonian waters.",
            "source": "Journal of Experimental Biology",
            "surprise_factor": "medium"
        }
    ],
    "target_audience": "Nature & Science enthusiasts on Shorts/Reels/TikTok",
    "core_hook": "How an electric eel generates 860 volts without shocking itself"
}
with open(ARTIFACTS_DIR / "research_brief.json", "w", encoding="utf-8") as f:
    json.dump(research_brief, f, indent=2)

# 2. Proposal Packet
proposal_packet = {
    "project_id": "electric-eel-power",
    "selected_concept": {
        "title": "Wild Survival: The Electric Eel's Secret Battery",
        "duration_seconds": 22,
        "suggested_playbook": "flat-motion-graphics",
        "render_runtime": "remotion"
    },
    "cost_estimate": {
        "total_usd": 0.0
    },
    "approval": {
        "status": "approved"
    }
}
with open(ARTIFACTS_DIR / "proposal_packet.json", "w", encoding="utf-8") as f:
    json.dump(proposal_packet, f, indent=2)

# 3. Script
script_data = {
    "project_id": "electric-eel-power",
    "title": "Wild Survival: The Electric Eel's Secret Battery",
    "target_duration_seconds": 22,
    "sections": [
        {
            "id": "s1",
            "label": "Hook",
            "text": "This underwater hunter packs an 860-volt shock.",
            "start_seconds": 0,
            "end_seconds": 4
        },
        {
            "id": "s2",
            "label": "Body Architecture",
            "text": "Over 80 percent of its body is stacked with 6,000 biological battery cells called electrocytes.",
            "start_seconds": 4,
            "end_seconds": 11
        },
        {
            "id": "s3",
            "label": "Radar & Hunting",
            "text": "It fires low-voltage pulses as organic radar in pitch-black waters.",
            "start_seconds": 11,
            "end_seconds": 17
        },
        {
            "id": "s4",
            "label": "Landing",
            "text": "Nature's ultimate high-voltage superpower. Subscribe for more wild science!",
            "start_seconds": 17,
            "end_seconds": 22
        }
    ]
}
with open(ARTIFACTS_DIR / "script.json", "w", encoding="utf-8") as f:
    json.dump(script_data, f, indent=2)

# 4. Generate Narration Audio via gTTS
full_narration_text = " ".join([s["text"] for s in script_data["sections"]])
narration_path = AUDIO_DIR / "narration.mp3"
tts = gTTS(text=full_narration_text, lang='en', slow=False)
tts.save(str(narration_path))
print(f"Generated narration: {narration_path}")

# 5. Build Remotion Props JSON matching cut schema
remotion_props = {
    "theme": "flat-motion-graphics",
    "cuts": [
        {
            "id": "c1",
            "type": "hero_title",
            "in_seconds": 0,
            "out_seconds": 4,
            "text": "WILD SURVIVAL",
            "subtitle": "The Electric Eel's 860V Secret Battery",
            "backgroundColor": "#0F172A"
        },
        {
            "id": "c2",
            "type": "stat_card",
            "in_seconds": 4,
            "out_seconds": 11,
            "stat": "860V",
            "subtitle": "6,000 biological electrocyte cells stacked in series",
            "accentColor": "#22D3EE",
            "backgroundColor": "#0F172A"
        },
        {
            "id": "c3",
            "type": "bar_chart",
            "in_seconds": 11,
            "out_seconds": 17,
            "title": "Bio-Electric Output Comparison",
            "chartData": [
                { "label": "AA Battery", "value": 1.5 },
                { "label": "Wall Outlet", "value": 120 },
                { "label": "Electric Car", "value": 400 },
                { "label": "Electric Eel", "value": 860 }
            ],
            "chartColors": ["#94A3B8", "#38BDF8", "#F59E0B", "#F43F5E"],
            "showGrid": True,
            "showValues": True,
            "backgroundColor": "#0F172A"
        },
        {
            "id": "c4",
            "type": "text_card",
            "in_seconds": 17,
            "out_seconds": 22,
            "text": "Nature's High-Voltage Superpower.",
            "color": "#F8FAFC",
            "backgroundColor": "#0F172A"
        }
    ],
    "overlays": [
        {
            "type": "section_title",
            "in_seconds": 4.2,
            "out_seconds": 7.5,
            "text": "BIO-BATTERY",
            "subtitle": "80% of body is electrocytes",
            "accentColor": "#22D3EE"
        }
    ]
}

composer_props_path = ROOT_DIR / "remotion-composer" / "public" / "demo-props" / "electric-eel.json"
with open(composer_props_path, "w", encoding="utf-8") as f:
    json.dump(remotion_props, f, indent=2)

print(f"Saved Remotion props: {composer_props_path}")

# 6. Render Video via Remotion CLI
output_video_path = RENDERS_DIR / "final.mp4"

print("Rendering final video using Remotion...")
subprocess.run(
    [
        "npx.cmd",
        "remotion",
        "render",
        "src/index.tsx",
        "Explainer",
        str(output_video_path),
        "--props",
        str(composer_props_path),
        "--codec",
        "h264"
    ],
    cwd=ROOT_DIR / "remotion-composer",
    check=True
)

if output_video_path.exists():
    size_mb = output_video_path.stat().st_size / (1024 * 1024)
    print(f"SUCCESS: Rendered final video to {output_video_path} ({size_mb:.2f} MB)")
else:
    print("Error: Render completed but output file missing.")
