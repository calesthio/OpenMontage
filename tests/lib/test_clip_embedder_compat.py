from lib.clip_embedder import _as_feature_tensor


class _Tensor:
    pass


class _ModelOutput:
    def __init__(self, pooler_output):
        self.pooler_output = pooler_output
        self.last_hidden_state = object()


def test_transformers_4_tensor_passes_through() -> None:
    tensor = _Tensor()
    assert _as_feature_tensor(tensor) is tensor


def test_transformers_5_output_unwraps_projected_pooler_output() -> None:
    tensor = _Tensor()
    assert _as_feature_tensor(_ModelOutput(tensor)) is tensor


def test_missing_pooler_output_does_not_replace_features_with_none() -> None:
    output = _ModelOutput(None)
    assert _as_feature_tensor(output) is output
