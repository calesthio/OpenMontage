import json
from pathlib import Path

from tools.audio.tts_segment_lab import TTSSegmentLab
from tools.base_tool import ToolResult


def write_script(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "sections": [
                    {"id": "s1", "text": "Opening line for audition."},
                    {"id": "s2", "text": "Second line for another voice."},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def base_manifest(tmp_path: Path) -> dict:
    script_path = tmp_path / "script.json"
    write_script(script_path)
    reference_audio = tmp_path / "reference.mp3"
    reference_audio.write_bytes(b"reference audio")
    return {
        "project": "unit-test",
        "run_id": "unit-run",
        "script_path": str(script_path),
        "output_dir": str(tmp_path / "tts-lab"),
        "defaults": {"preferred_provider": "auto", "voice": "alloy"},
        "segments": [
            {
                "id": "opening",
                "section_id": "s1",
                "label": "Opening",
                "reference": {
                    "id": "reference-current",
                    "audio": str(reference_audio),
                    "duration_seconds": 1.0,
                    "note": "Current approved audio.",
                },
                "variants": [
                    {
                        "id": "auto",
                        "note": "Auto route",
                        "overrides": {"speed": 1.0},
                    },
                    {
                        "id": "doubao",
                        "provider": "doubao",
                        "note": "Provider-specific route",
                        "provider_options": {"voice_id": "zh_female_vv_uranus_bigtts"},
                        "overrides": {"speech_rate": 8},
                    },
                ],
            }
        ],
    }


def test_dry_run_extracts_script_section_and_writes_review(tmp_path):
    tool = TTSSegmentLab()
    manifest = base_manifest(tmp_path)

    result = tool.execute({"operation": "dry_run", "manifest": manifest})

    assert result.success
    assert result.data["status"] == "completed"
    results_path = Path(result.data["results_path"])
    review_path = Path(result.data["review_path"])
    assert results_path.exists()
    assert review_path.exists()

    payload = json.loads(results_path.read_text(encoding="utf-8"))
    assert payload["segments"][0]["text"] == "Opening line for audition."
    assert payload["segments"][0]["variants"][0]["id"] == "reference-current"
    assert payload["segments"][0]["variants"][0]["source_type"] == "reference"
    assert payload["segments"][0]["variants"][1]["planned"] is True
    assert "Opening line for audition." in review_path.read_text(encoding="utf-8")
    assert "reference-current" in review_path.read_text(encoding="utf-8")


def test_generate_routes_variants_through_tts_selector(monkeypatch, tmp_path):
    calls = []

    def fake_execute(self, inputs):
        calls.append(inputs.copy())
        output_path = Path(inputs["output_path"])
        output_path.write_bytes(b"fake mp3")
        return ToolResult(
            success=True,
            data={
                "selected_provider": inputs.get("preferred_provider", "auto"),
                "selected_tool": f"{inputs.get('preferred_provider', 'auto')}_tts",
                "audio_duration_seconds": 1.23,
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
        )

    monkeypatch.setattr("tools.audio.tts_selector.TTSSelector.execute", fake_execute)
    monkeypatch.setattr("tools.audio.tts_selector.TTSSelector.estimate_cost", lambda self, inputs: 0.01)

    tool = TTSSegmentLab()
    result = tool.execute({"operation": "generate", "manifest": base_manifest(tmp_path)})

    assert result.success
    assert len(calls) == 2
    assert calls[0]["text"] == "Opening line for audition."
    assert calls[0]["preferred_provider"] == "auto"
    assert calls[1]["preferred_provider"] == "doubao"
    assert calls[1]["voice_id"] == "zh_female_vv_uranus_bigtts"
    assert calls[1]["speech_rate"] == 8
    assert Path(result.data["results_path"]).exists()


def test_select_writes_selection_manifest(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "tools.audio.tts_selector.TTSSelector.execute",
        lambda self, inputs: ToolResult(
            success=True,
            data={
                "selected_provider": inputs.get("preferred_provider", "auto"),
                "selected_tool": "fake_tts",
                "audio_duration_seconds": 2.0,
            },
            artifacts=[inputs["output_path"]],
        ),
    )
    monkeypatch.setattr("tools.audio.tts_selector.TTSSelector.estimate_cost", lambda self, inputs: 0.0)

    tool = TTSSegmentLab()
    generate_result = tool.execute({"operation": "generate", "manifest": base_manifest(tmp_path)})
    assert generate_result.success

    select_result = tool.execute(
        {
            "operation": "select",
            "manifest": base_manifest(tmp_path),
            "selections": {"opening": "doubao"},
        }
    )

    assert select_result.success
    selection_path = Path(select_result.data["selection_path"])
    payload = json.loads(selection_path.read_text(encoding="utf-8"))
    assert payload["selections"][0]["segment_id"] == "opening"
    assert payload["selections"][0]["variant_id"] == "doubao"
    assert payload["selections"][0]["selected_provider"] == "doubao"


def test_select_can_choose_reference_variant(tmp_path):
    tool = TTSSegmentLab()
    dry_result = tool.execute({"operation": "dry_run", "manifest": base_manifest(tmp_path)})
    assert dry_result.success

    select_result = tool.execute(
        {
            "operation": "select",
            "manifest": base_manifest(tmp_path),
            "selections": {"opening": "reference-current"},
        }
    )

    assert select_result.success
    payload = json.loads(Path(select_result.data["selection_path"]).read_text(encoding="utf-8"))
    assert payload["selections"][0]["variant_id"] == "reference-current"
    assert payload["selections"][0]["selected_provider"] == "reference"
    assert payload["selections"][0]["selected_tool"] == "reference_audio"


def test_analyze_writes_audio_profile_and_review_queue(monkeypatch, tmp_path):
    def fake_tts_execute(self, inputs):
        output_path = Path(inputs["output_path"])
        output_path.write_bytes(b"fake mp3")
        return ToolResult(
            success=True,
            data={
                "selected_provider": inputs.get("preferred_provider", "auto"),
                "selected_tool": "fake_tts",
                "audio_duration_seconds": 1.0,
            },
            artifacts=[str(output_path)],
        )

    monkeypatch.setattr("tools.audio.tts_selector.TTSSelector.execute", fake_tts_execute)
    monkeypatch.setattr("tools.audio.tts_selector.TTSSelector.estimate_cost", lambda self, inputs: 0.0)
    monkeypatch.setattr(
        "tools.analysis.audio_probe.AudioProbe.execute",
        lambda self, inputs: ToolResult(success=True, data={"duration_seconds": 1.0, "audio": {"sample_rate": 44100}}),
    )
    monkeypatch.setattr(
        "tools.analysis.audio_energy.AudioEnergy.execute",
        lambda self, inputs: ToolResult(
            success=True,
            data={
                "analysis": {"quiet_intro_seconds": 0, "active_seconds": 1},
                "energy_profile": [{"time_seconds": 0, "loudness_lufs": -24, "active": True}],
            },
        ),
    )

    tool = TTSSegmentLab()
    generate_result = tool.execute({"operation": "generate", "manifest": base_manifest(tmp_path)})
    assert generate_result.success

    analyze_result = tool.execute({"operation": "analyze", "results_path": generate_result.data["results_path"]})

    assert analyze_result.success
    profile_path = Path(analyze_result.data["audio_profile_path"])
    analysis_path = Path(analyze_result.data["analysis_path"])
    assert profile_path.exists()
    assert analysis_path.exists()
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    assert profile["summary"]["variants"] == 3
    assert profile["segments"][0]["variants"][1]["probe"]["status"] == "ok"
    assert "These checks are heuristics" in analysis_path.read_text(encoding="utf-8")


def test_analyze_flags_missing_audio(tmp_path):
    tool = TTSSegmentLab()
    dry_result = tool.execute({"operation": "dry_run", "manifest": base_manifest(tmp_path)})
    assert dry_result.success

    analyze_result = tool.execute({"operation": "analyze", "results_path": dry_result.data["results_path"]})

    assert analyze_result.success
    profile = json.loads(Path(analyze_result.data["audio_profile_path"]).read_text(encoding="utf-8"))
    missing_variant = profile["segments"][0]["variants"][1]
    assert missing_variant["suggested_review"] is True
    assert missing_variant["findings"][0]["kind"] == "audio_missing"


def test_annotate_writes_review_notes_and_review_queue(tmp_path):
    tool = TTSSegmentLab()
    dry_result = tool.execute({"operation": "dry_run", "manifest": base_manifest(tmp_path)})
    assert dry_result.success

    annotate_result = tool.execute(
        {
            "operation": "annotate",
            "results_path": dry_result.data["results_path"],
            "annotations": {
                "opening": {
                    "reference-current": {
                        "decision": "KEEP_REFERENCE",
                        "notes": "Still the safest approved take.",
                    },
                    "doubao": {
                        "decision": "NEEDS_REVIEW",
                        "issue_category": "tone",
                        "fix_target": "Try a steadier delivery.",
                        "notes": "Promising, but needs human listening.",
                    },
                }
            },
        }
    )

    assert annotate_result.success
    review_notes = json.loads(Path(annotate_result.data["review_notes_path"]).read_text(encoding="utf-8"))
    assert review_notes["summary"]["decisions"]["KEEP_REFERENCE"] == 1
    assert review_notes["summary"]["decisions"]["NEEDS_REVIEW"] == 1
    assert review_notes["summary"]["review_queue"][0]["variant_id"] == "doubao"

    annotated_review = Path(annotate_result.data["review_path"]).read_text(encoding="utf-8")
    assert "## Needs Human Review" in annotated_review
    assert "`KEEP_REFERENCE`" in annotated_review
    assert "Promising, but needs human listening." in annotated_review


def test_annotate_rejects_unknown_variant(tmp_path):
    tool = TTSSegmentLab()
    dry_result = tool.execute({"operation": "dry_run", "manifest": base_manifest(tmp_path)})
    assert dry_result.success

    annotate_result = tool.execute(
        {
            "operation": "annotate",
            "results_path": dry_result.data["results_path"],
            "annotations": {"opening": {"missing": {"decision": "REJECTED"}}},
        }
    )

    assert not annotate_result.success
    assert "Unknown variant" in annotate_result.error
