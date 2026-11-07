"""Music dramaturgy — per-scene music cues by narrative state (V8 §3.7).

Music is NOT one continuous drone for 15–20 minutes.  Instead it is
placed by dramatic state, with per-phase volume and character:

  hook          — minimum music, silence / low drone so the phrase reads
  mystery       — gradual build (scientific question)
  discovery     — investigative dynamics (story of discovery)
  explanation   — music steps back; voice and diagram come forward
  speculation   — indeterminate atmosphere (unknown / speculative)
  resolution    — tension release
  finale        — musical punctuation, not an abrupt cut

Music and SFX carry their own rights ledger.  Archive.org is not an
automatic free-use license.

Zero-cost: no generation, just volume/ducking parameters for the mixer.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

# V8 §3.7: music phases mapped to narrative roles.
MUSIC_PHASES = frozenset({
    "hook",
    "mystery",
    "discovery",
    "explanation",
    "speculation",
    "resolution",
    "finale",
})

# Default music volume (dB relative to narration) per phase.
# Lower = quieter.  Narration must always stay intelligible.
MUSIC_VOLUME_DB = {
    "hook": -30.0,        # near silence
    "mystery": -18.0,     # subtle build
    "discovery": -15.0,   # investigative dynamics
    "explanation": -24.0, # steps back for voice + diagram
    "speculation": -20.0, # indeterminate atmosphere
    "resolution": -16.0,  # tension release
    "finale": -12.0,      # musical punctuation
}

# Default fade duration per phase (seconds).
MUSIC_FADE_S = {
    "hook": 2.0,
    "mystery": 4.0,
    "discovery": 3.0,
    "explanation": 3.0,
    "speculation": 4.0,
    "resolution": 3.0,
    "finale": 2.0,
}

# Map narrative_role (from ScenePlan / SceneManifest) to music phase.
ROLE_TO_PHASE = {
    "establish_context": "hook",
    "introduce_subject": "mystery",
    "build_tension": "mystery",
    "deliver_payload": "discovery",
    "transition": "explanation",
    "emotional_beat": "resolution",
    "evidence": "explanation",
    "comparison": "discovery",
    "resolution": "resolution",
    "call_to_action": "finale",
}


@dataclass
class MusicCue:
    """One music cue for a scene — volume, phase, fade."""

    phase: str  # one of MUSIC_PHASES
    volume_db: float  # dB relative to narration
    fade_in_s: float
    fade_out_s: float
    enabled: bool  # False = no music for this scene (silence/low drone)
    rights_basis: str | None = None  # explicit_license | source_policy_us_gov | ...
    source_url: str | None = None
    credit: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> list[str]:
        problems: list[str] = []
        if self.phase not in MUSIC_PHASES:
            problems.append(f"invalid music phase {self.phase!r}; "
                            f"valid: {sorted(MUSIC_PHASES)}")
        if self.enabled and not self.rights_basis:
            problems.append("music enabled but no rights_basis recorded")
        return problems


@dataclass
class MusicPlan:
    """Complete per-scene music plan for one episode."""

    episode_id: str
    cues: dict[str, MusicCue] = None  # scene_id -> MusicCue
    created_at: str = ""

    def __post_init__(self) -> None:
        if self.cues is None:
            self.cues = {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "cues": {sid: c.to_dict() for sid, c in self.cues.items()},
            "created_at": self.created_at,
        }

    def validate(self) -> list[str]:
        problems: list[str] = []
        for sid, cue in self.cues.items():
            for p in cue.validate():
                problems.append(f"{sid}: {p}")
        return problems


def phase_for_role(narrative_role: str) -> str:
    """Map a narrative role to a music phase (V8 §3.7)."""
    return ROLE_TO_PHASE.get(narrative_role, "explanation")


def cue_for_scene(
    scene_id: str,
    narrative_role: str,
    *,
    music_available: bool = False,
    rights_basis: str | None = None,
    source_url: str | None = None,
    credit: str | None = None,
) -> MusicCue:
    """Build a MusicCue for one scene.

    If no licensed music is available, the cue is disabled (silence / low
    drone per V8 §3.7 hook/finale guidance).
    """
    phase = phase_for_role(narrative_role)
    enabled = bool(music_available and rights_basis)
    return MusicCue(
        phase=phase,
        volume_db=MUSIC_VOLUME_DB[phase],
        fade_in_s=MUSIC_FADE_S[phase],
        fade_out_s=MUSIC_FADE_S[phase],
        enabled=enabled,
        rights_basis=rights_basis,
        source_url=source_url,
        credit=credit,
    )


def music_volume_for_phase(phase: str) -> float:
    """Return the default music volume (dB) for a phase."""
    return MUSIC_VOLUME_DB.get(phase, -24.0)


def fade_for_phase(phase: str) -> tuple[float, float]:
    """Return (fade_in_s, fade_out_s) for a phase."""
    f = MUSIC_FADE_S.get(phase, 3.0)
    return f, f
