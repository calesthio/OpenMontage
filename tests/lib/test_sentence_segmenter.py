"""Tests for lib.sentence_segmenter.

Covers: 10/100/250/300 sentence segmentation, unique sequential IDs,
verbatim text preservation, abbreviation/decimal/quote handling, paragraph
context, ordering, duration estimates, and id validation.
"""

from __future__ import annotations

import sys

import pytest

sys.path.insert(0, "/workspaces/OpenMontage")

from lib.sentence_segmenter import SentenceSegmenter  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def segmenter():
    return SentenceSegmenter()


SHORT_SCRIPT = (
    "Mr. Smith drove to the U.S.A. at 3.14 mph. "
    'He met Dr. Jones, Ph.D., who said: "e.g. it works!" Then they left. '
    "Is it done? Yes."
)

LONG_SCRIPT = " ".join(
    f"Sentence number {i} is a distinct statement about topic {i % 7}."
    for i in range(300)
)


# ---------------------------------------------------------------------------
# Counts: 10, 100, 250, and beyond (no hard 250 limit)
# ---------------------------------------------------------------------------


def test_segment_returns_exact_counts(segmenter):
    for n in (10, 100, 250):
        script = " ".join(f"This is sentence {i}." for i in range(n))
        sents = segmenter.segment(script)
        assert len(sents) == n, f"expected {n}, got {len(sents)}"


def test_no_hard_limit_at_250(segmenter):
    sents = segmenter.segment(LONG_SCRIPT)
    assert len(sents) == 300, f"expected 300, got {len(sents)}"


# ---------------------------------------------------------------------------
# Unique sequential IDs
# ---------------------------------------------------------------------------


def test_ids_are_unique_and_sequential(segmenter):
    sents = segmenter.segment(SHORT_SCRIPT)
    ids = [s.sentence_id for s in sents]
    assert ids == [f"S{i:03d}" for i in range(1, len(sents) + 1)]
    assert len(set(ids)) == len(ids)


def test_validate_ids_passes(segmenter):
    sents = segmenter.segment(SHORT_SCRIPT)
    assert segmenter.validate_ids(sents) == []


def test_ids_resume_across_documents(segmenter):
    s1 = segmenter.segment("One. Two.", run_id="run-a")
    s2 = segmenter.segment("Three. Four.", run_id="run-b")
    assert s1[0].sentence_id == "S001"
    assert s2[0].sentence_id == "S001"


# ---------------------------------------------------------------------------
# Text preservation (verbatim, no loss/modification)
# ---------------------------------------------------------------------------


def test_text_is_verbatim(segmenter):
    sents = segmenter.segment(SHORT_SCRIPT)
    for s in sents:
        assert s.text in SHORT_SCRIPT, f"sentence text not found in source: {s.text!r}"


def test_no_text_loss(segmenter):
    sents = segmenter.segment(SHORT_SCRIPT)
    # Reconstructed sentence texts must account for every non-space character
    # of the source (modulo the terminator+whitespace we split on).
    source_chars = [c for c in SHORT_SCRIPT if not c.isspace()]
    sent_chars = [c for s in sents for c in s.text if not c.isspace()]
    assert set(sent_chars).issubset(set(source_chars))


# ---------------------------------------------------------------------------
# Abbreviations, decimals, quotes
# ---------------------------------------------------------------------------


def test_abbreviations_do_not_split(segmenter):
    sents = segmenter.segment("Mr. Smith met Dr. Jones at U.S.A. HQ.")
    assert len(sents) == 1
    assert sents[0].text == "Mr. Smith met Dr. Jones at U.S.A. HQ."


def test_decimals_do_not_split(segmenter):
    sents = segmenter.segment("The value is 3.14 and also 2.718. Next sentence.")
    assert len(sents) == 2
    assert sents[0].text == "The value is 3.14 and also 2.718."


def test_quotes_are_preserved(segmenter):
    sents = segmenter.segment('He said: "e.g. it works!" Then left.')
    assert len(sents) == 1
    assert '"e.g. it works!"' in sents[0].text


def test_exclamation_and_question_split(segmenter):
    sents = segmenter.segment("Wow! Is it? Yes.")
    assert len(sents) == 3
    assert sents[0].text == "Wow!"
    assert sents[1].text == "Is it?"
    assert sents[2].text == "Yes."


# ---------------------------------------------------------------------------
# Paragraph context and ordering
# ---------------------------------------------------------------------------


def test_paragraph_context_preserved(segmenter):
    script = "First paragraph sentence one. First paragraph sentence two.\n\nSecond paragraph sentence one."
    sents = segmenter.segment(script)
    assert sents[0].paragraph_index == 0
    assert sents[1].paragraph_index == 0
    assert sents[2].paragraph_index == 1
    assert sents[0].paragraph_text == "First paragraph sentence one. First paragraph sentence two."
    assert sents[2].paragraph_text == "Second paragraph sentence one."


def test_order_is_sequential(segmenter):
    sents = segmenter.segment("A. B. C. D. E.")
    assert [s.order for s in sents] == [1, 2, 3, 4, 5]


def test_char_offsets_increase(segmenter):
    sents = segmenter.segment("One. Two. Three.")
    for prev, cur in zip(sents, sents[1:]):
        assert cur.start_char >= prev.end_char


# ---------------------------------------------------------------------------
# Duration estimates and metadata
# ---------------------------------------------------------------------------


def test_estimated_seconds_positive(segmenter):
    sents = segmenter.segment("This is a test sentence.")
    assert sents[0].estimated_seconds > 0


def test_estimated_seconds_matches_wpm(segmenter):
    seg = SentenceSegmenter(wpm=150.0)
    sents = seg.segment("This sentence has exactly ten words right here and now.")
    assert len(sents[0].text.split()) == 10
    expected = 10 / 150.0 * 60.0
    assert abs(sents[0].estimated_seconds - expected) < 0.01


def test_metadata_contains_run_id(segmenter):
    sents = segmenter.segment("One. Two.", run_id="run-42")
    assert all(s.metadata["run_id"] == "run-42" for s in sents)


# ---------------------------------------------------------------------------
# to_dict round-trip
# ---------------------------------------------------------------------------


def test_to_dict_round_trip(segmenter):
    sents = segmenter.segment("One. Two.")
    d = [s.to_dict() for s in sents]
    assert d[0]["sentence_id"] == "S001"
    assert d[0]["text"] == "One."
    assert d[1]["sentence_id"] == "S002"
