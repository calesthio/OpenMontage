"""Regression: a provider's code-level model default must match its schema's
declared `model.default`.

Bug: runway_video and higgsfield_video hardcoded stale model defaults in
estimate_cost/estimate_runtime/execute (`gen4_turbo` / `kling_3.0`) while the
schema advertised `seedance_2.0` as the premium default. Omitting `model` then
quoted the wrong (cheap) model's cost and silently generated a different model
than the schema promised — a Decision-Communication / cost-accuracy violation.
"""

import pytest

import tools.video.higgsfield_video as higgsfield_video
import tools.video.runway_video as runway_video
from tools.video.higgsfield_video import HiggsFieldVideo
from tools.video.runway_video import RunwayVideo


@pytest.mark.parametrize(
    "tool_cls, module",
    [(RunwayVideo, runway_video), (HiggsFieldVideo, higgsfield_video)],
)
def test_default_model_constant_matches_schema(tool_cls, module):
    # `execute()` reads `model` via `_DEFAULT_MODEL`; locking the constant to the
    # schema default guards the silent-model-swap path without a network call.
    schema_default = tool_cls().input_schema["properties"]["model"]["default"]
    assert module._DEFAULT_MODEL == schema_default


@pytest.mark.parametrize("tool_cls", [RunwayVideo, HiggsFieldVideo])
def test_estimate_default_model_matches_schema(tool_cls):
    tool = tool_cls()
    schema_default = tool.input_schema["properties"]["model"]["default"]

    # Cost/runtime with `model` omitted must equal the schema's declared default,
    # not some stale hardcoded fallback.
    assert tool.estimate_cost({}) == tool.estimate_cost({"model": schema_default}), (
        f"{tool.name}.estimate_cost default model diverges from schema default "
        f"{schema_default!r}"
    )
    assert tool.estimate_runtime({}) == tool.estimate_runtime({"model": schema_default}), (
        f"{tool.name}.estimate_runtime default model diverges from schema default "
        f"{schema_default!r}"
    )
