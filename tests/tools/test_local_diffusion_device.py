"""Regression for #886: local_diffusion ignored Apple Silicon (MPS) and
defaulted to a model id that was removed from the Hugging Face Hub."""

from __future__ import annotations

import sys
import types

import pytest

from tools.graphics.image_gen import ImageGen
from tools.graphics import local_diffusion
from tools.graphics.local_diffusion import LocalDiffusion


@pytest.fixture(autouse=True)
def isolated_pipeline_cache():
    """Each hardware fake owns its pipeline; residency is tested within a case."""
    local_diffusion._PIPELINE_CACHE.clear()
    yield
    local_diffusion._PIPELINE_CACHE.clear()


class _FakePipe:
    def __init__(self, calls):
        self.calls = calls

    def to(self, device):
        self.calls["device"] = device
        return self

    def enable_model_cpu_offload(self):
        self.calls["device"] = "cuda"
        self.calls["cpu_offload"] = True

    def __call__(self, *args, **kwargs):
        image = types.SimpleNamespace(save=lambda path: None)
        return types.SimpleNamespace(images=[image])


def _install_fakes(monkeypatch, *, cuda: bool, mps: bool):
    calls: dict = {}

    torch = types.ModuleType("torch")
    torch.float16 = "float16"
    torch.float32 = "float32"
    torch.cuda = types.SimpleNamespace(
        is_available=lambda: cuda, empty_cache=lambda: None
    )
    torch.backends = types.SimpleNamespace(
        mps=types.SimpleNamespace(is_available=lambda: mps)
    )

    def generator(device):
        # older PyTorch can't create a Generator on MPS
        if device == "mps":
            raise RuntimeError("Device type MPS is not supported for torch.Generator() api.")
        calls["generator_device"] = device
        return types.SimpleNamespace(manual_seed=lambda seed: None)

    torch.Generator = generator

    class Pipeline:
        @staticmethod
        def from_pretrained(model_id, torch_dtype, **kwargs):
            calls["model"] = model_id
            calls["dtype"] = torch_dtype
            calls["variant"] = kwargs.get("variant")
            return _FakePipe(calls)

    diffusers = types.ModuleType("diffusers")
    diffusers.StableDiffusionPipeline = Pipeline
    diffusers.AutoPipelineForText2Image = Pipeline

    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "diffusers", diffusers)
    return calls


@pytest.mark.parametrize(
    ("cuda", "mps", "device", "dtype", "gen_device"),
    [
        (True, True, "cuda", "float16", "cuda"),
        (False, True, "mps", "float16", "cpu"),
        (False, False, "cpu", "float32", "cpu"),
    ],
)
def test_local_diffusion_picks_device(
    monkeypatch, tmp_path, cuda, mps, device, dtype, gen_device
):
    calls = _install_fakes(monkeypatch, cuda=cuda, mps=mps)

    result = LocalDiffusion().execute(
        {"prompt": "a cat", "seed": 1, "output_path": str(tmp_path / "out.png")}
    )

    assert result.success, result.error
    assert calls["device"] == device
    assert calls["generator_device"] == gen_device
    assert calls["dtype"] == dtype
    assert calls.get("cpu_offload", False) is cuda
    assert calls["variant"] == ("fp16" if cuda else None)


def test_local_diffusion_default_model_is_reachable(monkeypatch, tmp_path):
    calls = _install_fakes(monkeypatch, cuda=False, mps=False)

    LocalDiffusion().execute({"prompt": "a cat", "output_path": str(tmp_path / "o.png")})

    assert calls["model"] != "stabilityai/stable-diffusion-2-1-base"
    assert LocalDiffusion.input_schema["properties"]["model"]["default"] == calls["model"]


def test_image_gen_local_backend_uses_mps(monkeypatch, tmp_path):
    calls = _install_fakes(monkeypatch, cuda=False, mps=True)

    ImageGen()._generate_local({"prompt": "a cat", "output_path": str(tmp_path / "o.png")})

    assert calls["device"] == "mps"
    assert calls["dtype"] == "float16"


def test_image_gen_local_backend_seeded_on_mps(monkeypatch, tmp_path):
    calls = _install_fakes(monkeypatch, cuda=False, mps=True)

    result = ImageGen()._generate_local(
        {"prompt": "a cat", "seed": 1, "output_path": str(tmp_path / "o.png")}
    )

    assert result.success, result.error
    assert calls["device"] == "mps"
    assert calls["generator_device"] == "cpu"
