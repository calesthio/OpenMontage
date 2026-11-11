"""jimeng_video estimates what execute() would submit.

``duration`` is read only when ``frames`` is omitted (10 s or more -> 241
frames, shorter -> 121). The estimate has to follow the same mapping: the
budget cap in tools/base_tool.py refuses a paid call on ``estimate_cost``, so a
10-second clip estimated at the 5-second price slips past a cap it does not
fit. No provider is called here.
"""

from __future__ import annotations

import pytest

from tools.video.jimeng_video import JimengVideo


@pytest.fixture()
def tool() -> JimengVideo:
    return JimengVideo()


def test_duration_10_estimates_like_241_frames(tool: JimengVideo) -> None:
    assert tool.estimate_cost({"prompt": "x", "duration": 10}) == tool.estimate_cost(
        {"prompt": "x", "frames": 241}
    )
    assert tool.estimate_runtime({"prompt": "x", "duration": 10}) == tool.estimate_runtime(
        {"prompt": "x", "frames": 241}
    )


def test_duration_10_costs_more_than_duration_5(tool: JimengVideo) -> None:
    assert tool.estimate_cost({"prompt": "x", "duration": 10}) > tool.estimate_cost(
        {"prompt": "x", "duration": 5}
    )


def test_string_duration_behaves_like_int(tool: JimengVideo) -> None:
    # video_selector passes duration through as a string ("5", "10").
    assert tool.estimate_cost({"prompt": "x", "duration": "10"}) == tool.estimate_cost(
        {"prompt": "x", "duration": 10}
    )
    assert tool.estimate_runtime({"prompt": "x", "duration": "10"}) == tool.estimate_runtime(
        {"prompt": "x", "duration": 10}
    )


def test_frames_wins_over_duration(tool: JimengVideo) -> None:
    assert tool.estimate_cost({"prompt": "x", "frames": 121, "duration": 10}) == tool.estimate_cost(
        {"prompt": "x", "frames": 121}
    )
    assert tool.estimate_runtime(
        {"prompt": "x", "frames": 121, "duration": 10}
    ) == tool.estimate_runtime({"prompt": "x", "frames": 121})


def test_no_length_input_estimates_the_5s_default(tool: JimengVideo) -> None:
    assert tool.estimate_cost({"prompt": "x"}) == tool.estimate_cost({"prompt": "x", "frames": 121})


@pytest.mark.parametrize(
    "inputs",
    [
        {"prompt": "x"},
        {"prompt": "x", "duration": 5},
        {"prompt": "x", "duration": 9},
        {"prompt": "x", "duration": 10},
        {"prompt": "x", "duration": "12"},
        {"prompt": "x", "frames": 241, "duration": 5},
        {"prompt": "x", "frames": 121, "duration": 10},
    ],
)
def test_estimate_prices_the_frames_execute_submits(tool: JimengVideo, inputs: dict) -> None:
    submitted = JimengVideo._build_payload(inputs)["frames"]
    assert tool.estimate_cost(inputs) == tool.estimate_cost({"prompt": "x", "frames": submitted})
    assert tool.estimate_runtime(inputs) == tool.estimate_runtime({"prompt": "x", "frames": submitted})
