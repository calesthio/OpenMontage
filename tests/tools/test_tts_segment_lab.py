import json
import os
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
    compare_path = Path(result.data["compare_path"])
    assert results_path.exists()
    assert review_path.exists()
    assert compare_path.exists()

    payload = json.loads(results_path.read_text(encoding="utf-8"))
    assert payload["segments"][0]["text"] == "Opening line for audition."
    assert payload["segments"][0]["variants"][0]["id"] == "reference-current"
    assert payload["segments"][0]["variants"][0]["source_type"] == "reference"
    assert payload["segments"][0]["variants"][1]["planned"] is True
    assert "Opening line for audition." in review_path.read_text(encoding="utf-8")
    assert "reference-current" in review_path.read_text(encoding="utf-8")
    compare_html = compare_path.read_text(encoding="utf-8")
    assert "TTS Voice Comparison" in compare_html
    assert "Opening line for audition." in compare_html
    assert "reference-current" in compare_html
    assert "Audio has not been generated yet" in compare_html
    assert "data-save-review" in compare_html
    assert "data-selection-field" in compare_html
    assert "data-selection-note" in compare_html
    assert "data-regenerate-all-field" in compare_html
    assert "selection_policy: 'one_variant_per_segment'" in compare_html
    assert "Review: Unreviewed" in compare_html
    assert "Selected: 0/1" in compare_html
    assert "Status: completed" not in compare_html
    assert "Use this take" in compare_html
    assert "None of these; generate a new take" in compare_html
    assert "Keep reference" not in compare_html
    assert "Reject" not in compare_html


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
    compare_path = Path(result.data["compare_path"])
    assert compare_path.exists()
    compare_html = compare_path.read_text(encoding="utf-8")
    assert "doubao" in compare_html
    assert "opening__doubao.mp3" in compare_html


def test_compare_page_uses_chinese_ui_for_chinese_script(tmp_path):
    script_path = tmp_path / "script.json"
    script_path.write_text(
        json.dumps({"sections": [{"id": "s1", "text": "生产问题出现时，先从日志里找到线索。"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    manifest = {
        "project": "unit-test",
        "run_id": "zh-run",
        "script_path": str(script_path),
        "output_dir": str(tmp_path / "tts-lab-zh"),
        "segments": [
            {
                "id": "opening",
                "section_id": "s1",
                "variants": [{"id": "auto"}],
            }
        ],
    }

    result = TTSSegmentLab().execute({"operation": "dry_run", "manifest": manifest})

    assert result.success
    compare_html = Path(result.data["compare_path"]).read_text(encoding="utf-8")
    assert '<html lang="zh">' in compare_html
    assert "TTS 音色对比" in compare_html
    assert "尚未生成音频" in compare_html
    assert "评审状态: 待评审" in compare_html


def test_dry_run_compare_page_does_not_link_stale_generated_audio(tmp_path):
    manifest = base_manifest(tmp_path)
    output_dir = Path(manifest["output_dir"])
    output_dir.mkdir(parents=True)
    stale_audio = output_dir / "opening__auto.mp3"
    stale_audio.write_bytes(b"stale generated audio from an earlier run")

    result = TTSSegmentLab().execute({"operation": "dry_run", "manifest": manifest})

    assert result.success
    compare_html = Path(result.data["compare_path"]).read_text(encoding="utf-8")
    assert "opening__auto.mp3" not in compare_html
    assert "Audio has not been generated yet" in compare_html


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


def test_annotate_accepts_review_payload_and_defers_selection_until_complete(tmp_path):
    tool = TTSSegmentLab()
    dry_result = tool.execute({"operation": "dry_run", "manifest": base_manifest(tmp_path)})
    assert dry_result.success
    payload_path = tmp_path / "tts-review.json"
    payload_path.write_text(
        json.dumps(
            {
                "selections": {"opening": "reference-current"},
                "annotations": {
                    "opening": {
                        "reference-current": {"decision": "KEEP_REFERENCE", "notes": "Best current take."},
                        "doubao": {
                            "decision": "REGENERATE",
                            "issue_category": "tone",
                            "fix_target": "Try a less dramatic delivery.",
                            "notes": "Too dramatic for the line.",
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    annotate_result = tool.execute(
        {
            "operation": "annotate",
            "results_path": dry_result.data["results_path"],
            "annotations_path": str(payload_path),
        }
    )

    assert annotate_result.success
    assert annotate_result.data["review_complete"] is False
    assert annotate_result.data["next_operation"] == "apply_review"
    assert annotate_result.data["selection_count"] == 0
    assert annotate_result.data["selection_path"] is None
    assert annotate_result.data["action_item_count"] == 1
    assert annotate_result.data["action_items"][0]["variant_id"] == "doubao"
    review_notes = json.loads(Path(annotate_result.data["review_notes_path"]).read_text(encoding="utf-8"))
    assert review_notes["action_items"][0]["decision"] == "REGENERATE"
    assert review_notes["completion"]["selection_deferred_reason"] == "pending_review_actions"
    compare_html = Path(annotate_result.data["compare_path"]).read_text(encoding="utf-8")
    assert 'data-selection-field value="reference-current" checked' in compare_html
    assert "Best current take." in compare_html


def test_annotate_writes_final_selection_only_when_all_segments_approved(tmp_path):
    tool = TTSSegmentLab()
    dry_result = tool.execute({"operation": "dry_run", "manifest": base_manifest(tmp_path)})
    assert dry_result.success

    annotate_result = tool.execute(
        {
            "operation": "annotate",
            "results_path": dry_result.data["results_path"],
            "annotations": {"opening": {"reference-current": {"decision": "KEEP_REFERENCE"}}},
            "selections": {"opening": "reference-current"},
        }
    )

    assert annotate_result.success
    assert annotate_result.data["review_complete"] is True
    assert annotate_result.data["next_operation"] == "complete"
    assert annotate_result.data["selection_count"] == 1
    selection = json.loads(Path(annotate_result.data["selection_path"]).read_text(encoding="utf-8"))
    assert selection["selections"][0]["variant_id"] == "reference-current"


def test_annotate_accepts_segment_regenerate_actions(tmp_path):
    tool = TTSSegmentLab()
    manifest = base_manifest(tmp_path)
    manifest["segments"].append(
        {
            "id": "second",
            "section_id": "s2",
            "label": "Second",
            "variants": [{"id": "auto", "note": "Auto route"}],
        }
    )
    dry_result = tool.execute({"operation": "dry_run", "manifest": manifest})
    assert dry_result.success
    payload_path = tmp_path / "tts-review.json"
    payload_path.write_text(
        json.dumps(
            {
                "selections": {"opening": "reference-current"},
                "annotations": {
                    "opening": {
                        "reference-current": {
                            "decision": "REGENERATE",
                            "notes": "This is close; make the opening less dramatic.",
                            "fix_target": "Reduce the dramatic emphasis.",
                        }
                    }
                },
                "segment_actions": {
                    "second": {
                        "decision": "REGENERATE",
                        "notes": "None of the takes fit; try a steadier voice.",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    annotate_result = tool.execute(
        {
            "operation": "annotate",
            "results_path": dry_result.data["results_path"],
            "annotations_path": str(payload_path),
        }
    )

    assert annotate_result.success
    assert annotate_result.data["review_complete"] is False
    assert annotate_result.data["next_operation"] == "apply_review"
    assert annotate_result.data["selection_count"] == 0
    assert annotate_result.data["selection_path"] is None
    assert annotate_result.data["action_item_count"] == 2
    action_items = annotate_result.data["action_items"]
    assert action_items[0]["variant_id"] == "reference-current"
    assert action_items[1]["variant_id"] is None
    assert action_items[1]["notes"] == "None of the takes fit; try a steadier voice."
    review_notes = json.loads(Path(annotate_result.data["review_notes_path"]).read_text(encoding="utf-8"))
    assert review_notes["segment_actions"][0]["segment_id"] == "second"
    compare_html = Path(annotate_result.data["compare_path"]).read_text(encoding="utf-8")
    assert "This is close; make the opening less dramatic." in compare_html


def test_apply_review_generates_follow_up_audition_round(monkeypatch, tmp_path):
    calls = []

    def fake_execute(self, inputs):
        calls.append(inputs.copy())
        output_path = Path(inputs["output_path"])
        output_path.write_bytes(b"fake reviewed mp3")
        return ToolResult(
            success=True,
            data={
                "selected_provider": inputs.get("preferred_provider", "auto"),
                "selected_tool": "fake_tts",
                "audio_duration_seconds": 1.5,
            },
            artifacts=[str(output_path)],
        )

    monkeypatch.setattr("tools.audio.tts_selector.TTSSelector.execute", fake_execute)
    monkeypatch.setattr("tools.audio.tts_selector.TTSSelector.estimate_cost", lambda self, inputs: 0.0)

    manifest = base_manifest(tmp_path)
    manifest["segments"].append(
        {
            "id": "second",
            "section_id": "s2",
            "label": "Second",
            "variants": [
                {
                    "id": "fast",
                    "provider": "doubao",
                    "provider_options": {"voice_id": "zh_male_liufei_uranus_bigtts"},
                    "overrides": {"speech_rate": 7},
                }
            ],
        }
    )
    generate_result = TTSSegmentLab().execute({"operation": "generate", "manifest": manifest})
    assert generate_result.success
    calls.clear()
    payload_path = tmp_path / "review-submit.json"
    payload_path.write_text(
        json.dumps(
            {
                "selections": {"opening": "doubao"},
                "annotations": {
                    "opening": {
                        "doubao": {
                            "decision": "REGENERATE",
                            "notes": "语速再稍微快一点",
                            "fix_target": "语速再稍微快一点",
                        }
                    }
                },
                "segment_actions": {
                    "second": {
                        "decision": "REGENERATE",
                        "notes": "都不行，换一个声音重新生成",
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    apply_result = TTSSegmentLab().execute(
        {
            "operation": "apply_review",
            "results_path": generate_result.data["results_path"],
            "annotations_path": str(payload_path),
            "output_dir": str(tmp_path / "review-round"),
        }
    )

    assert apply_result.success
    assert apply_result.data["regenerated_count"] == 2
    assert len(calls) == 2
    assert calls[0]["speech_rate"] == 9
    assert calls[1]["voice_id"] != "zh_male_liufei_uranus_bigtts"
    round_results = json.loads(Path(apply_result.data["results_path"]).read_text(encoding="utf-8"))
    assert round_results["selections"]["opening"] == "doubao-review-adjusted"
    assert round_results["selections"]["second"] == "fast-review-new"
    compare_html = Path(apply_result.data["compare_path"]).read_text(encoding="utf-8")
    assert "已按上一轮建议重新生成" in compare_html
    assert "已按上一轮反馈生成新候选" in compare_html
    assert 'data-selection-field value="doubao-review-adjusted" checked' in compare_html
    assert Path(apply_result.data["review_submission_path"]).exists()


def test_apply_review_can_continue_for_multiple_rounds(monkeypatch, tmp_path):
    calls = []

    def fake_execute(self, inputs):
        calls.append(inputs.copy())
        output_path = Path(inputs["output_path"])
        output_path.write_bytes(b"fake reviewed mp3")
        return ToolResult(
            success=True,
            data={
                "selected_provider": inputs.get("preferred_provider", "auto"),
                "selected_tool": "fake_tts",
                "audio_duration_seconds": 1.5,
            },
            artifacts=[str(output_path)],
        )

    monkeypatch.setattr("tools.audio.tts_selector.TTSSelector.execute", fake_execute)
    monkeypatch.setattr("tools.audio.tts_selector.TTSSelector.estimate_cost", lambda self, inputs: 0.0)

    generate_result = TTSSegmentLab().execute({"operation": "generate", "manifest": base_manifest(tmp_path)})
    assert generate_result.success

    round1_payload = tmp_path / "review-round-1.json"
    round1_payload.write_text(
        json.dumps(
            {
                "selections": {"opening": "doubao"},
                "annotations": {
                    "opening": {
                        "doubao": {
                            "decision": "REGENERATE",
                            "notes": "语速再稍微快一点",
                        }
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    round1 = TTSSegmentLab().execute(
        {
            "operation": "apply_review",
            "results_path": generate_result.data["results_path"],
            "annotations_path": str(round1_payload),
            "output_dir": str(tmp_path / "review-round-1"),
        }
    )
    assert round1.success
    assert round1.data["next_operation"] == "annotate"

    round2_payload = tmp_path / "review-round-2.json"
    round2_payload.write_text(
        json.dumps(
            {
                "selections": {"opening": "doubao-review-adjusted"},
                "annotations": {
                    "opening": {
                        "doubao-review-adjusted": {
                            "decision": "REGENERATE",
                            "notes": "语速再稍微快一点",
                        }
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    round2 = TTSSegmentLab().execute(
        {
            "operation": "apply_review",
            "results_path": round1.data["results_path"],
            "annotations_path": str(round2_payload),
            "output_dir": str(tmp_path / "review-round-2"),
        }
    )

    assert round2.success
    assert round2.data["regenerated_count"] == 1
    assert calls[-1]["speech_rate"] == 10
    round2_results = json.loads(Path(round2.data["results_path"]).read_text(encoding="utf-8"))
    assert round2_results["selections"]["opening"] == "doubao-review-adjusted-review-adjusted"


def test_generate_loads_project_env_file_before_tts_selector(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DOUBAO_SPEECH_API_KEY", raising=False)
    (tmp_path / ".env").write_text("DOUBAO_SPEECH_API_KEY=from-project-env\n", encoding="utf-8")
    calls = []

    def fake_execute(self, inputs):
        calls.append(os.environ.get("DOUBAO_SPEECH_API_KEY"))
        output_path = Path(inputs["output_path"])
        output_path.write_bytes(b"fake mp3")
        return ToolResult(
            success=True,
            data={
                "selected_provider": inputs.get("preferred_provider", "auto"),
                "selected_tool": "fake_tts",
                "audio_duration_seconds": 1.23,
            },
            artifacts=[str(output_path)],
        )

    monkeypatch.setattr("tools.audio.tts_selector.TTSSelector.execute", fake_execute)
    monkeypatch.setattr("tools.audio.tts_selector.TTSSelector.estimate_cost", lambda self, inputs: 0.0)

    result = TTSSegmentLab().execute({"operation": "generate", "manifest": base_manifest(tmp_path)})

    assert result.success
    assert calls[0] == "from-project-env"
    assert str(tmp_path / ".env") in result.data["loaded_env_files"]


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
