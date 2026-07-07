from lib.variation_checker import check_scene_variation


def _scene(scene_id: str, shot_size: str) -> dict:
    return {
        "id": scene_id,
        "description": f"{scene_id} description",
        "shot_intent": "support story beat",
        "texture_keywords": ["texture"],
        "shot_language": {
            "shot_size": shot_size,
            "camera_movement": "dolly_in",
            "lighting_key": "soft",
        },
    }


def test_non_consecutive_same_size_pairs_do_not_trigger_violation() -> None:
    scenes = [
        _scene("s1", "wide"),
        _scene("s2", "wide"),
        _scene("s3", "cu"),
        _scene("s4", "cu"),
        _scene("s5", "medium"),
        _scene("s6", "medium"),
    ]

    result = check_scene_variation(scenes)

    assert not any("consecutive same-size shots" in violation for violation in result["violations"])


def test_true_run_of_three_same_size_shots_is_flagged() -> None:
    scenes = [
        _scene("s1", "wide"),
        _scene("s2", "wide"),
        _scene("s3", "wide"),
        _scene("s4", "cu"),
    ]

    result = check_scene_variation(scenes)

    assert "3 consecutive same-size shots. Vary shot sizes between scenes for editorial rhythm." in result["violations"]


def test_unspecified_shots_do_not_extend_same_size_run() -> None:
    scenes = [
        _scene("s1", "wide"),
        _scene("s2", "wide"),
        _scene("s3", "unspecified"),
        _scene("s4", "wide"),
        _scene("s5", "wide"),
    ]

    result = check_scene_variation(scenes)

    assert not any("consecutive same-size shots" in violation for violation in result["violations"])
