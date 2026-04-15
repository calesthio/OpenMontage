"""Unified protocol for stock media source adapters.

Every source (Pexels, Archive.org, NASA, Wikimedia, Unsplash, ...)
implements the same small interface. The corpus builder fans out across
all enabled sources, normalises their results into `Candidate` objects,
downloads what it decides to keep, and writes everything to the local
corpus. During selection the agent never sees which source a clip came
from — it only sees `ClipRecord` rows retrieved by similarity.

Design intent
-------------
- **Separation of concerns.** Adapters handle API shape, licensing
  metadata, and downloading. `lib/corpus.py` handles indexing and
  retrieval math. The agent handles WHAT to search for and WHICH
  results to accept.
- **Interchangeable.** Any adapter satisfies the same protocol, so the
  corpus builder can iterate `for src in sources: src.search(q, f)`
  without branching on source type.
- **Dumb by design.** No ranking, no de-dup, no filtering beyond what
  the API itself accepts. Judgment work happens after embedding, in
  the agent. Adapters just convert "API JSON" → "normalised Candidate".

Adding a new source
-------------------
1. Create `tools/video/stock_sources/<name>.py` with a class that
   satisfies `StockSource` — a `name` attribute plus `is_available`,
   `search`, and `download` methods.
2. Normalise the API's response into `Candidate` objects. Keep every
   field the corpus might later want to display or attribute (creator,
   licence, source URL, description/tags for the text channel of the
   CLIP fused ranking).
3. Give the class a stable `name` attribute and optional discoverability
   metadata such as `display_name`, `install_instructions`, `supports`,
   and `priority`. The package auto-discovers concrete adapters.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Protocol, runtime_checkable


@dataclass
class Candidate:
    """One pre-download search result, normalised across sources.

    A `Candidate` is what a source adapter returns from `search()`. It
    carries everything the corpus builder needs to decide whether to
    download, plus the provenance fields that later get copied into the
    `ClipRecord`.

    Fields that don't apply to a given kind default to zero/empty — for
    an image, `duration` is 0.0; for a source that doesn't expose fps,
    `extra` may hold it or it may be absent entirely. Adapters should
    populate as much as they cheaply can and leave the rest alone.
    """

    source: str                             # adapter name, e.g. "pexels"
    source_id: str                          # unique within that source
    source_url: str                         # landing page (human readable)
    download_url: str                       # direct file URL
    kind: str                               # "video" or "image"
    width: int = 0
    height: int = 0
    duration: float = 0.0                   # seconds (0 for images)
    creator: str = ""                       # attribution name
    license: str = ""                       # licence string or URL
    source_tags: str = ""                   # title + description + tags joined
    thumbnail_url: str = ""                 # for previews and image-fallback embeds
    extra: dict[str, Any] = field(default_factory=dict)  # source-specific junk

    @property
    def clip_id(self) -> str:
        """Stable ID used as the corpus row key.

        Format is ``"<source>_<source_id>"``. Matches the convention in
        `lib/corpus.ClipRecord`, so the corpus builder can copy this
        directly when it materialises the row.
        """
        return f"{self.source}_{self.source_id}"


@dataclass
class SearchFilters:
    """Filters a source adapter applies when searching.

    Not every source supports every filter — adapters MAY ignore fields
    they don't understand. The corpus builder sets these liberally and
    trusts each source to do the best it can with what it has. The
    missing filters are caught later by the agent at retrieval time.
    """

    kind: str = "video"                     # "video", "image", or "any"
    min_duration: Optional[float] = None    # seconds; None = no floor
    max_duration: Optional[float] = None    # seconds; None = no ceiling
    orientation: Optional[str] = None       # "landscape" | "portrait" | "square"
    min_width: Optional[int] = None         # resolution floor in pixels
    per_page: int = 20
    page: int = 1


@runtime_checkable
class StockSource(Protocol):
    """Protocol every stock source adapter must satisfy.

    Attributes
    ----------
    name:
        Stable key used in the corpus (becomes the prefix of each
        `ClipRecord.clip_id`) and in any agent-facing source list. Do
        NOT change it after a corpus has been built against it —
        existing rows would orphan.

    Methods
    -------
    is_available:
        Cheap, non-network check. Answers "does the environment have
        the keys / dependencies this source needs?" The corpus builder
        silently skips unavailable sources during fan-out.

    search:
        Returns a flat list of `Candidate` objects in whatever order
        the source's own relevance ranking gave them. An empty list is
        legal (and common for niche queries). Network errors should be
        raised — the corpus builder catches and logs per-source so one
        flaky API doesn't poison the whole run.

    download:
        Saves the candidate's file to `out_path` (creating parent
        directories if needed) and returns the final path. This is a
        blocking call; any caching is the corpus builder's
        responsibility, not the adapter's.
    """

    name: str

    def is_available(self) -> bool: ...

    def search(self, query: str, filters: SearchFilters) -> list[Candidate]: ...

    def download(self, candidate: Candidate, out_path: Path) -> Path: ...
