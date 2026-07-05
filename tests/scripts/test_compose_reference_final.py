from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace


def _final_edit_plan(
    project_dir: Path,
    clip_path: Path,
    *,
    status: str = "ready_for_compose",
    audio_tracks: list[dict] | None = None,
) -> dict:
    return {
        "version": "1.0",
        "status": status,
        "render_runtime": "ffmpeg",
        "timeline": [
            {
                "order": 1,
                "scene_id": "s1",
                "clip_path": str(clip_path),
                "clip_exists": clip_path.is_file(),
                "timeline_start": 0.0,
                "timeline_end": 8.0,
                "duration": 8.0,
                "script_text": "人工确认后的文案。",
                "subtitle_text": "人工确认后的文案。",
                "transition": "cut",
            }
        ],
        "ready_clip_count": 1 if clip_path.is_file() else 0,
        "missing_clip_count": 0 if clip_path.is_file() else 1,
        "total_duration": 8.0,
        "compose_handoff": {
            "video_paths": [str(clip_path)],
            "subtitle_strategy": "use timeline[].subtitle_text",
            "output_path": str(project_dir / "renders" / "reference-final.mp4"),
            "requires_all_clips": True,
            **({"audio_tracks": audio_tracks} if audio_tracks is not None else {}),
        },
    }


def _two_clip_final_edit_plan(project_dir: Path, first_clip: Path, second_clip: Path) -> dict:
    plan = _final_edit_plan(project_dir, first_clip)
    plan["timeline"].append(
        {
            "order": 2,
            "scene_id": "s2",
            "clip_path": str(second_clip),
            "clip_exists": second_clip.is_file(),
            "timeline_start": 8.0,
            "timeline_end": 16.0,
            "duration": 8.0,
            "script_text": "第二段文案。",
            "subtitle_text": "第二段文案。",
            "transition": "cut",
        }
    )
    plan["ready_clip_count"] = 2
    plan["missing_clip_count"] = 0
    plan["total_duration"] = 16.0
    plan["compose_handoff"]["video_paths"] = [str(first_clip), str(second_clip)]
    return plan


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_compose_refuses_plan_that_is_not_ready(tmp_path, capsys):
    compose_final = importlib.import_module("scripts.compose_reference_final")
    project_dir = tmp_path / "project"
    missing_clip = project_dir / "assets" / "video" / "missing.mp4"
    plan_path = _write_json(
        project_dir / "artifacts" / "reference-final-edit" / "plan.json",
        _final_edit_plan(project_dir, missing_clip, status="waiting_for_generated_clips"),
    )

    exit_code = compose_final.main([str(plan_path), "--project-dir", str(project_dir)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "ready_for_compose" in captured.err


def test_compose_dry_run_writes_render_report_without_rendering(tmp_path, capsys):
    compose_final = importlib.import_module("scripts.compose_reference_final")
    project_dir = tmp_path / "project"
    clip_path = project_dir / "assets" / "video" / "s1.mp4"
    clip_path.parent.mkdir(parents=True, exist_ok=True)
    clip_path.write_bytes(b"fake mp4")
    plan_path = _write_json(
        project_dir / "artifacts" / "reference-final-edit" / "plan.json",
        _final_edit_plan(project_dir, clip_path),
    )

    exit_code = compose_final.main([str(plan_path), "--project-dir", str(project_dir), "--dry-run"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    report = payload["render_report"]

    assert exit_code == 0
    assert payload["dry_run"] is True
    assert report["status"] == "dry_run_ready"
    assert report["clip_count"] == 1
    assert report["output_path"] == str(project_dir / "renders" / "reference-final.mp4")
    assert report["quality_profile"] == "high"
    assert report["video_crf"] == 18
    assert report["video_preset"] == "medium"
    assert Path(payload["json_path"]).is_file()
    assert Path(payload["markdown_path"]).is_file()
    assert not (project_dir / "renders" / "reference-final.mp4").exists()


def test_compose_dry_run_writes_subtitle_sidecar_from_timeline(tmp_path, capsys):
    compose_final = importlib.import_module("scripts.compose_reference_final")
    project_dir = tmp_path / "project"
    clip_path = project_dir / "assets" / "video" / "s1.mp4"
    clip_path.parent.mkdir(parents=True, exist_ok=True)
    clip_path.write_bytes(b"fake mp4")
    plan_path = _write_json(
        project_dir / "artifacts" / "reference-final-edit" / "plan.json",
        _final_edit_plan(project_dir, clip_path),
    )

    exit_code = compose_final.main([str(plan_path), "--project-dir", str(project_dir), "--dry-run"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    subtitle_path = Path(payload["render_report"]["subtitle_path"])

    assert exit_code == 0
    assert subtitle_path.is_file()
    assert payload["render_report"]["subtitle_cue_count"] == 1
    subtitle_text = subtitle_path.read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:08,000" in subtitle_text
    assert "人工确认后的文案\n" in subtitle_text
    assert "人工确认后的文案。" not in subtitle_text


def test_compose_splits_long_chinese_subtitle_into_timed_cues(tmp_path, capsys):
    compose_final = importlib.import_module("scripts.compose_reference_final")
    project_dir = tmp_path / "project"
    clip_path = project_dir / "assets" / "video" / "s1.mp4"
    clip_path.parent.mkdir(parents=True, exist_ok=True)
    clip_path.write_bytes(b"fake mp4")
    plan = _final_edit_plan(project_dir, clip_path)
    plan["timeline"][0]["timeline_end"] = 15.0
    plan["timeline"][0]["duration"] = 15.0
    plan["timeline"][0]["subtitle_text"] = (
        "在这些案子上面，我积累了充足的实战经验。"
        "如果你身边刚好缺一位靠谱的律师朋友，今天刷到这条视频，"
        "不妨给徐律师点个赞、留个关注。"
        "徐律师就是你的私人法律顾问。"
        "往后再遇上工程扯皮、刑事案件相关麻烦，"
        "我会尽全力帮你维护你的合法权益。"
    )
    plan["total_duration"] = 15.0
    plan_path = _write_json(
        project_dir / "artifacts" / "reference-final-edit" / "plan.json",
        plan,
    )

    exit_code = compose_final.main([str(plan_path), "--project-dir", str(project_dir), "--dry-run"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    subtitle_text = Path(payload["render_report"]["subtitle_path"]).read_text(encoding="utf-8")

    assert exit_code == 0
    subtitle_lines = [
        line
        for line in subtitle_text.splitlines()
        if line and "-->" not in line and not line.isdigit()
    ]
    assert payload["render_report"]["subtitle_cue_count"] >= 6
    assert all(len(line) <= 13 for line in subtitle_lines)
    assert "00:00:00,000 --> 00:00:15,000" not in subtitle_text
    assert "关注。 徐律师" not in subtitle_text
    assert "积\n累" not in subtitle_text
    assert "经\n验" not in subtitle_text
    assert "法\n律" not in subtitle_text
    assert "你\n的合法权益" not in subtitle_text
    assert "徐律师就是你的" in subtitle_text
    assert "私人法律顾问\n" in subtitle_text
    assert "私人法律顾问。" not in subtitle_text


def test_compose_uses_oral_subtitle_planner_for_short_form_cues(tmp_path, capsys):
    compose_final = importlib.import_module("scripts.compose_reference_final")
    project_dir = tmp_path / "project"
    clip_path = project_dir / "assets" / "video" / "s1.mp4"
    clip_path.parent.mkdir(parents=True, exist_ok=True)
    clip_path.write_bytes(b"fake mp4")
    plan = _final_edit_plan(project_dir, clip_path)
    plan["timeline"][0]["timeline_end"] = 15.0
    plan["timeline"][0]["duration"] = 15.0
    plan["timeline"][0]["subtitle_text"] = (
        "在这些案子上面，我积累了充足的实战经验。"
        "如果你身边刚好缺一位靠谱的律师朋友，今天刷到这条视频，"
        "不妨给徐律师点个赞、留个关注。"
        "徐律师就是你的私人法律顾问。"
        "往后再遇上工程扯皮、刑事案件相关麻烦，"
        "我会尽全力帮你维护你的合法权益。"
    )
    plan["total_duration"] = 15.0
    plan_path = _write_json(
        project_dir / "artifacts" / "reference-final-edit" / "plan.json",
        plan,
    )

    exit_code = compose_final.main([str(plan_path), "--project-dir", str(project_dir), "--dry-run"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    subtitle_text = Path(payload["render_report"]["subtitle_path"]).read_text(encoding="utf-8")
    cue_blocks = [block for block in subtitle_text.strip().split("\n\n") if block.strip()]
    cue_texts = ["\n".join(block.splitlines()[2:]) for block in cue_blocks]

    assert exit_code == 0
    assert payload["render_report"]["subtitle_cue_count"] >= 10
    assert all(len(text.splitlines()) <= 2 for text in cue_texts)
    assert all(
        len(line) <= 12
        for text in cue_texts
        for line in text.splitlines()
        if line.strip()
    )
    assert "如果你身边刚好缺一位\n靠谱的律师朋友，\n今天刷到这条视频，" not in subtitle_text
    assert "私人法律顾问" in cue_texts
    assert all(
        not line.rstrip().endswith(("，", ",", "。", "！", "!", "？", "?", "、", "；", ";", "：", ":"))
        for text in cue_texts
        for line in text.splitlines()
        if line.strip()
    )


def test_compose_can_use_subtitle_polish_plan_cues(tmp_path, capsys):
    compose_final = importlib.import_module("scripts.compose_reference_final")
    project_dir = tmp_path / "project"
    clip_path = project_dir / "assets" / "video" / "s1.mp4"
    clip_path.parent.mkdir(parents=True, exist_ok=True)
    clip_path.write_bytes(b"fake mp4")
    final_plan = _final_edit_plan(project_dir, clip_path)
    final_plan["timeline"][0]["subtitle_text"] = "原始字幕不应该进入 SRT。"
    final_plan_path = _write_json(
        project_dir / "artifacts" / "reference-final-edit" / "plan.json",
        final_plan,
    )
    polish_plan_path = _write_json(
        project_dir / "artifacts" / "reference-subtitles" / "plan-subtitle-polish-plan.json",
        {
            "version": "1.0",
            "provider": "doubao",
            "mode": "dry_run",
            "api_called": False,
            "timeline": [
                {
                    "scene_id": "s1",
                    "cues": [
                        {"start": 0.0, "end": 1.5, "text": "润色后的第一句。"},
                        {"start": 1.5, "end": 8.0, "text": "中间，逗号保留。"},
                    ],
                }
            ],
        },
    )

    exit_code = compose_final.main(
        [
            str(final_plan_path),
            "--project-dir",
            str(project_dir),
            "--dry-run",
            "--subtitle-polish-plan",
            str(polish_plan_path),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    subtitle_text = Path(payload["render_report"]["subtitle_path"]).read_text(encoding="utf-8")

    assert exit_code == 0
    assert payload["render_report"]["subtitle_source"] == "subtitle_polish_plan"
    assert payload["render_report"]["subtitle_cue_count"] == 2
    assert "润色后的第一句" in subtitle_text
    assert "润色后的第一句。" not in subtitle_text
    assert "中间，逗号保留\n" in subtitle_text
    assert "中间，逗号保留。" not in subtitle_text
    assert "原始字幕不应该进入 SRT" not in subtitle_text


def test_compose_records_existing_audio_tracks_in_render_report(tmp_path, capsys):
    compose_final = importlib.import_module("scripts.compose_reference_final")
    project_dir = tmp_path / "project"
    clip_path = project_dir / "assets" / "video" / "s1.mp4"
    audio_path = project_dir / "assets" / "audio" / "voice.mp3"
    clip_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    clip_path.write_bytes(b"fake mp4")
    audio_path.write_bytes(b"fake mp3")
    plan_path = _write_json(
        project_dir / "artifacts" / "reference-final-edit" / "plan.json",
        _final_edit_plan(
            project_dir,
            clip_path,
            audio_tracks=[{"path": str(audio_path), "role": "speech", "volume": 1.0}],
        ),
    )

    exit_code = compose_final.main([str(plan_path), "--project-dir", str(project_dir), "--dry-run"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["render_report"]["audio_track_count"] == 1
    assert payload["render_report"]["audio_tracks"][0]["path"] == str(audio_path)


def test_compose_refuses_missing_audio_tracks(tmp_path, capsys):
    compose_final = importlib.import_module("scripts.compose_reference_final")
    project_dir = tmp_path / "project"
    clip_path = project_dir / "assets" / "video" / "s1.mp4"
    missing_audio = project_dir / "assets" / "audio" / "missing.mp3"
    clip_path.parent.mkdir(parents=True, exist_ok=True)
    clip_path.write_bytes(b"fake mp4")
    plan_path = _write_json(
        project_dir / "artifacts" / "reference-final-edit" / "plan.json",
        _final_edit_plan(
            project_dir,
            clip_path,
            audio_tracks=[{"path": str(missing_audio), "role": "speech"}],
        ),
    )

    exit_code = compose_final.main([str(plan_path), "--project-dir", str(project_dir), "--dry-run"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "missing audio tracks" in captured.err


def test_compose_invokes_video_stitch_and_writes_render_report(tmp_path, capsys, monkeypatch):
    compose_final = importlib.import_module("scripts.compose_reference_final")
    project_dir = tmp_path / "project"
    clip_path = project_dir / "assets" / "video" / "s1.mp4"
    second_clip_path = project_dir / "assets" / "video" / "s2.mp4"
    clip_path.parent.mkdir(parents=True, exist_ok=True)
    clip_path.write_bytes(b"fake mp4")
    second_clip_path.write_bytes(b"fake mp4")
    plan_path = _write_json(
        project_dir / "artifacts" / "reference-final-edit" / "plan.json",
        _two_clip_final_edit_plan(project_dir, clip_path, second_clip_path),
    )
    calls: list[dict] = []

    class FakeVideoStitch:
        def execute(self, inputs: dict):
            calls.append(inputs)
            output_path = Path(inputs["output_path"])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"fake final mp4")
            return SimpleNamespace(
                success=True,
                error=None,
                data={"output_path": str(output_path), "method": "concat"},
                artifacts=[str(output_path)],
                duration_seconds=0.01,
                cost_usd=0.0,
                model=None,
            )

    monkeypatch.setattr(compose_final, "VideoStitch", FakeVideoStitch)

    exit_code = compose_final.main([str(plan_path), "--project-dir", str(project_dir)])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert calls[0]["operation"] == "stitch"
    assert calls[0]["clips"] == [str(clip_path), str(second_clip_path)]
    assert calls[0]["transition"] == "cut"
    assert calls[0]["crf"] == 18
    assert calls[0]["preset"] == "medium"
    assert payload["render_report"]["status"] == "rendered"
    assert payload["render_report"]["quality_profile"] == "high"
    assert Path(payload["render_report"]["output_path"]).is_file()


def test_compose_can_burn_subtitles_after_stitch(tmp_path, capsys, monkeypatch):
    compose_final = importlib.import_module("scripts.compose_reference_final")
    project_dir = tmp_path / "project"
    clip_path = project_dir / "assets" / "video" / "s1.mp4"
    second_clip_path = project_dir / "assets" / "video" / "s2.mp4"
    clip_path.parent.mkdir(parents=True, exist_ok=True)
    clip_path.write_bytes(b"fake mp4")
    second_clip_path.write_bytes(b"fake mp4")
    plan_path = _write_json(
        project_dir / "artifacts" / "reference-final-edit" / "plan.json",
        _two_clip_final_edit_plan(project_dir, clip_path, second_clip_path),
    )
    stitch_calls: list[dict] = []
    compose_calls: list[dict] = []

    class FakeVideoStitch:
        def execute(self, inputs: dict):
            stitch_calls.append(inputs)
            output_path = Path(inputs["output_path"])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"fake stitched mp4")
            return SimpleNamespace(
                success=True,
                error=None,
                data={"output_path": str(output_path), "method": "concat"},
            )

    class FakeVideoCompose:
        def execute(self, inputs: dict):
            compose_calls.append(inputs)
            output_path = Path(inputs["output_path"])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"fake subtitled mp4")
            return SimpleNamespace(
                success=True,
                error=None,
                data={"output": str(output_path), "operation": "burn_subtitles"},
            )

    monkeypatch.setattr(compose_final, "VideoStitch", FakeVideoStitch)
    monkeypatch.setattr(compose_final, "VideoCompose", FakeVideoCompose)

    exit_code = compose_final.main(
        [str(plan_path), "--project-dir", str(project_dir), "--burn-subtitles"]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert stitch_calls[0]["output_path"] != str(project_dir / "renders" / "reference-final.mp4")
    assert compose_calls[0]["operation"] == "burn_subtitles"
    assert compose_calls[0]["input_path"] == stitch_calls[0]["output_path"]
    assert compose_calls[0]["subtitle_path"] == payload["render_report"]["subtitle_path"]
    assert compose_calls[0]["output_path"] == str(project_dir / "renders" / "reference-final.mp4")
    assert compose_calls[0]["crf"] == 18
    assert compose_calls[0]["preset"] == "medium"
    assert payload["render_report"]["burned_subtitles"] is True


def test_compose_single_clip_burns_subtitles_without_stitch(tmp_path, capsys, monkeypatch):
    compose_final = importlib.import_module("scripts.compose_reference_final")
    project_dir = tmp_path / "project"
    clip_path = project_dir / "assets" / "video" / "s1.mp4"
    clip_path.parent.mkdir(parents=True, exist_ok=True)
    clip_path.write_bytes(b"fake mp4")
    plan_path = _write_json(
        project_dir / "artifacts" / "reference-final-edit" / "plan.json",
        _final_edit_plan(project_dir, clip_path),
    )
    compose_calls: list[dict] = []

    class FailVideoStitch:
        def execute(self, inputs: dict):
            raise AssertionError("single-clip compose should not invoke VideoStitch")

    class FakeVideoCompose:
        def execute(self, inputs: dict):
            compose_calls.append(inputs)
            output_path = Path(inputs["output_path"])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"fake subtitled mp4")
            return SimpleNamespace(
                success=True,
                error=None,
                data={"output": str(output_path), "operation": "burn_subtitles"},
            )

    monkeypatch.setattr(compose_final, "VideoStitch", FailVideoStitch)
    monkeypatch.setattr(compose_final, "VideoCompose", FakeVideoCompose)

    exit_code = compose_final.main(
        [str(plan_path), "--project-dir", str(project_dir), "--burn-subtitles"]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert compose_calls[0]["operation"] == "burn_subtitles"
    assert compose_calls[0]["input_path"] == str(clip_path)
    assert compose_calls[0]["subtitle_style"]["font"] == "Hiragino Sans GB"
    assert compose_calls[0]["subtitle_style"]["font_size"] == 12
    assert compose_calls[0]["subtitle_style"]["fontsdir"] == "/System/Library/Fonts"
    assert compose_calls[0]["crf"] == 18
    assert compose_calls[0]["preset"] == "medium"
    assert payload["render_report"]["burned_subtitles"] is True


def test_compose_quality_standard_uses_legacy_crf(tmp_path, capsys, monkeypatch):
    compose_final = importlib.import_module("scripts.compose_reference_final")
    project_dir = tmp_path / "project"
    clip_path = project_dir / "assets" / "video" / "s1.mp4"
    clip_path.parent.mkdir(parents=True, exist_ok=True)
    clip_path.write_bytes(b"fake mp4")
    plan_path = _write_json(
        project_dir / "artifacts" / "reference-final-edit" / "plan.json",
        _final_edit_plan(project_dir, clip_path),
    )
    compose_calls: list[dict] = []

    class FakeVideoCompose:
        def execute(self, inputs: dict):
            compose_calls.append(inputs)
            output_path = Path(inputs["output_path"])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"fake subtitled mp4")
            return SimpleNamespace(success=True, error=None, data={"output": str(output_path)})

    monkeypatch.setattr(compose_final, "VideoCompose", FakeVideoCompose)

    exit_code = compose_final.main(
        [
            str(plan_path),
            "--project-dir",
            str(project_dir),
            "--burn-subtitles",
            "--quality",
            "standard",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert compose_calls[0]["crf"] == 23
    assert compose_calls[0]["preset"] == "medium"
    assert payload["render_report"]["quality_profile"] == "standard"
    assert payload["render_report"]["video_crf"] == 23


def test_compose_can_mix_audio_after_stitch(tmp_path, capsys, monkeypatch):
    compose_final = importlib.import_module("scripts.compose_reference_final")
    project_dir = tmp_path / "project"
    clip_path = project_dir / "assets" / "video" / "s1.mp4"
    audio_path = project_dir / "assets" / "audio" / "voice.mp3"
    clip_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    clip_path.write_bytes(b"fake mp4")
    audio_path.write_bytes(b"fake mp3")
    plan_path = _write_json(
        project_dir / "artifacts" / "reference-final-edit" / "plan.json",
        _final_edit_plan(
            project_dir,
            clip_path,
            audio_tracks=[{"path": str(audio_path), "role": "speech", "volume": 1.0}],
        ),
    )
    stitch_calls: list[dict] = []
    mixer_calls: list[dict] = []
    compose_calls: list[dict] = []

    class FakeVideoStitch:
        def execute(self, inputs: dict):
            stitch_calls.append(inputs)
            output_path = Path(inputs["output_path"])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"fake stitched mp4")
            return SimpleNamespace(
                success=True,
                error=None,
                data={"output_path": str(output_path), "method": "concat"},
            )

    class FakeAudioMixer:
        def execute(self, inputs: dict):
            mixer_calls.append(inputs)
            output_path = Path(inputs["output_path"])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"fake mix wav")
            return SimpleNamespace(
                success=True,
                error=None,
                data={"output": str(output_path), "operation": "full_mix"},
            )

    class FakeVideoCompose:
        def execute(self, inputs: dict):
            compose_calls.append(inputs)
            output_path = Path(inputs["output_path"])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"fake muxed mp4")
            return SimpleNamespace(
                success=True,
                error=None,
                data={"output": str(output_path), "operation": "compose"},
            )

    monkeypatch.setattr(compose_final, "VideoStitch", FakeVideoStitch)
    monkeypatch.setattr(compose_final, "AudioMixer", FakeAudioMixer)
    monkeypatch.setattr(compose_final, "VideoCompose", FakeVideoCompose)

    exit_code = compose_final.main(
        [str(plan_path), "--project-dir", str(project_dir), "--mix-audio"]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert mixer_calls[0]["operation"] == "full_mix"
    assert mixer_calls[0]["tracks"][0]["path"] == str(audio_path)
    assert compose_calls[0]["operation"] == "compose"
    assert compose_calls[0]["audio_path"] == mixer_calls[0]["output_path"]
    assert compose_calls[0]["output_path"] == str(project_dir / "renders" / "reference-final.mp4")
    assert payload["render_report"]["mixed_audio_path"] == mixer_calls[0]["output_path"]
    assert payload["render_report"]["mixed_audio"] is True
