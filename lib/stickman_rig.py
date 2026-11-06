"""Stickman Rig v1 — original SVG character rig for OpenMontage.

Programmatic, vector-based, no per-pose image generation. Provides:
  * RigProfile (proportions, signature detail, palette)
  * Pose / Expression / Prop definitions
  * Forward kinematics + SVG emission
  * Keyframe validation
  * Content-addressed cache key helper

Zero-cost: pure Python + SVG strings. No rendering, no network, no credits.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Constants / defaults
# ---------------------------------------------------------------------------

SIGNATURE_DETAIL_ID = "magnifying_lens"

DEFAULT_PROPORTIONS: dict[str, float] = {
    "head_diameter": 1.0,
    "torso": 1.6,
    "upper_arm": 0.7,
    "forearm": 0.7,
    "thigh": 0.8,
    "shin": 0.8,
    "foot": 0.35,
    "hand": 0.25,
}

VALID_VIEWS = ("front", "three_quarter", "profile", "back")
VALID_EXPRESSIONS = (
    "neutral", "curious", "surprised", "determined", "concerned",
    "happy", "frustrated", "focused",
)

KEYFRAME_FIELDS = ("x", "y", "angle", "scaleX", "scaleY", "alpha", "progress", "w")

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class RigProfile:
    rig_id: str
    character_id: str
    display_name: str = "Researcher"
    proportions: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_PROPORTIONS))
    signature_detail_id: str = SIGNATURE_DETAIL_ID
    accent_color: str = "#2a9d8f"
    ink_color: str = "#1f2320"
    min_height_heads: float = 4.0
    max_height_heads: float = 4.5
    allowed_poses: list[str] = field(default_factory=list)
    allowed_expressions: list[str] = field(default_factory=lambda: list(VALID_EXPRESSIONS))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def total_height_heads(self) -> float:
        p = self.proportions
        # head + torso + (thigh+shin) approximated in head units
        return 1.0 + p["torso"] / p["head_diameter"] + (p["thigh"] + p["shin"]) / p["head_diameter"] * 0.5

    def validate(self) -> list[str]:
        issues: list[str] = []
        p = self.proportions
        for k in ("head_diameter", "torso", "upper_arm", "forearm", "thigh", "shin"):
            if p.get(k, 0) <= 0:
                issues.append(f"invalid proportion: {k}")
        if self.signature_detail_id != SIGNATURE_DETAIL_ID:
            issues.append(f"unexpected signature detail: {self.signature_detail_id}")
        if self.min_height_heads > self.max_height_heads:
            issues.append("min_height_heads > max_height_heads")
        return issues


@dataclass
class RigFrame:
    """One static pose of the rig."""
    pose_id: str
    expression_id: str = "neutral"
    view: str = "front"
    props: list[str] = field(default_factory=list)  # prop ids attached
    prop_slots: dict[str, str] = field(default_factory=dict)  # slot -> prop_id
    overrides: dict[str, float] = field(default_factory=dict)  # joint angle overrides
    motivated_hold: bool = False
    signature_detail_present: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self, profile: RigProfile, pose_library: dict[str, Any]) -> list[str]:
        issues: list[str] = []
        if self.pose_id not in pose_library:
            issues.append(f"unknown pose: {self.pose_id}")
        if profile.allowed_poses and self.pose_id not in profile.allowed_poses:
            issues.append(f"pose not allowed by profile: {self.pose_id}")
        if self.expression_id not in VALID_EXPRESSIONS:
            issues.append(f"unknown expression: {self.expression_id}")
        if profile.allowed_expressions and self.expression_id not in profile.allowed_expressions:
            issues.append(f"expression not allowed by profile: {self.expression_id}")
        if self.view not in VALID_VIEWS:
            issues.append(f"unknown view: {self.view}")
        if not self.signature_detail_present:
            issues.append("missing signature detail (magnifying lens)")
        return issues


@dataclass
class Keyframe:
    t: float
    values: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"t": self.t, **self.values}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Keyframe":
        t = float(d["t"])
        vals = {k: float(v) for k, v in d.items() if k != "t"}
        return cls(t=t, values=vals)


@dataclass
class RigMotionEvent:
    """Per-part keyframe track for one shot."""
    part_id: str
    keyframes: list[Keyframe] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"part_id": self.part_id, "keyframes": [k.to_dict() for k in self.keyframes]}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RigMotionEvent":
        return cls(
            part_id=d["part_id"],
            keyframes=[Keyframe.from_dict(k) for k in d.get("keyframes", [])],
        )


# ---------------------------------------------------------------------------
# Forward kinematics
# ---------------------------------------------------------------------------


def _positions(frame: RigFrame, pose: dict[str, Any], profile: RigProfile) -> dict[str, tuple[float, float]]:
    """Compute joint positions in rig space (origin at hip, Y down)."""
    p = profile.proportions
    T = p["torso"]
    U = p["upper_arm"]
    F = p["forearm"]
    Hl = p["thigh"]
    Sh = p["shin"]

    angles = dict(pose.get("joint_angles", {}))
    angles.update(frame.overrides or {})

    torso_lean = angles.get("torso_lean", 0.0)
    head_tilt = angles.get("head_tilt", 0.0)
    al_s = angles.get("arm_l_shoulder", 0.0)
    al_e = angles.get("arm_l_elbow", 0.0)
    ar_s = angles.get("arm_r_shoulder", 0.0)
    ar_e = angles.get("arm_r_elbow", 0.0)
    ll_h = angles.get("leg_l_hip", 0.0)
    ll_k = angles.get("leg_l_knee", 0.0)
    lr_h = angles.get("leg_r_hip", 0.0)
    lr_k = angles.get("leg_r_knee", 0.0)

    import math

    def rot(v, a):
        x, y = v
        return (x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a))

    hip = (0.0, 0.0)
    neck = (hip[0] + rot((0.0, -T), torso_lean)[0],
            hip[1] + rot((0.0, -T), torso_lean)[1])
    shoulder = (hip[0] + rot((0.0, -T * 0.9), torso_lean)[0],
                hip[1] + rot((0.0, -T * 0.9), torso_lean)[1])
    head_center = (neck[0] + rot((0.0, -0.9), torso_lean + head_tilt)[0],
                   neck[1] + rot((0.0, -0.9), torso_lean + head_tilt)[1])

    # left arm
    elbow_l = (shoulder[0] + rot((0.0, U), torso_lean + al_s)[0],
               shoulder[1] + rot((0.0, U), torso_lean + al_s)[1])
    wrist_l = (elbow_l[0] + rot((0.0, F), torso_lean + al_s + al_e)[0],
               elbow_l[1] + rot((0.0, F), torso_lean + al_s + al_e)[1])
    # right arm
    elbow_r = (shoulder[0] + rot((0.0, U), torso_lean + ar_s)[0],
               shoulder[1] + rot((0.0, U), torso_lean + ar_s)[1])
    wrist_r = (elbow_r[0] + rot((0.0, F), torso_lean + ar_s + ar_e)[0],
               elbow_r[1] + rot((0.0, F), torso_lean + ar_s + ar_e)[1])

    # legs
    knee_l = (hip[0] + rot((0.0, Hl), ll_h)[0],
              hip[1] + rot((0.0, Hl), ll_h)[1])
    ankle_l = (knee_l[0] + rot((0.0, Sh), ll_h + ll_k)[0],
               knee_l[1] + rot((0.0, Sh), ll_h + ll_k)[1])
    knee_r = (hip[0] + rot((0.0, Hl), lr_h)[0],
              hip[1] + rot((0.0, Hl), lr_h)[1])
    ankle_r = (knee_r[0] + rot((0.0, Sh), lr_h + lr_k)[0],
               knee_r[1] + rot((0.0, Sh), lr_h + lr_k)[1])

    return {
        "hip": hip,
        "neck": neck,
        "shoulder": shoulder,
        "head": head_center,
        "elbow_l": elbow_l,
        "wrist_l": wrist_l,
        "elbow_r": elbow_r,
        "wrist_r": wrist_r,
        "knee_l": knee_l,
        "ankle_l": ankle_l,
        "knee_r": knee_r,
        "ankle_r": ankle_r,
    }


# ---------------------------------------------------------------------------
# SVG emission
# ---------------------------------------------------------------------------


def _svg_line(x1, y1, x2, y2, stroke, width=2.5):
    return f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{stroke}" stroke-width="{width}" stroke-linecap="round"/>'


def _svg_circle(cx, cy, r, stroke, fill="none", width=2.5):
    return f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" stroke="{stroke}" stroke-width="{width}" fill="{fill}"/>'


def emit_svg(
    frame: RigFrame,
    pose: dict[str, Any],
    profile: RigProfile,
    *,
    canvas_w: int = 400,
    canvas_h: int = 600,
    scale: float = 40.0,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
) -> str:
    """Emit an SVG string for one rig frame."""
    ink = profile.ink_color
    accent = profile.accent_color
    p = profile.proportions
    hd = p["head_diameter"]
    head_r = hd / 2.0 * scale * 0.5  # visual
    # use head_diameter as radius unit
    head_radius = (hd * scale) / 2.0

    pos = _positions(frame, pose, profile)
    # scale + center
    def S(pt):
        return (pt[0] * scale + canvas_w / 2.0 + offset_x,
                pt[1] * scale + canvas_h / 2.0 + offset_y)

    hip = S(pos["hip"])
    neck = S(pos["neck"])
    shoulder = S(pos["shoulder"])
    head = S(pos["head"])
    elbow_l = S(pos["elbow_l"])
    wrist_l = S(pos["wrist_l"])
    elbow_r = S(pos["elbow_r"])
    wrist_r = S(pos["wrist_r"])
    knee_l = S(pos["knee_l"])
    ankle_l = S(pos["ankle_l"])
    knee_r = S(pos["knee_r"])
    ankle_r = S(pos["ankle_r"])

    parts: list[str] = []
    # torso
    parts.append(_svg_line(hip[0], hip[1], neck[0], neck[1], ink))
    # head
    parts.append(_svg_circle(head[0], head[1], head_radius, ink))
    # face (expression)
    parts.append(_face_svg(head[0], head[1], head_radius, frame.expression_id, ink, frame.view))
    # signature detail: magnifying lens on right temple
    if frame.signature_detail_present:
        lens_cx = head[0] + head_radius * 0.55
        lens_cy = head[1] - head_radius * 0.15
        parts.append(_svg_circle(lens_cx, lens_cy, head_radius * 0.35, accent, fill="none", width=2.0))
        parts.append(_svg_line(lens_cx + head_radius * 0.25, lens_cy + head_radius * 0.25,
                               lens_cx + head_radius * 0.7, lens_cy + head_radius * 0.7, accent, width=2.0))
    # arms
    parts.append(_svg_line(shoulder[0], shoulder[1], elbow_l[0], elbow_l[1], ink))
    parts.append(_svg_line(elbow_l[0], elbow_l[1], wrist_l[0], wrist_l[1], ink))
    parts.append(_svg_circle(wrist_l[0], wrist_l[1], 3, ink, fill=ink))
    parts.append(_svg_line(shoulder[0], shoulder[1], elbow_r[0], elbow_r[1], ink))
    parts.append(_svg_line(elbow_r[0], elbow_r[1], wrist_r[0], wrist_r[1], ink))
    parts.append(_svg_circle(wrist_r[0], wrist_r[1], 3, ink, fill=ink))
    # legs
    parts.append(_svg_line(hip[0], hip[1], knee_l[0], knee_l[1], ink))
    parts.append(_svg_line(knee_l[0], knee_l[1], ankle_l[0], ankle_l[1], ink))
    parts.append(_svg_line(hip[0], hip[1], knee_r[0], knee_r[1], ink))
    parts.append(_svg_line(knee_r[0], knee_r[1], ankle_r[0], ankle_r[1], ink))

    # props
    for slot, prop_id in (frame.prop_slots or {}).items():
        anchor = _slot_anchor(slot, pos, S)
        parts.append(_prop_svg(prop_id, anchor[0], anchor[1], scale, accent, ink))

    # view-based horizontal flip for 'back'
    transform = ""
    if frame.view == "back":
        transform = f'transform="scale(-1,1)" transform-origin="{canvas_w/2} {canvas_h/2}"'

    body = "\n".join(parts)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="{canvas_h}" '
        f'viewBox="0 0 {canvas_w} {canvas_h}">\n'
        f'<g {transform}>\n{body}\n</g>\n</svg>'
    )


def _face_svg(cx, cy, r, expression, ink, view):
    # eyes
    eye_y = cy - r * 0.15
    lx = cx - r * 0.3
    rx = cx + r * 0.3
    parts = []
    # brows
    brow_y = cy - r * 0.45
    if expression in ("concerned", "frustrated", "focused"):
        parts.append(f'<line x1="{lx-r*0.15:.2f}" y1="{brow_y+r*0.1:.2f}" x2="{lx+r*0.15:.2f}" y2="{brow_y-r*0.1:.2f}" stroke="{ink}" stroke-width="1.5"/>')
        parts.append(f'<line x1="{rx-r*0.15:.2f}" y1="{brow_y-r*0.1:.2f}" x2="{rx+r*0.15:.2f}" y2="{brow_y+r*0.1:.2f}" stroke="{ink}" stroke-width="1.5"/>')
    elif expression in ("surprised", "happy"):
        parts.append(f'<line x1="{lx-r*0.15:.2f}" y1="{brow_y:.2f}" x2="{lx+r*0.15:.2f}" y2="{brow_y-r*0.15:.2f}" stroke="{ink}" stroke-width="1.5"/>')
        parts.append(f'<line x1="{rx-r*0.15:.2f}" y1="{brow_y-r*0.15:.2f}" x2="{rx+r*0.15:.2f}" y2="{brow_y:.2f}" stroke="{ink}" stroke-width="1.5"/>')
    else:
        parts.append(f'<line x1="{lx-r*0.15:.2f}" y1="{brow_y:.2f}" x2="{lx+r*0.15:.2f}" y2="{brow_y:.2f}" stroke="{ink}" stroke-width="1.5"/>')
        parts.append(f'<line x1="{rx-r*0.15:.2f}" y1="{brow_y:.2f}" x2="{rx+r*0.15:.2f}" y2="{brow_y:.2f}" stroke="{ink}" stroke-width="1.5"/>')
    # eyes
    if expression == "focused":
        parts.append(f'<circle cx="{lx:.2f}" cy="{eye_y:.2f}" r="2" fill="{ink}"/>')
        parts.append(f'<circle cx="{rx:.2f}" cy="{eye_y:.2f}" r="2" fill="{ink}"/>')
    else:
        parts.append(f'<circle cx="{lx:.2f}" cy="{eye_y:.2f}" r="2.5" fill="{ink}"/>')
        parts.append(f'<circle cx="{rx:.2f}" cy="{eye_y:.2f}" r="2.5" fill="{ink}"/>')
    # mouth
    mouth_y = cy + r * 0.25
    if expression in ("happy", "excited" if False else "happy"):
        parts.append(f'<path d="M {cx-r*0.3:.2f} {mouth_y:.2f} Q {cx:.2f} {mouth_y+r*0.35:.2f} {cx+r*0.3:.2f} {mouth_y:.2f}" stroke="{ink}" stroke-width="1.5" fill="none"/>')
    elif expression in ("surprised",):
        parts.append(f'<circle cx="{cx:.2f}" cy="{mouth_y:.2f}" r="{r*0.15:.2f}" stroke="{ink}" stroke-width="1.5" fill="none"/>')
    elif expression in ("concerned", "frustrated"):
        parts.append(f'<path d="M {cx-r*0.3:.2f} {mouth_y+r*0.15:.2f} Q {cx:.2f} {mouth_y-r*0.2:.2f} {cx+r*0.3:.2f} {mouth_y+r*0.15:.2f}" stroke="{ink}" stroke-width="1.5" fill="none"/>')
    elif expression == "focused":
        parts.append(f'<line x1="{cx-r*0.25:.2f}" y1="{mouth_y:.2f}" x2="{cx+r*0.25:.2f}" y2="{mouth_y:.2f}" stroke="{ink}" stroke-width="1.5"/>')
    else:
        parts.append(f'<line x1="{cx-r*0.2:.2f}" y1="{mouth_y:.2f}" x2="{cx+r*0.2:.2f}" y2="{mouth_y:.2f}" stroke="{ink}" stroke-width="1.5"/>')
    return "\n".join(parts)


def _slot_anchor(slot, pos, S):
    if slot == "hand_r":
        return S(pos["wrist_r"])
    if slot == "hand_l":
        return S(pos["wrist_l"])
    if slot == "head_lens":
        return S(pos["head"])
    return S(pos["hip"])


_PROP_SHAPES = {
    "magnifying_glass": lambda x, y, s, accent, ink: (
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{s*0.6:.2f}" stroke="{accent}" stroke-width="2" fill="none"/>'
        f'<line x1="{x+s*0.4:.2f}" y1="{y+s*0.4:.2f}" x2="{x+s*0.9:.2f}" y2="{y+s*0.9:.2f}" stroke="{ink}" stroke-width="2" stroke-linecap="round"/>'
    ),
    "flask": lambda x, y, s, accent, ink: (
        f'<path d="M {x-s*0.2:.2f} {y-s*0.6:.2f} L {x-s*0.2:.2f} {y+s*0.1:.2f} L {x-s*0.5:.2f} {y+s*0.6:.2f} L {x+s*0.5:.2f} {y+s*0.6:.2f} L {x+s*0.2:.2f} {y+s*0.1:.2f} L {x+s*0.2:.2f} {y-s*0.6:.2f} Z" stroke="{ink}" stroke-width="2" fill="none"/>'
    ),
    "book": lambda x, y, s, accent, ink: (
        f'<rect x="{x-s*0.4:.2f}" y="{y-s*0.25:.2f}" width="{s*0.8:.2f}" height="{s*0.5:.2f}" stroke="{ink}" stroke-width="2" fill="none"/>'
    ),
    "atom": lambda x, y, s, accent, ink: (
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{s*0.15:.2f}" fill="{accent}"/>'
        f'<ellipse cx="{x:.2f}" cy="{y:.2f}" rx="{s*0.5:.2f}" ry="{s*0.2:.2f}" stroke="{ink}" stroke-width="1.5" fill="none"/>'
    ),
    "dna": lambda x, y, s, accent, ink: (
        f'<path d="M {x-s*0.3:.2f} {y-s*0.6:.2f} Q {x+s*0.3:.2f} {y:.2f} {x-s*0.3:.2f} {y+s*0.6:.2f}" stroke="{accent}" stroke-width="2" fill="none"/>'
        f'<path d="M {x+s*0.3:.2f} {y-s*0.6:.2f} Q {x-s*0.3:.2f} {y:.2f} {x+s*0.3:.2f} {y+s*0.6:.2f}" stroke="{ink}" stroke-width="2" fill="none"/>'
    ),
}


def _prop_svg(prop_id, x, y, scale, accent, ink):
    s = scale * 0.5
    fn = _PROP_SHAPES.get(prop_id)
    if fn is None:
        return f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="{accent}"/>'
    return fn(x, y, s, accent, ink)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def validate_keyframes(part_id: str, keyframes: list[dict[str, Any]] | list[Keyframe]) -> list[str]:
    issues: list[str] = []
    prev_t = -1.0
    for kf in keyframes:
        t = kf.t if isinstance(kf, Keyframe) else float(kf.get("t", 0))
        if t <= prev_t and prev_t >= 0:
            # allow first
            if prev_t >= 0 and t <= prev_t and len(keyframes) > 1:
                # strict increasing except single
                pass
        vals = kf.values if isinstance(kf, Keyframe) else {k: v for k, v in kf.items() if k != "t"}
        if t < 0:
            issues.append(f"{part_id}: negative key time {t}")
        for k in vals:
            if k not in KEYFRAME_FIELDS:
                issues.append(f"{part_id}: unsupported keyframe field {k}")
            try:
                float(vals[k])
            except (TypeError, ValueError):
                issues.append(f"{part_id}: non-numeric value for {k}")
        prev_t = t
    # increasing check
    ts = [ (kf.t if isinstance(kf, Keyframe) else float(kf.get("t", 0))) for kf in keyframes ]
    for i in range(1, len(ts)):
        if not (ts[i] > ts[i - 1]):
            issues.append(f"{part_id}: key times must be strictly increasing")
            break
    return issues


def validate_rig_motion_events(events: list[RigMotionEvent] | list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    if not isinstance(events, list):
        return ["events must be a list"]
    for e in events:
        ev = e if isinstance(e, RigMotionEvent) else RigMotionEvent.from_dict(e)
        issues.extend(validate_keyframes(ev.part_id, ev.keyframes))
        if not ev.keyframes:
            issues.append(f"{ev.part_id}: empty keyframe track")
    return issues


def rig_cache_key(frame: RigFrame, pose: dict[str, Any]) -> str:
    import hashlib, json
    payload = json.dumps({"frame": frame.to_dict(), "pose": pose}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Cache key helper (content-addressed)
# ---------------------------------------------------------------------------


def content_addressed_key(parts: dict[str, Any]) -> str:
    import hashlib, json
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()
