from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import Mock

from tools.analysis.face_tracker import FaceTracker
from tools.base_tool import ToolStatus


def test_missing_mediapipe_solutions_uses_opencv_fallback(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "mediapipe", ModuleType("mediapipe"))
    monkeypatch.setitem(sys.modules, "cv2", ModuleType("cv2"))

    input_path = tmp_path / "input.mp4"
    input_path.touch()

    tracker = FaceTracker()
    opencv_result = {
        "video_width": 1920,
        "video_height": 1080,
        "fps": 30.0,
        "duration_seconds": 1.0,
        "frame_count": 1,
        "face_detected_count": 0,
        "faces": [],
    }
    track_opencv = Mock(return_value=opencv_result)
    track_mediapipe = Mock()
    monkeypatch.setattr(tracker, "_track_opencv", track_opencv)
    monkeypatch.setattr(tracker, "_track_mediapipe", track_mediapipe)

    assert tracker.get_status() == ToolStatus.DEGRADED

    result = tracker.execute({"input_path": str(input_path)})

    assert result.success
    assert result.data["method"] == "opencv_haar"
    track_opencv.assert_called_once_with(input_path, 5)
    track_mediapipe.assert_not_called()
