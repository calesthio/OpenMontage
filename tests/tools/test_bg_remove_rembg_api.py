"""Regression tests for the rembg call signature used by the bg_remove tool.

rembg's ``remove()`` selects a model via ``session=``, not ``model_name=``.
Passing ``model_name=`` lands in ``**kwargs``, which rembg forwards to
``new_session(*args, **kwargs)`` — where it collides with that function's own
first positional parameter and raises::

    TypeError: new_session() got multiple values for argument 'model_name'

These tests pin the calling convention so the tool cannot regress to the
broken form.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest


@pytest.fixture()
def fake_rembg(monkeypatch):
    """Inject a fake rembg exposing remove() and new_session()."""
    fake = MagicMock()
    fake.new_session.return_value = "fake-session"
    monkeypatch.setitem(sys.modules, "rembg", fake)
    return fake


@pytest.fixture()
def source_image(tmp_path):
    """A real on-disk image, so only rembg is faked."""
    from PIL import Image

    path = tmp_path / "input.png"
    Image.new("RGB", (8, 8), (10, 20, 30)).save(path)
    return path


def _run(fake_rembg, source_image, tmp_path, **extra):
    from tools.enhancement.bg_remove import BgRemove

    inputs = {"input_path": str(source_image), "output_path": str(tmp_path / "out.png")}
    inputs.update(extra)
    return BgRemove().execute(inputs)


def test_bg_remove_passes_session_not_model_name(fake_rembg, source_image, tmp_path):
    """remove() must receive session=; model_name= would raise inside rembg."""
    result = _run(fake_rembg, source_image, tmp_path)

    assert result.success is True, result.error
    fake_rembg.remove.assert_called_once()
    kwargs = fake_rembg.remove.call_args.kwargs
    assert "model_name" not in kwargs, (
        "model_name= falls through to new_session() and raises TypeError"
    )
    assert kwargs["session"] == "fake-session"


def test_bg_remove_builds_session_from_requested_model(fake_rembg, source_image, tmp_path):
    """The chosen model must reach new_session(), not be silently dropped."""
    _run(fake_rembg, source_image, tmp_path, model="isnet-general-use")

    fake_rembg.new_session.assert_called_once_with("isnet-general-use")


def test_bg_remove_defaults_to_u2net(fake_rembg, source_image, tmp_path):
    """Default model is u2net when none is requested."""
    _run(fake_rembg, source_image, tmp_path)

    fake_rembg.new_session.assert_called_once_with("u2net")
