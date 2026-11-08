"""Regression: basicsr-based enhancement tools on current torchvision.

basicsr 1.4.2 imports ``torchvision.transforms.functional_tensor`` (removed in
torchvision 0.17), so ``upscale`` and ``face_restore`` reported UNAVAILABLE
even when installed. face_restore also defaulted to CodeFormer, which the
gfpgan backend cannot build, so every default call failed after downloading
the weights.
"""

from __future__ import annotations

import sys
import types

from tools.enhancement._basicsr_compat import ensure_basicsr_compat
from tools.enhancement.face_restore import FaceRestore


def _install_fake_torchvision(monkeypatch, with_functional_tensor: bool):
    torchvision = types.ModuleType("torchvision")
    transforms = types.ModuleType("torchvision.transforms")
    functional = types.ModuleType("torchvision.transforms.functional")
    functional.rgb_to_grayscale = lambda img, num_output_channels=1: "gray"
    transforms.functional = functional
    torchvision.transforms = transforms
    monkeypatch.setitem(sys.modules, "torchvision", torchvision)
    monkeypatch.setitem(sys.modules, "torchvision.transforms", transforms)
    monkeypatch.setitem(sys.modules, "torchvision.transforms.functional", functional)
    monkeypatch.delitem(sys.modules, "torchvision.transforms.functional_tensor", raising=False)
    if with_functional_tensor:
        legacy = types.ModuleType("torchvision.transforms.functional_tensor")
        legacy.rgb_to_grayscale = "legacy"
        transforms.functional_tensor = legacy
        monkeypatch.setitem(sys.modules, "torchvision.transforms.functional_tensor", legacy)
    return functional


def test_shim_aliases_removed_module(monkeypatch):
    functional = _install_fake_torchvision(monkeypatch, with_functional_tensor=False)

    ensure_basicsr_compat()

    from torchvision.transforms.functional_tensor import rgb_to_grayscale

    assert rgb_to_grayscale is functional.rgb_to_grayscale


def test_shim_leaves_real_module_alone(monkeypatch):
    _install_fake_torchvision(monkeypatch, with_functional_tensor=True)

    ensure_basicsr_compat()

    assert sys.modules["torchvision.transforms.functional_tensor"].rgb_to_grayscale == "legacy"


def test_face_restore_defaults_to_gfpgan():
    schema = FaceRestore.input_schema["properties"]["model"]
    assert schema["default"] == "GFPGAN"


def test_face_restore_rejects_codeformer_before_loading(tmp_path, monkeypatch):
    image = tmp_path / "face.png"
    image.write_bytes(b"not decoded")
    # Fail loudly if the tool tries to import the gfpgan stack for CodeFormer.
    monkeypatch.setitem(sys.modules, "gfpgan", None)

    result = FaceRestore().execute({"input_path": str(image), "model": "CodeFormer"})

    assert result.success is False
    assert "GFPGAN" in result.error
