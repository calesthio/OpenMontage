"""Sentence Segmenter — splits an English script into unique, ordered sentences.

Each sentence receives a stable sequential ID (S001, S002, ...) and carries the
verbatim source text plus context (paragraph, offsets, word count, estimated
duration) so downstream stages can bind one sentence to one prompt, one image
and one audio fragment.

Rule enforced: ONE SENTENCE = ONE UNIQUE PROMPT = ONE UNIQUE IMAGE.

All work is local and zero-cost: no model calls, no generation, no credits.
Reuses :mod:`lib.script_analyzer` for duration estimation conventions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Any

# Imported for reuse: duration-estimation convention (words / 150 wpm * 60).
from lib.script_analyzer import ScriptAnalyzer  # noqa: E402


_WORDS_PER_MINUTE = 150.0


@dataclass
class Sentence:
    """One verbatim script sentence with stable identity and linking slots."""

    sentence_id: str  # "S001", "S002", ...
    text: str  # verbatim source text, never modified
    order: int  # 1-based sequence index
    paragraph_index: int  # zero-based paragraph the sentence belongs to
    paragraph_text: str  # full paragraph text for context
    start_char: int  # start offset in the full script
    end_char: int  # end offset (exclusive) in the full script
    word_count: int
    estimated_seconds: float
    metadata: dict[str, Any] = field(default_factory=dict)

    # Downstream links (populated by the factory pipeline, not here).
    prompt: str | None = None
    prompt_id: str | None = None
    image_path: str | None = None
    image_sha256: str | None = None
    audio_path: str | None = None
    audio_sha256: str | None = None
    duration_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Sentence-boundary rules
# ---------------------------------------------------------------------------

# Abbreviations (stored WITH trailing period) that must NOT terminate a
# sentence.  Only the last whitespace-delimited token ending in "." is
# checked against this set, so "sunset." is not falsely matched by "et.".
_ABBREVIATIONS_SET = {
    "mr.", "mrs.", "ms.", "miss.", "dr.", "prof.", "sr.", "jr.", "st.",
    "vs.", "etc.", "e.g.", "i.e.", "approx.", "fig.", "vol.", "no.",
    "inc.", "ltd.", "co.", "corp.", "u.s.", "u.k.", "u.s.a.", "u.k.a.",
    "ph.d.", "m.d.", "b.a.", "m.a.", "dept.", "univ.", "rev.", "hon.",
    "gen.", "col.", "capt.", "sgt.", "rep.", "sen.", "gov.", "pres.",
    "attn.", "ref.", "cf.", "et.", "al.", "opp.", "vols.",
}

# Single-letter initials (e.g. "J. Smith", "A. B. C.") are not sentence ends.
_INITIAL = re.compile(r"\b[A-Za-z]\.\s")

# Decimal numbers: digits.digits must not split.
_DECIMAL = re.compile(r"(?<=\d)\.(?=\d)")

# Ellipsis and multiple dots are one boundary, not several.
_ELLIPSIS = re.compile(r"\.{2,}")

# A real sentence terminator: . ! ? ... followed by whitespace and a capital
# letter / digit / quote / opening bracket.  The lookahead excludes lowercase
# continuations (e.g. "e.g. foo" / "3.14").
_TERMINATOR = re.compile(
    r"([.!?]|…|(?<!\d)\.(?!\d))"  # terminator (not a decimal point)
    r"\s+"                         # required whitespace after
    r"(?=[A-Z0-9\"\'\(\\[\u00c0-\u024f])"  # capital/digit/quote/bracket start
)


def _is_abbreviation(text: str) -> bool:
    """True if the last word before the period is a known abbreviation.

    Only the final whitespace-delimited token ending in "." is checked,
    so e.g. "sunset." (ends with "et.") is NOT treated as an abbreviation
    even though "et." is in the abbreviation list.
    """
    # Find the last token ending with a period.
    m = re.search(r"(\S+\.)\s*$", text.strip())
    if not m:
        return False
    last_token = m.group(1).lower()
    return last_token in _ABBREVIATIONS_SET


def _split_paragraphs(text: str) -> list[str]:
    """Split on blank lines, preserving paragraph order."""
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


def _sentence_spans(paragraph: str, offset: int) -> list[tuple[int, int, str]]:
    """Return (start, end, text) sentence spans within one paragraph.

    Boundaries are detected with ``_TERMINATOR`` then post-filtered so that
    abbreviations, decimals and initials do not split sentences.  The original
    text is never modified — only slice offsets are computed.
    """
    spans: list[tuple[int, int, str]] = []
    start = 0
    for m in _TERMINATOR.finditer(paragraph):
        term_start = m.start()
        term_end = m.end()
        # The character right before the terminator.
        before = paragraph[max(0, term_start - 1):term_start]
        after_ws = m.group(0)[len(m.group(0).rstrip()):]  # whitespace captured
        # Candidate sentence end = end of the terminator (before trailing ws).
        candidate_end = term_start + 1  # include the terminator char itself

        # --- Abbreviation guard -------------------------------------------
        # Check whether the text ending at this terminator is a known
        # abbreviation (e.g. "Mr.", "U.S.A.", "Ph.D.").  The full substring
        # up to and including the terminator is tested so multi-part forms
        # like "U.S.A." match.
        if _is_abbreviation(paragraph[start:term_start + 1]):
            # Do not split here; continue scanning.
            continue

        # --- Decimal guard: already excluded by regex (?<!\d)\.(?!\d) -----

        # --- Initial guard: "A. B." mid-sentence -------------------------
        if re.fullmatch(r"[A-Za-z]\.", before.strip()) and after_ws:
            next_char = paragraph[term_end:term_end + 1]
            if next_char and next_char[0].isalpha():
                # Looks like a mid-sentence initial; skip this boundary.
                continue

        end = candidate_end
        sentence = paragraph[start:end].strip()
        if sentence:
            spans.append((start + offset, end + offset, sentence))
        start = end

    # Tail of paragraph.
    tail = paragraph[start:].strip()
    if tail:
        spans.append((start + offset, len(paragraph) + offset, tail))
    return spans


class SentenceSegmenter:
    """Split a script into ordered, uniquely-ID'd sentences."""

    def __init__(self, wpm: float = _WORDS_PER_MINUTE, run_id: str | None = None) -> None:
        self.wpm = wpm
        self.run_id = run_id or "run"
        self._analyzer = ScriptAnalyzer(wpm=wpm)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def segment(self, script: str, run_id: str | None = None) -> list[Sentence]:
        """Split *script* into :class:`Sentence` instances.

        Every sentence keeps its verbatim text.  IDs are assigned sequentially
        as ``S001``, ``S002``, … across the whole document.  There is no
        upper bound on the number of sentences.
        """
        if run_id is not None:
            self.run_id = run_id
        paragraphs = _split_paragraphs(script)

        sentences: list[Sentence] = []
        counter = 1
        char_cursor = 0  # absolute offset into the full script

        for para_idx, paragraph in enumerate(paragraphs):
            para_start = script.find(paragraph, char_cursor)
            if para_start < 0:
                para_start = char_cursor
            # Re-sync cursor: paragraphs are separated by blank lines; find
            # this paragraph at or after the current cursor.
            spans = _sentence_spans(paragraph, para_start)
            for abs_start, abs_end, sentence_text in spans:
                wc = len(sentence_text.split())
                est = wc / self.wpm * 60.0
                sid = f"S{counter:03d}"
                sentences.append(
                    Sentence(
                        sentence_id=sid,
                        text=sentence_text,
                        order=counter,
                        paragraph_index=para_idx,
                        paragraph_text=paragraph,
                        start_char=abs_start,
                        end_char=abs_end,
                        word_count=wc,
                        estimated_seconds=round(est, 4),
                        metadata={
                            "run_id": self.run_id,
                            "source_paragraph": para_idx,
                        },
                    )
                )
                counter += 1
            # Advance cursor past this paragraph (incl. its trailing blank lines).
            end_search = script.find(paragraph, para_start)
            if end_search >= 0:
                char_cursor = end_search + len(paragraph)
            else:
                char_cursor = para_start + len(paragraph)

        return sentences

    def segment_to_dict(self, script: str, run_id: str | None = None) -> list[dict[str, Any]]:
        """Return sentences as plain dicts (JSON-friendly)."""
        return [s.to_dict() for s in self.segment(script, run_id=run_id)]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def estimate_seconds(text: str, wpm: float = _WORDS_PER_MINUTE) -> float:
        """Spoken duration estimate: words / wpm * 60."""
        return len(text.split()) / wpm * 60.0

    @staticmethod
    def validate_ids(sentences: list[Sentence]) -> list[str]:
        """Return list of problems (empty = all IDs unique and sequential)."""
        problems: list[str] = []
        seen: set[str] = set()
        expected = 1
        for s in sentences:
            if s.sentence_id in seen:
                problems.append(f"duplicate sentence id {s.sentence_id}")
            seen.add(s.sentence_id)
            m = re.fullmatch(r"S(\d+)", s.sentence_id)
            if not m or int(m.group(1)) != expected:
                problems.append(f"non-sequential id {s.sentence_id} at position {expected}")
                # Resync expected to the max seen so far keeps checking.
            expected = max(expected, int(m.group(1)) + 1 if m else expected + 1)
        return problems
