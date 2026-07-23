"""Regression tests: Corpus.diversify() must actually diversify at its default.

The greedy score mixed two incommensurate scales:

    score = diversity * (-sim_picked) + (1 - diversity) * (-remaining.index(i))

`sim_picked` is a cosine in [-1, 1]; `remaining.index(i)` is an absolute
list position, unbounded. At the default diversity=0.5 a candidate one
slot later needed a similarity gap > 1.0 to be preferred — impossible for
non-negative cosines — so diversify() returned the input order verbatim,
even when the list held exact duplicates. Its one documented job ("make
sure no two adjacent slots are visually redundant") never happened, and
the effective meaning of `diversity` changed with pool size.

The fix normalizes the position term to [0, 1] so both terms share a
scale. diversity=0 still returns input order; diversity=1 still picks the
most mutually dissimilar.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.corpus import EMBED_DIM, ClipRecord, Corpus


def _corpus(vectors: list[list[float]]) -> Corpus:
    """Build an in-memory corpus from small L2-normalised vectors."""
    corp = Corpus(Path("/nonexistent"))
    emb = np.zeros((len(vectors), EMBED_DIM), dtype=np.float32)
    for row, vec in enumerate(vectors):
        emb[row, : len(vec)] = vec
        emb[row] /= np.linalg.norm(emb[row])
    corp.clip_embeddings = emb
    corp.records = [
        ClipRecord(
            clip_id=f"c{row}",
            source="test",
            source_id=str(row),
            source_url="",
            local_path="",
        )
        for row in range(len(vectors))
    ]
    corp._id_to_row = {r.clip_id: i for i, r in enumerate(corp.records)}
    return corp


def test_default_diversity_separates_exact_duplicates():
    # c1 is an exact duplicate of c0; c2/c3 are orthogonal to both.
    corp = _corpus([[1, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]])

    kept = corp.diversify(["c0", "c1", "c2", "c3"], n=3)

    # The duplicate must not sit adjacent to its twin at the default.
    assert kept[0] == "c0"
    assert kept[1] != "c1"


def test_default_diversity_is_not_a_noop():
    # Three exact duplicates (c0, c2, c5) interleaved with distinct clips.
    # The old scoring returned the input order verbatim here.
    corp = _corpus(
        [
            [1, 0, 0],
            [0.8, 0.6, 0],
            [1, 0, 0],
            [0.6, 0.8, 0],
            [0, 1, 0],
            [1, 0, 0],
        ]
    )
    ids = [f"c{i}" for i in range(6)]

    kept = corp.diversify(ids, n=6)

    assert kept != ids  # reorders when the input holds duplicates
    for a, b in zip(kept, kept[1:]):  # and no two adjacent slots are twins
        va = corp.clip_embeddings[corp._id_to_row[a]]
        vb = corp.clip_embeddings[corp._id_to_row[b]]
        assert float(va @ vb) < 0.999


def test_diversity_semantics_do_not_collapse_with_pool_size():
    # Duplicate of c0 right at position 1, moderately-related fillers,
    # one orthogonal clip at the end. With the unnormalised position
    # term the duplicate always won slot 2 at diversity=0.5 because the
    # positional penalty scaled with the pool.
    half_sqrt3 = np.sqrt(3) / 2
    vectors = [[1, 0, 0], [1, 0, 0]] + [[0.5, half_sqrt3, 0]] * 8 + [[0, 0, 1]]
    corp = _corpus(vectors)
    ids = [f"c{i}" for i in range(len(vectors))]

    kept = corp.diversify(ids, n=3, diversity=0.5)

    assert kept[0] == "c0"
    assert "c1" not in kept[:2]  # the exact duplicate no longer wins slot 2


def test_diversity_zero_keeps_input_order():
    corp = _corpus([[1, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]])
    ids = ["c0", "c1", "c2", "c3"]

    assert corp.diversify(ids, n=4, diversity=0.0) == ids


def test_diversity_one_picks_most_dissimilar():
    # c1 duplicates c0; c2 and c3 are mutually orthogonal.
    corp = _corpus([[1, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]])

    kept = corp.diversify(["c0", "c1", "c2", "c3"], n=3, diversity=1.0)

    assert kept == ["c0", "c2", "c3"]


def test_empty_and_unknown_ids():
    corp = _corpus([[1, 0, 0]])

    assert corp.diversify([], n=3) == []
    assert corp.diversify(["nope"], n=3) == []
    assert corp.diversify(["c0", "nope"], n=3) == ["c0"]
