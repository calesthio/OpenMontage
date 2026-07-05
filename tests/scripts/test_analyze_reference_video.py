from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts import analyze_reference_video


def test_analyze_local_video_writes_replication_package(tmp_path, monkeypatch):
    video_path = tmp_path / "input.mp4"
    video_path.write_bytes(b"fake-video")

    def fake_probe(path: Path) -> dict:
        assert path == video_path
        return {
            "duration_seconds": 6.0,
            "width": 720,
            "height": 1280,
            "fps": 30.0,
            "has_audio": True,
        }

    def fake_detect(path: Path, project_dir: Path, duration: float) -> dict:
        assert path == video_path
        assert duration == 6.0
        return {
            "method": "fixed_interval_fallback",
            "scenes": [
                {
                    "scene_id": "s1",
                    "start": 0.0,
                    "end": 3.0,
                    "visual_summary": "参考视频片段 1",
                    "keyframes": [],
                },
                {
                    "scene_id": "s2",
                    "start": 3.0,
                    "end": 6.0,
                    "visual_summary": "参考视频片段 2",
                    "keyframes": [],
                },
            ],
        }

    def fake_transcribe(path: Path, project_dir: Path, has_audio: bool) -> dict:
        assert has_audio is True
        return {
            "status": "ok",
            "raw_text": "前三秒给出钩子，然后展示卖点。",
            "segments": [
                {"start": 0.0, "end": 3.0, "text": "前三秒给出钩子"},
                {"start": 3.0, "end": 6.0, "text": "然后展示卖点"},
            ],
        }

    monkeypatch.setattr(analyze_reference_video, "probe_video", fake_probe)
    monkeypatch.setattr(analyze_reference_video, "analyze_scenes", fake_detect)
    monkeypatch.setattr(analyze_reference_video, "transcribe_reference", fake_transcribe)
    monkeypatch.setattr(analyze_reference_video.shutil, "which", lambda name: f"/mock/{name}")

    result = analyze_reference_video.analyze_local_video(
        video_path=video_path,
        project_dir=tmp_path / "project",
    )

    assert Path(result["json_path"]).is_file()
    assert Path(result["markdown_path"]).is_file()
    package = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert package["source"]["input_type"] == "local_file"
    assert package["source"]["local_video_path"] == str(video_path)
    assert package["transcript"]["raw_text"] == "前三秒给出钩子，然后展示卖点。"
    assert package["replication_strategy"]["recommended_mode"] == "seedance"
    assert package["replication_strategy"]["alternatives"] == ["seedance"]


def test_analyze_url_downloads_reference_then_builds_package(tmp_path, monkeypatch):
    downloaded_video = tmp_path / "downloaded.mp4"
    downloaded_video.write_bytes(b"fake-video")

    class _DownloadResult:
        success = True
        data = {
            "video_path": str(downloaded_video),
            "metadata": {"title": "Douyin sample", "duration": 6.0},
            "platform": "other_url",
        }
        error = None

    class _FakeDownloader:
        def execute(self, inputs):
            assert inputs["url"] == "https://v.douyin.com/example/"
            assert inputs["format"] == "video"
            assert inputs["max_resolution"] == "720p"
            return _DownloadResult()

    def fake_probe(path: Path) -> dict:
        assert path == downloaded_video.resolve()
        return {
            "duration_seconds": 6.0,
            "width": 720,
            "height": 1280,
            "fps": 30.0,
            "has_audio": False,
        }

    monkeypatch.setattr(analyze_reference_video, "VideoDownloader", _FakeDownloader)
    monkeypatch.setattr(analyze_reference_video, "probe_video", fake_probe)
    monkeypatch.setattr(
        analyze_reference_video,
        "analyze_scenes",
        lambda path, project_dir, duration: {
            "method": "fixed_interval_fallback",
            "scenes": [
                {
                    "scene_id": "s1",
                    "start": 0.0,
                    "end": 6.0,
                    "visual_summary": "下载后的视频片段",
                    "keyframes": [],
                }
            ],
        },
    )
    monkeypatch.setattr(
        analyze_reference_video,
        "transcribe_reference",
        lambda path, project_dir, has_audio: {
            "status": "pending_transcription",
            "reason": "no_audio_stream",
        },
    )
    monkeypatch.setattr(analyze_reference_video.shutil, "which", lambda name: f"/mock/{name}")

    result = analyze_reference_video.analyze_reference_source(
        source="https://v.douyin.com/example/",
        project_dir=tmp_path / "project",
    )

    package = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert package["source"]["input_type"] == "url"
    assert package["source"]["input"] == "https://v.douyin.com/example/"
    assert package["source"]["local_video_path"] == str(downloaded_video.resolve())
    assert package["source"]["ingest_method"] == "video_downloader"
    assert package["source"]["download_metadata"]["title"] == "Douyin sample"


def test_main_returns_fallback_when_url_download_fails(tmp_path, monkeypatch, capsys):
    class _DownloadResult:
        success = False
        data = {"platform": "other_url", "metadata": {"title": "blocked"}}
        error = "login required"

    class _FakeDownloader:
        def execute(self, inputs):
            return _DownloadResult()

    monkeypatch.setattr(analyze_reference_video, "VideoDownloader", _FakeDownloader)

    exit_code = analyze_reference_video.main(
        ["https://v.douyin.com/blocked/", "--project-dir", str(tmp_path / "project")]
    )

    captured = capsys.readouterr()
    assert exit_code == 3
    payload = json.loads(captured.err)
    assert payload["status"] == "download_failed"
    assert payload["input"] == "https://v.douyin.com/blocked/"
    assert payload["fallback_required"] == "local_video_file"
    assert "login required" in payload["reason"]


def test_main_returns_error_for_missing_video(tmp_path, capsys):
    missing_path = tmp_path / "missing.mp4"

    exit_code = analyze_reference_video.main([str(missing_path)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Video file not found" in captured.err


def test_script_can_run_as_file_for_missing_video(tmp_path):
    missing_path = tmp_path / "missing.mp4"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/analyze_reference_video.py",
            str(missing_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "Video file not found" in result.stderr


def test_transcribe_reference_returns_pending_when_model_is_not_cached(monkeypatch, tmp_path):
    class _AvailableStatus:
        value = "available"

    class _OfflineTranscriber:
        def get_status(self):
            return _AvailableStatus()

        def execute(self, inputs):
            raise RuntimeError(
                "ConnectError: offline and no cached model snapshot is available"
            )

    monkeypatch.setattr(analyze_reference_video, "Transcriber", _OfflineTranscriber)

    result = analyze_reference_video.transcribe_reference(
        video_path=tmp_path / "input.mp4",
        project_dir=tmp_path / "project",
        has_audio=True,
    )

    assert result["status"] == "pending_transcription"
    assert result["reason"] == "transcriber_model_download_required"


def test_transcribe_reference_marks_empty_segments_as_no_speech(monkeypatch, tmp_path):
    class _AvailableStatus:
        value = "available"

    class _Result:
        success = True
        data = {"segments": [], "language": "zh"}

    class _NoSpeechTranscriber:
        def get_status(self):
            return _AvailableStatus()

        def execute(self, inputs):
            return _Result()

    monkeypatch.setattr(analyze_reference_video, "Transcriber", _NoSpeechTranscriber)

    result = analyze_reference_video.transcribe_reference(
        video_path=tmp_path / "input.mp4",
        project_dir=tmp_path / "project",
        has_audio=True,
    )

    assert result["status"] == "pending_transcription"
    assert result["reason"] == "no_speech_detected"
