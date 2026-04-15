"""Stock media source adapters.

Unified-protocol wrappers around free stock APIs (Pexels, Archive.org,
NASA, ...) used by `corpus_builder` to populate the local clip corpus.
See `base.py` for the protocol contract and the "adding a new source"
checklist.

Discovery
---------
Adapters are auto-discovered from this package. `all_sources()` returns
one instance of every concrete adapter class found under
`tools.video.stock_sources`, ordered by each class's optional
`priority` and then by name. `available_sources()` filters to the ones
whose `is_available()` returns True right now.

This keeps source discoverability aligned with the rest of the repo:
adding a new adapter file is enough to make it visible to
`corpus_builder` and to preflight metadata.
"""
from __future__ import annotations

import importlib
import inspect
import pkgutil

from .base import Candidate, SearchFilters, StockSource

__all__ = [
    "Candidate",
    "SearchFilters",
    "StockSource",
    "all_sources",
    "available_sources",
    "get_source",
    "source_catalog",
    "source_summary",
]

def _is_source_adapter_class(cls: type) -> bool:
    """Return True for concrete source adapters in this package."""
    return (
        inspect.isclass(cls)
        and cls.__module__.startswith(f"{__name__}.")
        and cls.__module__ != f"{__name__}.base"
        and isinstance(getattr(cls, "name", None), str)
        and bool(getattr(cls, "name", None))
        and callable(getattr(cls, "is_available", None))
        and callable(getattr(cls, "search", None))
        and callable(getattr(cls, "download", None))
    )


def _source_classes() -> list[type]:
    """Auto-discover stock source classes under this package."""
    discovered: dict[str, type] = {}
    for module_info in pkgutil.iter_modules(__path__, f"{__name__}."):
        if module_info.ispkg or module_info.name.endswith(".base"):
            continue
        module = importlib.import_module(module_info.name)
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if not _is_source_adapter_class(cls):
                continue
            discovered[getattr(cls, "name")] = cls
    return sorted(
        discovered.values(),
        key=lambda cls: (
            int(getattr(cls, "priority", 100)),
            getattr(cls, "display_name", getattr(cls, "name")).lower(),
        ),
    )


def all_sources() -> list[StockSource]:
    """Instantiate every registered adapter, whether available or not.

    Returned instances are cheap — adapters keep no state beyond env
    var reads, so constructing them has no cost. Use this when you
    want to show the user what sources exist regardless of whether
    their credentials are configured.
    """
    return [cls() for cls in _source_classes()]


def available_sources() -> list[StockSource]:
    """Return only the adapters whose `is_available()` is True.

    This is what the corpus builder uses during a normal run. An empty
    list means no sources are configured — the caller should surface
    that to the user with install instructions, not silently produce
    an empty corpus.
    """
    return [s for s in all_sources() if s.is_available()]


def source_catalog() -> list[dict[str, object]]:
    """Return discoverability metadata for every stock source."""
    catalog: list[dict[str, object]] = []
    for source in all_sources():
        cls = source.__class__
        available = bool(source.is_available())
        catalog.append({
            "name": source.name,
            "display_name": getattr(cls, "display_name", source.name),
            "provider": getattr(cls, "provider", source.name),
            "status": "available" if available else "unavailable",
            "install_instructions": getattr(
                cls,
                "install_instructions",
                "See the source adapter docs for setup details.",
            ),
            "supports": getattr(cls, "supports", {}),
        })
    return catalog


def source_summary() -> dict[str, object]:
    """Summarize source availability for preflight and tool contracts."""
    catalog = source_catalog()
    available = [entry["name"] for entry in catalog if entry["status"] == "available"]
    unavailable = [entry["name"] for entry in catalog if entry["status"] != "available"]
    return {
        "configured": len(available),
        "total": len(catalog),
        "available_source_names": available,
        "unavailable_source_names": unavailable,
    }


def get_source(name: str) -> StockSource:
    """Look up a single adapter by its `name` attribute.

    Raises `KeyError` if no registered adapter claims that name. Useful
    for tests and for agents that want to pin to a specific source
    (e.g. "only Archive.org for this topic").
    """
    for s in all_sources():
        if s.name == name:
            return s
    raise KeyError(f"No stock source registered with name={name!r}")
