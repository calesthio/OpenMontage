"""Tests for Apple Silicon MPS / device resolution helper.

These tests mock at sys.modules level so they run without torch installed.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest


@pytest.fixture()
def mock_torch():
    """Inject a fake torch module into sys.modules for the duration of a test."""
    fake = MagicMock()
    # Restore whatever was there before (real torch, or nothing)
    previous = sys.modules.get("torch", None)
    sys.modules["torch"] = fake
    yield fake
    if previous is None:
        sys.modules.pop("torch", None)
    else:
        sys.modules["torch"] = previous


# ------------------------------------------------------------------
# get_torch_device — basic routing
# ------------------------------------------------------------------

def test_get_torch_device_returns_mps_when_cuda_absent(mock_torch):
    """mps is used when cuda is unavailable but mps is available."""
    mock_torch.cuda.is_available.return_value = False
    mock_torch.backends.mps.is_built.return_value = True
    mock_torch.backends.mps.is_available.return_value = True

    from tools.video._shared import get_torch_device
    assert get_torch_device() == "mps"


def test_get_torch_device_returns_cpu_as_fallback(mock_torch):
    """cpu is the final fallback when neither cuda nor mps is available."""
    mock_torch.cuda.is_available.return_value = False
    mock_torch.backends.mps.is_built.return_value = True
    mock_torch.backends.mps.is_available.return_value = False

    from tools.video._shared import get_torch_device
    assert get_torch_device() == "cpu"


def test_get_torch_device_returns_cuda_when_available(mock_torch):
    """cuda takes priority over mps when both are present."""
    mock_torch.cuda.is_available.return_value = True
    mock_torch.backends.mps.is_built.return_value = True
    mock_torch.backends.mps.is_available.return_value = True

    from tools.video._shared import get_torch_device
    assert get_torch_device() == "cuda"


def test_get_torch_device_returns_cpu_when_torch_not_installed():
    """cpu is returned safely when torch cannot be imported."""
    previous = sys.modules.pop("torch", None)
    try:
        # Make torch unimportable
        sys.modules["torch"] = None  # type: ignore[assignment]
        from tools.video._shared import get_torch_device
        assert get_torch_device() == "cpu"
    finally:
        if previous is None:
            sys.modules.pop("torch", None)
        else:
            sys.modules["torch"] = previous


# ------------------------------------------------------------------
# get_torch_device — MPS guard (torch.backends.mps missing)
# ------------------------------------------------------------------

def test_get_torch_device_cpu_when_mps_backend_missing(mock_torch):
    """Falls back to cpu when torch.backends.mps does not exist (e.g. Linux wheels)."""
    mock_torch.cuda.is_available.return_value = False
    # Simulate a torch build without mps backend
    del mock_torch.backends.mps

    from tools.video._shared import get_torch_device
    assert get_torch_device() == "cpu"


def test_get_torch_device_cpu_when_mps_not_built(mock_torch):
    """Falls back to cpu when MPS is not built into torch."""
    mock_torch.cuda.is_available.return_value = False
    mock_torch.backends.mps.is_built.return_value = False
    mock_torch.backends.mps.is_available.return_value = False

    from tools.video._shared import get_torch_device
    assert get_torch_device() == "cpu"


# ------------------------------------------------------------------
# load_diffusers_pipeline — device and dtype routing
# ------------------------------------------------------------------

def _make_pipeline_mocks(monkeypatch, *, cuda=False, mps=False, bf16=False):
    """Helper: inject fake torch + diffusers and return the pipeline mock."""
    import importlib

    fake_torch = MagicMock()
    fake_torch.cuda.is_available.return_value = cuda
    fake_torch.cuda.is_bf16_supported.return_value = bf16
    fake_torch.backends.mps.is_built.return_value = mps
    fake_torch.backends.mps.is_available.return_value = mps
    fake_torch.float16 = "float16"
    fake_torch.float32 = "float32"
    fake_torch.bfloat16 = "bfloat16"

    fake_pipeline_instance = MagicMock()
    fake_pipeline_class = MagicMock()
    fake_pipeline_class.from_pretrained = MagicMock(return_value=fake_pipeline_instance)
    fake_diffusers = MagicMock()
    fake_diffusers.LTXPipeline = fake_pipeline_class

    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "diffusers", fake_diffusers)

    from tools.video import _shared
    importlib.reload(_shared)

    return _shared, fake_pipeline_class, fake_pipeline_instance


def test_load_diffusers_pipeline_routes_to_mps(monkeypatch):
    """load_diffusers_pipeline must call .to('mps') on Apple Silicon when offload is off."""
    _shared, fake_cls, fake_inst = _make_pipeline_mocks(monkeypatch, mps=True)

    _shared.load_diffusers_pipeline("LTXPipeline", "Lightricks/LTX-Video", enable_offload=False)

    fake_inst.to.assert_called_once_with("mps")
    # MPS should use float16 (not bfloat16, not float32)
    fake_cls.from_pretrained.assert_called_once_with(
        "Lightricks/LTX-Video", torch_dtype="float16"
    )


def test_load_diffusers_pipeline_offload_falls_back_on_mps(monkeypatch):
    """enable_offload=True on MPS must NOT call enable_model_cpu_offload() — it's CUDA-only."""
    _shared, _, fake_inst = _make_pipeline_mocks(monkeypatch, mps=True)

    _shared.load_diffusers_pipeline("LTXPipeline", "Lightricks/LTX-Video", enable_offload=True)

    # Must NOT call enable_model_cpu_offload() on MPS
    fake_inst.enable_model_cpu_offload.assert_not_called()
    # Must fall back to .to("mps")
    fake_inst.to.assert_called_once_with("mps")


def test_load_diffusers_pipeline_cpu_uses_float32(monkeypatch):
    """CPU fallback must use float32 — float16 is emulated and unreliable on CPU."""
    _shared, fake_cls, fake_inst = _make_pipeline_mocks(monkeypatch)  # neither cuda nor mps

    _shared.load_diffusers_pipeline("LTXPipeline", "Lightricks/LTX-Video", enable_offload=False)

    fake_inst.to.assert_called_once_with("cpu")
    fake_cls.from_pretrained.assert_called_once_with(
        "Lightricks/LTX-Video", torch_dtype="float32"
    )


# ------------------------------------------------------------------
# install_instructions — Apple Silicon guidance
# ------------------------------------------------------------------

def test_upscale_install_instructions_mentions_apple_silicon():
    """install_instructions must not tell M-series users they need CUDA."""
    from tools.enhancement.upscale import Upscale
    tool = Upscale()
    inst = tool.install_instructions
    assert "MPS" in inst or "Apple" in inst or "macOS" in inst, (
        f"install_instructions is CUDA-only, misleads Apple Silicon users: {inst!r}"
    )


@pytest.mark.parametrize("module_path,class_name", [
    ("tools.enhancement.face_restore", "FaceRestore"),
    ("tools.video.ltx_video_local", "LTXVideoLocal"),
])
def test_local_gpu_tool_mentions_apple_silicon(module_path, class_name):
    """Every LOCAL_GPU tool must tell users MPS/Apple Silicon works."""
    import importlib
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    tool = cls()
    inst = tool.install_instructions
    assert "MPS" in inst or "Apple" in inst or "macOS" in inst, (
        f"{class_name}.install_instructions has no Apple Silicon guidance: {inst!r}"
    )


# ------------------------------------------------------------------
# upscale.py — signature guard for device=
# ------------------------------------------------------------------

def test_upscale_build_upsampler_uses_signature_guard(monkeypatch):
    """_build_upsampler must use inspect to check if RealESRGANer accepts device=."""
    import importlib
    import inspect

    fake_torch = MagicMock()
    fake_torch.device = lambda x: f"device({x})"

    fake_rrdbnet = MagicMock()

    # Build a fake RealESRGANer whose __init__ DOES accept device=
    class FakeRealESRGANer:
        def __init__(self, *, scale, model_path, model, dni_weight, half, device=None):
            self.called_with_device = device
    fake_realesrganer_cls = FakeRealESRGANer

    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    basicsr_mock = MagicMock()
    basicsr_mock.archs.rrdbnet_arch.RRDBNet = fake_rrdbnet
    monkeypatch.setitem(sys.modules, "basicsr", basicsr_mock)
    monkeypatch.setitem(sys.modules, "basicsr.archs", basicsr_mock.archs)
    monkeypatch.setitem(sys.modules, "basicsr.archs.rrdbnet_arch", basicsr_mock.archs.rrdbnet_arch)

    realesrgan_mock = MagicMock()
    realesrgan_mock.RealESRGANer = fake_realesrganer_cls
    monkeypatch.setitem(sys.modules, "realesrgan", realesrgan_mock)

    fake_shared = MagicMock()
    monkeypatch.setitem(sys.modules, "tools.video._shared", fake_shared)
    fake_shared.get_torch_device.return_value = "mps"

    from tools.enhancement import upscale
    importlib.reload(upscale)

    tool = upscale.Upscale()
    result = tool._build_upsampler(scale=4, model_name="RealESRGAN_x4plus", denoise_strength=0.5, face_enhance=False)
    assert result.called_with_device == "device(mps)"


def test_upscale_build_upsampler_skips_device_when_unsupported(monkeypatch):
    """_build_upsampler must NOT pass device= if the installed version doesn't accept it."""
    import importlib

    fake_torch = MagicMock()
    fake_torch.device = lambda x: f"device({x})"

    fake_rrdbnet = MagicMock()

    # Build a fake RealESRGANer whose __init__ does NOT accept device=
    class FakeRealESRGANerNoDevice:
        def __init__(self, *, scale, model_path, model, dni_weight, half):
            self.called_with_device = None  # no device param
    fake_realesrganer_cls = FakeRealESRGANerNoDevice

    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    basicsr_mock = MagicMock()
    basicsr_mock.archs.rrdbnet_arch.RRDBNet = fake_rrdbnet
    monkeypatch.setitem(sys.modules, "basicsr", basicsr_mock)
    monkeypatch.setitem(sys.modules, "basicsr.archs", basicsr_mock.archs)
    monkeypatch.setitem(sys.modules, "basicsr.archs.rrdbnet_arch", basicsr_mock.archs.rrdbnet_arch)

    realesrgan_mock = MagicMock()
    realesrgan_mock.RealESRGANer = fake_realesrganer_cls
    monkeypatch.setitem(sys.modules, "realesrgan", realesrgan_mock)

    fake_shared = MagicMock()
    monkeypatch.setitem(sys.modules, "tools.video._shared", fake_shared)
    fake_shared.get_torch_device.return_value = "mps"

    from tools.enhancement import upscale
    importlib.reload(upscale)

    tool = upscale.Upscale()
    # Should NOT raise TypeError about unexpected keyword argument 'device'
    result = tool._build_upsampler(scale=4, model_name="RealESRGAN_x4plus", denoise_strength=0.5, face_enhance=False)
    assert result.called_with_device is None


# ------------------------------------------------------------------
# face_restore.py — signature guard and device routing
# ------------------------------------------------------------------

def test_face_restore_uses_signature_guard(monkeypatch):
    """FaceRestore must use inspect to check if GFPGANer accepts device=."""
    import importlib

    fake_cv2 = MagicMock()
    fake_cv2.imread.return_value = "fake_image_data"
    fake_cv2.imwrite.return_value = True

    fake_torch = MagicMock()
    fake_torch.device = lambda x: f"device({x})"

    fake_rrdbnet = MagicMock()

    # GFPGANer that DOES accept device=
    class FakeGFPGANer:
        def __init__(self, *, model_path, upscale, arch, bg_upsampler=None, device=None):
            self.called_with_device = device
        def enhance(self, img, **kwargs):
            return (None, [1], "fake_restored")

    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    basicsr_mock = MagicMock()
    basicsr_mock.archs.rrdbnet_arch.RRDBNet = fake_rrdbnet
    monkeypatch.setitem(sys.modules, "basicsr", basicsr_mock)
    monkeypatch.setitem(sys.modules, "basicsr.archs", basicsr_mock.archs)
    monkeypatch.setitem(sys.modules, "basicsr.archs.rrdbnet_arch", basicsr_mock.archs.rrdbnet_arch)

    realesrgan_mock = MagicMock()
    monkeypatch.setitem(sys.modules, "realesrgan", realesrgan_mock)

    gfpgan_mock = MagicMock()
    gfpgan_mock.GFPGANer = FakeGFPGANer
    monkeypatch.setitem(sys.modules, "gfpgan", gfpgan_mock)

    fake_shared = MagicMock()
    fake_shared.get_torch_device.return_value = "mps"
    monkeypatch.setitem(sys.modules, "tools.video._shared", fake_shared)

    from tools.enhancement import face_restore
    importlib.reload(face_restore)

    from pathlib import Path
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "mkdir", lambda self, *a, **kw: None)

    tool = face_restore.FaceRestore()
    result = tool.execute({"input_path": "dummy.png"})
    assert result.success is True
