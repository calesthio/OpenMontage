"""Do the sources that claim to be configured actually answer?

`is_available()` is a static declaration — usually "is my API key set?" — not
a probe. That is the right default (a probe on every call would make the
preflight menu slow and flaky), but it means an upstream that changes or dies
keeps advertising itself. `corpus_builder` then fans out across it, catches
the per-source error, and carries on with fewer clips than the agent thinks it
asked for.

Measured on 2026-08-31 with no API keys set, three of the seven sources
reporting themselves configured actually returned results:

    coverr      401 Unauthorized   (advertised a keyless free tier)
    nara        non-JSON response
    loc         403 Forbidden
    pond5_pd    403 on the API, web fallback returned nothing

`coverr` is fixed at the source — it now requires COVERR_API_KEY. The rest are
live upstream failures that only a real request can detect, so this test hits
the network and is skipped by default, like any other live test in the suite.

    OPENMONTAGE_ALLOW_NETWORK=1 pytest tests/tools/test_stock_source_health.py -v -s
"""

from __future__ import annotations

import pytest

from tools.video.stock_sources import available_sources
from tools.video.stock_sources.base import SearchFilters


def test_available_sources_are_declared_consistently():
    """Offline: every advertised source must expose the full protocol.

    Cheap structural check that runs in normal CI — it cannot detect a dead
    endpoint, but it does catch an adapter that advertises itself while
    missing a method the corpus builder will call.
    """
    for src in available_sources():
        assert isinstance(getattr(src, "name", ""), str) and src.name
        for method in ("is_available", "search", "download"):
            assert callable(getattr(src, method, None)), (
                f"{src.name} advertises availability but has no {method}()"
            )


@pytest.mark.live_api
def test_advertised_sources_actually_answer():
    """Online: an advertised source must return results for a generic query."""
    dead: list[str] = []
    filters = SearchFilters(kind="video", per_page=3)

    for src in available_sources():
        try:
            hits = src.search("landscape", filters)
        except Exception as exc:
            dead.append(f"{src.name}: {type(exc).__name__}: {str(exc)[:80]}")
            continue
        if not hits:
            dead.append(f"{src.name}: returned 0 results")

    assert not dead, (
        "sources report is_available() == True but do not answer:\n  "
        + "\n  ".join(dead)
    )
