import json
from pathlib import Path

from tools.analysis.pre_render_narration_sync_gate import PreRenderNarrationSyncGate


def base_manifest(tmp_path: Path) -> dict:
    return {
        "project": "unit-test",
        "run_id": "sync-run",
        "output_dir": str(tmp_path / "pre-render-sync"),
        "tolerance_seconds": 0.4,
        "narration_segments": [
            {
                "id": "s1",
                "section_id": "s1",
                "text": "Use TraceID to follow the request across systems.",
                "start_seconds": 1.0,
                "end_seconds": 4.0,
            },
            {
                "id": "s2",
                "section_id": "s2",
                "text": "When code context is available, JoyCode shows the exact log keys.",
                "start_seconds": 4.0,
                "end_seconds": 8.0,
            },
        ],
        "captions": [
            {
                "section_id": "s1",
                "text": "Use TraceID to follow the request across systems.",
                "start_seconds": 1.0,
                "end_seconds": 4.0,
            }
        ],
        "screen_texts": [
            {
                "section_id": "s2",
                "text": "JoyCode exact log keys",
                "start_seconds": 4.4,
            }
        ],
        "visual_cues": [
            {
                "id": "joycode",
                "section_id": "s2",
                "timestamp_seconds": 4.1,
                "narration_anchor": "code context",
                "expected_state": "JoyCode screenshot is visible.",
            }
        ],
        "term_rules": [
            {
                "required": "TraceID",
                "forbidden": ["TID"],
            }
        ],
    }


def test_gate_passes_clean_pre_render_sync_manifest(tmp_path):
    result = PreRenderNarrationSyncGate().execute({"operation": "review", "manifest": base_manifest(tmp_path)})

    assert result.success
    assert result.data["status"] == "passed"
    assert result.data["recommended_next_action"] == "ready_to_render"
    assert result.data["finding_count"] == 0
    assert Path(result.data["results_path"]).exists()
    assert Path(result.data["review_path"]).exists()
    html = Path(result.data["review_html_path"]).read_text(encoding="utf-8")
    assert "Pre-render Narration Sync Gate" in html
    assert "No sync issues found." in html


def test_gate_flags_caption_term_and_visual_timing_drift(tmp_path):
    manifest = base_manifest(tmp_path)
    manifest["captions"][0]["text"] = "Use TID to follow the request across systems."
    manifest["visual_cues"][0]["timestamp_seconds"] = 5.2

    result = PreRenderNarrationSyncGate().execute({"operation": "review", "manifest": manifest})

    assert not result.success
    assert result.data["status"] == "needs-revision"
    assert result.data["recommended_next_action"] == "revise_before_render"
    kinds = {finding["kind"] for finding in result.data["findings"]}
    assert "caption_text_mismatch" in kinds
    assert "forbidden_term" in kinds
    assert "visual_cue_timing_mismatch" in kinds
    review = Path(result.data["review_path"]).read_text(encoding="utf-8")
    assert "Do not ask the user yet" in review
    assert "TraceID" in review


def test_gate_warns_when_visual_cue_needs_agent_review(tmp_path):
    manifest = base_manifest(tmp_path)
    manifest["visual_cues"][0].pop("expected_state")

    result = PreRenderNarrationSyncGate().execute({"operation": "review", "manifest": manifest})

    assert result.success
    assert result.data["status"] == "needs-agent-review"
    assert result.data["recommended_next_action"] == "agent_review_required"
    assert result.data["findings"][0]["kind"] == "visual_cue_missing_expected_state"


def test_gate_loads_narration_and_captions_from_paths(tmp_path):
    narration_path = tmp_path / "selection.json"
    narration_path.write_text(
        json.dumps(
            {
                "selections": [
                    {
                        "segment_id": "s1",
                        "section_id": "s1",
                        "text": "The final narration is locked.",
                        "start_seconds": 0.0,
                        "end_seconds": 2.0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    captions_path = tmp_path / "captions.json"
    captions_path.write_text(
        json.dumps(
            [
                {
                    "section_id": "s1",
                    "text": "The final narration is locked.",
                    "start_seconds": 0.0,
                    "end_seconds": 2.0,
                }
            ]
        ),
        encoding="utf-8",
    )
    manifest = {
        "project": "unit-test",
        "run_id": "path-run",
        "output_dir": str(tmp_path / "pre-render-sync-paths"),
        "tts_selection_path": str(narration_path),
        "captions_path": str(captions_path),
    }

    result = PreRenderNarrationSyncGate().execute({"operation": "review", "manifest": manifest})

    assert result.success
    payload = json.loads(Path(result.data["results_path"]).read_text(encoding="utf-8"))
    assert payload["summary"]["narration_segments"] == 1
    assert payload["summary"]["captions"] == 1
