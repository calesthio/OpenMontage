from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tools.analysis.scene_detect import SceneDetect


@pytest.mark.parametrize(
    ("method", "detector_name", "threshold_key", "default"),
    [
        ("content", "ContentDetector", "threshold", 27.0),
        ("threshold", "ThresholdDetector", "threshold", 12.0),
        ("adaptive", "AdaptiveDetector", "adaptive_threshold", 3.0),
    ],
)
def test_pyscenedetect_preserves_explicit_threshold(
    monkeypatch, method, detector_name, threshold_key, default
):
    detectors = SimpleNamespace(
        ContentDetector=Mock(), ThresholdDetector=Mock(), AdaptiveDetector=Mock()
    )
    manager = Mock()
    manager.get_scene_list.return_value = []
    backend = SimpleNamespace(
        open_video=Mock(return_value=SimpleNamespace(frame_rate=24.0)),
        SceneManager=Mock(return_value=manager),
    )
    monkeypatch.setitem(sys.modules, "scenedetect", backend)
    monkeypatch.setitem(sys.modules, "scenedetect.detectors", detectors)

    tool = SceneDetect()
    detector = getattr(detectors, detector_name)
    inputs = {"input_path": "clip.mp4", "method": method}
    tool._detect_pyscenedetect(inputs)
    detector.assert_called_once_with(min_scene_len=24, **{threshold_key: default})

    detector.reset_mock()
    tool._detect_pyscenedetect({**inputs, "threshold": 0.0})
    detector.assert_called_once_with(min_scene_len=24, **{threshold_key: 0.0})
