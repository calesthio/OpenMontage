"""Script Analyzer — splits a spoken script into meaning blocks and flags
visual requirements for downstream scene planning.

All work is local and zero-cost: no model calls, no generation, no credits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MeaningBlock:
    """One contiguous stretch of script that carries a single idea."""

    block_id: str
    start_char: int
    end_char: int
    text: str
    block_type: str  # "exposition" | "claim" | "transition" | "conclusion"
    word_count: int
    estimated_seconds: float


@dataclass
class VisualMoment:
    """A timestamped point where the picture must change or illustrate."""

    moment_id: str
    block_id: str
    char_position: int
    text_fragment: str
    moment_type: str  # "reveal" | "compare" | "process" | "evidence" | "conclusion"
    description: str


@dataclass
class ScientificClaim:
    """A factual statement in the script that needs visual backing."""

    claim_id: str
    block_id: str
    text: str
    start_char: int
    end_char: int
    confidence_hint: str  # "high" | "medium" | "low" (heuristic only)


@dataclass
class ScriptAnalysis:
    """Complete result of analysing a script."""

    title: str
    target_duration_seconds: float
    total_words: int
    estimated_seconds: float
    blocks: list[MeaningBlock]
    visual_moments: list[VisualMoment]
    scientific_claims: list[ScientificClaim]
    characters_mentioned: list[str]
    visual_style_hint: str
    repetition_flags: list[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-ZА-ЯЁ])")
_CLAIM_MARKERS = (
    "is", "are", "was", "were", "has", "have", "reached", "covers",
    "spans", "weighs", "measures", "equals", "costs", "lasts",
    "formed", "created", "built", "discovered", "found", "shows",
)
_GENERIC_FILLERS = (
    "in today's world", "cutting-edge", "state-of-the-art",
    "revolutionary", "amazing", "incredible", "stunning",
    "a professional", "dynamic", "vibrant", "breathtaking",
)


def _estimate_seconds(text: str, wpm: float = 150.0) -> float:
    """Rough spoken duration: average ~150 words per minute for narration."""
    words = len(text.split())
    return words / wpm * 60.0


def _split_into_blocks(text: str) -> list[tuple[int, int, str]]:
    """Split script text into meaning blocks by sentence boundaries."""
    blocks: list[tuple[int, int, str]] = []
    pos = 0
    for m in _SENTENCE_SPLIT.finditer(text):
        # m.group(0) is only the matched whitespace; the sentence text lies
        # between the previous position and the start of this match.
        sentence = text[pos:m.start()].strip()
        if sentence:
            blocks.append((pos, m.start(), sentence))
        pos = m.end()
    tail = text[pos:].strip()
    if tail:
        blocks.append((pos, len(text), tail))
    return blocks


def _classify_block(text: str) -> str:
    """Heuristic block classification."""
    low = text.lower()
    if any(w in low for w in ("however", "but", "meanwhile", "on the other hand", "next", "then")):
        return "transition"
    if any(w in low for w in ("in conclusion", "to sum up", "finally", "in short", "therefore")):
        return "conclusion"
    if any(m in text for m in _CLAIM_MARKERS) and len(text.split()) >= 6:
        return "claim"
    return "exposition"


def _find_scientific_claims(text: str, block_id: str, block_start: int) -> list[ScientificClaim]:
    """Flag sentences that assert a measurable fact (heuristic only)."""
    claims: list[ScientificClaim] = []
    pos = 0
    i = -1
    for i, m in enumerate(_SENTENCE_SPLIT.finditer(text)):
        # m.group(0) is only the matched whitespace; the sentence text lies
        # between the previous position and the start of this match.
        sentence = text[pos:m.start()].strip()
        pos = m.end()
        if not sentence:
            continue
        # A sentence is a "claim candidate" if it contains a number, unit,
        # or a claim marker verb and is not pure opinion.
        looks_factual = bool(
            re.search(r"\d+", sentence)
            or re.search(r"(km|miles|kg|tons|years|degrees|°|percent|%|billion|million|trillion)", sentence, re.I)
            or any(marker in sentence for marker in _CLAIM_MARKERS)
        )
        if looks_factual and len(sentence.split()) >= 5:
            claims.append(
                ScientificClaim(
                    claim_id=f"{block_id}-claim-{i}",
                    block_id=block_id,
                    text=sentence,
                    start_char=m.start(),
                    end_char=m.end(),
                    confidence_hint="medium",
                )
            )
    # Handle the last sentence (tail after the last match)
    tail = text[pos:].strip()
    if tail:
        i += 1
        looks_factual = bool(
            re.search(r"\d+", tail)
            or re.search(r"(km|miles|kg|tons|years|degrees|°|percent|%|billion|million|trillion)", tail, re.I)
            or any(marker in tail for marker in _CLAIM_MARKERS)
        )
        if looks_factual and len(tail.split()) >= 5:
            claims.append(
                ScientificClaim(
                    claim_id=f"{block_id}-claim-{i}",
                    block_id=block_id,
                    text=tail,
                    start_char=pos,
                    end_char=len(text),
                    confidence_hint="medium",
                )
            )
    return claims


def _detect_repetition(blocks: list[MeaningBlock]) -> list[str]:
    """Flag blocks that repeat near-identical phrasing."""
    flags: list[str] = []
    seen: dict[str, int] = {}
    for b in blocks:
        norm = re.sub(r"\W+", " ", b.text.lower()).strip()
        if norm in seen:
            flags.append(
                f"Block {b.block_id} repeats near-identical text of block {seen[norm]}"
            )
        else:
            seen[norm] = b.block_id
    return flags


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class ScriptAnalyzer:
    """Analyse a spoken script into meaning blocks, visual moments,
    scientific claims, and character mentions."""

    def __init__(self, wpm: float = 150.0) -> None:
        self.wpm = wpm

    def analyze(
        self,
        *,
        title: str,
        script: str,
        target_duration_seconds: float,
        characters: list[str] | None = None,
        visual_style: str = "bold ink illustration",
    ) -> ScriptAnalysis:
        """Run the full analysis and return a :class:`ScriptAnalysis`."""
        characters = characters or []
        blocks_raw = _split_into_blocks(script)

        blocks: list[MeaningBlock] = []
        visual_moments: list[VisualMoment] = []
        scientific_claims: list[ScientificClaim] = []

        char_running = 0
        for idx, (start, end, sentence) in enumerate(blocks_raw):
            block_id = f"{title.lower().replace(' ', '_')}-block-{idx:03d}"
            btype = _classify_block(sentence)
            wc = len(sentence.split())
            est = _estimate_seconds(sentence, self.wpm)
            blocks.append(
                MeaningBlock(
                    block_id=block_id,
                    start_char=start,
                    end_char=end,
                    text=sentence,
                    block_type=btype,
                    word_count=wc,
                    estimated_seconds=est,
                )
            )

            # Every block boundary is a potential visual moment.
            vm_type = "reveal" if btype in ("claim", "conclusion") else "exposition"
            visual_moments.append(
                VisualMoment(
                    moment_id=f"{block_id}-moment",
                    block_id=block_id,
                    char_position=start,
                    text_fragment=sentence[:80],
                    moment_type=vm_type,
                    description=sentence,
                )
            )

            scientific_claims.extend(
                _find_scientific_claims(sentence, block_id, start)
            )

            char_running = end

        total_words = len(script.split())
        estimated = sum(b.estimated_seconds for b in blocks)
        repetition_flags = _detect_repetition(blocks)

        # Character mentions: simple substring match against provided list.
        mentioned: list[str] = []
        low_script = script.lower()
        for ch in characters:
            if ch.lower() in low_script:
                mentioned.append(ch)

        return ScriptAnalysis(
            title=title,
            target_duration_seconds=target_duration_seconds,
            total_words=total_words,
            estimated_seconds=estimated,
            blocks=blocks,
            visual_moments=visual_moments,
            scientific_claims=scientific_claims,
            characters_mentioned=mentioned,
            visual_style_hint=visual_style,
            repetition_flags=repetition_flags,
        )

    def to_dict(self, analysis: ScriptAnalysis) -> dict[str, Any]:
        return {
            "title": analysis.title,
            "target_duration_seconds": analysis.target_duration_seconds,
            "total_words": analysis.total_words,
            "estimated_seconds": round(analysis.estimated_seconds, 2),
            "blocks": [
                {
                    "block_id": b.block_id,
                    "start_char": b.start_char,
                    "end_char": b.end_char,
                    "text": b.text,
                    "block_type": b.block_type,
                    "word_count": b.word_count,
                    "estimated_seconds": round(b.estimated_seconds, 2),
                }
                for b in analysis.blocks
            ],
            "visual_moments": [
                {
                    "moment_id": m.moment_id,
                    "block_id": m.block_id,
                    "char_position": m.char_position,
                    "text_fragment": m.text_fragment,
                    "moment_type": m.moment_type,
                    "description": m.description,
                }
                for m in analysis.visual_moments
            ],
            "scientific_claims": [
                {
                    "claim_id": c.claim_id,
                    "block_id": c.block_id,
                    "text": c.text,
                    "start_char": c.start_char,
                    "end_char": c.end_char,
                    "confidence_hint": c.confidence_hint,
                }
                for c in analysis.scientific_claims
            ],
            "characters_mentioned": analysis.characters_mentioned,
            "visual_style_hint": analysis.visual_style_hint,
            "repetition_flags": analysis.repetition_flags,
        }
