import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from tools.analysis.visual_timing_qa import VisualTimingQA


def base_manifest(tmp_path: Path) -> dict:
    video_path = tmp_path / "final.mp4"
    video_path.write_bytes(b"fake video")
    return {
        "project": "unit-test",
        "run_id": "timing-run",
        "video_path": str(video_path),
        "duration_seconds": 12.0,
        "output_dir": str(tmp_path / "visual-timing"),
        "offsets_seconds": [-0.5, 0, 0.5],
        "cues": [
            {
                "id": "feedback",
                "section_id": "s6",
                "label": "Feedback reveal",
                "timestamp_seconds": 4.0,
                "narration": "Feedback returns to the user.",
                "expected_state": "The next-version Skill node is highlighted.",
                "risk": "Reveal may run too early.",
                "review_questions": ["Is the highlighted node visible?"],
            }
        ],
    }


def test_dry_run_writes_review_without_extracting_frames(tmp_path):
    tool = VisualTimingQA()
    result = tool.execute({"operation": "dry_run", "manifest": base_manifest(tmp_path)})

    assert result.success
    assert result.data["operation"] == "dry_run"
    assert result.data["cue_count"] == 1

    results_path = Path(result.data["results_path"])
    review_path = Path(result.data["review_path"])
    review_html_path = Path(result.data["review_html_path"])
    payload = json.loads(results_path.read_text(encoding="utf-8"))
    cue = payload["cues"][0]
    assert cue["planned"] is True
    assert cue["initial_review"]["decision"] == "UNREVIEWED"
    assert [point["timestamp_seconds"] for point in cue["frame_points"]] == [3.5, 4.0, 4.5]
    review = review_path.read_text(encoding="utf-8")
    assert "Feedback returns to the user." in review
    assert "Initial auto UNREVIEWED: `1`" in review
    assert "Reviewer decision:" in review
    assert "PASS - visual timing and state match the cue" in review
    assert "WRONG_EXPECTATION" in review
    assert "## Summary" in review
    assert "UNREVIEWED: `1`" in review
    html = review_html_path.read_text(encoding="utf-8")
    assert "Visual Timing QA Review" in html
    assert "Feedback returns to the user." in html
    assert "Planned frame timestamps" in html
    assert "Reviewer: UNREVIEWED" in html


def test_review_extracts_cue_frames_and_contact_sheet(monkeypatch, tmp_path):
    commands = []

    def fake_run_command(self, cmd, *, timeout=None, cwd=None):
        commands.append(cmd)
        if cmd[0] == "ffprobe":
            return subprocess.CompletedProcess(cmd, 0, stdout='{"format":{"duration":"12.0"}}', stderr="")
        output_path = Path(cmd[-1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake image")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(VisualTimingQA, "run_command", fake_run_command)

    tool = VisualTimingQA()
    result = tool.execute({"operation": "review", "manifest": base_manifest(tmp_path)})

    assert result.success
    cue = result.data["cues"][0]
    assert len(cue["frames"]) == 3
    assert cue["contact_sheet"]
    assert cue["initial_review"]["decision"] in {"PASS", "NEEDS_REVIEW"}
    assert Path(cue["contact_sheet"]).exists()
    review_html = Path(result.data["review_html_path"]).read_text(encoding="utf-8")
    assert "Contact sheet" in review_html
    assert "feedback_contact_sheet.jpg" in review_html
    assert "00_minus0_500_3.500s.jpg" in review_html
    assert any(cmd[0] == "ffprobe" for cmd in commands)
    assert sum(1 for cmd in commands if cmd[0] == "ffmpeg") == 4


def test_review_clamps_frame_points_to_video_bounds(monkeypatch, tmp_path):
    manifest = base_manifest(tmp_path)
    manifest["cues"][0]["timestamp_seconds"] = 0.2

    def fake_run_command(self, cmd, *, timeout=None, cwd=None):
        if cmd[0] == "ffprobe":
            return subprocess.CompletedProcess(cmd, 0, stdout='{"format":{"duration":"1.0"}}', stderr="")
        output_path = Path(cmd[-1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake image")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(VisualTimingQA, "run_command", fake_run_command)

    tool = VisualTimingQA()
    result = tool.execute({"operation": "review", "manifest": manifest})

    assert result.success
    timestamps = [frame["timestamp_seconds"] for frame in result.data["cues"][0]["frames"]]
    assert timestamps == [0.0, 0.2, 0.7]


def test_annotate_writes_notes_and_annotated_review(tmp_path):
    tool = VisualTimingQA()
    dry_result = tool.execute({"operation": "dry_run", "manifest": base_manifest(tmp_path)})
    assert dry_result.success

    annotate_result = tool.execute(
        {
            "operation": "annotate",
            "results_path": dry_result.data["results_path"],
            "annotations": {
                "feedback": {
                    "decision": "NEEDS_REVIEW",
                    "reviewer": "agent",
                    "confidence": "medium",
                    "issue_category": "scene_expectation",
                    "notes": "Looks close, but the reviewer should confirm the intended state.",
                    "fix_target": "Confirm cue expectation.",
                    "requires_user_review": True,
                    "user_decision": "DEFERRED",
                    "user_notes": "Reviewer will check later.",
                }
            },
        }
    )

    assert annotate_result.success
    notes_path = Path(annotate_result.data["review_notes_path"])
    annotated_path = Path(annotate_result.data["annotated_review_path"])
    annotated_html_path = Path(annotate_result.data["annotated_review_html_path"])
    notes = json.loads(notes_path.read_text(encoding="utf-8"))
    review = annotated_path.read_text(encoding="utf-8")
    html = annotated_html_path.read_text(encoding="utf-8")

    assert notes["annotations"][0]["decision"] == "NEEDS_REVIEW"
    assert notes["annotations"][0]["issue_category"] == "scene_expectation"
    assert notes["annotations"][0]["user_decision"] == "DEFERRED"
    assert "- [x] NEEDS_REVIEW" in review
    assert "NEEDS_REVIEW: `1`" in review
    assert "Reviewer queue:" in review
    assert "Issue category: scene_expectation" in review
    assert "Looks close, but the reviewer should confirm" in review
    assert "Reviewer: NEEDS_REVIEW" in html
    assert "Looks close, but the reviewer should confirm" in html
    assert "DEFERRED Reviewer will check later." in html


def test_review_supports_five_frame_windows(tmp_path):
    manifest = base_manifest(tmp_path)
    manifest["offsets_seconds"] = [-1.2, -0.6, 0, 0.6, 1.2]

    tool = VisualTimingQA()
    result = tool.execute({"operation": "dry_run", "manifest": manifest})

    assert result.success
    points = result.data["cues"][0]["frame_points"]
    assert [point["timestamp_seconds"] for point in points] == [2.8, 3.4, 4.0, 4.6, 5.2]


def test_suggest_cues_from_captions(tmp_path):
    captions_path = tmp_path / "captions.json"
    captions_path.write_text(
        json.dumps(
            [
                {"word": "普通解释句", "startMs": 1000, "endMs": 2000},
                {"word": "再运行 doctor 自检", "startMs": 4000, "endMs": 5000},
                {"word": "反馈提交之后，怎么变成下一版 Skill", "startMs": 8000, "endMs": 9000},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    tool = VisualTimingQA()
    result = tool.execute(
        {
            "operation": "suggest_cues",
            "captions_path": str(captions_path),
            "output_dir": str(tmp_path / "suggested"),
            "project": "unit-test",
            "run_id": "suggest-run",
            "speed_multiplier": 2.0,
            "per_category_limit": 2,
        }
    )

    assert result.success
    assert result.data["cue_count"] == 2
    assert Path(result.data["suggested_cues_path"]).exists()
    assert Path(result.data["suggested_review_path"]).exists()
    cues = result.data["cues"]
    assert cues[0]["score"] >= cues[1]["score"]
    assert any("doctor" in cue["narration"] for cue in cues)
    assert any(cue["timestamp_seconds"] == 2.0 for cue in cues)
    assert all(cue.get("category") for cue in cues)
    assert "Manifest Draft" in Path(result.data["suggested_review_path"]).read_text(encoding="utf-8")


def test_initial_review_flags_static_reveal_window(monkeypatch, tmp_path):
    manifest = base_manifest(tmp_path)

    def fake_run_command(self, cmd, *, timeout=None, cwd=None):
        if cmd[0] == "ffprobe":
            return subprocess.CompletedProcess(cmd, 0, stdout='{"format":{"duration":"12.0"}}', stderr="")
        output_path = Path(cmd[-1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (320, 180), "navy")
        image.save(output_path)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(VisualTimingQA, "run_command", fake_run_command)

    result = VisualTimingQA().execute({"operation": "review", "manifest": manifest})

    assert result.success
    initial = result.data["cues"][0]["initial_review"]
    assert initial["decision"] == "NEEDS_REVIEW"
    assert "Little visible change" in initial["notes"]
    review = Path(result.data["review_path"]).read_text(encoding="utf-8")
    assert "Initial auto NEEDS_REVIEW: `1`" in review
    assert "Initial auto-review queue:" in review


def test_initial_review_flags_late_reveal(monkeypatch, tmp_path):
    manifest = base_manifest(tmp_path)
    calls = {"frame": 0}

    def fake_run_command(self, cmd, *, timeout=None, cwd=None):
        if cmd[0] == "ffprobe":
            return subprocess.CompletedProcess(cmd, 0, stdout='{"format":{"duration":"12.0"}}', stderr="")
        output_path = Path(cmd[-1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.name.endswith("_contact_sheet.jpg"):
            image = Image.new("RGB", (960, 180), "white")
        else:
            calls["frame"] += 1
            color = "black" if calls["frame"] < 3 else "white"
            image = Image.new("RGB", (320, 180), color)
        image.save(output_path)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(VisualTimingQA, "run_command", fake_run_command)

    result = VisualTimingQA().execute({"operation": "review", "manifest": manifest})

    assert result.success
    initial = result.data["cues"][0]["initial_review"]
    assert initial["decision"] == "NEEDS_REVIEW"
    assert "after the target frame" in initial["notes"]


def test_initial_review_flags_empty_subtitle_band(monkeypatch, tmp_path):
    manifest = base_manifest(tmp_path)
    manifest["cues"][0]["expected_state"] = "字幕 should be visible at the bottom."
    manifest["cues"][0]["narration"] = "字幕出现。"

    def fake_run_command(self, cmd, *, timeout=None, cwd=None):
        if cmd[0] == "ffprobe":
            return subprocess.CompletedProcess(cmd, 0, stdout='{"format":{"duration":"12.0"}}', stderr="")
        output_path = Path(cmd[-1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (320, 180), "black")
        image.save(output_path)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(VisualTimingQA, "run_command", fake_run_command)

    result = VisualTimingQA().execute({"operation": "review", "manifest": manifest})

    assert result.success
    initial = result.data["cues"][0]["initial_review"]
    assert initial["decision"] == "NEEDS_REVIEW"
    assert "subtitles may be missing" in initial["notes"]


def test_initial_review_passes_when_bottom_caption_has_edges(monkeypatch, tmp_path):
    manifest = base_manifest(tmp_path)
    manifest["cues"][0]["expected_state"] = "字幕 should be visible at the bottom."
    manifest["cues"][0]["narration"] = "字幕出现。"

    def fake_run_command(self, cmd, *, timeout=None, cwd=None):
        if cmd[0] == "ffprobe":
            return subprocess.CompletedProcess(cmd, 0, stdout='{"format":{"duration":"12.0"}}', stderr="")
        output_path = Path(cmd[-1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (320, 180), "black")
        draw = ImageDraw.Draw(image)
        draw.rectangle((55, 135, 265, 170), fill="white")
        draw.text((70, 145), "caption text", fill="black")
        image.save(output_path)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(VisualTimingQA, "run_command", fake_run_command)

    result = VisualTimingQA().execute({"operation": "review", "manifest": manifest})

    assert result.success
    initial = result.data["cues"][0]["initial_review"]
    assert "Subtitles may be missing" not in initial["notes"]
