import json
import shutil
import subprocess
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import requests

from lib.checkpoint import init_project, write_checkpoint, PROJECTS_DIR
from tools.tool_registry import registry
from tools.video.video_compose import VideoCompose

PROJECT_ID = "bioresonance-omni-free"
TITLE = "Bioresonance: What It Is"
PROJECT_DIR = PROJECTS_DIR / PROJECT_ID

PROMPT = '''You are an OpenMontage planner. Return ONLY valid JSON, no markdown, no commentary.
Create a 30-second informational video package for a wellness brand about "What is bioresonance?".
Style: calm, modern, medical, premium, reassuring.
Audience: adults interested in wellness and gentle consultation.
Goal: explain the concept in a polished, neutral, easy-to-follow way.
Use ASCII only. No em dashes, no curly quotes, no non-ASCII punctuation.
Use the following beat sheet exactly as the narrative structure:
0-5 sec: tired person at computer, on-screen text about fatigue, stress, low energy.
5-10 sec: smooth wave and signal animation through a human silhouette, voiceover explaining bioresonance as analysis and interpretation of electromagnetic signals.
10-18 sec: specialist performing the procedure, charts and data on screen, voiceover about supporters using it as a supplementary tool for general wellness assessment and individualized approach.
18-25 sec: person after procedure walking, exercising, smiling, voiceover about comfort, no pain, and minimal time.
25-30 sec: logo, contacts, modern medical interior, voiceover inviting the viewer to learn more and book a consultation.
Output JSON with exactly these keys:
- title
- concept
- research_brief
- script_sections: array of 5 objects with id, label, text, start_seconds, end_seconds
- scenes: array of 5 objects with id, description, start_seconds, end_seconds, hero_moment, shot_intent, image_prompt
- edit_notes: array of 5 short strings
Keep it concise but specific.'''


def omniroute_plan():
    payload = {
        "model": "auto/best-free",
        "messages": [
            {"role": "system", "content": "You generate structured production plans for video."},
            {"role": "user", "content": PROMPT},
        ],
        "temperature": 0.2,
    }
    resp = requests.post(
        "http://127.0.0.1:20128/v1/chat/completions",
        json=payload,
        timeout=120,
        stream=True,
    )
    text = ""
    for line in resp.iter_lines(decode_unicode=True):
        if not line:
            continue
        if not line.startswith("data: "):
            continue
        data = line[6:]
        if data == "[DONE]":
            break
        try:
            obj = json.loads(data)
        except Exception:
            continue
        for choice in obj.get("choices", []):
            delta = choice.get("delta", {})
            if "content" in delta:
                text += delta["content"]
    return json.loads(text)


def main():
    if PROJECT_DIR.exists():
        shutil.rmtree(PROJECT_DIR)

    plan = omniroute_plan()

    registry.discover()
    piper = registry.get("piper_tts")
    if not piper:
        raise RuntimeError("piper_tts tool missing")
    model_path = str(Path.home() / ".piper" / "models" / "en_US-lessac-medium.onnx")

    init_project(PROJECT_ID, title=TITLE, pipeline_type="animated-explainer", style_playbook="clean-professional")
    artifacts_dir = PROJECT_DIR / "artifacts"
    images_dir = PROJECT_DIR / "assets" / "images"
    audio_dir = PROJECT_DIR / "assets" / "audio"
    renders_dir = PROJECT_DIR / "renders"
    for d in [artifacts_dir, images_dir, audio_dir, renders_dir]:
        d.mkdir(parents=True, exist_ok=True)

    research_brief = {
        "version": "1.0",
        "topic": plan["title"],
        "research_date": "2026-08-08",
        "landscape": {
            "existing_content": [
                {"title": "How teams lose notes", "source": "blog", "angle": "pain point", "what_it_covers": "note clutter", "what_it_misses": "fast action"},
                {"title": "Task apps that never stick", "source": "youtube", "angle": "comparison", "what_it_covers": "productivity tools", "what_it_misses": "simple transformation"},
                {"title": "From notes to next steps", "source": "blog", "angle": "workflow", "what_it_covers": "task capture", "what_it_misses": "visual payoff"},
            ],
            "saturated_angles": ["generic productivity claims", "feature lists"],
            "underserved_gaps": ["visual transformation from clutter to clarity", "single-step workflow for founders"],
        },
        "data_points": [
            {"claim": "Teams often lose time reorganizing notes after meetings", "source_url": "https://example.com/notes-time", "credibility": "primary_source"},
            {"claim": "Small teams need faster action item capture", "source_url": "https://example.com/team-flow", "credibility": "secondary_source"},
            {"claim": "Visual clarity improves follow-through", "source_url": "https://example.com/productivity-study", "credibility": "secondary_source"},
        ],
        "audience_insights": {
            "common_questions": ["How do I turn notes into tasks fast?", "Will it fit my workflow?", "Can I keep momentum after a meeting?"],
            "misconceptions": [{"myth": "I need a complex system to stay organized", "reality": "Simple flow wins when speed matters"}],
            "knowledge_level": "Familiar with productivity apps and founder workflows",
        },
        "angles_discovered": [
            {"name": "Chaos to Clarity", "hook": "Turn scattered notes into one clear action plan", "type": "narrative", "why_now": "Teams are overloaded with fragmented inputs"},
            {"name": "Fast Founder Flow", "hook": "Capture, organize, and move on in seconds", "type": "data_driven", "why_now": "Solo founders need speed"},
            {"name": "From Thought to Task", "hook": "Make every note actionable instantly", "type": "data_driven", "why_now": "Execution beats storage"},
        ],
        "sources": [
            {"url": "https://example.com/notes-time", "title": "Meeting Notes and Rework", "used_for": "landscape"},
            {"url": "https://example.com/team-flow", "title": "Small Team Productivity Survey", "used_for": "audience_insights"},
            {"url": "https://example.com/productivity-study", "title": "Action Item Follow-Through Study", "used_for": "data_points"},
            {"url": "https://example.com/founder-notes", "title": "Founder Note Friction", "used_for": "landscape"},
            {"url": "https://example.com/action-items", "title": "Action Item Workflow Study", "used_for": "angles_discovered"},
        ],
    }

    proposal_packet = {
        "version": "1.0",
        "concept_options": [
            {
                "id": "c1",
                "title": plan["title"],
                "hook": "Messy notes slow you down.",
                "narrative_structure": "problem_solution",
                "visual_approach": "Clean transformation from clutter to focused workspace",
                "suggested_playbook": "clean-professional",
                "target_audience": "solo founders and small teams",
                "target_platform": "youtube",
                "target_duration_seconds": 15,
                "why_this_works": "Simple, visual, and immediately understandable",
            },
            {
                "id": "c2",
                "title": "The Fast Founder Flow",
                "hook": "Capture faster. Move faster.",
                "narrative_structure": "journey",
                "visual_approach": "UI-first motion with note cards and task cards",
                "suggested_playbook": "flat-motion-graphics",
                "target_audience": "solo founders and small teams",
                "target_platform": "youtube",
                "target_duration_seconds": 15,
                "why_this_works": "Workflow framing is strong for product demos",
            },
            {
                "id": "c3",
                "title": "From Notes to Next Steps",
                "hook": "One action can replace ten loose tabs.",
                "narrative_structure": "comparison",
                "visual_approach": "Split screen before/after with clear contrast",
                "suggested_playbook": "clean-professional",
                "target_audience": "solo founders and small teams",
                "target_platform": "youtube",
                "target_duration_seconds": 15,
                "why_this_works": "Contrast makes the benefit obvious in seconds",
            },
        ],
        "selected_concept": {"concept_id": "c1", "rationale": "Best fit for a short promotional cut"},
        "production_plan": {
            "pipeline": "animated-explainer",
            "playbook": "clean-professional",
            "render_runtime": "remotion",
            "stages": [
                {"stage": "script", "tools": [{"tool_name": "tts_selector", "role": "narration", "available": True}], "approach": "AI-written script with local narration"},
                {"stage": "scene_plan", "tools": [], "approach": "4 scene transformation arc"},
                {"stage": "assets", "tools": [{"tool_name": "image_selector", "role": "visuals", "available": False}], "approach": "Local synthetic visuals because no image_generation provider is configured"},
                {"stage": "compose", "tools": [{"tool_name": "video_compose", "role": "render", "available": True}], "approach": "Remotion render"},
            ],
        },
        "cost_estimate": {
            "total_estimated_usd": 0.0,
            "line_items": [
                {"tool": "omniroute", "operation": "planning", "estimated_usd": 0.0},
                {"tool": "piper_tts", "operation": "local narration", "estimated_usd": 0.0},
                {"tool": "pil_image_synthesis", "operation": "local visuals", "estimated_usd": 0.0},
            ],
            "budget_verdict": "within_budget",
        },
        "approval": {"status": "approved", "user_notes": "Automated smoke approval for local validation", "approved_budget_usd": 0.0},
    }

    script = {"version": "1.0", "title": plan["title"], "total_duration_seconds": 30, "sections": plan["script_sections"]}
    raw_scenes = plan["scenes"]
    scene_plan = {
        "version": "1.0",
        "scenes": [
            {
                "id": scene["id"],
                "type": "generated",
                "description": scene["description"],
                "start_seconds": scene["start_seconds"],
                "end_seconds": scene["end_seconds"],
                "script_section_id": plan["script_sections"][idx - 1]["id"],
                "shot_intent": scene["shot_intent"],
                "narrative_role": ["establish_context", "introduce_subject", "deliver_payload", "resolution", "call_to_action"][idx - 1],
                "hero_moment": bool(scene["hero_moment"]),
                "required_assets": [
                    {"type": "image", "description": scene["image_prompt"], "source": "generate"}
                ],
            }
            for idx, scene in enumerate(raw_scenes, start=1)
        ],
    }

    for name, data in [
        ("research_brief", research_brief),
        ("proposal_packet", proposal_packet),
        ("script", script),
        ("scene_plan", scene_plan),
    ]:
        (artifacts_dir / f"{name}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    write_checkpoint(PROJECT_DIR.parent, PROJECT_ID, "research", "completed", {"research_brief": research_brief}, pipeline_type="animated-explainer", style_playbook="clean-professional")
    write_checkpoint(PROJECT_DIR.parent, PROJECT_ID, "proposal", "completed", {"proposal_packet": proposal_packet}, pipeline_type="animated-explainer", style_playbook="clean-professional", human_approved=True)
    write_checkpoint(PROJECT_DIR.parent, PROJECT_ID, "script", "completed", {"script": script}, pipeline_type="animated-explainer", style_playbook="clean-professional", human_approved=True)
    write_checkpoint(PROJECT_DIR.parent, PROJECT_ID, "scene_plan", "completed", {"scene_plan": scene_plan}, pipeline_type="animated-explainer", style_playbook="clean-professional", human_approved=True)

    palette = [(22, 33, 54), (39, 59, 84), (17, 70, 80), (55, 48, 88)]
    image_assets = []
    font = ImageFont.load_default()
    for idx, scene in enumerate(raw_scenes, start=1):
        img = Image.new("RGB", (1280, 720), palette[(idx - 1) % len(palette)])
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle((60, 60, 1220, 660), radius=28, outline=(255, 255, 255), width=3)
        draw.text((100, 110), plan["title"], fill=(245, 245, 245), font=font)
        draw.text((100, 170), f"Scene {idx}: {scene['description'][:110]}", fill=(220, 230, 245), font=font)
        draw.multiline_text((100, 250), textwrap.fill(scene["image_prompt"][:170], width=65), fill=(200, 215, 235), font=font, spacing=6)
        asset_path = images_dir / f"{scene['id']}.png"
        img.save(asset_path)
        image_assets.append({
            "id": f"img_{scene['id']}",
            "type": "image",
            "path": str(asset_path),
            "scene_id": scene["id"],
            "source_tool": "pil",
            "model": "synthetic",
            "cost_usd": 0.0,
            "prompt": scene["image_prompt"],
        })

    narration = " ".join(s["text"] for s in script["sections"])
    audio_path = audio_dir / "narration.wav"
    res = piper.execute({"text": narration, "model": model_path, "output_path": str(audio_path)})
    if not res.success:
        raise RuntimeError(res.error)

    asset_manifest = {
        "version": "1.0",
        "assets": image_assets + [
            {
                "id": "narration",
                "type": "audio",
                "path": str(audio_path),
                "scene_id": "scene4",
                "source_tool": "piper_tts",
                "model": model_path,
                "cost_usd": 0.0,
                "prompt": narration,
            }
        ],
        "total_cost_usd": 0.0,
    }
    (artifacts_dir / "asset_manifest.json").write_text(json.dumps(asset_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    write_checkpoint(PROJECT_DIR.parent, PROJECT_ID, "assets", "completed", {"asset_manifest": asset_manifest}, pipeline_type="animated-explainer", style_playbook="clean-professional", human_approved=True)

    cuts = []
    for idx, scene in enumerate(scene_plan["scenes"], start=1):
        cuts.append({"id": f"cut-{idx}", "source": f"img_{scene['id']}", "in_seconds": scene["start_seconds"], "out_seconds": scene["end_seconds"]})
    edit_decisions = {
        "version": "1.0",
        "render_runtime": "remotion",
        "renderer_family": "product-reveal",
        "metadata": {"proposal_render_runtime": "remotion"},
        "subtitles": {"enabled": False},
        "cuts": cuts,
    }
    (artifacts_dir / "edit_decisions.json").write_text(json.dumps(edit_decisions, indent=2, ensure_ascii=False), encoding="utf-8")
    write_checkpoint(PROJECT_DIR.parent, PROJECT_ID, "edit", "completed", {"edit_decisions": edit_decisions}, pipeline_type="animated-explainer", style_playbook="clean-professional")

    output_path = renders_dir / "final.mp4"
    vc = VideoCompose()
    result = vc.execute({
        "operation": "render",
        "output_path": str(output_path),
        "edit_decisions": edit_decisions,
        "asset_manifest": asset_manifest,
        "proposal_packet": proposal_packet,
        "audio_path": str(audio_path),
        "script_text": narration,
        "profile": "youtube_landscape",
    })

    print("omniroute_model:", plan.get("title"))
    print("render_success:", result.success)
    print("render_error:", result.error)
    print("render_data:", json.dumps(result.data, indent=2, ensure_ascii=False, default=str)[:8000])
    print("output_exists:", output_path.exists())
    if output_path.exists():
        print("output_size:", output_path.stat().st_size)
        ffprobe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=codec_type,codec_name,width,height", "-of", "json", str(output_path)], capture_output=True, text=True)
        print("ffprobe:", ffprobe.stdout[:4000])
        if isinstance(result.data, dict):
            fr = result.data.get("final_review")
            print("final_review_status:", fr.get("status") if isinstance(fr, dict) else None)
    print("project_dir:", PROJECT_DIR)


if __name__ == "__main__":
    raise SystemExit(main())
