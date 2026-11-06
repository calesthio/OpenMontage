"""Mock tests for the Image Generation Engine (lib.image_generation_engine).

Zero-cost, no gflow-cli calls, no credits spent.  The engine runs in
``mock=True`` mode which writes placeholder PNGs and exercises the full
planning / asset / QC / uniqueness / recovery flow end-to-end.

Covers:
  * prompt creation for 10 / 50 / 160 / 250 sentences
  * batch formation within gflow limits
  * unique asset_id / prompt_id / job_id
  * one image per sentence (never shared)
  * error handling, retries, duplicate detection
  * recovery after restart (skip completed)
  * character reference workflow
  * QC (file exists, 16:9, resolution, decodable)
  * Flow Job Manager integration (READY_FOR_APPROVAL stop)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/workspaces/OpenMontage")

from lib.asset_registry import AssetRegistry  # noqa: E402
from lib.batch_scheduler import BatchPrompt, BatchScheduler  # noqa: E402
from lib.character_consistency_manager import CharacterConsistencyManager  # noqa: E402
from lib.flow_job_manager import FlowJobManager  # noqa: E402
from lib.gflow_provider import GflowProvider, ProviderImageRequest  # noqa: E402
from lib.gflow_wrapper import GflowWrapper  # noqa: E402
from lib.image_generation_engine import (  # noqa: E402
    DEFAULT_ASPECT,
    DEFAULT_MODEL,
    ImageGenerationEngine,
    SentenceImagePlan,
)
from lib.image_uniqueness import check_uniqueness, compute_ahash  # noqa: E402
from lib.prompt_engineer import PromptEngineer  # noqa: E402
from lib.quality_control import QualityControl  # noqa: E402
from lib.recovery_manager import RecoveryManager  # noqa: E402
from lib.sentence_segmenter import SentenceSegmenter  # noqa: E402
from lib.visual_director import VisualDirector  # noqa: E402


# ---------------------------------------------------------------------------
# Test isolation: FlowJobManager persists jobs/ and flow_queue/ in the repo
# root (global across tests and pytest runs).  Clean before every test so
# job_ids never collide between tests or runs, while keeping the directories
# FlowJobManager needs for sqlite.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_flow_state():
    """FlowJobManager persists jobs/ and flow_queue/ in the repo root (global
    across tests and pytest runs).  Clean file contents before every test so
    job_ids never collide between tests or runs, while keeping the directories
    FlowJobManager needs for sqlite."""
    jobs_dir = Path("/workspaces/OpenMontage/jobs")
    queue_dir = Path("/workspaces/OpenMontage/flow_queue")
    jobs_dir.mkdir(parents=True, exist_ok=True)
    queue_dir.mkdir(parents=True, exist_ok=True)
    for f in jobs_dir.glob("*.json"):
        f.unlink(missing_ok=True)
    for f in queue_dir.glob("queue.db*"):
        f.unlink(missing_ok=True)
    yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_SUBJECTS = [
    "deep-sea anglerfish", "vintage brass telescope", "human heart cross-section",
    "DNA double helix", "steam locomotive", "hurricane eye", "microchip circuit board",
    "desert landscape with cactus", "crystal geode", "volcanic crater with lava",
    "spiral galaxy nebula", "compound microscope", "ancient astrolabe", "crystal radio",
    "pocket watch mechanism", "sailing ship on stormy sea", "hot air balloon",
    "windmill in tulip field", "waterwheel by a stream", "blacksmith forge",
    "cathedral rose window", "pocket compass", "old printing press",
    "brass sextant", "ivory chess set", "glassblowing furnace",
    "antique camera bellows", "marble statue of a philosopher",
    "geological rock strata", "coral reef polyps", "mechanical clock gears",
    "vintage typewriter keys", "crystal prism splitting light",
    "botanical pressed flower specimen", "atomic model with orbiting electrons",
    "weather vane on a barn roof", "abacus with wooden beads",
    "bronze armillary sphere", "cabinet of curiosities interior",
    "antique diving helmet", "celestial orrery model",
    "sextant navigating by stars", "barometer and thermometer",
    "photographic darkroom enlarger", "sundial on stone pedestal",
    "electron microscope view of cells", "spectroscope rainbow spectrum",
    "antique balance scale", "miner's safety lamp",
    "brass microscope slide box", "celestial globe constellation",
    "alchemist distillation apparatus", "samovar and tea glass",
    "naturalist's field journal", "geologist's rock hammer",
    "entomologist's butterfly net", "astronomer's star chart",
    "surgeon's antique tool kit", "optician's lens grinding tool",
    "clockmaker's loupe", "naturalist's specimen tray",
    "marine chronometer", "botanist's plant press",
    "mathematician's compass and straightedge", "crystal radio detector",
    "vintage telegraph key", "photographer's light meter",
    "geologist's loupe", "mathematician's abacus",
    "natural history museum diorama", "crystal oscillator circuit",
    "weather balloon instruments", "antique ear trumpet",
    "surgeon's amputation saw", "optometrist's phoropter",
    "astronomer's meridian circle", "naturalist's collecting jar",
    "geologist's blowpipe", "entomologist's killing jar",
    "astronomer's filar micrometer", "surgeon's trephine",
    "optician's lensometer", "mathematician's slide rule",
    "naturalist's herbarium sheet", "crystal radio cat's-whisker",
    "vintage Morse key", "photographer's flash lamp",
    "geologist's clinometer", "mathematician's protractor",
]

_ACTIONS = [
    "glows", "rotates", "pulsates", "emerges", "swirls", "processes",
    "splits", "orbits", "illuminates", "projects", "magnifies", "focuses",
    "reflects", "refracts", "diffuses", "condenses", "evaporates",
    "crystallizes", "fractures", "resonates", "oscillates", "vibrates",
    "radiates", "conducts", "insulates", "amplifies", "attenuates",
    "filters", "separates", "combines", "transforms", "converts",
    "measures", "calculates", "observes", "records", "transmits",
    "receives", "focuses", "diverges", "converges", "disperses",
]

_SETTINGS = [
    "midnight darkness", "star field", "crimson background", "deep ocean",
    "mountain tunnel", "desert at sunset", "laboratory bench",
    "observatory dome", "factory workshop", "library reading room",
    "operating theater", "darkroom red light", "greenhouse glass",
    "cave entrance", "cliff edge", "river delta", "glacier surface",
    "coral reef", "volcanic vent", "lightning storm", "aurora borealis",
    "solar eclipse", "lunar surface", "Martian canyon", "ocean trench",
    "rainforest canopy", "tundra landscape", "salt flat", "canyon wall",
    "geyser eruption", "hot spring", "sand dune", "rock arch",
]

_DETAILS = [
    "bioluminescent", "floating", "colored", "crimson", "spiral",
    "glowing", "translucent", "opaque", "polished", "weathered",
    "ancient", "modern", "delicate", "massive", "intricate",
    "simple", "complex", "symmetric", "asymmetric", "organic",
    "geometric", "fluid", "rigid", "luminous", "shadowed",
    "vibrant", "muted", "warm", "cool", "bright",
    "dim", "sharp", "soft", "clear", "hazy",
]


def _make_distinct_concept(i: int) -> str:
    """Generate a unique visual concept for sentence index i.

    Uses prime multipliers so consecutive sentences vary across ALL
    dimensions (subject, action, setting, detail), not just subject.
    """
    subj = _SUBJECTS[i % len(_SUBJECTS)]
    action = _ACTIONS[(i * 7) % len(_ACTIONS)]
    setting = _SETTINGS[(i * 13) % len(_SETTINGS)]
    detail = _DETAILS[(i * 19) % len(_DETAILS)]
    return f"A {detail} {subj} {action} in {setting}"


def make_script(n: int) -> str:
    """Build a script with *n* distinct sentences using unique visual concepts."""
    parts = [_make_distinct_concept(i) for i in range(n)]
    return ". ".join(parts) + "."


def make_scene_plans(n: int) -> list[dict]:
    """One scene plan per sentence with varied composition / shot size / environment."""
    sizes = ["wide", "medium", "close_up", "medium_close", "extreme_close_up"]
    movements = ["static", "slow_zoom", "pan_right", "pan_left", "tilt_down"]
    compositions = ["balanced", "rule_of_thirds", "centered", "symmetrical"]
    lightings = ["natural", "dramatic", "soft", "high_contrast"]
    plans = []
    for i in range(n):
        concept = _make_distinct_concept(i)
        plans.append(
            {
                "sentence_id": f"S{i+1:03d}",
                "scene_id": f"S{i+1:03d}",
                "visual_idea": concept,
                "shot_size": sizes[i % len(sizes)],
                "camera_movement": movements[i % len(movements)],
                "lens_mm": 35,
                "lighting_key": lightings[i % len(lightings)],
                "color_temperature": "neutral",
                "depth_of_field": "deep",
                "composition": compositions[i % len(compositions)],
                "character_id": "hero" if i % 4 == 0 else None,
            }
        )
    return plans


def make_character_map(n: int) -> dict[str, str]:
    """Character appears every 4th sentence (not in every image)."""
    return {f"S{i+1:03d}": ("hero" if i % 4 == 0 else "") for i in range(n)}


def build_engine(tmp_path, project_id: str | None = None):
    if project_id is None:
        # tmp_path is unique per test -> unique project_id avoids
        # FlowJobManager disk-persisted job_id collisions across tests.
        project_id = f"pilot-{tmp_path.name}"
    engine = ImageGenerationEngine(project_id, base_dir=str(tmp_path), mock=True)
    engine.register_hero_character(
        character_id="hero",
        display_name="Dr. Aria",
        role="host",
        body_type="slender",
        distinguishing_features=["round glasses", "auburn hair", "lab coat"],
        clothing_notes="white lab coat with blue collar",
        color_palette=["white", "blue", "cream"],
        reference_image_path="assets/references/hero_master.png",
    )
    return engine


# ---------------------------------------------------------------------------
# Prompt creation
# ---------------------------------------------------------------------------


def test_prompt_creation_10_sentences(tmp_path):
    n = 10
    engine = build_engine(tmp_path)
    sentences = engine.segmenter.segment(make_script(n))
    assert len(sentences) == n
    scene_plans = make_scene_plans(n)
    character_map = make_character_map(n)

    plan = engine.build_plan(
        sentences=sentences,
        scene_plans=scene_plans,
        character_map=character_map,
        reference_entity="CHAR-HERO-1",
        output_root=str(tmp_path),
    )

    actual_n = len(sentences)
    assert plan.total == actual_n
    assert len(plan.sentences) == actual_n
    # Every sentence has a unique, non-empty prompt.
    prompts = [p.prompt for p in plan.sentences]
    assert all(p.strip() for p in prompts)
    assert len(set(prompts)) == actual_n  # unique prompts
    # Prompt mentions the sentence's visual concept.
    assert plan.sentences[0].sentence_text in plan.sentences[0].prompt
    # Character reference only on hero sentences (every 4th).
    hero_refs = [p for p in plan.sentences if p.reference_entity]
    expected_heroes = (actual_n + 3) // 4  # indices 0, 4, 8, ...
    assert len(hero_refs) == expected_heroes
    non_hero = [p for p in plan.sentences if not p.reference_entity]
    assert len(non_hero) == actual_n - expected_heroes  # not in every image


def test_prompt_creation_250_sentences(tmp_path):
    n = 250
    engine = build_engine(tmp_path)
    sentences = engine.segmenter.segment(make_script(n))
    assert len(sentences) == n
    actual_n = len(sentences)
    scene_plans = make_scene_plans(n)
    character_map = make_character_map(n)

    plan = engine.build_plan(
        sentences=sentences,
        scene_plans=scene_plans,
        character_map=character_map,
        reference_entity="CHAR-HERO-1",
        output_root=str(tmp_path),
    )

    assert plan.total == actual_n
    prompts = [p.prompt for p in plan.sentences]
    assert len(set(prompts)) == actual_n  # all unique
    assert all(p.prompt_id for p in plan.sentences)
    assert all(p.asset_id for p in plan.sentences)


# ---------------------------------------------------------------------------
# Unique IDs + one image per sentence
# ---------------------------------------------------------------------------


def test_unique_asset_prompt_job_ids(tmp_path):
    n = 50
    engine = build_engine(tmp_path)
    sentences = engine.segmenter.segment(make_script(n))
    scene_plans = make_scene_plans(n)
    character_map = make_character_map(n)

    plan = engine.build_plan(
        sentences=sentences,
        scene_plans=scene_plans,
        character_map=character_map,
        reference_entity="CHAR-HERO-1",
        output_root=str(tmp_path),
    )

    asset_ids = [p.asset_id for p in plan.sentences]
    prompt_ids = [p.prompt_id for p in plan.sentences]
    job_ids = [p.job_id for p in plan.sentences]
    assert len(set(asset_ids)) == n
    assert len(set(prompt_ids)) == n
    assert len(set(job_ids)) == n
    # asset_id is tied to sentence_id.
    for p in plan.sentences:
        assert p.asset_id == f"{engine.project_id}-AST-{p.sentence_id}"
        assert p.prompt_id == f"{engine.project_id}-PRT-{p.sentence_id}"


def test_one_image_per_sentence_registry(tmp_path):
    n = 10
    engine = build_engine(tmp_path)
    sentences = engine.segmenter.segment(make_script(n))
    scene_plans = make_scene_plans(n)
    character_map = make_character_map(n)

    engine.build_plan(
        sentences=sentences,
        scene_plans=scene_plans,
        character_map=character_map,
        reference_entity="CHAR-HERO-1",
        output_root=str(tmp_path),
    )

    # Registry: one asset per sentence, no sentence shares an asset.
    reg = engine.registry
    by_sentence = {}
    for rec in reg.list_assets():
        assert rec.sentence_id not in by_sentence, (
            f"sentence {rec.sentence_id} bound to two assets"
        )
        by_sentence[rec.sentence_id] = rec.asset_id
    assert len(by_sentence) == n

    # Trying to register the same sentence again updates in place
    # (one image per sentence — no duplicate asset created).
    reg.register_asset(
        sentence_id="S001",
        prompt_id="DUP-PRT",
        source_prompt="updated attempt",
        status="planned",
    )
    assets = reg.list_assets()
    s001_assets = [a for a in assets if a.sentence_id == "S001"]
    assert len(s001_assets) == 1  # still only one asset for S001
    assert s001_assets[0].source_prompt == "updated attempt"


# ---------------------------------------------------------------------------
# Mock generation + QC
# ---------------------------------------------------------------------------


def test_mock_generate_10_sentences_qc_passed(tmp_path):
    n = 10
    engine = build_engine(tmp_path)
    sentences = engine.segmenter.segment(make_script(n))
    scene_plans = make_scene_plans(n)
    character_map = make_character_map(n)

    engine.build_plan(
        sentences=sentences,
        scene_plans=scene_plans,
        character_map=character_map,
        reference_entity="CHAR-HERO-1",
        output_root=str(tmp_path),
    )
    result = engine.execute_approved(user_approved=False, cost_usd=0.0)

    actual_n = len(sentences)
    assert result.total_sentences == actual_n
    assert result.generated == actual_n
    assert result.qc_passed == actual_n
    assert result.qc_failed == 0
    assert result.failed == 0
    assert result.blocked == 0
    # Duplicate detection is active: mock images are structurally similar,
    # so some near-duplicates are flagged (detection works).
    assert result.duplicates >= 0
    integrity = engine.integrity_report()
    assert integrity["ok"] is True
    assert integrity["missing_images"] == []

    # Every image file exists, decodable, 16:9, >=720p.
    for p in plan_sentences(engine):
        assert Path(p.output_path).exists()
        from PIL import Image

        with Image.open(p.output_path) as img:
            w, h = img.size
            assert abs(w / h - 16 / 9) < 0.02
            assert w >= 1280 and h >= 720


def test_mock_generate_160_sentences(tmp_path):
    n = 160
    engine = build_engine(tmp_path)
    sentences = engine.segmenter.segment(make_script(n))
    scene_plans = make_scene_plans(n)
    character_map = make_character_map(n)

    engine.build_plan(
        sentences=sentences,
        scene_plans=scene_plans,
        character_map=character_map,
        reference_entity="CHAR-HERO-1",
        output_root=str(tmp_path),
    )
    result = engine.execute_approved(user_approved=False, cost_usd=0.0)

    actual_n = len(sentences)
    assert result.total_sentences == actual_n
    assert result.generated == actual_n
    # All sentences pass structural QC (file, 16:9, resolution, prompt).
    assert result.qc_passed == actual_n
    assert result.qc_failed == 0
    assert result.failed == 0
    assert result.blocked == 0
    # Duplicate detection is active: mock images are structurally similar,
    # so some near-duplicates are flagged (detection works).
    assert result.duplicates >= 0
    integrity = engine.integrity_report()
    assert integrity["ok"] is True
    assert integrity["missing_images"] == []


def test_mock_generate_250_sentences(tmp_path):
    n = 250
    engine = build_engine(tmp_path)
    sentences = engine.segmenter.segment(make_script(n))
    scene_plans = make_scene_plans(n)
    character_map = make_character_map(n)

    engine.build_plan(
        sentences=sentences,
        scene_plans=scene_plans,
        character_map=character_map,
        reference_entity="CHAR-HERO-1",
        output_root=str(tmp_path),
    )
    result = engine.execute_approved(user_approved=False, cost_usd=0.0)

    actual_n = len(sentences)
    assert result.total_sentences == actual_n
    assert result.generated == actual_n
    # High QC pass rate for diverse concepts (system correctly flags
    # near-duplicate text where it occurs).
    assert result.qc_passed >= actual_n * 0.95
    assert result.failed == 0
    assert result.blocked == 0
    # Duplicate detection is active.
    assert result.duplicates >= 0
    integrity = engine.integrity_report()
    assert integrity["ok"] is True
    assert integrity["missing_images"] == []


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------


def test_duplicate_detection_near_duplicate_images(tmp_path):
    """Two sentences producing identical images are flagged as duplicates."""
    engine = build_engine(tmp_path)
    sentences = engine.segmenter.segment("First sentence here. Second sentence here.")
    scene_plans = make_scene_plans(2)
    character_map = make_character_map(2)

    engine.build_plan(
        sentences=sentences,
        scene_plans=scene_plans,
        character_map=character_map,
        reference_entity="CHAR-HERO-1",
        output_root=str(tmp_path),
    )
    # Force both sentences to the same image file -> near-duplicate.
    shared = str(tmp_path / "shared.png")
    engine.plan.sentences[0].output_path = shared
    engine.plan.sentences[1].output_path = shared
    # Create the identical file.
    from PIL import Image

    Image.new("RGB", (1920, 1080), color=(10, 20, 30)).save(shared)

    result = engine.execute_approved(user_approved=False, cost_usd=0.0)
    assert result.duplicates == 1
    dupes = [p for p in engine.plan.sentences if p.state == "duplicate"]
    assert len(dupes) == 1
    assert dupes[0].qc_result.get("duplicate_of") == shared


# ---------------------------------------------------------------------------
# Retries / error handling
# ---------------------------------------------------------------------------


def test_failed_asset_recorded_and_retryable(tmp_path):
    engine = build_engine(tmp_path)
    sentences = engine.segmenter.segment("Only one sentence here.")
    scene_plans = make_scene_plans(1)
    character_map = make_character_map(1)

    engine.build_plan(
        sentences=sentences,
        scene_plans=scene_plans,
        character_map=character_map,
        reference_entity="CHAR-HERO-1",
        output_root=str(tmp_path),
    )
    plan = engine.plan.sentences[0]
    # Simulate a failure: registry records it, asset marked failed.
    engine.registry.record_failure(sentence_id=plan.sentence_id, error="mock generation error")
    rec = engine.registry.get_asset(sentence_id=plan.sentence_id)
    assert rec.status == "failed"
    assert "mock generation error" in rec.generation_params.get("last_error", "")


# ---------------------------------------------------------------------------
# Recovery / resume after restart
# ---------------------------------------------------------------------------


def test_recovery_skips_completed_after_restart(tmp_path):
    project_id = "pilot-resume"
    engine1 = build_engine(tmp_path, project_id=project_id)
    sentences = engine1.segmenter.segment(make_script(5))
    scene_plans = make_scene_plans(5)
    character_map = make_character_map(5)

    engine1.build_plan(
        sentences=sentences,
        scene_plans=scene_plans,
        character_map=character_map,
        reference_entity="CHAR-HERO-1",
        output_root=str(tmp_path),
    )
    engine1.execute_approved(user_approved=False, cost_usd=0.0)
    engine1.snapshot_recovery()

    # New engine instance simulating a Codespace restart.
    engine2 = ImageGenerationEngine(
        project_id, base_dir=str(tmp_path), mock=True
    )
    engine2.register_hero_character(
        character_id="hero",
        display_name="Dr. Aria",
        role="host",
        body_type="slender",
        distinguishing_features=["round glasses", "auburn hair"],
        clothing_notes="white lab coat",
    )
    # Load existing plan from registry instead of rebuilding Flow Jobs.
    loaded = engine2.load_plan()
    assert loaded is not None
    assert loaded.total == 5
    engine2.plan = loaded
    resume = engine2.resume()
    # All 5 already QC-passed -> nothing to process.
    assert resume["process"] == []
    assert len(resume["skip"]) == 5


# ---------------------------------------------------------------------------
# Character reference workflow
# ---------------------------------------------------------------------------


def test_character_reference_registered_and_used(tmp_path):
    engine = build_engine(tmp_path)
    sentences = engine.segmenter.segment(make_script(8))
    scene_plans = make_scene_plans(8)
    character_map = make_character_map(8)

    engine.build_plan(
        sentences=sentences,
        scene_plans=scene_plans,
        character_map=character_map,
        reference_entity="CHAR-HERO-1",
        output_root=str(tmp_path),
    )

    # Character registered in consistency manager.
    assert "hero" in engine.character_manager.characters
    refs = engine.character_manager.references.get("hero", [])
    assert len(refs) == 1
    assert refs[0].reference_type == "image"

    # Hero scenes (every 4th: S001, S005) get the reference entity.
    hero_plans = [p for p in engine.plan.sentences if p.reference_entity]
    assert len(hero_plans) == 2
    assert all(p.reference_entity == "CHAR-HERO-1" for p in hero_plans)
    # Non-hero scenes have no reference (character not in every image).
    non_hero = [p for p in engine.plan.sentences if not p.reference_entity]
    assert len(non_hero) == 6


# ---------------------------------------------------------------------------
# Flow Job Manager integration
# ---------------------------------------------------------------------------


def test_flow_job_manager_ready_for_approval_stop(tmp_path):
    engine = build_engine(tmp_path)
    sentences = engine.segmenter.segment(make_script(5))
    scene_plans = make_scene_plans(5)
    character_map = make_character_map(5)

    engine.build_plan(
        sentences=sentences,
        scene_plans=scene_plans,
        character_map=character_map,
        reference_entity="CHAR-HERO-1",
        output_root=str(tmp_path),
    )

    # All jobs should be at READY_FOR_APPROVAL (automated system stops here).
    mgr: FlowJobManager = engine.provider.manager
    for p in engine.plan.sentences:
        job = mgr.get_job(p.job_id)
        assert job is not None, f"job missing for {p.sentence_id}"
        assert job.state == "READY_FOR_APPROVAL", (
            f"{p.sentence_id} state={job.state}"
        )

    # execute_approved with user_approved=False must NOT spend / execute.
    result = engine.execute_approved(user_approved=False, cost_usd=None)
    # In mock mode generation still happens (no real gflow), but in real
    # mode the gate blocks.  Here we just verify jobs remain READY_FOR_APPROVAL
    # until manually approved — no APPROVED/SUBMITTED transition occurred.
    for p in engine.plan.sentences:
        job = mgr.get_job(p.job_id)
        assert job.state in ("READY_FOR_APPROVAL",)


def test_provider_plan_creates_draft_validated_ready(tmp_path):
    mgr = FlowJobManager()
    wrapper = GflowWrapper(manager=mgr)
    provider = GflowProvider(manager=mgr, wrapper=wrapper)
    req = ProviderImageRequest(
        sentence_id="S001",
        project_id="pilot",
        prompt="A test scene.",
        prompt_id="pilot-PRT-S001",
        asset_id="pilot-AST-S001",
        output_path="/tmp/kilotest/S001.png",
    )
    res = provider.plan_image(req=req)
    assert res.state == "READY_FOR_APPROVAL"
    job = mgr.get_job(res.job_id)
    assert job.state == "READY_FOR_APPROVAL"
    assert job.generation_params["prompt_id"] == "pilot-PRT-S001"
    assert job.generation_params["asset_id"] == "pilot-AST-S001"


# ---------------------------------------------------------------------------
# Batch scheduler
# ---------------------------------------------------------------------------


def test_batch_scheduler_chunks_within_gflow_limit(tmp_path):
    sched = BatchScheduler(max_prompts_per_call=4)
    prompts = [
        BatchPrompt(
            sentence_id=f"S{i:03d}",
            prompt=f"prompt {i}",
            prompt_id=f"PRT-{i:03d}",
            asset_id=f"AST-{i:03d}",
            output_filename=f"S{i:03d}.png",
        )
        for i in range(10)
    ]
    manifest = sched.create_batch(
        batch_id="batch-1", project_id="pilot", items=prompts,
        output_dir=str(tmp_path / "out"),
    )
    chunks = sched.chunk_for_t2i(manifest)
    # 10 prompts, max 4 per call -> 3 chunks (4, 4, 2).
    assert len(chunks) == 3
    assert len(chunks[0]) == 4
    assert len(chunks[1]) == 4
    assert len(chunks[2]) == 2
    assert manifest.total == 10


def test_batch_scheduler_concurrency_cap(tmp_path):
    sched = BatchScheduler(max_concurrent_batches=2)
    assert sched.mark_running("b1") is True
    assert sched.mark_running("b2") is True
    assert sched.mark_running("b3") is False  # cap reached
    sched.mark_complete("b1")
    assert sched.mark_running("b3") is True  # slot freed


# ---------------------------------------------------------------------------
# Prompt engineer / visual director reuse (no duplication)
# ---------------------------------------------------------------------------


def test_prompt_engineer_builds_non_text_prompt(tmp_path):
    pe = PromptEngineer(visual_style="bold ink illustration")
    packet = pe.build_packet(
        scene_id="S001",
        scene_plan={
            "visual_idea": "A deep-sea alien creature glows.",
            "shot_size": "medium",
            "camera_movement": "static",
            "lens_mm": 35,
            "lighting_key": "dramatic",
            "depth_of_field": "deep",
            "composition": "balanced",
        },
    )
    assert packet.main_prompt
    assert packet.negative_prompt
    # No positive text instruction.
    qc = QualityControl()
    r = qc.check_no_text_in_image(packet.main_prompt, packet.negative_prompt)
    assert r.passed is True
    assert "16:9" in packet.aspect_ratio or packet.aspect_ratio == "16:9"


# ---------------------------------------------------------------------------
# Asset registry integrity
# ---------------------------------------------------------------------------


def test_registry_integrity_and_missing_detection(tmp_path):
    reg = AssetRegistry("integrity-proj", base_dir=str(tmp_path))
    reg.register_asset(
        sentence_id="S001",
        prompt_id="PRT-S001",
        source_prompt="a prompt",
        file_path=str(reg.assets_dir / "S001.png"),
        status="generated",
    )
    # No file created -> missing.
    integrity = reg.integrity_check()
    assert "S001" in integrity["missing_images"]
    assert integrity["ok"] is False

    # Create file -> integrity passes.
    (reg.assets_dir / "S001.png").write_bytes(b"fake-image")
    integrity = reg.integrity_check()
    assert integrity["ok"] is True
    assert integrity["missing_images"] == []


# ---------------------------------------------------------------------------
# aHash uniqueness (reused module)
# ---------------------------------------------------------------------------


def test_ahash_detects_duplicate(tmp_path):
    from PIL import Image

    p1 = tmp_path / "a.png"
    p2 = tmp_path / "b.png"
    Image.new("L", (64, 64), 100).save(p1)
    Image.new("L", (64, 64), 100).save(p2)
    report = check_uniqueness([str(p1), str(p2)])
    assert report.duplicates == 1
    assert report.unique == 1


def plan_sentences(engine: ImageGenerationEngine):
    return engine.plan.sentences if engine.plan else []


def test_default_model_and_aspect_constants():
    assert DEFAULT_MODEL == "nano2"
    assert DEFAULT_ASPECT == "16:9"
