"""Regression tests for CLIP feature unwrapping across transformers versions.

transformers < 5 returned a plain tensor from ``get_text_features()`` and
``get_image_features()``. 5.x returns a ``BaseModelOutputWithPooling`` whose
``pooler_output`` already holds the projected, shared-space embedding. The
embedder called ``.norm()`` directly on the result, so on 5.x every embed
raised::

    AttributeError: 'BaseModelOutputWithPooling' object has no attribute 'norm'

That failure is silent at the pipeline level — `corpus_builder` counts each
candidate as merely "failed" and keeps downloading — so it is worth pinning.

These tests exercise the pure-Python unwrap helper and need neither torch nor
a downloaded model.
"""

from __future__ import annotations

from lib.clip_embedder import _as_feature_tensor


class _FakeTensor:
    """Stands in for a torch tensor: notably has no ``pooler_output``."""

    def __init__(self, tag: str = "tensor") -> None:
        self.tag = tag


class _FakeModelOutput:
    """Stands in for transformers' BaseModelOutputWithPooling."""

    def __init__(self, pooler_output, last_hidden_state=None) -> None:
        self.pooler_output = pooler_output
        self.last_hidden_state = last_hidden_state


def test_plain_tensor_passes_through_unchanged():
    """transformers 4.x path: a bare tensor must be returned as-is."""
    t = _FakeTensor()
    assert _as_feature_tensor(t) is t


def test_model_output_is_unwrapped_to_pooler_output():
    """transformers 5.x path: unwrap to pooler_output, the projected embedding."""
    pooled = _FakeTensor("pooled")
    out = _FakeModelOutput(pooler_output=pooled, last_hidden_state=_FakeTensor("hidden"))
    assert _as_feature_tensor(out) is pooled


def test_last_hidden_state_is_not_used():
    """last_hidden_state is per-token and the wrong rank — never select it."""
    hidden = _FakeTensor("hidden")
    out = _FakeModelOutput(pooler_output=_FakeTensor("pooled"), last_hidden_state=hidden)
    assert _as_feature_tensor(out) is not hidden


def test_output_without_pooler_output_falls_back_to_itself():
    """Unknown wrapper shapes must not raise; degrade to the object itself."""

    class _Bare:
        pass

    obj = _Bare()
    assert _as_feature_tensor(obj) is obj


def test_none_pooler_output_falls_back_to_the_object():
    """A present-but-None pooler_output must not be returned as the features."""
    out = _FakeModelOutput(pooler_output=None)
    assert _as_feature_tensor(out) is out
