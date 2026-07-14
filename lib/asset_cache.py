"""Content-addressed cache for reproducible tool outputs.

Every paid generation tool (FLUX, Imagen, ElevenLabs, Kling, ...) already
declares the two things needed to know when a call is a repeat: its
``idempotency_key_fields`` (the inputs that determine the output) and its
``determinism`` class. Nothing consumed them, so re-running a pipeline with
the same brief paid the same provider for the same bytes again. This cache
closes that gap: when a deterministic (or seed-pinned) tool is about to
produce an artifact it has produced before, the bytes are linked back from
disk and the API call is skipped.

Keyed by *content*, not by output path. The cache key is derived by the tool
(``BaseTool.cache_key``) from tool identity + version + the declared
idempotency fields, so the same prompt/seed/model resolves to the same entry
no matter where the caller asks the file to land. That is also why an edit
recomputes only what changed: touch one scene's prompt and only that scene's
key moves, so every other asset is a hit. There is no dependency graph and no
scheduler here. Correct keys make selective recompute fall out for free.

Design decisions
----------------

- **Only reproducible calls are cached.** Deterministic tools always; seeded
  tools only when a seed is pinned in the inputs (an unpinned seed is
  effectively stochastic and must not be frozen); stochastic tools never.
  The eligibility decision lives in the tool wrapper; this module trusts the
  key it is handed.

- **Manifest is JSONL, rewritten atomically.** One entry per line carrying the
  content key, the reconstruction metadata (tool, version, model, seed, the
  original ``cost_usd`` that a hit now saves, and the ToolResult ``data``
  payload), and LRU timestamps. Mutations rewrite the whole file via
  ``os.replace`` so readers always see a consistent snapshot.

- **File locking on every mutation.** Concurrent runs against the same cache
  serialize on ``asset_cache.lock``. Uses ``filelock`` when importable, else a
  naive ``O_EXCL`` create-file fallback with a polling retry. 60s timeout.

- **Hard links first, copies as fallback.** Same-filesystem restores hard-link
  the blob into the caller's output path, which is instant and free on disk.
  Cross-drive (Windows C:->D:) falls back to ``shutil.copy2``.

- **LRU eviction at cap.** Default cap is 20 GB, overridable via
  ``OPENMONTAGE_ASSET_CACHE_MAX_GB``. Ingesting past the cap evicts
  least-recently-accessed entries until there is room.

- **Off unless asked.** Enabled only when ``OPENMONTAGE_ASSET_CACHE`` is set to
  a truthy value, so it can never change the behavior of an existing run that
  did not opt in. The directory honors ``OPENMONTAGE_ASSET_CACHE_DIR``.

Non-goals (intentional for this phase)
--------------------------------------
- **Single-artifact tools only.** Tools that emit one file at ``output_path``
  (the shape of every paid image / audio / video generator here) are cached.
  Multi-artifact tools (batch image sets, TTS + sidecar metadata) are left for
  a follow-up rather than guessing a path remap.
- **No cross-machine sync.** The cache lives on one filesystem; there is no
  shared-object-store story yet.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator, Optional

try:
    import filelock  # type: ignore
    _HAVE_FILELOCK = True
except ImportError:
    _HAVE_FILELOCK = False


# Default 20 GB cap. Overridable via OPENMONTAGE_ASSET_CACHE_MAX_GB.
_DEFAULT_MAX_TOTAL_BYTES = 20 * 1024 * 1024 * 1024

# Reject ingesting an artifact under this size; almost always a failed or
# empty generation the caller did not catch.
_MIN_USABLE_BYTES = 1


# ----------------------------------------------------------------------
# Config resolution
# ----------------------------------------------------------------------


def asset_cache_enabled() -> bool:
    """Whether the asset cache is active.

    Off by default. Honors ``OPENMONTAGE_ASSET_CACHE``: ``1``/``true``/``yes``/
    ``on`` (any case) enable it; anything else (including unset) leaves it
    off, so an existing run that did not opt in behaves exactly as before.
    """
    val = os.environ.get("OPENMONTAGE_ASSET_CACHE", "").strip().lower()
    return val in {"1", "true", "yes", "on"}


def default_asset_cache_dir() -> Path:
    """Resolve the cache directory.

    Honors ``OPENMONTAGE_ASSET_CACHE_DIR`` if set, else
    ``~/.openmontage/asset_cache``. Kept separate from the clip byte cache
    (``clips_cache``) so eviction budgets do not contend.
    """
    override = os.environ.get("OPENMONTAGE_ASSET_CACHE_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".openmontage" / "asset_cache"


def default_max_total_bytes() -> int:
    """Resolve the max-cache-size budget.

    Honors ``OPENMONTAGE_ASSET_CACHE_MAX_GB`` (float or int) if set, else the
    default 20 GB. An invalid override falls back to the default rather than
    crashing a production run over a bad env var.
    """
    override = os.environ.get("OPENMONTAGE_ASSET_CACHE_MAX_GB")
    if override:
        try:
            return int(float(override) * 1024 * 1024 * 1024)
        except ValueError:
            pass
    return _DEFAULT_MAX_TOTAL_BYTES


# ----------------------------------------------------------------------
# Dataclass for one manifest row
# ----------------------------------------------------------------------


@dataclass
class AssetCacheEntry:
    """One row in the cache manifest.

    ``key`` is the content hash the tool computed. ``data_json`` is the
    ToolResult ``data`` payload serialized so a hit can hand back the same
    structured result the live call would have. ``cost_usd`` is what the
    original call cost, i.e. what a hit now saves.
    """

    key: str
    file_name: str          # relative to cache_dir, e.g. "<hash>.png"
    size_bytes: int
    added_at: float
    last_access_at: float
    tool_name: str = ""
    tool_version: str = ""
    model: str = ""
    seed: Optional[int] = None
    cost_usd: float = 0.0
    data_json: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AssetCacheEntry":
        # Tolerate extra fields from future schema evolution; only read the
        # ones we know about. Missing fields default.
        seed = d.get("seed", None)
        try:
            seed = int(seed) if seed is not None else None
        except (TypeError, ValueError):
            seed = None
        return cls(
            key=str(d["key"]),
            file_name=str(d["file_name"]),
            size_bytes=int(d.get("size_bytes", 0) or 0),
            added_at=float(d.get("added_at", 0.0) or 0.0),
            last_access_at=float(
                d.get("last_access_at", d.get("added_at", 0.0)) or 0.0
            ),
            tool_name=str(d.get("tool_name", "") or ""),
            tool_version=str(d.get("tool_version", "") or ""),
            model=str(d.get("model", "") or ""),
            seed=seed,
            cost_usd=float(d.get("cost_usd", 0.0) or 0.0),
            data_json=str(d.get("data_json", "") or ""),
        )


# ----------------------------------------------------------------------
# The cache itself
# ----------------------------------------------------------------------


class AssetCache:
    """Process-safe, LRU-evicted, content-addressed cache of tool outputs.

    Not a singleton; see ``get_default_asset_cache()`` for the process-level
    default. Tests that want a pristine cache should instantiate
    ``AssetCache(cache_dir=tmp_path)`` directly.
    """

    MANIFEST_NAME = "asset_manifest.jsonl"
    LOCK_NAME = "asset_cache.lock"

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        max_total_bytes: Optional[int] = None,
    ):
        self.cache_dir = Path(cache_dir) if cache_dir else default_asset_cache_dir()
        self.max_total_bytes = (
            int(max_total_bytes)
            if max_total_bytes is not None
            else default_max_total_bytes()
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.cache_dir / self.MANIFEST_NAME
        self.lock_path = self.cache_dir / self.LOCK_NAME

        # Per-instance runtime counters. Reset when a new AssetCache is built.
        self.hits = 0
        self.misses = 0
        self.evictions_count = 0
        self.bytes_evicted = 0
        self.cost_saved_usd = 0.0

    # ------------------------------------------------------------------
    # Locking
    # ------------------------------------------------------------------

    @contextmanager
    def _locked(self, timeout: float = 60.0) -> Iterator[None]:
        """Acquire an exclusive lock for the duration of the block.

        Prefers ``filelock.FileLock``; falls back to a naive O_EXCL create-file
        lock with polling retry so the cache still works without ``filelock``
        installed. The fallback is not reentrant, so do not nest ``_locked()``.
        """
        if _HAVE_FILELOCK:
            lock = filelock.FileLock(str(self.lock_path), timeout=timeout)
            with lock:
                yield
            return

        deadline = time.time() + timeout
        acquired = False
        while time.time() < deadline:
            try:
                fd = os.open(
                    str(self.lock_path),
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
                os.close(fd)
                acquired = True
                break
            except FileExistsError:
                time.sleep(0.05)
        if not acquired:
            raise TimeoutError(
                f"AssetCache: could not acquire lock at {self.lock_path} "
                f"after {timeout}s"
            )
        try:
            yield
        finally:
            try:
                os.unlink(self.lock_path)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Manifest I/O (caller holds the lock)
    # ------------------------------------------------------------------

    def _read_manifest(self) -> dict[str, AssetCacheEntry]:
        """Read the manifest into a dict keyed by content key.

        Malformed lines are skipped silently; one bad row must not poison the
        whole manifest. Missing file returns an empty dict (first-run case).
        """
        entries: dict[str, AssetCacheEntry] = {}
        if not self.manifest_path.exists():
            return entries
        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                        entry = AssetCacheEntry.from_dict(d)
                        entries[entry.key] = entry
                    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                        continue
        except OSError:
            return {}
        return entries

    def _write_manifest(self, entries: dict[str, AssetCacheEntry]) -> None:
        """Rewrite the manifest atomically via a sibling tmpfile + os.replace."""
        tmp_fd, tmp_name = tempfile.mkstemp(
            prefix="asset_manifest.", suffix=".tmp", dir=str(self.cache_dir)
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                for entry in entries.values():
                    f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
            os.replace(tmp_name, self.manifest_path)
        except Exception:
            try:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)
            except OSError:
                pass
            raise

    # ------------------------------------------------------------------
    # Public API: try_restore, store, stats
    # ------------------------------------------------------------------

    def try_restore(self, key: str, dest: Path) -> Optional[dict[str, Any]]:
        """Materialize a cached artifact for ``key`` into ``dest`` if present.

        Returns the reconstruction metadata (``data``, ``model``, ``seed``,
        ``cost_usd``, ``tool_name``, ``tool_version``) on a hit, or ``None`` on
        a miss. On hit the entry's ``last_access_at`` is bumped for LRU. On
        manifest/filesystem drift (entry present, blob gone) the stale entry is
        pruned and the call reports a miss so the caller regenerates.
        """
        dest = Path(dest)
        with self._locked():
            entries = self._read_manifest()
            entry = entries.get(key)
            if entry is None:
                self.misses += 1
                return None

            blob_path = self.cache_dir / entry.file_name
            if not blob_path.exists():
                del entries[key]
                self._write_manifest(entries)
                self.misses += 1
                return None

            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() or dest.is_symlink():
                try:
                    dest.unlink()
                except OSError:
                    pass

            if not _link_or_copy(blob_path, dest):
                # Cannot reach dest, so treat as a miss and let the caller regenerate.
                # The blob is still valid; leave the entry alone.
                self.misses += 1
                return None

            entry.last_access_at = time.time()
            entries[key] = entry
            self._write_manifest(entries)
            self.hits += 1
            self.cost_saved_usd += entry.cost_usd

            try:
                data = json.loads(entry.data_json) if entry.data_json else {}
            except (json.JSONDecodeError, TypeError):
                data = {}
            return {
                "data": data if isinstance(data, dict) else {},
                "model": entry.model or None,
                "seed": entry.seed,
                "cost_usd": entry.cost_usd,
                "tool_name": entry.tool_name,
                "tool_version": entry.tool_version,
            }

    def store(
        self,
        key: str,
        source_path: Path,
        *,
        tool_name: str = "",
        tool_version: str = "",
        model: str = "",
        seed: Optional[int] = None,
        cost_usd: float = 0.0,
        data: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Ingest a freshly produced artifact under ``key``.

        ``source_path`` is the file the tool just wrote to its output path. We
        do not move or mutate it; the caller keeps its file and the cache
        holds a second reference via hard link (or copy on cross-drive).
        Returns ``True`` if stored (or already present), ``False`` on failure
        (missing/empty source, lock timeout, link/copy failure).
        """
        source_path = Path(source_path)
        if not source_path.exists():
            return False
        try:
            size_bytes = source_path.stat().st_size
        except OSError:
            return False
        if size_bytes < _MIN_USABLE_BYTES:
            return False

        try:
            data_json = json.dumps(data or {}, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError):
            data_json = "{}"

        with self._locked():
            entries = self._read_manifest()

            if key in entries and (self.cache_dir / entries[key].file_name).exists():
                entries[key].last_access_at = time.time()
                self._write_manifest(entries)
                return True

            self._evict_to_fit_locked(entries, size_bytes)

            # Blob name is the key plus the source extension. Keys are SHA-256
            # hex, so they are unique and filesystem-safe.
            ext = source_path.suffix or ""
            blob_name = f"{key}{ext}"
            blob_path = self.cache_dir / blob_name

            if blob_path.exists():
                try:
                    blob_path.unlink()
                except OSError:
                    return False

            if not _link_or_copy(source_path, blob_path):
                return False

            now = time.time()
            entries[key] = AssetCacheEntry(
                key=key,
                file_name=blob_name,
                size_bytes=size_bytes,
                added_at=now,
                last_access_at=now,
                tool_name=tool_name,
                tool_version=tool_version,
                model=model,
                seed=seed,
                cost_usd=float(cost_usd or 0.0),
                data_json=data_json,
            )
            self._write_manifest(entries)
            return True

    def stats(self) -> dict[str, Any]:
        """Snapshot of cache state plus this session's hit/miss/savings counters."""
        with self._locked():
            entries = self._read_manifest()
        total_bytes = sum(e.size_bytes for e in entries.values())
        return {
            "cache_dir": str(self.cache_dir),
            "entry_count": len(entries),
            "total_bytes": total_bytes,
            "total_mb": round(total_bytes / (1024 * 1024), 1),
            "max_total_bytes": self.max_total_bytes,
            "max_total_gb": round(self.max_total_bytes / (1024 ** 3), 2),
            "usage_fraction": (
                round(total_bytes / self.max_total_bytes, 3)
                if self.max_total_bytes > 0 else 0.0
            ),
            "hits_this_session": self.hits,
            "misses_this_session": self.misses,
            "cost_saved_usd_this_session": round(self.cost_saved_usd, 4),
            "evictions_this_session": self.evictions_count,
            "bytes_evicted_this_session": self.bytes_evicted,
            "filelock_backend": "filelock" if _HAVE_FILELOCK else "o_excl_fallback",
        }

    # ------------------------------------------------------------------
    # LRU eviction (caller holds the lock)
    # ------------------------------------------------------------------

    def _evict_to_fit_locked(
        self, entries: dict[str, AssetCacheEntry], needed_bytes: int
    ) -> None:
        """Evict least-recently-accessed entries until ``needed_bytes`` fits.

        Mutates ``entries`` in place. Skips victims whose blob has already
        vanished (drift) so eviction is best-effort and never blocks a store.
        """
        if needed_bytes <= 0:
            return
        current_bytes = sum(e.size_bytes for e in entries.values())
        if current_bytes + needed_bytes <= self.max_total_bytes:
            return

        sorted_victims = sorted(entries.values(), key=lambda e: e.last_access_at)
        for victim in sorted_victims:
            if current_bytes + needed_bytes <= self.max_total_bytes:
                break
            blob_path = self.cache_dir / victim.file_name
            try:
                if blob_path.exists():
                    blob_path.unlink()
            except OSError:
                # In-use on Windows, for instance. Leave it; try the next.
                continue
            current_bytes -= victim.size_bytes
            del entries[victim.key]
            self.evictions_count += 1
            self.bytes_evicted += victim.size_bytes


# ----------------------------------------------------------------------
# Module-level helpers
# ----------------------------------------------------------------------


def _link_or_copy(src: Path, dst: Path) -> bool:
    """Hard-link ``src`` to ``dst``; on failure fall back to ``shutil.copy2``.

    Hard linking is instant and uses zero extra disk on the same filesystem.
    Cross-drive / cross-filesystem raises ``OSError`` on ``os.link`` and we
    copy the bytes instead. Returns ``True`` on success.
    """
    src = Path(src)
    dst = Path(dst)
    try:
        os.link(str(src), str(dst))
        return True
    except (OSError, NotImplementedError):
        pass
    try:
        shutil.copy2(str(src), str(dst))
        return True
    except (OSError, shutil.SameFileError):
        return False


# ----------------------------------------------------------------------
# Default-singleton accessor
# ----------------------------------------------------------------------


_DEFAULT_CACHE: Optional[AssetCache] = None


def get_default_asset_cache() -> AssetCache:
    """Return a process-level default ``AssetCache`` at the resolved path.

    Lazily constructed on first call. Tests wanting a pristine cache should
    instantiate ``AssetCache(cache_dir=tmp_path)`` directly.
    """
    global _DEFAULT_CACHE
    if _DEFAULT_CACHE is None:
        _DEFAULT_CACHE = AssetCache()
    return _DEFAULT_CACHE


def reset_default_asset_cache() -> None:
    """Drop the cached singleton so the next accessor re-reads env vars.

    Useful for tests that mutate ``OPENMONTAGE_ASSET_CACHE_DIR``.
    """
    global _DEFAULT_CACHE
    _DEFAULT_CACHE = None
