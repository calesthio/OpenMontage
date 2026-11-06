"""Stickman Pose Library — parametric, extensible poses.

Each pose is a dict with:
  * joint_angles: {joint: radians} (deviations from neutral)
  * default_expression
  * default_view
  * prop_slots: {slot: prop_id or None}
  * description
  * mirrorable: bool
"""

from __future__ import annotations

from lib.stickman_rig import VALID_EXPRESSIONS

# Neutral standing: all zeros.
_NEUTRAL_ANGLES = {
    "torso_lean": 0.0,
    "head_tilt": 0.0,
    "arm_l_shoulder": 0.0,
    "arm_l_elbow": 0.0,
    "arm_r_shoulder": 0.0,
    "arm_r_elbow": 0.0,
    "leg_l_hip": 0.0,
    "leg_l_knee": 0.0,
    "leg_r_hip": 0.0,
    "leg_r_knee": 0.0,
}

import math


def _a(deg: float) -> float:
    return deg * math.pi / 180.0


POSES: dict[str, dict] = {
    "idle": {
        "joint_angles": dict(_NEUTRAL_ANGLES),
        "default_expression": "neutral",
        "default_view": "front",
        "prop_slots": {},
        "description": "Relaxed standing, arms at sides.",
        "mirrorable": True,
    },
    "walking": {
        "joint_angles": {
            **_NEUTRAL_ANGLES,
            "arm_l_shoulder": _a(-25),
            "arm_r_shoulder": _a(25),
            "leg_l_hip": _a(25),
            "leg_l_knee": _a(-15),
            "leg_r_hip": _a(-15),
            "leg_r_knee": _a(10),
        },
        "default_expression": "focused",
        "default_view": "three_quarter",
        "prop_slots": {},
        "description": "Mid-stride walk cycle (frame A).",
        "mirrorable": True,
    },
    "running": {
        "joint_angles": {
            **_NEUTRAL_ANGLES,
            "torso_lean": _a(12),
            "arm_l_shoulder": _a(-60),
            "arm_l_elbow": _a(45),
            "arm_r_shoulder": _a(60),
            "arm_r_elbow": _a(-45),
            "leg_l_hip": _a(45),
            "leg_l_knee": _a(-60),
            "leg_r_hip": _a(-30),
            "leg_r_knee": _a(20),
        },
        "default_expression": "focused",
        "default_view": "three_quarter",
        "prop_slots": {},
        "description": "Dynamic running pose.",
        "mirrorable": True,
    },
    "pointing": {
        "joint_angles": {
            **_NEUTRAL_ANGLES,
            "arm_r_shoulder": _a(-90),
            "arm_r_elbow": _a(0),
            "head_tilt": _a(-5),
        },
        "default_expression": "determined",
        "default_view": "front",
        "prop_slots": {},
        "description": "Right arm extended, pointing.",
        "mirrorable": True,
    },
    "explaining": {
        "joint_angles": {
            **_NEUTRAL_ANGLES,
            "arm_l_shoulder": _a(-30),
            "arm_l_elbow": _a(30),
            "arm_r_shoulder": _a(-70),
            "arm_r_elbow": _a(20),
            "head_tilt": _a(-8),
        },
        "default_expression": "curious",
        "default_view": "front",
        "prop_slots": {},
        "description": "Both hands gesturing, explaining a concept.",
        "mirrorable": True,
    },
    "thinking": {
        "joint_angles": {
            **_NEUTRAL_ANGLES,
            "arm_r_shoulder": _a(-110),
            "arm_r_elbow": _a(90),
            "head_tilt": _a(10),
            "torso_lean": _a(-3),
        },
        "default_expression": "focused",
        "default_view": "three_quarter",
        "prop_slots": {},
        "description": "Chin on hand, head tilted.",
        "mirrorable": True,
    },
    "surprised": {
        "joint_angles": {
            **_NEUTRAL_ANGLES,
            "arm_l_shoulder": _a(-120),
            "arm_l_elbow": _a(30),
            "arm_r_shoulder": _a(-120),
            "arm_r_elbow": _a(-30),
            "torso_lean": _a(-5),
        },
        "default_expression": "surprised",
        "default_view": "front",
        "prop_slots": {},
        "description": "Arms up, open posture.",
        "mirrorable": True,
    },
    "examining": {
        "joint_angles": {
            **_NEUTRAL_ANGLES,
            "arm_r_shoulder": _a(-60),
            "arm_r_elbow": _a(40),
            "head_tilt": _a(15),
            "torso_lean": _a(5),
        },
        "default_expression": "focused",
        "default_view": "three_quarter",
        "prop_slots": {"hand_r": "magnifying_glass"},
        "description": "Holding magnifying glass up to eye.",
        "mirrorable": True,
    },
    "holding": {
        "joint_angles": {
            **_NEUTRAL_ANGLES,
            "arm_r_shoulder": _a(-40),
            "arm_r_elbow": _a(40),
        },
        "default_expression": "neutral",
        "default_view": "front",
        "prop_slots": {"hand_r": None},
        "description": "Right hand forward, palm up, ready to hold a prop.",
        "mirrorable": True,
    },
    "looking_through_lens": {
        "joint_angles": {
            **_NEUTRAL_ANGLES,
            "arm_r_shoulder": _a(-80),
            "arm_r_elbow": _a(30),
            "head_tilt": _a(5),
            "torso_lean": _a(3),
        },
        "default_expression": "focused",
        "default_view": "three_quarter",
        "prop_slots": {"hand_r": "magnifying_glass"},
        "description": "Looking through the magnifying glass.",
        "mirrorable": True,
    },
    "interacting": {
        "joint_angles": {
            **_NEUTRAL_ANGLES,
            "arm_l_shoulder": _a(-20),
            "arm_l_elbow": _a(20),
            "arm_r_shoulder": _a(-50),
            "arm_r_elbow": _a(30),
            "head_tilt": _a(-5),
        },
        "default_expression": "curious",
        "default_view": "front",
        "prop_slots": {"hand_r": None, "hand_l": None},
        "description": "Both hands interacting with a scientific object.",
        "mirrorable": True,
    },
}


def get_pose(pose_id: str) -> dict:
    if pose_id not in POSES:
        raise KeyError(f"unknown pose: {pose_id}")
    return POSES[pose_id]


def mirror_pose(pose: dict) -> dict:
    """Mirror a pose horizontally (swap left/right joints)."""
    import copy
    out = copy.deepcopy(pose)
    ja = out["joint_angles"]
    swaps = [
        ("arm_l_shoulder", "arm_r_shoulder"),
        ("arm_l_elbow", "arm_r_elbow"),
        ("leg_l_hip", "leg_r_hip"),
        ("leg_l_knee", "leg_r_knee"),
    ]
    for a, b in swaps:
        ja[a], ja[b] = ja.get(b, 0.0), ja.get(a, 0.0)
    if out.get("prop_slots"):
        new_slots = {}
        for slot, prop in out["prop_slots"].items():
            if slot == "hand_l":
                new_slots["hand_r"] = prop
            elif slot == "hand_r":
                new_slots["hand_l"] = prop
            else:
                new_slots[slot] = prop
        out["prop_slots"] = new_slots
    return out


def list_poses() -> list[str]:
    return sorted(POSES.keys())


def pose_to_frame(pose_id: str, expression_id: str | None = None, view: str | None = None,
                  props: list[str] | None = None, prop_slots: dict | None = None) -> "RigFrame":
    from lib.stickman_rig import RigFrame
    pose = get_pose(pose_id)
    return RigFrame(
        pose_id=pose_id,
        expression_id=expression_id or pose.get("default_expression", "neutral"),
        view=view or pose.get("default_view", "front"),
        props=props or [],
        prop_slots=prop_slots if prop_slots is not None else dict(pose.get("prop_slots", {})),
    )
