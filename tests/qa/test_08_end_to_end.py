#!/usr/bin/env python3
"""QA Test 08: End-to-end animated-explainer pipeline simulation.

Walks through all 7 stages (idea -> publish) with synthetic artifacts,
validating checkpoints, artifact schemas, and cost tracking at each step.
The compose stage runs real tools (audio_mixer + video_compose) to produce
an actual output video. All other stages use synthetic data.

No API keys needed -- uses ffmpeg-generated fixtures throughout.
"""

import sys, os, json, subprocess, shutil
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
sys.path.insert(0, PROJECT_ROOT)

from lib.env_loader import load_env
load_env()

from lib.checkpoint import (
    write_checkpoint,
    read_checkpoint,
    get_completed_stages,
    get_next_stage,
    STAGES,
    CANONICAL_STAGE_ARTIFACTS,
)
from tools.cost_tracker import CostTracker, BudgetMode
from schemas.artifacts import validate_artifact, list_schemas
from styles.playbook_loader import load_playbook, validate_accessibility

OUT = os.path.join(os.path.dirname(__file__), "output")
PIPELINE_DIR = Path(OUT) / "e2e_pipeline"
PROJECT_ID = "qa_e2e_test"
ASSETS_DIR = Path(OUT) / "e2e_assets"

# Clean previous run
if PIPELINE_DIR.exists():
    shutil.rmtree(PIPELINE_DIR)
if ASSETS_DIR.exists():
    shutil.rmtree(ASSETS_DIR)
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

PASS = 0
FAIL = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}" + (f" -- {detail}" if detail else ""))
    else:
        FAIL += 1
        print(f"  [FAIL] {name}" + (f" -- {detail}" if detail else ""))

def ensure_audio(path, duration=5):
    if os.path.exists(path):
        return
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"sine=frequency=440:duration={duration}",
         "-ar", "44100", "-ac", "1", path],
        capture_output=True, check=True,
    )

def ensure_video(path, duration=5, width=1280, height=720, color="blue"):
    if os.path.exists(path):
        return
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", f"color=c={color}:s={width}x{height}:d={duration}:r=30",
         "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
         "-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p",
         "-g", "30", "-keyint_min", "30",
         "-c:a", "aac", "-shortest", path],
        capture_output=True, check=True,
    )

# ===================================================================
# Setup: Cost tracker + playbook
# ===================================================================
print("--- Setup ---")
cost_log = PIPELINE_DIR / PROJECT_ID / "cost_log.json"
tracker = CostTracker(
    budget_total_usd=5.0,
    mode=BudgetMode.OBSERVE,
    cost_log_path=cost_log,
)
print(f"  Budget: ${tracker.budget_total_usd}")
print(f"  Available schemas: {list_schemas()}")

playbook = load_playbook("clean-professional")
a11y = validate_accessibility(playbook)
print(f"  Playbook a11y: pass={a11y['pass']}, errors={a11y['error_count']}, warnings={a11y['warning_count']}")

# ===================================================================
# Stage 0: research -> research_brief (minimal, to satisfy pipeline order)
# ===================================================================
print("\n--- Stage 0: research ---")
research_brief = {
    "version": "1.0",
    "topic": "AI Video Production",
    "research_date": "2026-04-02",
    "landscape": {
        "existing_content": [
            {"title": "AI Video Tools Explained", "source": "youtube", "angle": "tutorial", "what_it_covers": "Tool comparison", "what_it_misses": "End-to-end pipeline"},
            {"title": "Making Videos with AI", "source": "blog", "angle": "overview", "what_it_covers": "Market landscape", "what_it_misses": "Hands-on workflow"},
            {"title": "AI Content Creation Guide", "source": "youtube", "angle": "how-to", "what_it_covers": "Individual tools", "what_it_misses": "Orchestration concept"},
        ],
        "saturated_angles": ["basic tool demos", "AI will replace editors"],
        "underserved_gaps": ["End-to-end orchestration pipeline", "Cost vs quality tradeoffs"],
    },
    "data_points": [
        {"claim": "AI video market growing 25% YoY", "source_url": "https://example.com/report", "credibility": "primary_source"},
        {"claim": "70% of creators want automated editing", "source_url": "https://example.com/survey", "credibility": "primary_source"},
        {"claim": "Average production time drops 80% with AI", "source_url": "https://example.com/study", "credibility": "secondary_source"},
    ],
    "audience_insights": {
        "common_questions": [
            "Can AI really make professional-looking videos?",
            "How much does AI video production cost?",
            "What tools do I need to get started?",
        ],
        "misconceptions": [
            {"myth": "AI videos always look robotic", "reality": "Modern AI produces broadcast-quality output"},
        ],
        "knowledge_level": "Familiar with basic editing but not AI-specific tools",
    },
    "angles_discovered": [
        {"name": "60-Second Studio", "hook": "Your entire production team in a single prompt", "type": "trending", "why_now": "AI orchestration tools just reached production quality"},
        {"name": "Quality Democratization", "hook": "Pro-grade video without pro skills", "type": "evergreen", "why_now": "Creator economy growing, skill gap remains"},
        {"name": "The Hidden Cost Myth", "hook": "AI video costs pennies, not thousands", "type": "contrarian", "why_now": "Most creators still think AI video is expensive"},
    ],
    "sources": [
        {"url": "https://example.com/ai-video", "title": "AI Video Production Overview", "used_for": "landscape"},
        {"url": "https://example.com/ai-tools", "title": "Top AI Video Tools 2026", "used_for": "data_points"},
        {"url": "https://example.com/workflow", "title": "Automated Video Workflows", "used_for": "angles"},
        {"url": "https://example.com/creators", "title": "Creator Economy Report", "used_for": "audience_insights"},
        {"url": "https://example.com/market", "title": "AI Video Market Analysis", "used_for": "landscape"},
    ],
}
try:
    validate_artifact("research_brief", research_brief)
    check("Research brief validates against schema", True)
except Exception as e:
    check("Research brief validates against schema", False, str(e))

cp_path = write_checkpoint(
    PIPELINE_DIR, PROJECT_ID, "research", "completed",
    artifacts={"research_brief": research_brief},
    pipeline_type="animated-explainer",
    style_playbook="clean-professional",
)
check("Research checkpoint written", cp_path.exists())

# ===================================================================
# Stage 1: proposal -> proposal_packet
# ===================================================================
print("\n--- Stage 1: proposal ---")
proposal_packet = {
    "version": "1.0",
    "concept_options": [
        {
            "id": "c1",
            "title": "AI Video Production in 60 Seconds",
            "hook": "What if you could create a professional video in 60 seconds?",
            "narrative_structure": "problem_solution",
            "visual_approach": "Clean motion graphics with side-by-side comparisons",
            "suggested_playbook": "clean-professional",
            "target_audience": "content creators and developers",
            "target_platform": "youtube",
            "target_duration_seconds": 60,
            "why_this_works": "Direct problem/solution framing with clear visual proof points",
        },
        {
            "id": "c2",
            "title": "The 60-Second Studio",
            "hook": "Your entire production team, in a single prompt.",
            "narrative_structure": "journey",
            "visual_approach": "Animated workflow diagram that builds step by step",
            "suggested_playbook": "flat-motion-graphics",
            "target_audience": "content creators and developers",
            "target_platform": "youtube",
            "target_duration_seconds": 60,
            "why_this_works": "Journey structure creates natural pacing for a process walkthrough",
        },
        {
            "id": "c3",
            "title": "From Prompt to Premiere",
            "hook": "Traditional video production takes weeks. This takes seconds.",
            "narrative_structure": "comparison",
            "visual_approach": "Split-screen timeline comparison: old way vs AI way",
            "suggested_playbook": "clean-professional",
            "target_audience": "content creators and developers",
            "target_platform": "youtube",
            "target_duration_seconds": 60,
            "why_this_works": "Comparison structure makes the value proposition immediately tangible",
        },
    ],
    "selected_concept": {"concept_id": "c1", "rationale": "Direct problem/solution framing is most effective for this audience"},
    "production_plan": {
        "pipeline": "animated-explainer",
        "playbook": "clean-professional",
        "render_runtime": "remotion",
        "stages": [
            {"stage": "script", "tools": [{"tool_name": "tts_selector", "role": "narration", "available": True}], "approach": "AI-written script with TTS narration"},
            {"stage": "scene_plan", "tools": [], "approach": "5 scenes with motion graphics"},
            {"stage": "assets", "tools": [{"tool_name": "image_selector", "role": "visuals", "available": True}], "approach": "AI-generated images"},
            {"stage": "edit", "tools": [], "approach": "Automated edit decisions"},
            {"stage": "compose", "tools": [{"tool_name": "video_compose", "role": "render", "available": True}], "approach": "Remotion render"},
        ],
    },
    "cost_estimate": {
        "total_estimated_usd": 0.50,
        "line_items": [
            {"tool": "tts_selector", "operation": "narration", "estimated_usd": 0.10},
            {"tool": "image_selector", "operation": "5 images", "estimated_usd": 0.30},
            {"tool": "music_gen", "operation": "background track", "estimated_usd": 0.10},
        ],
        "budget_verdict": "within_budget",
    },
    "approval": {
        "status": "approved",
        "approved_budget_usd": 2.00,
    },
}

try:
    validate_artifact("proposal_packet", proposal_packet)
    check("Proposal packet validates against schema", True)
except Exception as e:
    check("Proposal packet validates against schema", False, str(e))

cp_path = write_checkpoint(
    PIPELINE_DIR, PROJECT_ID, "proposal", "completed", human_approved=True,
    artifacts={"proposal_packet": proposal_packet},
    pipeline_type="animated-explainer",
    style_playbook="clean-professional",
)
check("Proposal checkpoint written", cp_path.exists())
check("Next stage after proposal", get_next_stage(PIPELINE_DIR, PROJECT_ID, "animated-explainer") == "script")

# ===================================================================
# Stage 2: script
# ===================================================================
print("\n--- Stage 2: script ---")

# Section timestamps (cumulative)
SECTIONS = [
    ("s1_hook",    "Hook",    0,  8, "What if creating a professional video took less time than making your morning coffee?"),
    ("s2_setup",   "Setup",   8, 20, "Traditional video production involves scripting, filming, editing, and post-production. It takes days, sometimes weeks."),
    ("s3_build",   "Build",  20, 38, "Now imagine an AI that handles all of that. You type a topic, and it writes the script, generates visuals, creates narration, mixes audio, and delivers a finished video."),
    ("s4_climax",  "Climax", 38, 50, "This is not science fiction. OpenMontage is an open-source platform that orchestrates AI tools into a complete video pipeline."),
    ("s5_landing", "Landing", 50, 60, "The future of video creation is open, automated, and available right now. Try it yourself."),
]

script = {
    "version": "1.0",
    "title": "AI Video Production in 60 Seconds",
    "total_duration_seconds": 60,
    "sections": [
        {
            "id": sid,
            "label": label,
            "text": text,
            "start_seconds": start,
            "end_seconds": end,
            "speaker_directions": "Confident, engaging tone",
            "enhancement_cues": [
                {"type": "overlay", "description": f"Visual for {label} section", "timestamp_seconds": start + 2},
            ],
        }
        for sid, label, start, end, text in SECTIONS
    ],
}

try:
    validate_artifact("script", script)
    check("Script validates against schema", True)
except Exception as e:
    check("Script validates against schema", False, str(e))

write_checkpoint(
    PIPELINE_DIR, PROJECT_ID, "script", "completed", human_approved=True,
    artifacts={"script": script},
    pipeline_type="animated-explainer",
)
check("Completed stages", get_completed_stages(PIPELINE_DIR, PROJECT_ID) == ["research", "proposal", "script"])  # research, proposal and script in pipeline order

# ===================================================================
# Stage 3: scene_plan
# ===================================================================
print("\n--- Stage 3: scene_plan ---")

SCENE_TYPES = ["text_card", "diagram", "animation", "generated", "text_card"]
scene_plan = {
    "version": "1.0",
    "style_playbook": "clean-professional",
    "scenes": [
        {
            "id": f"sc{i+1}",
            "type": SCENE_TYPES[i],
            "description": f"Scene for {label} section",
            "start_seconds": start,
            "end_seconds": end,
            "script_section_id": sid,
            "required_assets": [
                {"type": "narration", "description": f"TTS narration for {label}", "source": "generate"},
                {"type": "image", "description": f"Visual for {label}", "source": "generate"},
            ],
        }
        for i, (sid, label, start, end, _) in enumerate(SECTIONS)
    ],
}

try:
    validate_artifact("scene_plan", scene_plan)
    check("Scene plan validates against schema", True)
except Exception as e:
    check("Scene plan validates against schema", False, str(e))

write_checkpoint(
    PIPELINE_DIR, PROJECT_ID, "scene_plan", "completed", human_approved=True,
    artifacts={"scene_plan": scene_plan},
    pipeline_type="animated-explainer",
)

# ===================================================================
# Stage 4: assets (generate fixtures)
# ===================================================================
print("\n--- Stage 4: assets ---")

# Generate TTS fixtures (one per section)
tts_files = {}
for sid, label, start, end, _ in SECTIONS:
    path = str(ASSETS_DIR / f"tts_{sid}.mp3")
    ensure_audio(path, duration=end - start)
    tts_files[sid] = path

# Generate music fixture
music_path = str(ASSETS_DIR / "music_bg.mp3")
ensure_audio(music_path, duration=60)

# Build asset manifest (schema: id, type, path, source_tool, scene_id required)
clean_assets = []
for i, (sid, label, start, end, _) in enumerate(SECTIONS):
    scene_id = f"sc{i+1}"
    clean_assets.append({
        "id": f"a_tts_{sid}",
        "type": "narration",
        "path": tts_files[sid],
        "source_tool": "elevenlabs_tts",
        "scene_id": scene_id,
    })
    # Image fixture
    img_path = str(ASSETS_DIR / f"img_{scene_id}.png")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"color=c=darkblue:s=1280x720:d=1", "-frames:v", "1", img_path],
        capture_output=True, check=True,
    )
    clean_assets.append({
        "id": f"a_img_{scene_id}",
        "type": "image",
        "path": img_path,
        "source_tool": "image_selector",
        "scene_id": scene_id,
    })

clean_assets.append({
    "id": "a_music",
    "type": "music",
    "path": music_path,
    "source_tool": "music_gen",
    "scene_id": "sc1",
})

asset_manifest = {
    "version": "1.0",
    "assets": clean_assets,
    "total_cost_usd": 0.0,
}

try:
    validate_artifact("asset_manifest", asset_manifest)
    check("Asset manifest validates against schema", True)
except Exception as e:
    check("Asset manifest validates against schema", False, str(e))

# Verify all files exist
all_exist = all(os.path.exists(a["path"]) for a in asset_manifest["assets"])
check("All asset files exist on disk", all_exist)

# Track costs
eid = tracker.estimate("image_selector", "generate", 0.15)
tracker.approve_tool("image_selector")
tracker.reserve(eid)
tracker.reconcile(eid, 0.0, success=True)
print(f"  Cost snapshot: {tracker.cost_snapshot()}")

write_checkpoint(
    PIPELINE_DIR, PROJECT_ID, "assets", "completed", human_approved=True,
    artifacts={"asset_manifest": asset_manifest},
    pipeline_type="animated-explainer",
    cost_snapshot=tracker.cost_snapshot(),
)

# ===================================================================
# Stage 5: edit (edit_decisions)
# ===================================================================
print("\n--- Stage 5: edit ---")

# Create video clips for the compose step
colors = ["darkblue", "darkgreen", "darkorange", "darkred", "purple"]
scene_videos = {}
for i, scene in enumerate(scene_plan["scenes"]):
    scid = scene["id"]
    dur = scene["end_seconds"] - scene["start_seconds"]
    vid_path = str(ASSETS_DIR / f"scene_{scid}.mp4")
    ensure_video(vid_path, duration=dur, color=colors[i % len(colors)])
    scene_videos[scid] = vid_path

edit_decisions = {
    "version": "1.0",
    "render_runtime": proposal_packet["production_plan"]["render_runtime"],
    "cuts": [
        {
            "id": f"cut_{scene['id']}",
            "source": scene_videos[scene["id"]],
            "in_seconds": 0,
            "out_seconds": scene["end_seconds"] - scene["start_seconds"],
            "speed": 1.0,
        }
        for scene in scene_plan["scenes"]
    ],
    "music": {
        "asset_id": "a_music",
        "volume": 0.2,
        "ducking": True,
        "fade_in_seconds": 1.0,
        "fade_out_seconds": 2.0,
    },
    "subtitles": {
        "enabled": True,
        "style": "clean-professional",
    },
}

try:
    validate_artifact("edit_decisions", edit_decisions)
    check("Edit decisions validates against schema", True)
except Exception as e:
    check("Edit decisions validates against schema", False, str(e))

write_checkpoint(
    PIPELINE_DIR, PROJECT_ID, "edit", "completed",
    artifacts={"edit_decisions": edit_decisions},
    pipeline_type="animated-explainer",
)

# ===================================================================
# Stage 6: compose (REAL tool execution)
# ===================================================================
print("\n--- Stage 6: compose (real tools) ---")

from tools.audio.audio_mixer import AudioMixer
from tools.video.video_compose import VideoCompose

# Step 1: Mix narration + music
print("  Mixing audio...")
mixer = AudioMixer()
mix_output = str(ASSETS_DIR / "final_mix.wav")

# Combine all narration into one track first
concat_narration = str(ASSETS_DIR / "narration_concat.wav")
narration_list = str(ASSETS_DIR / "narration_list.txt")
with open(narration_list, "w") as f:
    for sid, _, _, _, _ in SECTIONS:
        safe = tts_files[sid].replace("\\", "/")
        f.write(f"file '{safe}'\n")

subprocess.run(
    ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", narration_list,
     "-c", "copy", concat_narration],
    capture_output=True, check=True,
)

mix_result = mixer.execute({
    "operation": "duck",
    "tracks": [
        {"path": concat_narration, "role": "speech"},
        {"path": music_path, "role": "music"},
    ],
    "ducking": {"enabled": True, "music_volume_during_speech": 0.15},
    "output_path": mix_output,
})
check("Audio mix succeeded", mix_result.success, mix_result.error or "")

# Step 2: Compose video
print("  Composing video...")
composer = VideoCompose()
final_video = str(Path(OUT) / "e2e_final_output.mp4")

compose_result = composer.execute({
    "operation": "compose",
    "edit_decisions": {
        "cuts": [
            {"source": c["source"], "in_seconds": c["in_seconds"], "out_seconds": c["out_seconds"], "speed": c.get("speed", 1.0)}
            for c in edit_decisions["cuts"]
        ],
    },
    "audio_path": mix_output,
    "codec": "libx264",
    "crf": 23,
    "preset": "fast",
    "output_path": final_video,
})
check("Video compose succeeded", compose_result.success, compose_result.error or "")
check("Output video exists", os.path.exists(final_video))

# Probe the output
duration = 0.0
video_stream = {}
audio_stream = {}
if os.path.exists(final_video):
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", "-show_streams", final_video],
        capture_output=True, text=True,
    )
    info = json.loads(probe.stdout)
    fmt = info.get("format", {})
    duration = float(fmt.get("duration", 0))
    for s in info.get("streams", []):
        if s.get("codec_type") == "video" and not video_stream:
            video_stream = s
        elif s.get("codec_type") == "audio" and not audio_stream:
            audio_stream = s

    print(f"  Output: {video_stream.get('width')}x{video_stream.get('height')}"
          f" {video_stream.get('codec_name')} | {duration:.1f}s"
          f" | Audio: {audio_stream.get('codec_name')}"
          f" | Size: {os.path.getsize(final_video)} bytes")

    check("Video has audio track", bool(audio_stream))
    check("Video has video track", bool(video_stream))
    check("Duration > 30s", duration > 30, f"{duration:.1f}s")

render_report = {
    "version": "1.0",
    "outputs": [
        {
            "path": final_video,
            "format": "mp4",
            "codec": video_stream.get("codec_name", "h264"),
            "audio_codec": audio_stream.get("codec_name", "aac"),
            "resolution": f"{video_stream.get('width', 1280)}x{video_stream.get('height', 720)}",
            "fps": 30,
            "duration_seconds": round(duration, 2),
            "file_size_bytes": os.path.getsize(final_video) if os.path.exists(final_video) else 0,
            "platform_target": "youtube",
        }
    ],
    "render_time_seconds": compose_result.duration_seconds,
}

try:
    validate_artifact("render_report", render_report)
    check("Render report validates against schema", True)
except Exception as e:
    check("Render report validates against schema", False, str(e))

write_checkpoint(
    PIPELINE_DIR, PROJECT_ID, "compose", "completed",
    artifacts={"render_report": render_report},
    pipeline_type="animated-explainer",
    cost_snapshot=tracker.cost_snapshot(),
)

# ===================================================================
# Stage 7: publish
# ===================================================================
print("\n--- Stage 7: publish ---")

publish_log = {
    "version": "1.0",
    "entries": [
        {
            "platform": "youtube",
            "status": "exported",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "export_path": str(Path(OUT) / "e2e_export"),
            "metadata_used": {
                "title": "AI Video Production in 60 Seconds",
                "description": "See how AI orchestrates an entire video production pipeline.",
                "hashtags": ["#AI", "#VideoProduction", "#OpenMontage"],
                "chapters": [
                    {"time": "0:00", "label": "Hook"},
                    {"time": "0:08", "label": "The Problem"},
                    {"time": "0:20", "label": "The Solution"},
                    {"time": "0:38", "label": "OpenMontage"},
                    {"time": "0:50", "label": "Try It"},
                ],
            },
        }
    ],
}

try:
    validate_artifact("publish_log", publish_log)
    check("Publish log validates against schema", True)
except Exception as e:
    check("Publish log validates against schema", False, str(e))

write_checkpoint(
    PIPELINE_DIR, PROJECT_ID, "publish", "completed", human_approved=True,
    artifacts={"publish_log": publish_log},
    pipeline_type="animated-explainer",
)

# ===================================================================
# Final validation
# ===================================================================
print("\n--- Final validation ---")

E2E_STAGES = ["research", "proposal", "script", "scene_plan", "assets", "edit", "compose", "publish"]
completed = get_completed_stages(PIPELINE_DIR, PROJECT_ID)
check("All 8 stages completed", len(completed) == 8, f"completed={completed}")
check("Next stage is None (done)", get_next_stage(PIPELINE_DIR, PROJECT_ID, "animated-explainer") is None)
check("Stages in correct order", completed == E2E_STAGES, f"{completed}")

# Verify all checkpoints are readable
for stage in E2E_STAGES:
    cp = read_checkpoint(PIPELINE_DIR, PROJECT_ID, stage)
    check(f"Checkpoint {stage} readable", cp is not None)
    if cp:
        expected_artifact = CANONICAL_STAGE_ARTIFACTS[stage]
        check(f"  Has canonical artifact '{expected_artifact}'", expected_artifact in cp.get("artifacts", {}))

# Cost summary
print(f"\n  Final cost: {tracker.cost_snapshot()}")

# ===================================================================
# Summary
# ===================================================================
print(f"\n{'='*60}")
print(f"END-TO-END TEST COMPLETE: {PASS} passed, {FAIL} failed")
print(f"{'='*60}")

if os.path.exists(final_video):
    print(f"\nFinal video: {final_video}")
    print("INSPECT: Open in VLC/media player to verify A/V sync, transitions, and content.")
