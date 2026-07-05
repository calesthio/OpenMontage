from lib.delivery_promise import PromiseType, classify_from_brief


def test_classify_from_brief_source_led_reclassification_clears_motion_requirement() -> None:
    promise = classify_from_brief("talking-head", {"has_footage": True})

    assert promise.promise_type == PromiseType.SOURCE_LED
    assert promise.source_required is True
    assert promise.motion_required is False


def test_classify_from_brief_explicit_motion_override_survives_reclassification() -> None:
    promise = classify_from_brief(
        "talking-head",
        {"has_footage": True, "motion_required": True},
    )

    assert promise.promise_type == PromiseType.SOURCE_LED
    assert promise.motion_required is True


def test_classify_from_brief_avatar_defaults_stay_motion_required_without_footage() -> None:
    promise = classify_from_brief("talking-head", {})

    assert promise.promise_type == PromiseType.AVATAR_PRESENTER
    assert promise.motion_required is True
