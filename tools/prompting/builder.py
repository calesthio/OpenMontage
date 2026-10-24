"""Prompt builder for the speculative-evolution niche (AI stills only).

Renders one creature/scene spec (YAML-shaped: subject, anatomy spec with
limb/eye/horn counts, environment, light, style, palette, camera, constraints)
into model-specific prompts for three targets: sdxl, zimage, klein.

Each target supports three variants:
  A = tags        (comma-separated keyword phrases)
  B = prose       (full sentences, standard order)
  C = prose with anatomy first (anatomy details moved to the front)

A negation-style vs positive-style switch controls how the "no text"
constraint is phrased:
  negation  -> "no text, no watermark" style exclusions
  positive  -> "clean image without text, text-free" style inclusions

Pure stdlib + PyYAML. No network. Deterministic: same inputs => same output.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:  # pragma: no cover - yaml is a hard dependency of this module
    import yaml
except Exception:  # pragma: no cover
    yaml = None


# ---------------------------------------------------------------------------
# Deny-list: real people, brands, logos must never be injected into a prompt.
# The builder raises on any subject/anatomy that mentions a deny term, and the
# rendered prompt is re-checked before it is returned.
# ---------------------------------------------------------------------------
_DENY_TERMS: Tuple[str, ...] = (
    # real people / celebrity-ish tokens (must never appear as a subject)
    "elon musk", "beyonce", "tom cruise", "angelina jolie", "brad pitt",
    "taylor swift", "donald trump", "joe biden", "barack obama",
    # brands / logos (must never appear as a subject or be injected)
    "coca-cola", "cocacola", "pepsi", "nike", "adidas", "microsoft",
    "samsung", "tesla", "bmw", "mercedes", "disney", "marvel", "star wars",
    "harry potter", "lego", "playstation", "xbox",
    # word-boundary-safe brand anchors (avoid matching inside other words)
    " apple ", " microsoft ", " google ", " amazon ", " meta ",
    " nike logo", " apple logo",
)


def _contains_deny_term(text: str) -> Optional[str]:
    low = text.lower()
    for term in _DENY_TERMS:
        if term in low:
            return term
    return None


# ---------------------------------------------------------------------------
# Spec model
# ---------------------------------------------------------------------------
@dataclass
class AnatomySpec:
    """Written anatomy of a creature, with counts."""
    limb_count: int
    eye_count: int
    horn_count: int
    dominant_features: List[str] = field(default_factory=list)

    def counts_line(self) -> str:
        return (
            f"{self.limb_count} limbs, {self.eye_count} eyes, "
            f"{self.horn_count} horns"
        )


@dataclass
class CreatureSpec:
    """One creature/scene spec, YAML-shaped."""
    subject: str
    anatomy: AnatomySpec
    environment: str
    light: str
    style: str
    palette: Dict[str, str] = field(default_factory=dict)
    camera: str = ""
    constraints: Dict[str, bool] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: Dict[str, Any]) -> "CreatureSpec":
        anatomy = data.get("anatomy", {}) or {}
        return cls(
            subject=str(data.get("subject", "")),
            anatomy=AnatomySpec(
                limb_count=int(anatomy.get("limb_count", 0)),
                eye_count=int(anatomy.get("eye_count", 0)),
                horn_count=int(anatomy.get("horn_count", 0)),
                dominant_features=list(anatomy.get("dominant_features", []) or []),
            ),
            environment=str(data.get("environment", "")),
            light=str(data.get("light", "")),
            style=str(data.get("style", "")),
            palette={str(k): str(v) for k, v in (data.get("palette") or {}).items()},
            camera=str(data.get("camera", "")),
            constraints={str(k): bool(v) for k, v in (data.get("constraints") or {}).items()},
        )

    @classmethod
    def from_yaml(cls, text: str) -> "CreatureSpec":
        if yaml is None:
            raise RuntimeError("PyYAML is required to load YAML specs")
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError("YAML spec must be a mapping at top level")
        return cls.from_mapping(data)


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------
class PromptBuilder:
    """Render a CreatureSpec into model-specific prompts."""

    # SDXL: structured phrases + a separate negative prompt.
    SDXL_NEGATIVE_DEFAULT = (
        "extra limbs, fused legs, duplicate subject, text, watermark, "
        "photorealism"
    )
    SDXL_GUIDANCE = 7.5
    SDXL_STEPS = 50

    # Z-Image: no negative prompt, guidance 0, 9 steps (per Z-Image-Turbo
    # official guidance; see tools/prompting/SOURCES.md).
    ZIMAGE_GUIDANCE = 0.0
    ZIMAGE_STEPS = 9

    # klein (FLUX.2-klein-4B family): no negative prompt, 4 steps (project
    # configuration; BFL official guide does not prescribe a step count for
    # klein — see tools/prompting/SOURCES.md).
    KLEIN_STEPS = 4

    # Output length bounds (characters).
    MIN_PROMPT_LEN = 10
    MAX_PROMPT_LEN = 1200

    def __init__(self, seed: int = 4000):
        self.seed = seed

    # -- public API -------------------------------------------------------
    def build(
        self,
        target: str,
        variant: str,
        spec: CreatureSpec,
        negation_style: bool = False,
    ) -> Dict[str, Any]:
        """Render one prompt dict.

        Returns a dict with keys: target, variant, prompt, negative_prompt,
        guidance_scale, steps, seed, negation_style.
        negative_prompt is a str for sdxl, None for zimage/klein.
        """
        target = target.lower()
        variant = variant.upper()
        if target not in {"sdxl", "zimage", "klein"}:
            raise ValueError(f"unknown target: {target!r}")
        if variant not in {"A", "B", "C"}:
            raise ValueError(f"unknown variant: {variant!r}")

        self._validate_spec(spec)

        parts = self._parts(spec)
        prompt = self._render(target, variant, parts, spec, negation_style)
        self._check_no_deny_terms(prompt)
        self._check_length(prompt)

        negative_prompt: Optional[str] = None
        guidance = None
        steps = None
        if target == "sdxl":
            negative_prompt = self.SDXL_NEGATIVE_DEFAULT
            guidance = self.SDXL_GUIDANCE
            steps = self.SDXL_STEPS
        elif target == "zimage":
            guidance = self.ZIMAGE_GUIDANCE
            steps = self.ZIMAGE_STEPS
        elif target == "klein":
            steps = self.KLEIN_STEPS

        return {
            "target": target,
            "variant": variant,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "guidance_scale": guidance,
            "steps": steps,
            "seed": self.seed,
            "negation_style": bool(negation_style),
        }

    # -- internals --------------------------------------------------------
    def _validate_spec(self, spec: CreatureSpec) -> None:
        if not spec.subject.strip():
            raise ValueError("subject is required")
        deny = _contains_deny_term(spec.subject)
        if deny:
            raise ValueError(f"subject contains denied term: {deny!r}")
        for feat in spec.anatomy.dominant_features:
            deny = _contains_deny_term(feat)
            if deny:
                raise ValueError(f"dominant feature contains denied term: {deny!r}")
        if spec.anatomy.limb_count < 0 or spec.anatomy.eye_count < 0 or spec.anatomy.horn_count < 0:
            raise ValueError("anatomy counts must be non-negative")

    def _parts(self, spec: CreatureSpec) -> Dict[str, str]:
        palette = ", ".join(f"{k} {v}" for k, v in spec.palette.items())
        return {
            "subject": spec.subject.strip(),
            "anatomy": spec.anatomy.counts_line(),
            "features": ", ".join(spec.anatomy.dominant_features),
            "environment": spec.environment.strip(),
            "light": spec.light.strip(),
            "style": spec.style.strip(),
            "palette": palette,
            "camera": spec.camera.strip(),
            "counts": spec.anatomy.counts_line(),
        }

    def _no_text_phrase(self, negation_style: bool) -> str:
        if negation_style:
            return "no text, no watermark, no letters, no numerals"
        return (
            "clean image without text, text-free, no letters, no numerals, "
            "no watermark"
        )

    def _render(
        self,
        target: str,
        variant: str,
        p: Dict[str, str],
        spec: CreatureSpec,
        negation_style: bool,
    ) -> str:
        no_text = self._no_text_phrase(negation_style)
        style_phrase = f"{p['style']}" if p["style"] else "flat-vector field-guide plate"
        palette_phrase = f", {p['palette']}" if p["palette"] else ""
        anatomy_phrase = f"{p['counts']}; {p['features']}".strip("; ") if p["features"] else p["counts"]

        if target == "sdxl":
            return self._render_sdxl(variant, p, style_phrase, palette_phrase, anatomy_phrase, no_text)
        if target == "zimage":
            return self._render_zimage(variant, p, style_phrase, palette_phrase, anatomy_phrase, no_text)
        return self._render_klein(variant, p, style_phrase, palette_phrase, anatomy_phrase, no_text)

    def _render_sdxl(
        self,
        variant: str,
        p: Dict[str, str],
        style_phrase: str,
        palette_phrase: str,
        anatomy_phrase: str,
        no_text: str,
    ) -> str:
        # SDXL: structured keyword phrases. Variant A tags; B/C prose-ish but
        # still phrase-based for SDXL.
        chunks = [
            p["subject"],
            anatomy_phrase,
            p["environment"],
            p["light"],
            style_phrase,
            palette_phrase,
            p["camera"],
            no_text,
            "not photorealistic",
            "no people",
            "no logos",
        ]
        body = ", ".join(c for c in chunks if c)
        if variant == "A":
            return body
        if variant == "B":
            return f"{p['subject']}, {anatomy_phrase}, in {p['environment']}, {p['light']}, {style_phrase}{palette_phrase}. {no_text}, not photorealistic, no people, no logos."
        # C: anatomy first
        return f"{anatomy_phrase}; {p['subject']}, in {p['environment']}, {p['light']}, {style_phrase}{palette_phrase}. {no_text}, not photorealistic, no people, no logos."

    def _render_zimage(
        self,
        variant: str,
        p: Dict[str, str],
        style_phrase: str,
        palette_phrase: str,
        anatomy_phrase: str,
        no_text: str,
    ) -> str:
        # Z-Image: descriptive prose, style stated FIRST, 3-5 key visual
        # concepts, constraints phrased positively, no negative prompt.
        lead = (
            f"A {style_phrase} field-guide plate. {p['subject']} "
            f"with {anatomy_phrase}."
        )
        concepts = [
            f"set in {p['environment']}",
            f"lit by {p['light']}",
            f"{palette_phrase.strip(', ')}" if p["palette"] else f"rendered in {style_phrase}",
        ]
        concepts = [c for c in concepts if c][:5]
        body = ". ".join(concepts)
        if variant == "A":
            # tags-style but still a single descriptive string for zimage
            return (
                f"{style_phrase}, {p['subject']}, {anatomy_phrase}, "
                f"{p['environment']}, {p['light']}, {no_text}, "
                f"not photorealistic, no people, no logos{palette_phrase}"
            )
        if variant == "B":
            return f"{lead} {body}. {no_text}, not photorealistic, no people, no logos."
        # C: anatomy first
        return (
            f"{anatomy_phrase} on {p['subject']}. {lead} {body}. "
            f"{no_text}, not photorealistic, no people, no logos."
        )

    def _render_klein(
        self,
        variant: str,
        p: Dict[str, str],
        style_phrase: str,
        palette_phrase: str,
        anatomy_phrase: str,
        no_text: str,
    ) -> str:
        # klein: narrative prose, subject + anatomy in the FIRST sentence,
        # constraints positively, no negative prompt, 4 steps.
        first = f"{p['subject']} has {anatomy_phrase}."
        rest = (
            f"It is shown {p['environment']}, {p['light']}, in a "
            f"{style_phrase}{palette_phrase}. {p['camera']} "
            f"{no_text}, not photorealistic, no people, no logos."
        )
        if variant == "A":
            return (
                f"{p['subject']}, {anatomy_phrase}, {p['environment']}, "
                f"{p['light']}, {style_phrase}{palette_phrase}, {no_text}, "
                f"not photorealistic, no people, no logos"
            )
        if variant == "B":
            return f"{first} {rest}"
        # C: anatomy first (already anatomy-forward; lead with counts)
        return (
            f"{anatomy_phrase}. {first} {rest}"
        )

    # -- checks -----------------------------------------------------------
    def _check_no_deny_terms(self, prompt: str) -> None:
        deny = _contains_deny_term(prompt)
        if deny:
            raise ValueError(f"rendered prompt contains denied term: {deny!r}")

    def _check_length(self, prompt: str) -> None:
        n = len(prompt)
        if n < self.MIN_PROMPT_LEN:
            raise ValueError(f"prompt too short ({n} chars < {self.MIN_PROMPT_LEN})")
        if n > self.MAX_PROMPT_LEN:
            raise ValueError(f"prompt too long ({n} chars > {self.MAX_PROMPT_LEN})")
