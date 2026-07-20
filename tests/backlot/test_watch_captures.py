"""Tests for the Backlot dogfood screenshot watcher helpers."""

from scripts.backlot_watch_captures import capture_slug, state_fingerprint


def test_capture_slug_keeps_names_filesystem_safe():
    assert capture_slug("why-cities-glow", "scene_plan", "awaiting_human") == (
        "why-cities-glow-scene_plan-awaiting_human"
    )
    assert capture_slug("../bad id", "C:\\stage", "in progress!") == "bad-id-C-stage-in-progress"


def test_state_fingerprint_changes_on_board_relevant_state_only():
    state = {
        "stages": [
            {"name": "script", "status": "completed", "partial_progress": None},
            {"name": "assets", "status": "in_progress", "partial_progress": {"done": ["sc1"]}},
        ],
        "storyboard": {
            "scenes": [
                {
                    "id": "sc1",
                    "generating": False,
                    "visual": {"path": "assets/images/sc1.png", "exists": True},
                    "takes": [{"path": "assets/images/sc1.png"}],
                },
                {"id": "sc2", "generating": True, "generating_tool": "flux_image", "visual": None},
            ]
        },
        "cost": {"total_spent_usd": 0.1},
        "media": {"renders": []},
        "events": [{"event": "start", "tool": "flux_image"}],
        "last_activity": 123,
    }
    same = dict(state)
    same["last_activity"] = 999

    changed = dict(state)
    changed["storyboard"] = {
        "scenes": [
            state["storyboard"]["scenes"][0],
            {"id": "sc2", "generating": False, "visual": {"path": "assets/images/sc2.png", "exists": True}},
        ]
    }

    assert state_fingerprint(state) == state_fingerprint(same)
    assert state_fingerprint(state) != state_fingerprint(changed)
