#!/usr/bin/env python3
"""tools/illustration/image_brief.py - the image brief step.

From a script (markdown beats with claim ids) and the claim ledger, derive
ONE image prompt per visual beat, tagged KNOWN / INFERENCE / SPECULATION.

The brief is the contract between the script and the image engine:

  script.md + claim_ledger.md + niche specs + style.json + locked model
        -> image_brief.json  (one entry per visual beat)

Rules:
  * the prompt text is built by tools/prompting (OpenCode-owned, READ ONLY),
  * the anatomy counts of a creature are always in its prompt,
  * a beat whose claim is not in the ledger is an error (fail closed),
  * a beat that no subject can be derived for is recorded as skipped,
  * the brief is deterministic: same inputs -> same bytes.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from tools.illustration.model_registry import ModelAdapter
from tools.illustration.style_kit import StyleSpec
from tools.prompting.builder import PromptBuilder

try:  # pragma: no cover - yaml is a hard dependency of the builder
    import yaml
except Exception:  # pragma: no cover
    yaml = None

#: The three evidence classes of an image.
TAGS: Tuple[str, ...] = ("KNOWN", "INFERENCE", "SPECULATION")

#: Ledger source types that count as real (documented) science.
REAL_SOURCE_TYPES: Tuple[str, ...] = ("TWO", "SINGLE")

#: Hedge words: a hedged statement about a real place is an inference.
HEDGES: Tuple[str, ...] = (
    "may", "might", "could", "would", "perhaps", "possibly", "plausible",
    "unproven", "we do not know", "not yet", "if ", "should",
)

_STOP_WORDS = set("""
a an the of and or in on at to for with without from into over under is are was
were be been it its they their this that these those there here what which who
whom whose than then as by could may might must shall should will would can
not no nor only own same so too very just more most some such each few other
another new old one two three many much both either none all any per every
into out up down again further once because while during before after above
below we our us their his her them us me my i you your he she
""".split())

_BEAT_RE = re.compile(r"^-\s+(?P<text>.*?)\s*(?:\[(?P<claims>[^\]]*)\])?\s*$")
_CLAIM_RE = re.compile(r"^(?P<id>[A-Z]{1,4}-\d+)\s*$")


class ImageBriefError(RuntimeError):
    """The brief cannot be built (unknown beat, unknown claim, bad input)."""


@dataclass(frozen=True)
class Beat:
    beat_id: str
    chapter: str
    text: str
    claim_ids: Tuple[str, ...]


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9']+", text.lower())
            if len(w) >= 3 and w not in _STOP_WORDS}


def _same_word(a: str, b: str) -> bool:
    """Loose word match: a 6-character prefix, a 4-character prefix for short
    words, or an exact match. ("creating" must not match "creature")."""
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    if len(short) >= 6:
        return short[:6] == long[:6]
    if len(short) >= 4:
        return short[:4] == long[:4]
    return a == b


def _score(words: set[str], keywords: set[str]) -> int:
    return sum(1 for w in words for k in keywords if _same_word(w, k))


def parse_script(text: str) -> List[Beat]:
    """Parse the script markdown into beats (one per bullet line)."""
    beats: List[Beat] = []
    chapter = ""
    for line in text.splitlines():
        if line.startswith("## "):
            chapter = line[3:].strip()
            continue
        match = _BEAT_RE.match(line)
        if not match:
            continue
        body = (match.group("text") or "").strip()
        if not body:
            continue
        raw_claims = match.group("claims") or ""
        claim_ids = tuple(c.strip() for c in raw_claims.split(",") if c.strip())
        beats.append(Beat(f"b{len(beats) + 1:03d}", chapter, body, claim_ids))
    if not beats:
        raise ImageBriefError("the script has no beats")
    return beats


def parse_ledger(text: str) -> Dict[str, Dict[str, Any]]:
    """Parse the claim ledger markdown table."""
    claims: Dict[str, Dict[str, Any]] = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 5:
            continue
        if not _CLAIM_RE.match(cells[0]):
            continue
        claims[cells[0]] = {
            "claim": cells[1],
            "source_type": cells[3],
            "evidence_notes": cells[4],
        }
    if not claims:
        raise ImageBriefError("the claim ledger has no claim rows")
    return claims


def _load_specs(spec_dir: Path) -> List[Dict[str, Any]]:
    if yaml is None:
        raise ImageBriefError("PyYAML is required to read the niche specs")
    if not spec_dir.is_dir():
        raise ImageBriefError(f"spec directory not found: {spec_dir}")
    specs = []
    for path in sorted(spec_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not data.get("name"):
            raise ImageBriefError(f"{path}: not a creature spec mapping")
        data["_source"] = str(path)
        specs.append(data)
    if not specs:
        raise ImageBriefError(f"no specs in {spec_dir}")
    return specs


def _spec_keywords(spec: Dict[str, Any]) -> set[str]:
    keywords = _tokens(str(spec.get("name") or ""))
    keywords |= _tokens(str(spec.get("role") or ""))
    keywords |= _tokens(" ".join(str(e) for e in (spec.get("environment") or [])))
    return keywords


def _is_hedged(text: str) -> bool:
    low = text.lower()
    return any(h in low for h in HEDGES)


def _tag_for(beat: Beat, claims: Dict[str, Dict[str, Any]],
             subject_type: str) -> str:
    """KNOWN / INFERENCE / SPECULATION for one image."""
    source_types = {claims[c]["source_type"] for c in beat.claim_ids
                    if c in claims}
    if subject_type == "species":
        return "SPECULATION"
    if "SPECULATION" in source_types:
        return "SPECULATION"
    if "SINGLE" in source_types or _is_hedged(beat.text):
        return "INFERENCE"
    if source_types & set(REAL_SOURCE_TYPES):
        return "KNOWN"
    return "INFERENCE"


def _resolve_subject(beat: Beat, beats_by_index: List[Beat],
                     specs: List[Dict[str, Any]],
                     claims: Dict[str, Dict[str, Any]],
                     cur_species: Optional[str],
                     cur_habitat: Optional[str],
                     ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Resolve the visual subject of one beat (deterministic rules)."""
    species = [s for s in specs if s.get("type") == "species"]
    habitats = [s for s in specs if s.get("type") == "habitat"]
    plates = [s for s in specs if s.get("type") == "food_web_plate"]

    beat_words = _tokens(beat.text)
    named = [s for s in species if str(s["name"]).lower() in beat.text.lower()]
    claim_words: set[str] = set()
    claim_species: set[str] = set()
    for cid in beat.claim_ids:
        claim_text = str(claims.get(cid, {}).get("claim", ""))
        claim_words |= _tokens(claim_text)
        low = claim_text.lower()
        for s in species:
            if str(s["name"]).lower() in low:
                claim_species.add(str(s["name"]))
    collective = (
        any(_same_word(w, "creature") for w in beat_words)
        or ("food" in beat_words and "web" in beat_words)
        or len(claim_species) >= 2
    )

    if len(named) >= 2 and plates:
        return plates[0], "multi"
    if len(named) == 1:
        return named[0], "name"
    if collective and plates:
        return plates[0], "collective"
    if re.match(r"^(it|its|they|their)\b", beat.text.lower()) and cur_species:
        for s in species:
            if s["name"] == cur_species:
                return s, "pronoun"
    chapter = beat.chapter.lower()
    chapter_named = [s for s in species if str(s["name"]).lower() in chapter]
    if len(chapter_named) == 1:
        return chapter_named[0], "chapter"

    scored = sorted(((_score(beat_words | claim_words, _spec_keywords(s)),
                       s["name"]) for s in habitats), reverse=True)
    if scored and scored[0][0] >= 2 and (len(scored) == 1
                                         or scored[0][0] > scored[1][0]):
        for s in habitats:
            if s["name"] == scored[0][1]:
                return s, "keywords"
    if cur_habitat:
        for s in habitats:
            if s["name"] == cur_habitat:
                return s, "chapter-continuation"
    return None, None


def _view_for(subject_type: str, index: int, camera: Dict[str, str]) -> str:
    """Cycle the camera vocabulary so a subject is seen from several angles."""
    if subject_type == "species":
        order = ["front", "side", "three_quarter", "detail_crop"]
    else:
        order = ["wide_context", "detail_crop"]
    available = [name for name in order if name in camera]
    if not available:
        available = list(camera)
    return available[index % len(available)]


def build_brief(script_path: str | Path, ledger_path: str | Path,
                spec_dir: str | Path, style: StyleSpec, adapter: ModelAdapter,
                *, max_images: Optional[int] = None,
                required_beats: Sequence[str] = (),
                seed_base: Optional[int] = None) -> Dict[str, Any]:
    """Build the image brief. Raises ImageBriefError (fail closed)."""
    from tools.illustration.creature_sheet import creature_spec_from_yaml

    script_file = Path(script_path)
    ledger_file = Path(ledger_path)
    if not script_file.is_file():
        raise ImageBriefError(f"script not found: {script_file}")
    if not ledger_file.is_file():
        raise ImageBriefError(f"claim ledger not found: {ledger_file}")

    beats = parse_script(script_file.read_text(encoding="utf-8"))
    claims = parse_ledger(ledger_file.read_text(encoding="utf-8"))

    for beat in beats:
        for cid in beat.claim_ids:
            if cid not in claims:
                raise ImageBriefError(
                    f"beat {beat.beat_id} references the unknown claim {cid!r} "
                    "(the ledger does not contain it)")
    known_ids = {b.beat_id for b in beats}
    for required in required_beats:
        if required not in known_ids:
            raise ImageBriefError(f"unknown beat {required!r}")

    specs = _load_specs(Path(spec_dir))
    base = int(seed_base if seed_base is not None
               else style.seed_policy.get("base", 3000))
    low, high = style.seed_policy.get("range", [3000, 3999])

    entries: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    cur_species: Optional[str] = None
    cur_habitat: Optional[str] = None
    cur_chapter = None
    view_index: Dict[str, int] = {}

    for beat in beats:
        if beat.chapter != cur_chapter:
            cur_chapter = beat.chapter
            cur_species = None
            cur_habitat = None
        spec, rule = _resolve_subject(beat, beats, specs, claims,
                                       cur_species, cur_habitat)
        if spec is None:
            skipped.append({"beat_id": beat.beat_id, "chapter": beat.chapter,
                            "reason": "no subject could be derived for this beat",
                            "text": beat.text})
            continue
        subject_type = str(spec.get("type") or "species")
        if subject_type == "species":
            cur_species = str(spec["name"])
        else:
            cur_habitat = str(spec["name"])

        index = view_index.get(str(spec["name"]), 0)
        view_index[str(spec["name"])] = index + 1
        view = _view_for(subject_type, index, style.camera_vocabulary)

        seed = base + len(entries)
        if not (int(low) <= seed <= int(high)):
            raise ImageBriefError(
                f"seed {seed} is outside the reserved range {low}-{high}")

        creature = creature_spec_from_yaml(spec, style, adapter)
        creature.camera = style.camera_vocabulary.get(view, "")
        built = PromptBuilder(seed=seed).build(
            adapter.prompt_target, adapter.prompt_variant, creature)
        prompt = built["prompt"]
        if built.get("negative_prompt"):
            prompt = prompt  # the negative prompt travels in its own field

        entries.append({
            "render_id": f"r{len(entries) + 1:04d}",
            "beat_id": beat.beat_id,
            "chapter": beat.chapter,
            "text": beat.text,
            "claim_ids": list(beat.claim_ids),
            "tag": _tag_for(beat, claims, subject_type),
            "subject": str(spec["name"]),
            "subject_type": subject_type,
            "subject_rule": rule,
            "view": view,
            "prompt": prompt,
            "negative_prompt": built.get("negative_prompt"),
            "steps": adapter.steps,
            "guidance": adapter.guidance,
            "seed": seed,
            "prompt_sha256": hashlib.sha256(
                f"{adapter.key}|{prompt}|{seed}".encode("utf-8")).hexdigest(),
            "spec_source": str(spec.get("_source") or ""),
        })

    if max_images is not None and len(entries) > int(max_images):
        skipped.extend({"beat_id": e["beat_id"], "chapter": e["chapter"],
                        "reason": "dropped by the episode budget",
                        "text": e["text"]} for e in entries[int(max_images):])
        entries = entries[:int(max_images)]

    tags = {tag: sum(1 for e in entries if e["tag"] == tag) for tag in TAGS}
    doc: Dict[str, Any] = {
        "schema_version": 1,
        "niche_id": style.niche_id,
        "style_name": style.style_name,
        "model": adapter.key,
        "script": str(script_file),
        "ledger": str(ledger_file),
        "spec_dir": str(spec_dir),
        "entries": entries,
        "skipped": skipped,
        "tags": tags,
        "seed_policy": dict(style.seed_policy),
    }
    doc["brief_sha256"] = hashlib.sha256(
        json.dumps(doc, sort_keys=True).encode("utf-8")).hexdigest()
    return doc


def brief_from_file(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        raise ImageBriefError(f"brief not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))
