"""Tests for local_diffusion's pipeline loading: AutoPipeline (SD 1.x/2.x and SDXL),
fp16 variant with fallback on CUDA, CPU offload, and the single-model pipeline cache
(reuse across batch calls, release on model switch). diffusers/torch are faked, so no
weights are downloaded and no GPU is needed."""

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.graphics import local_diffusion
from tools.graphics.local_diffusion import LocalDiffusion

SDXL = "stabilityai/stable-diffusion-xl-base-1.0"
SD15 = "runwayml/stable-diffusion-v1-5"


def _fake_torch(cuda: bool):
    torch = types.ModuleType("torch")
    torch.cuda = types.SimpleNamespace(is_available=lambda: cuda, empty_cache=MagicMock())
    torch.float16 = "float16"
    torch.float32 = "float32"
    torch.Generator = MagicMock()
    return torch


def _fake_pipe(name: str = "pipe"):
    pipe = MagicMock(name=name)
    image = MagicMock(name="image")
    image.save.side_effect = lambda p: Path(p).write_bytes(b"PNG")
    pipe.return_value.images = [image]
    pipe.to.return_value = pipe
    return pipe


@pytest.fixture
def fakes(monkeypatch, tmp_path):
    """Install fake torch/diffusers modules; yields the AutoPipeline class, pipe, etc."""
    local_diffusion._PIPELINE_CACHE.clear()
    pipe = _fake_pipe()
    auto = MagicMock(name="AutoPipelineForText2Image")
    auto.from_pretrained.return_value = pipe
    diffusers = types.ModuleType("diffusers")
    diffusers.AutoPipelineForText2Image = auto
    monkeypatch.setitem(sys.modules, "diffusers", diffusers)
    state = types.SimpleNamespace(auto=auto, pipe=pipe, out=tmp_path, torch=None)

    def use_cuda(flag: bool):
        state.torch = _fake_torch(flag)
        monkeypatch.setitem(sys.modules, "torch", state.torch)

    state.use_cuda = use_cuda
    use_cuda(False)
    yield state
    local_diffusion._PIPELINE_CACHE.clear()


def _run(fakes, **over):
    inputs = {"prompt": "a red fox", "output_path": str(fakes.out / "img.png"),
              "model": SDXL, **over}
    return LocalDiffusion().execute(inputs)


def test_cpu_loads_fp32_moves_to_cpu_and_writes_image(fakes):
    res = _run(fakes, seed=7)
    assert res.success, res.error
    fakes.auto.from_pretrained.assert_called_once_with(SDXL, torch_dtype="float32")
    fakes.pipe.to.assert_called_once_with("cpu")
    fakes.pipe.enable_model_cpu_offload.assert_not_called()
    assert Path(res.data["output"]).is_file()
    assert res.model == SDXL
    assert res.seed == 7


def test_same_model_is_reused_across_batch_calls(fakes):
    assert _run(fakes).success
    assert _run(fakes).success
    assert _run(fakes).success
    assert fakes.auto.from_pretrained.call_count == 1
    assert list(local_diffusion._PIPELINE_CACHE) == [SDXL]


def test_switching_models_releases_the_previous_pipeline(fakes):
    fakes.use_cuda(True)
    first, second, third = _fake_pipe("sdxl"), _fake_pipe("sd15"), _fake_pipe("sdxl-again")
    fakes.auto.from_pretrained.side_effect = [first, second, third]

    assert _run(fakes, model=SDXL).success
    assert _run(fakes, model=SD15).success
    # Only the active model stays resident; the previous one had its offload hooks
    # removed and the CUDA cache was flushed.
    assert list(local_diffusion._PIPELINE_CACHE) == [SD15]
    assert local_diffusion._PIPELINE_CACHE[SD15] is second
    first.remove_all_hooks.assert_called_once_with()
    second.remove_all_hooks.assert_not_called()
    assert fakes.torch.cuda.empty_cache.called

    # Coming back to the first model reloads it: nothing was retained.
    assert _run(fakes, model=SDXL).success
    assert fakes.auto.from_pretrained.call_count == 3
    assert list(local_diffusion._PIPELINE_CACHE) == [SDXL]
    second.remove_all_hooks.assert_called_once_with()


def test_release_tolerates_pipelines_without_hooks(fakes):
    bare = types.SimpleNamespace()  # no remove_all_hooks attribute at all
    local_diffusion._PIPELINE_CACHE["old/model"] = bare
    local_diffusion._release_cached_pipelines(fakes.torch)
    assert local_diffusion._PIPELINE_CACHE == {}


def test_cuda_loads_fp16_variant_with_cpu_offload(fakes):
    fakes.use_cuda(True)
    assert _run(fakes).success
    fakes.auto.from_pretrained.assert_called_once_with(SDXL, torch_dtype="float16", variant="fp16")
    fakes.pipe.enable_model_cpu_offload.assert_called_once_with()
    fakes.pipe.to.assert_not_called()


def test_cuda_falls_back_when_repo_has_no_fp16_variant(fakes):
    fakes.use_cuda(True)
    fakes.auto.from_pretrained.side_effect = [OSError("no fp16 variant"), fakes.pipe]
    assert _run(fakes).success
    calls = fakes.auto.from_pretrained.call_args_list
    assert calls[0].kwargs == {"torch_dtype": "float16", "variant": "fp16"}
    assert calls[1].kwargs == {"torch_dtype": "float16"}
    assert fakes.pipe.enable_model_cpu_offload.called


def test_generation_error_is_reported_not_raised(fakes):
    fakes.pipe.side_effect = RuntimeError("CUDA out of memory")
    res = _run(fakes)
    assert res.success is False
    assert "CUDA out of memory" in res.error
