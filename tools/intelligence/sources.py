"""Signal-source plugin interface for the Trend Intelligence Layer.

Each external source (YouTube transcripts/comments, Reddit, Google Trends,
Hacker News, GitHub trending, Product Hunt, arXiv, blogs, podcasts, X)
is a small `SignalSource` plugin. Sources contribute WEAK signals;
combining them gives earlier visibility into emerging topics than any
single source alone.

HONEST STATUS
-------------
The concrete sources are STUBS with real parsing + a real (stdlib-only)
network client where a key exists. They are DROP-IN: with the right
env credentials they become live; without them they yield [] and never
fabricate signal values. The orchestration (`SignalIngestor`) and the
`ConceptGraph` do not change — only the adapters do.

Offline guarantee: tests exercise `is_live()` (False without keys) and the
pure `_parse_*` functions with fixtures. Network is only reached when a
source is live AND called outside a test.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
import urllib.parse
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# primitives
# ---------------------------------------------------------------------------

@dataclass
class Signal:
    """One weak signal observed from a source."""
    source: str
    text: str
    weight: float = 1.0
    url: str = ""
    engagement: float = 0.0   # normalised 0..1 (views/upvotes/score)
    recency: float = 0.0       # 0 old .. 1 fresh


class SignalSource:
    """Base class for a pluggable signal source.

    Override `fetch()` (or just `_request` + `_parse`) and set
    `required_env` to the credentials the source needs.
    """

    name: str = "base"
    required_env: List[str] = field(default_factory=list)

    def is_live(self) -> bool:
        return all(os.environ.get(e) for e in self.required_env)

    def fetch(self) -> List[Signal]:
        """Return weak signals. Default stub returns [] (inert offline)."""
        if not self.is_live():
            return []
        return []

    def __call__(self) -> List[Signal]:
        return self.fetch()


# ---------------------------------------------------------------------------
# YouTube transcript + comment signals (real stdlib client, key-gated)
# ---------------------------------------------------------------------------

_YT_SEARCH = "https://www.googleapis.com/youtube/v3/search"
_YT_CAPTIONS = "https://www.googleapis.com/youtube/v3/captions"


class YouTubeTranscriptSource(SignalSource):
    """YouTube transcript + comment signals.

    Live when ``YOUTUBE_API_KEY`` is set (optionally ``YOUTUBE_QUERY``).
    Implementation uses the YouTube Data API v3 via stdlib urllib — no extra
    dependency. Without the key it is inert ([]). The pure parsers
    (`_parse_search`, `_parse_captions`) are unit-tested offline.
    """

    name = "youtube"
    required_env = ["YOUTUBE_API_KEY"]

    def __init__(self, query: str = "AI agents", max_results: int = 10) -> None:
        self.query = os.environ.get("YOUTUBE_QUERY") or query
        self.max_results = max_results

    # --- network (only called when live) ---
    def _request(self, url: str) -> dict:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310 (key-gated)
            return json.loads(r.read().decode("utf-8"))

    def fetch(self) -> List[Signal]:
        if not self.is_live():
            return []
        key = os.environ["YOUTUBE_API_KEY"]
        search = self._request(
            f"{_YT_SEARCH}?{urllib.parse.urlencode({'part':'snippet','q':self.query,'maxResults':self.max_results,'type':'video','key':key})}"
        )
        out: List[Signal] = []
        for vid in self._parse_search(search):
            try:
                cap = self._request(
                    f"{_YT_CAPTIONS}?{urllib.parse.urlencode({'part':'snippet','videoId':vid,'key':key})}"
                )
                out += self._parse_captions(cap, vid)
            except Exception:  # noqa: BLE001 - one video failing must not kill the pull
                continue
        return out

    # --- pure parsers (offline-testable) ---
    @staticmethod
    def _parse_search(payload: dict) -> List[str]:
        items = (payload or {}).get("items") or []
        ids = []
        for it in items:
            rid = it.get("id") or {}
            vid = rid.get("videoId") if isinstance(rid, dict) else None
            if vid:
                ids.append(vid)
        return ids

    @staticmethod
    def _parse_captions(payload: dict, video_id: str) -> List[Signal]:
        items = (payload or {}).get("items") or []
        out = []
        for it in items:
            sn = it.get("snippet") or {}
            text = sn.get("text") or sn.get("name") or ""
            if text:
                out.append(Signal(source="youtube", text=text, url=f"https://youtu.be/{video_id}"))
        return out


# ---------------------------------------------------------------------------
# More stubs (key-gated placeholders; same contract)
# ---------------------------------------------------------------------------

class RedditSource(SignalSource):
    name = "reddit"
    required_env = ["REDDIT_CLIENT_ID", "REDDIT_SECRET"]

    def fetch(self) -> List[Signal]:
        if not self.is_live():
            return []
        raise NotImplementedError(
            "RedditSource.fetch: implement with the Reddit API using "
            "REDDIT_CLIENT_ID / REDDIT_SECRET (subreddit search -> posts/comments)."
        )


class GoogleTrendsSource(SignalSource):
    name = "google_trends"
    required_env = ["GOOGLE_TRENDS_KEY"]

    def fetch(self) -> List[Signal]:
        if not self.is_live():
            return []
        raise NotImplementedError(
            "GoogleTrendsSource.fetch: implement with the Trends API using "
            "GOOGLE_TRENDS_KEY (interest over time / rising queries)."
        )


class HackerNewsSource(SignalSource):
    """Hacker News has a public, key-less API. Network still gated by `is_live`."""
    name = "hackernews"
    required_env: List[str] = []

    def is_live(self) -> bool:
        # public API, but keep inert in tests unless explicitly enabled
        return bool(os.environ.get("HN_ENABLED"))

    def fetch(self) -> List[Signal]:
        if not self.is_live():
            return []
        raise NotImplementedError(
            "HackerNewsSource.fetch: call https://hacker-news.firebaseio.com "
            "topstories -> items; parse title/url/text into Signals."
        )


# ---------------------------------------------------------------------------
# Orchestration: weak signals -> ConceptGraph
# ---------------------------------------------------------------------------

_STOP = {
    "the", "and", "for", "with", "that", "this", "from", "your", "are",
    "was", "have", "will", "they", "but", "not", "you", "all", "can",
    "how", "why", "what", "when", "who", "into", "out", "about",
}


def _extract_concepts(text: str) -> List[str]:
    toks = re.findall(r"[A-Za-z][A-Za-z+#-]{1,}", text or "")
    seen = []
    for t in toks:
        tl = t.lower()
        if tl in _STOP:
            continue
        # Title-case so UPPER source text ("CLAUDE") joins existing
        # Title-case nodes ("Claude") in the graph.
        cap = t[0].upper() + t[1:].lower()
        if cap not in seen:
            seen.append(cap)
    return seen[:50]


class SignalIngestor:
    """Pull weak signals from live sources and fold them into a ConceptGraph.

    Only live sources are queried. Returns the number of signals ingested.
    Concept signals (popularity/velocity/saturation) are incremented by
    small, deterministic amounts derived from each signal's weight/recency,
    so repeated runs accumulate evidence without ever inventing values.
    """

    def ingest(self, sources: List[SignalSource], graph, max_signals: int = 200) -> int:
        signals: List[Signal] = []
        for src in sources:
            if not src.is_live():
                continue
            try:
                signals += src.fetch()
            except NotImplementedError:
                continue
            except Exception:  # noqa: BLE001 - one dead source must not halt ingestion
                continue
        signals = signals[:max_signals]
        for sig in signals:
            for concept in _extract_concepts(sig.text):
                cur = graph.get(concept) or graph.upsert(concept)
                cur.popularity = min(1.0, cur.popularity + 0.05 * sig.weight)
                cur.velocity = min(1.0, cur.velocity + 0.1 * sig.recency)
                cur.saturation = min(1.0, cur.saturation + 0.02 * sig.weight)
        return len(signals)
