"""Regression: local video variants must load the pipeline that matches the
checkpoint and operation.

HunyuanVideo 1.5 and LTX-2 were mapped to the older HunyuanVideoPipeline /
LTXPipeline classes (and Hunyuan to a non-diffusers repo), and cogvideo-5b
advertised image_to_video without an I2V checkpoint, so every call failed at
load or inference time. These tests pin the routing without torch/diffusers.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

from tools.video import _shared
from tools.video._shared import COGVIDEO_VARIANTS, HUNYUAN_VARIANTS, LTX_LOCAL_VARIANTS


def test_hunyuan_points_at_diffusers_repos_and_classes():
    meta = HUNYUAN_VARIANTS["hunyuan-1.5"]
    assert meta["hf_id"].startswith("hunyuanvideo-community/") and "Diffusers" in meta["hf_id"]
    assert meta["hf_i2v_id"].endswith("_i2v")
    assert meta["pipeline_class"] == "HunyuanVideo15Pipeline"
    assert meta["i2v_pipeline_class"] == "HunyuanVideo15ImageToVideoPipeline"


def test_ltx2_uses_ltx2_pipelines_and_muxes_audio():
    meta = LTX_LOCAL_VARIANTS["ltx2-local"]
    assert meta["pipeline_class"] == "LTX2Pipeline"
    assert meta["i2v_pipeline_class"] == "LTX2ImageToVideoPipeline"
    assert meta["generates_audio"] is True


def test_cogvideo_5b_i2v_has_dedicated_checkpoint():
    meta = COGVIDEO_VARIANTS["cogvideo-5b"]
    assert meta["i2v"] is True
    assert meta["hf_i2v_id"] == "THUDM/CogVideoX-5b-I2V"
    assert meta["i2v_pipeline_class"] == "CogVideoXImageToVideoPipeline"


class _I2VPipeline:
    """Mimics HunyuanVideo15ImageToVideoPipeline: no width/height/frame_rate."""

    def __init__(self):
        self.calls = []

    def __call__(self, image, prompt, num_frames=121, num_inference_steps=50, generator=None):
        self.calls.append(
            {"image": image, "prompt": prompt, "num_frames": num_frames,
             "num_inference_steps": num_inference_steps}
        )
        out = MagicMock()
        out.frames = [["frame"]]
        return out


@pytest.fixture
def fake_runtime(monkeypatch):
    fake_torch = MagicMock()
    fake_diffusers_utils = MagicMock()
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "diffusers", MagicMock(utils=fake_diffusers_utils))
    monkeypatch.setitem(sys.modules, "diffusers.utils", fake_diffusers_utils)
    monkeypatch.setattr(_shared, "probe_output", lambda path: {})
    monkeypatch.setattr(_shared, "load_reference_image", lambda inputs, w, h: "IMG")
    return fake_diffusers_utils


def test_i2v_routes_to_i2v_checkpoint_and_filters_unsupported_args(monkeypatch, fake_runtime, tmp_path):
    pipeline = _I2VPipeline()
    loaded = {}

    def fake_load(pipeline_class, model_id, enable_offload, **kwargs):
        loaded.update(pipeline_class=pipeline_class, model_id=model_id, **kwargs)
        return pipeline

    monkeypatch.setattr(_shared, "load_diffusers_pipeline", fake_load)

    result = _shared.generate_local_video(
        tool_name="hunyuan_video",
        variants=HUNYUAN_VARIANTS,
        default_variant="hunyuan-1.5",
        inputs={
            "prompt": "a fox",
            "operation": "image_to_video",
            "reference_image_path": "ref.png",
            "num_frames": 33,
            "output_path": str(tmp_path / "out.mp4"),
        },
    )

    assert result.success, result.error
    meta = HUNYUAN_VARIANTS["hunyuan-1.5"]
    assert loaded["pipeline_class"] == meta["i2v_pipeline_class"]
    assert loaded["model_id"] == meta["hf_i2v_id"]
    assert loaded["transformer_class"] == meta["transformer_class"]
    # width/height/frame_rate are not accepted by this pipeline and must be dropped.
    assert pipeline.calls == [
        {"image": "IMG", "prompt": "a fox", "num_frames": 33, "num_inference_steps": 30}
    ]
    fake_runtime.export_to_video.assert_called_once()


def test_t2v_keeps_base_checkpoint(monkeypatch, fake_runtime, tmp_path):
    loaded = {}

    def fake_load(pipeline_class, model_id, enable_offload, **kwargs):
        loaded.update(pipeline_class=pipeline_class, model_id=model_id)
        pipe = MagicMock()
        pipe.return_value.frames = [["frame"]]
        return pipe

    monkeypatch.setattr(_shared, "load_diffusers_pipeline", fake_load)

    result = _shared.generate_local_video(
        tool_name="cogvideo_video",
        variants=COGVIDEO_VARIANTS,
        default_variant="cogvideo-5b",
        inputs={"prompt": "a dog", "output_path": str(tmp_path / "out.mp4")},
    )

    assert result.success, result.error
    assert loaded == {"pipeline_class": "CogVideoXPipeline", "model_id": "THUDM/CogVideoX-5b"}
