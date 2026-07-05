from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_review_reference_final_writes_local_review_reports(tmp_path):
    review = importlib.import_module("scripts.review_reference_final")
    project_dir = tmp_path / "project"
    final_video = project_dir / "renders" / "reference-final.mp4"
    final_video.parent.mkdir(parents=True, exist_ok=True)
    final_video.write_bytes(b"fake mp4")
    subtitle = project_dir / "assets" / "subtitles" / "reference-final.srt"
    subtitle.parent.mkdir(parents=True, exist_ok=True)
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n", encoding="utf-8")
    render_report = _write_json(
        project_dir / "artifacts" / "reference-render" / "sample-render-report.json",
        {
            "status": "rendered",
            "dry_run": False,
            "output_path": str(final_video),
            "subtitle_path": str(subtitle),
            "burned_subtitles": True,
            "mixed_audio": True,
            "mixed_audio_path": str(project_dir / "assets" / "audio" / "mix.wav"),
            "quality_profile": "high",
            "clip_count": 1,
            "total_duration": 15,
        },
    )

    result = review.review_final_render(
        project_dir=project_dir,
        render_report_path=render_report,
        reviewer="operator",
    )

    assert result["status"] == "final_review_ready_for_delivery"
    assert result["project_dir"] == str(project_dir.resolve())
    assert result["source_render_report_path"] == str(render_report.resolve())
    assert result["render"]["output_path"] == str(final_video.resolve())
    assert result["render"]["exists"] is True
    assert result["render"]["file_size_bytes"] == len(b"fake mp4")
    assert result["render"]["burned_subtitles"] is True
    assert result["render"]["mixed_audio"] is True
    assert result["render"]["quality_profile"] == "high"
    assert result["human_review"]["reviewer"] == "operator"
    assert result["human_review"]["delivery_export_phrase"] == "APPROVE FINAL DELIVERY"
    assert result["safety"]["local_only"] is True
    assert result["safety"]["paid_generation_started_by_review"] is False
    assert {item["id"] for item in result["checklist"]} >= {
        "play_final_mp4",
        "verify_subtitles",
        "verify_authorized_assets",
        "approve_delivery_export",
    }

    json_report = Path(result["review_report_path"])
    markdown_report = Path(result["markdown_report_path"])
    assert json_report.is_file()
    assert markdown_report.is_file()
    assert json.loads(json_report.read_text(encoding="utf-8"))["status"] == (
        "final_review_ready_for_delivery"
    )
    markdown = markdown_report.read_text(encoding="utf-8")
    assert "# Final Render Review" in markdown
    assert "APPROVE FINAL DELIVERY" in markdown
    assert "reference-final.mp4" in markdown


def test_review_reference_final_rejects_dry_run_report(tmp_path):
    review = importlib.import_module("scripts.review_reference_final")
    project_dir = tmp_path / "project"
    render_report = _write_json(
        project_dir / "artifacts" / "reference-render" / "sample-render-report.json",
        {"status": "rendered", "dry_run": True, "output_path": "renders/reference-final.mp4"},
    )

    with pytest.raises(ValueError, match="non-dry-run rendered report"):
        review.review_final_render(project_dir=project_dir, render_report_path=render_report)


def test_review_reference_final_main_prints_json(tmp_path, capsys):
    review = importlib.import_module("scripts.review_reference_final")
    project_dir = tmp_path / "project"
    final_video = project_dir / "renders" / "reference-final.mp4"
    final_video.parent.mkdir(parents=True, exist_ok=True)
    final_video.write_bytes(b"fake mp4")
    render_report = _write_json(
        project_dir / "artifacts" / "reference-render" / "sample-render-report.json",
        {"status": "rendered", "dry_run": False, "output_path": str(final_video)},
    )

    exit_code = review.main(
        [str(project_dir), "--render-report", str(render_report), "--reviewer", "operator"]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "final_review_ready_for_delivery"
    assert payload["review_report_path"].endswith("-final-review.json")
