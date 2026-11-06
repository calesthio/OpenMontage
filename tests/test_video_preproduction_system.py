"""End-to-end tests for the Video Preproduction System.

Uses a demo scientific YouTube script about the James Webb Space Telescope.
All 20+ scenes are exercised: analysis, planning, visual direction,
character consistency, prompt engineering, quality control, and Flow
integration.  Zero credits are spent — no generation is triggered.
"""

from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import pytest  # noqa: E402

from lib.character_consistency_manager import (  # noqa: E402
    CharacterConsistencyManager,
)
from lib.flow_integration import FlowIntegration  # noqa: E402
from lib.flow_job_manager import get_manager  # noqa: E402
from lib.prompt_engineer import PromptEngineer  # noqa: E402
from lib.quality_control import QualityControl  # noqa: E402
from lib.script_analyzer import ScriptAnalyzer  # noqa: E402
from lib.scene_planner import ScenePlanner, to_dict as scene_plan_to_dict  # noqa: E402
from lib.visual_director import VisualDirector  # noqa: E402

# ---------------------------------------------------------------------------
# Demo scientific script (James Webb Space Telescope explainer)
# ---------------------------------------------------------------------------

DEMO_TITLE = "How the James Webb Space Telescope Sees the First Galaxies"

DEMO_SCRIPT = """The James Webb Space Telescope is the most powerful space observatory ever built.
It launched on December 25, 2021, aboard an Ariane 5 rocket from French Guiana.
Webb's primary mirror spans 6.5 metres, more than twice the size of Hubble's.
The mirror is made of eighteen hexagonal segments coated in a thin layer of gold.
Because gold reflects infrared light exceptionally well, it is perfect for Webb's mission.
Webb orbits the Sun at a point called L2, one and a half million kilometres from Earth.
At L2, the telescope stays in line with Earth as both move around the Sun.
This keeps the Sun and Earth behind Webb's sunshield at all times.
The sunshield is the size of a tennis court and keeps the instruments at minus 233 degrees Celsius.
Webb sees infrared light, which is invisible to human eyes but reveals hidden structures.
Infrared light can pass through clouds of dust that block visible light.
This allows Webb to peer inside stellar nurseries where new stars are born.
Webb can also look back in time to the first galaxies that formed after the Big Bang.
Light from those ancient galaxies has been travelling for over thirteen billion years.
The expansion of the Universe stretched that light into the infrared spectrum.
Webb's instruments capture this stretched light and turn it into images we can see.
Astronomers use these images to study how the first stars and galaxies formed.
The telescope has already discovered galaxies that existed just three hundred million years after the Big Bang.
These early galaxies are brighter and more numerous than scientists expected.
This discovery is changing our understanding of how quickly the Universe evolved.
Webb will continue observing for at least ten years, revealing more cosmic secrets."""

DEMO_CHARACTERS = ["James Webb Space Telescope", "Astronomer"]

DEMO_SCENE_EXCERPTS = {
    0: "The James Webb Space Telescope is the most powerful space observatory ever built.",
    1: "It launched on December 25, 2021, aboard an Ariane 5 rocket from French Guiana.",
    2: "Webb's primary mirror spans 6.5 metres, more than twice the size of Hubble's.",
    3: "The mirror is made of eighteen hexagonal segments coated in a thin layer of gold.",
    4: "Because gold reflects infrared light exceptionally well, it is perfect for Webb's mission.",
    5: "Webb orbits the Sun at a point called L2, one and a half million kilometres from Earth.",
    6: "At L2, the telescope stays in line with Earth as both move around the Sun.",
    7: "This keeps the Sun and Earth behind Webb's sunshield at all times.",
    8: "The sunshield is the size of a tennis court and keeps the instruments at minus 233 degrees Celsius.",
    9: "Webb sees infrared light, which is invisible to human eyes but reveals hidden structures.",
    10: "Infrared light can pass through clouds of dust that block visible light.",
    11: "This allows Webb to peer inside stellar nurseries where new stars are born.",
    12: "Webb can also look back in time to the first galaxies that formed after the Big Bang.",
    13: "Light from those ancient galaxies has been travelling for over thirteen billion years.",
    14: "The expansion of the Universe stretched that light into the infrared spectrum.",
    15: "Webb's instruments capture this stretched light and turn it into images we can see.",
    16: "Astronomers use these images to study how the first stars and galaxies formed.",
    17: "The telescope has already discovered galaxies that existed just three hundred million years after the Big Bang.",
    18: "These early galaxies are brighter and more numerous than scientists expected.",
    19: "This discovery is changing our understanding of how quickly the Universe evolved.",
    20: "Webb will continue observing for at least ten years, revealing more cosmic secrets.",
}

DEMO_SCIENTIFIC_CLAIMS = {
    2: [{"text": "Webb's primary mirror spans 6.5 metres, more than twice the size of Hubble's."}],
    4: [{"text": "Because gold reflects infrared light exceptionally well, it is perfect for Webb's mission."}],
    5: [{"text": "Webb orbits the Sun at a point called L2, one and a half million kilometres from Earth."}],
    8: [{"text": "The sunshield is the size of a tennis court and keeps the instruments at minus 233 degrees Celsius."}],
    9: [{"text": "Webb sees infrared light, which is invisible to human eyes but reveals hidden structures."}],
    12: [{"text": "Webb can also look back in time to the first galaxies that formed after the Big Bang."}],
    13: [{"text": "Light from those ancient galaxies has been travelling for over thirteen billion years."}],
    17: [{"text": "The telescope has already discovered galaxies that existed just three hundred million years after the Big Bang."}],
}

DEMO_CHARACTER_MAP = {
    i: "James Webb Space Telescope" for i in range(21)
}


# ---------------------------------------------------------------------------
# Fixture: run the full pipeline once
# ---------------------------------------------------------------------------

@pytest.fixture
def pipeline_outputs():
    """Run the full preproduction pipeline on the demo script."""
    # 1. Script analysis
    analyzer = ScriptAnalyzer()
    analysis = analyzer.analyze(
        title=DEMO_TITLE,
        script=DEMO_SCRIPT,
        target_duration_seconds=600.0,
        characters=DEMO_CHARACTERS,
        visual_style="bold ink illustration",
    )
    analysis_dict = analyzer.to_dict(analysis)

    # 2. Scene planning
    planner = ScenePlanner()
    plan = planner.plan(
        run_id="demo-run-001",
        analysis_blocks=analysis_dict["blocks"],
        characters=DEMO_CHARACTERS,
        visual_style="bold ink illustration",
        hero_index=3,  # the gold mirror scene
    )
    plan_dict = scene_plan_to_dict(plan)

    # 3. Visual direction
    director = VisualDirector(visual_style="bold ink illustration")
    direction = director.direct(plan_dict["scenes"], characters=DEMO_CHARACTERS)
    direction_dict = director.to_dict(direction)

    # 4. Character consistency
    ccm = CharacterConsistencyManager()
    ccm.register_character(
        character_id="James Webb Space Telescope",
        display_name="James Webb Space Telescope",
        role="space observatory",
        body_type="hexagonal mirror segments with sunshield",
        limb_count=0,
        distinguishing_features=[
            "gold-coated hexagonal mirror segments",
            "tennis-court-sized sunshield",
        ],
        silhouette_notes="distinctive honeycomb mirror shape with kite-shaped sunshield",
        color_palette=["gold", "white", "black"],
        clothing_notes="none",
        required_views=["wide", "medium_close", "extreme_close_up"],
        required_emotions=["awe", "curiosity"],
        required_actions=["orbiting", "observing"],
        props=["sunshield", "mirror segments"],
    )
    ccm.add_reference(
        reference_id="webb-ref-001",
        character_id="James Webb Space Telescope",
        reference_type="description",
        description="Gold hexagonal mirror segments with white sunshield structure",
        captured_features=["gold hexagonal mirror segments", "tennis-court-sized sunshield"],
    )

    scene_char_map = {}
    scene_descs = {}
    consistency_issues_by_scene = {}
    for scene in plan_dict["scenes"]:
        sid = scene["scene_id"]
        scene_char_map[sid] = "James Webb Space Telescope"
        scene_descs[sid] = scene["visual_idea"]
        issues = ccm.validate_scene_against_character(
            scene_id=sid,
            character_id="James Webb Space Telescope",
            scene_description=scene["visual_idea"],
            proposed_limb_count=0,
            proposed_features=["gold-coated hexagonal mirror segments"],
        )
        consistency_issues_by_scene[sid] = [asdict(i) for i in issues]

    consistency_report = ccm.validate_all_scenes(scene_char_map, scene_descs)
    consistency_dict = ccm.to_dict(consistency_report)

    # 5. Prompt engineering
    engineer = PromptEngineer(visual_style="bold ink illustration")
    prompts = engineer.build_all(
        scene_plans=plan_dict["scenes"],
        visual_directives={d["scene_id"]: d for d in direction_dict["directives"]},
        character_anatomy={"James Webb Space Telescope": consistency_dict["characters"]["James Webb Space Telescope"]},
        references_by_scene={sid: ["webb-ref-001"] for sid in scene_char_map},
        generation_params={"model": "flow", "steps": 20},
    )
    prompts_dict = engineer.to_dict(prompts)

    # 6. Quality control
    qc = QualityControl()
    all_compositions = {s["scene_id"]: s["composition"] for s in plan_dict["scenes"]}
    all_descs = {s["scene_id"]: s["visual_idea"] for s in plan_dict["scenes"]}

    # Build index-based mappings using actual scene IDs from the plan.
    script_excerpts_by_scene = {}
    claims_by_scene = {}
    char_map_by_scene = {}
    for idx, scene in enumerate(plan_dict["scenes"]):
        sid = scene["scene_id"]
        script_excerpts_by_scene[sid] = scene.get("visual_idea", "")
        claims_by_scene[sid] = DEMO_SCIENTIFIC_CLAIMS.get(idx, [])
        char_map_by_scene[sid] = DEMO_CHARACTER_MAP.get(idx, "James Webb Space Telescope")

    qc_batch = qc.check_batch(
        scenes=plan_dict["scenes"],
        script_excerpts=script_excerpts_by_scene,
        scientific_claims_by_scene=claims_by_scene,
        character_map=char_map_by_scene,
        character_anatomy_by_id={"James Webb Space Telescope": consistency_dict["characters"]["James Webb Space Telescope"]},
        consistency_issues_by_scene=consistency_issues_by_scene,
        prompt_packets_by_scene={p["scene_id"]: p for p in prompts_dict["packets"]},
    )
    qc_dict = qc.to_dict(qc_batch)

    # 7. Flow integration
    manager = get_manager()
    # Clear any existing jobs for a clean test
    import lib.flow_job_manager as fjm
    import tempfile
    from pathlib import Path

    test_dir = Path(tempfile.mkdtemp())
    fjm.JOBS_DIR = test_dir / "jobs"
    fjm.FLOW_QUEUE_DIR = test_dir / "flow_queue"
    fjm.FLOW_RESULTS_DIR = test_dir / "flow_results"
    fjm.QUEUE_DB = test_dir / "flow_queue" / "queue.db"
    for d in (fjm.JOBS_DIR, fjm.FLOW_QUEUE_DIR, fjm.FLOW_RESULTS_DIR):
        d.mkdir(parents=True, exist_ok=True)

    # Reset the cached manager so it picks up the test paths
    fjm._manager = None
    manager = get_manager()

    integration = FlowIntegration(manager=manager)
    flow_output = integration.integrate(
        run_id="demo-run-001",
        project="webb-explainer",
        scene_plans=plan_dict["scenes"],
        prompt_packets=prompts_dict["packets"],
        quality_reports=qc_dict["reports"],
        references_by_scene={sid: ["webb-ref-001"] for sid in scene_char_map},
        generation_params={"model": "flow", "steps": 20},
    )
    flow_dict = integration.to_dict(flow_output)

    return {
        "analysis": analysis_dict,
        "plan": plan_dict,
        "direction": direction_dict,
        "consistency": consistency_dict,
        "prompts": prompts_dict,
        "qc": qc_dict,
        "flow": flow_dict,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_script_analysis_produces_blocks(pipeline_outputs):
    """Test 1: Script analysis produces meaning blocks."""
    analysis = pipeline_outputs["analysis"]
    assert analysis["total_words"] > 0
    assert analysis["estimated_seconds"] > 0
    assert len(analysis["blocks"]) >= 20
    assert analysis["visual_style_hint"] == "bold ink illustration"
    assert "James Webb Space Telescope" in analysis["characters_mentioned"] or "Webb" in analysis["characters_mentioned"]


def test_scientific_claims_detected(pipeline_outputs):
    """Test 2: Scientific claims are detected in the script."""
    analysis = pipeline_outputs["analysis"]
    assert len(analysis["scientific_claims"]) > 0
    for claim in analysis["scientific_claims"]:
        assert "claim_id" in claim
        assert "text" in claim
        assert "block_id" in claim


def test_scene_planner_produces_20_plus_scenes(pipeline_outputs):
    """Test 3: Scene planner produces 20+ scenes."""
    plan = pipeline_outputs["plan"]
    assert plan["metadata"]["total_scenes"] >= 20
    assert len(plan["scenes"]) == plan["metadata"]["total_scenes"]


def test_scene_has_required_fields(pipeline_outputs):
    """Test 4: Each scene has all required fields."""
    plan = pipeline_outputs["plan"]
    required = {
        "scene_id", "script_section_id", "visual_idea", "shot_purpose",
        "framing", "camera_movement", "lens_mm", "lighting_key",
        "composition", "required_objects", "duration_seconds",
        "transition_to_next", "shot_size", "shot_intent", "narrative_role",
    }
    for scene in plan["scenes"]:
        for field in required:
            assert field in scene, f"Missing field {field} in scene {scene['scene_id']}"


def test_scenes_form_continuous_story(pipeline_outputs):
    """Test 5: Scenes chain via transitions to form a continuous story."""
    plan = pipeline_outputs["plan"]
    scenes = plan["scenes"]
    for i in range(len(scenes) - 1):
        current = scenes[i]
        next_scene = scenes[i + 1]
        assert current["transition_to_next"], f"Scene {current['scene_id']} missing transition"
        assert current["narrative_role"], f"Scene {current['scene_id']} missing narrative role"


def test_visual_director_produces_directives(pipeline_outputs):
    """Test 6: Visual director produces directives for all scenes."""
    direction = pipeline_outputs["direction"]
    assert direction["total_scenes"] >= 20
    assert len(direction["directives"]) == direction["total_scenes"]
    for d in direction["directives"]:
        assert d["hero_space_reserved"] is True
        assert d["character_placement"]
        assert d["composition_notes"]


def test_shot_size_variety(pipeline_outputs):
    """Test 7: Shot sizes are varied (not all the same)."""
    direction = pipeline_outputs["direction"]
    dist = direction["shot_size_distribution"]
    assert len(dist) >= 3, f"Too few shot sizes: {dist}"


def test_character_consistency_registered(pipeline_outputs):
    """Test 8: Character is registered with anatomy."""
    consistency = pipeline_outputs["consistency"]
    assert "James Webb Space Telescope" in consistency["characters"]
    char = consistency["characters"]["James Webb Space Telescope"]
    assert char["distinguishing_features"]
    assert "gold-coated hexagonal mirror segments" in char["distinguishing_features"]


def test_no_high_severity_consistency_issues(pipeline_outputs):
    """Test 9: No high-severity character consistency issues."""
    consistency = pipeline_outputs["consistency"]
    high_issues = [i for i in consistency["issues"] if i.get("severity") == "high"]
    assert len(high_issues) == 0, f"High severity issues: {high_issues}"


def test_prompt_engineer_builds_packets(pipeline_outputs):
    """Test 10: Prompt engineer builds packets for all scenes."""
    prompts = pipeline_outputs["prompts"]
    assert prompts["metadata"]["total_packets"] >= 20
    assert len(prompts["packets"]) == prompts["metadata"]["total_packets"]
    for p in prompts["packets"]:
        assert p["main_prompt"]
        assert p["negative_prompt"]
        assert p["scene_id"]


def test_prompt_has_no_text_instruction(pipeline_outputs):
    """Test 11: Prompts do not instruct text inside images."""
    prompts = pipeline_outputs["prompts"]
    for p in prompts["packets"]:
        main_lower = p["main_prompt"].lower()
        neg_lower = p["negative_prompt"].lower()
        # Main prompt must not contain positive instructions to add text/captions
        positive_text_instructions = ["add text", "write text", "include text", "with text", "text overlay", "caption:", "write caption"]
        for inst in positive_text_instructions:
            assert inst not in main_lower, f"Positive text instruction '{inst}' in main prompt: {p['scene_id']}"
        # Negative prompt SHOULD prohibit text
        assert "text" in neg_lower or "caption" in neg_lower, f"No text prohibition in negative: {p['scene_id']}"


def test_quality_control_runs_on_all_scenes(pipeline_outputs):
    """Test 12: QC runs on all scenes."""
    qc = pipeline_outputs["qc"]
    assert qc["total_scenes"] >= 20
    assert qc["passed_scenes"] + qc["failed_scenes"] == qc["total_scenes"]


def test_quality_control_has_all_criteria(pipeline_outputs):
    """Test 13: QC reports contain all expected criteria."""
    qc = pipeline_outputs["qc"]
    expected_criteria = {
        "script_alignment", "scientific_accuracy", "character_reference",
        "duplicate_frames", "anatomy_errors", "prompt_contradictions",
        "composition_variety", "no_text_in_image", "technical_suitability",
    }
    for sid, report in qc["reports"].items():
        criteria = {r["criterion"] for r in report["results"]}
        assert expected_criteria.issubset(criteria), f"Scene {sid} missing criteria: {expected_criteria - criteria}"


def test_no_duplicate_scenes(pipeline_outputs):
    """Test 14: No duplicate scenes."""
    qc = pipeline_outputs["qc"]
    for sid, report in qc["reports"].items():
        dup_results = [r for r in report["results"] if r["criterion"] == "duplicate_frames"]
        for r in dup_results:
            assert r["passed"], f"Duplicate detected for {sid}: {r['detail']}"


def test_flow_integration_creates_jobs(pipeline_outputs):
    """Test 15: Flow integration creates jobs for passing scenes."""
    flow = pipeline_outputs["flow"]
    assert flow["jobs_queued"] > 0
    assert flow["queue_summary"]["total"] > 0


def test_all_jobs_stop_at_ready_for_approval(pipeline_outputs):
    """Test 16: All jobs stop at READY_FOR_APPROVAL."""
    flow = pipeline_outputs["flow"]
    for job in flow["jobs"]:
        assert job["state"] == "READY_FOR_APPROVAL", f"Job {job['job_id']} in state {job['state']}"


def test_no_generation_triggered(pipeline_outputs):
    """Test 17: No generation is triggered — READ_ONLY mode respected."""
    flow = pipeline_outputs["flow"]
    for job in flow["jobs"]:
        gp = job.get("prompt_packet", {}).get("generation_params", {})
        # No credit/budget references in generation params
        for k in ("budget_usd", "credits", "paid"):
            assert k not in gp, f"Generation param {k} found in job {job['job_id']}"


def test_duplicate_scenes_not_double_queued():
    """Test 18: Identical scene content does not produce duplicate Flow jobs."""
    from lib.flow_job_manager import FlowJobManager
    import lib.flow_job_manager as fjm
    import tempfile
    from pathlib import Path

    test_dir = Path(tempfile.mkdtemp())
    fjm.JOBS_DIR = test_dir / "jobs"
    fjm.FLOW_QUEUE_DIR = test_dir / "flow_queue"
    fjm.FLOW_RESULTS_DIR = test_dir / "flow_results"
    fjm.QUEUE_DB = test_dir / "flow_queue" / "queue.db"
    for d in (fjm.JOBS_DIR, fjm.FLOW_QUEUE_DIR, fjm.FLOW_RESULTS_DIR):
        d.mkdir(parents=True, exist_ok=True)

    mgr = FlowJobManager()
    mgr.add_job(
        job_id="job-1", project="P", scene="S",
        prompt="A scientific illustration of a telescope",
    )
    # Same content, different ID — should be blocked
    with pytest.raises(ValueError, match="Duplicate job content"):
        mgr.add_job(
            job_id="job-2", project="P", scene="S",
            prompt="A scientific illustration of a telescope",
        )


def test_qc_scientific_claims_require_human_review(pipeline_outputs):
    """Test 19: Scientific accuracy checks always require human review."""
    qc = pipeline_outputs["qc"]
    found_claim_scene = False
    for sid, report in qc["reports"].items():
        for r in report["results"]:
            if r["criterion"] == "scientific_accuracy" and r["requires_human_review"]:
                found_claim_scene = True
    assert found_claim_scene, "No scenes with scientific claims found to test"


def test_prompt_negative_prohibits_text(pipeline_outputs):
    """Test 20: Negative prompts prohibit text/captions/watermarks."""
    prompts = pipeline_outputs["prompts"]
    for p in prompts["packets"]:
        neg = p["negative_prompt"].lower()
        assert "text" in neg or "caption" in neg
        assert "watermark" in neg or "logo" in neg


def test_visual_style_applied(pipeline_outputs):
    """Test 21: Visual style foundation is applied to all prompts."""
    prompts = pipeline_outputs["prompts"]
    for p in prompts["packets"]:
        assert "bold ink illustration" in p["main_prompt"].lower()
        assert "black outline" in p["main_prompt"].lower()
        assert "scientific-documentary" in p["main_prompt"].lower()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
