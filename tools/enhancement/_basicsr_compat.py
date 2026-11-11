"""Compatibility shim for basicsr on current torchvision.

basicsr 1.4.2 (pulled in by realesrgan and gfpgan) imports
``torchvision.transforms.functional_tensor``, which torchvision removed in
0.17. Without the shim ``import realesrgan`` / ``import gfpgan`` raise
ImportError, so the tools report UNAVAILABLE even when installed.
"""

from __future__ import annotations

import sys
import types


def ensure_basicsr_compat() -> None:
    """Alias the removed torchvision module before importing basicsr users."""
    try:
        import torchvision.transforms.functional_tensor  # noqa: F401
        return
    except ImportError:
        pass
    try:
        from torchvision.transforms import functional
    except ImportError:
        return  # torchvision missing; let the real import fail normally
    shim = types.ModuleType("torchvision.transforms.functional_tensor")
    shim.rgb_to_grayscale = functional.rgb_to_grayscale
    sys.modules["torchvision.transforms.functional_tensor"] = shim
