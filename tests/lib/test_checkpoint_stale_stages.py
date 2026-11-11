"""``get_stale_stages`` reports completed stages built from a superseded upstream.

``get_next_stage`` only looks at completion. Re-running an upstream stage left
every downstream checkpoint reading ``completed``, so a resumed run reported
"nothing left to do" on top of artifacts derived from the old upstream.
"""

from tests.contracts.test_phase0_contracts import sample_artifact

from lib.checkpoint import (
    get_next_stage,
    get_stale_stages,
    init_project,
    write_checkpoint,
)

PIPELINE = "framework-smoke"


def script(title="Smoke"):
    return {
        "version": "1.0",
        "title": title,
        "total_duration_seconds": 1,
        "sections": [
            {"id": "s1", "text": "One second.", "start_seconds": 0, "end_seconds": 1}
        ],
    }


def research(topic="Test Topic"):
    brief = sample_artifact("research_brief")
    brief["topic"] = topic
    return brief


def complete(tmp_path, stage, artifacts, **kwargs):
    return write_checkpoint(
        tmp_path, "run", stage, "completed", artifacts,
        pipeline_type=PIPELINE, human_approved=True, **kwargs,
    )


def finished_run(tmp_path):
    init_project("run", title="Run", pipeline_type=PIPELINE, pipeline_dir=tmp_path)
    complete(tmp_path, "research", {"research_brief": research()})
    complete(tmp_path, "script", {"script": script()})


def test_a_run_completed_in_order_has_no_stale_stages(tmp_path):
    finished_run(tmp_path)

    assert get_stale_stages(tmp_path, "run", PIPELINE) == []


def test_changed_upstream_marks_the_downstream_stage_stale(tmp_path):
    finished_run(tmp_path)
    complete(tmp_path, "research", {"research_brief": research("A different topic")})

    # Completion alone still says the run is finished ...
    assert get_next_stage(tmp_path, "run", PIPELINE) is None
    # ... which is exactly why the stale report exists.
    assert get_stale_stages(tmp_path, "run", PIPELINE) == [
        {"stage": "script", "superseded_by": "research"}
    ]


def test_rerunning_the_downstream_stage_clears_it(tmp_path):
    finished_run(tmp_path)
    complete(tmp_path, "research", {"research_brief": research("A different topic")})
    complete(tmp_path, "script", {"script": script("Rewritten")})

    assert get_stale_stages(tmp_path, "run", PIPELINE) == []


def test_metadata_only_rewrite_of_upstream_is_not_a_change(tmp_path):
    finished_run(tmp_path)
    complete(
        tmp_path, "research", {"research_brief": research()},
        metadata={"note": "review attached after the fact"},
    )

    assert get_stale_stages(tmp_path, "run", PIPELINE) == []


def test_unreadable_checkpoint_does_not_raise(tmp_path):
    finished_run(tmp_path)
    (tmp_path / "run" / "checkpoint_script.json").write_text("{not json", encoding="utf-8")

    assert get_stale_stages(tmp_path, "run", PIPELINE) == []
