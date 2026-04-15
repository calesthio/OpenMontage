"""Shared clip bytes cache for the corpus builder.

Phase 1 of the shared-corpus architecture: a process-safe, LRU-evicted
cache of downloaded clip files at ``~/.openmontage/clips_cache/``.
When the corpus builder decides to fetch a candidate, it first asks
this cache whether the bytes are already on disk from a previous
project run. If yes, the cache hard-links (or copies on cross-drive)
the existing blob into the caller's corpus directory and skips the
network fetch entirely. If no, the caller downloads as usual and then
``ingest()``s the fresh bytes so the next project benefits.

Design decisions
----------------

- **Per-project corpus index stays authoritative.** This cache holds
  *bytes only*. The ``index.jsonl`` / embeddings of a project corpus
  are scoped to that project's brief, so retrieval quality is not
  polluted by clips from unrelated topics. The cache only eliminates
  redundant downloads and disk copies of the underlying mp4/jpg files.

- **Manifest is JSONL, rewritten atomically.** One entry per line with
  provenance (source, license, creator) and LRU metadata (added_at,
  last_access_at). Mutations rewrite the whole file via
  ``os.replace`` so readers always see a consistent snapshot and
  crash-mid-write only loses the in-flight mutation, not the whole
  manifest.

- **File locking on every mutation.** Concurrent corpus_builder runs
  against the same cache serialize on ``cache_manifest.lock``. Uses
  ``filelock`` when available (it is, per pip), else a naive exclusive
  create-file fallback with a polling retry. 60s timeout.

- **Hard links first, copies as fallback.** On the same filesystem,
  hard-linking the cache blob into the caller's dest dir is free on
  disk and instant on wall-time. Cross-drive (Windows C:→D:) falls
  back to ``shutil.copy2`` automatically and logs nothing — the
  caller doesn't need to care either way.

- **LRU eviction at cap.** Default cap is 20 GB, overridable via
  ``OPENMONTAGE_CACHE_MAX_GB``. When ``ingest()`` would push total
  bytes above the cap, the cache evicts least-recently-accessed
  entries until there's room. Evictions unlink the blob file and drop
  the manifest row. In-flight entries (currently being ingested) are
  protected by the lock.

- **Transparent to the agent.** No skill-level changes. The agent
  keeps calling ``corpus_builder.execute(...)`` the way it always has.
  The cache tells its story via counters in the ``stats()`` payload
  that corpus_builder bubbles up into its return value.

Non-goals (intentional for Phase 1)
-----------------------------------
- **No embedding cache.** CLIP vectors are still computed per-project.
  That's Phase 2 and is where the real wall-time wins compound.
- **No query-result cache.** Source-API calls still run every time.
  That's Phase 3 and has the highest staleness risk.
- **No cross-machine sync.** Cache lives on one filesystem; there is
  no S3 / Dropbox / rsync story. A future phase can add that.
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


# Default 20 GB cap. Overridable via OPENMONTAGE_CACHE_MAX_GB.
_DEFAULT_MAX_TOTAL_BYTES = 20 * 1024 * 1024 * 1024

# Reject ingesting a source file under this size — almost always a
# failed/empty download that the caller didn't catch.
_MIN_USABLE_BYTES = 1024


# ----------------------------------------------------------------------
# Config resolution
# ----------------------------------------------------------------------


def default_cache_dir() -> Path:
    """Resolve the cache directory.

    Honors ``OPENMONTAGE_CACHE_DIR`` if set, else falls back to
    ``~/.openmontage/clips_cache``. Does not create the directory —
    that happens in ``ClipCache.__init__`` on first use.
    """
    override = os.environ.get("OPENMONTAGE_CACHE_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".openmontage" / "clips_cache"


def default_max_total_bytes() -> int:
    """Resolve the max-cache-size budget.

    Honors ``OPENMONTAGE_CACHE_MAX_GB`` (float or int) if set, else
    returns the default 20 GB. Invalid overrides silently fall back to
    the default rather than crashing — the cache shouldn't bring down
    a production run over a bad env var.
    """
    override = os.environ.get("OPENMONTAGE_CACHE_MAX_GB")
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
class CacheEntry:
    """One row in the cache manifest.

    Every field except ``clip_id``/``file_name``/``size_bytes`` is
    provenance metadata that the agent may want to display or attribute
    downstream. Stored flat (no nesting) so JSONL lines stay short.
    """

    clip_id: str
    file_name: str          # relative to cache_dir, e.g. "pexels_10039002.mp4"
    size_bytes: int
    added_at: float
    last_access_at: float
    source: str = ""
    source_id: str = ""
    source_url: str = ""
    license: str = ""
    creator: str = ""
    source_tags: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CacheEntry":
        # Tolerate extra fields from future schema evolution — only
        # read the ones we know about. Missing fields default.
        return cls(
            clip_id=str(d["clip_id"]),
            file_name=str(d["file_name"]),
            size_bytes=int(d.get("size_bytes", 0) or 0),
            added_at=float(d.get("added_at", 0.0) or 0.0),
            last_access_at=float(
                d.get("last_access_at", d.get("added_at", 0.0)) or 0.0
            ),
            source=str(d.get("source", "") or ""),
            source_id=str(d.get("source_id", "") or ""),
            source_url=str(d.get("source_url", "") or ""),
            license=str(d.get("license", "") or ""),
            creator=str(d.get("creator", "") or ""),
            source_tags=str(d.get("source_tags", "") or ""),
        )


# ----------------------------------------------------------------------
# The cache itself
# ----------------------------------------------------------------------


class ClipCache:
    """Process-safe, LRU-evicted cache of downloaded clip files.

    Not a singleton — but see ``get_default_cache()`` for the common
    singleton-at-default-path pattern the corpus builder uses.
    """

    MANIFEST_NAME = "cache_manifest.jsonl"
    LOCK_NAME = "cache_manifest.lock"

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        max_total_bytes: Optional[int] = None,
    ):
        self.cache_dir = Path(cache_dir) if cache_dir else default_cache_dir()
        self.max_total_bytes = (
            int(max_total_bytes)
            if max_total_bytes is not None
            else default_max_total_bytes()
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.cache_dir / self.MANIFEST_NAME
        self.lock_path = self.cache_dir / self.LOCK_NAME

        # Per-instance runtime counters. Reset every time a new
        # ClipCache object is built. For persistent totals, sum
        # across runs in the calling layer.
        self.hits = 0
        self.misses = 0
        self.evictions_count = 0
        self.bytes_evicted = 0

    # ------------------------------------------------------------------
    # Locking
    # ------------------------------------------------------------------

    @contextmanager
    def _locked(self, timeout: float = 60.0) -> Iterator[None]:
        """Acquire an exclusive lock for the duration of the block.

        Prefers ``filelock.FileLock`` (proper cross-platform, timeout
        support, reentrant). Falls back to a naive O_EXCL create-file
        lock with polling retry so the cache still works if filelock
        is somehow unavailable. The fallback is not reentrant — don't
        nest ``_locked()`` blocks.
        """
        if _HAVE_FILELOCK:
            lock = filelock.FileLock(str(self.lock_path), timeout=timeout)
            with lock:
                yield
            return

        # Fallback: O_EXCL create-file lock.
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
                f"ClipCache: could not acquire lock at {self.lock_path} "
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

    def _read_manifest(self) -> dict[str, CacheEntry]:
        """Read the manifest file into a dict keyed by clip_id.

        Malformed lines are skipped silently — a single bad row must
        not poison the whole manifest. Missing file returns an empty
        dict (first-run case).
        """
        entries: dict[str, CacheEntry] = {}
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
                        entry = CacheEntry.from_dict(d)
                        entries[entry.clip_id] = entry
                    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                        continue
        except OSError:
            # Manifest disappeared between exists() and open() —
            # treat as empty. The lock prevents this under normal
            # operation but filesystems can surprise us.
            return {}
        return entries

    def _write_manifest(self, entries: dict[str, CacheEntry]) -> None:
        """Rewrite the manifest file atomically.

        Writes to a sibling tmpfile and uses ``os.replace`` which is
        atomic on both POSIX and Windows. A crash between write and
        replace leaves the old manifest intact.
        """
        tmp_fd, tmp_name = tempfile.mkstemp(
            prefix="cache_manifest.", suffix=".tmp", dir=str(self.cache_dir)
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                for entry in entries.values():
                    f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
            os.replace(tmp_name, self.manifest_path)
        except Exception:
            # Best-effort cleanup of the tmpfile if replace failed
            try:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)
            except OSError:
                pass
            raise

    # ------------------------------------------------------------------
    # Public API — try_link, ingest, stats
    # ------------------------------------------------------------------

    def try_link(self, clip_id: str, dest: Path) -> bool:
        """Hard-link (or copy) a cached clip into ``dest`` if present.

        Returns ``True`` on cache hit, ``False`` on miss. On hit, the
        entry's ``last_access_at`` is bumped so LRU eviction keeps
        recently-used clips around.

        On manifest/filesystem drift (entry exists but blob file is
        gone), the stale entry is pruned and the call reports a miss,
        so the caller falls back to downloading fresh.
        """
        dest = Path(dest)
        with self._locked():
            entries = self._read_manifest()
            entry = entries.get(clip_id)
            if entry is None:
                self.misses += 1
                return False

            blob_path = self.cache_dir / entry.file_name
            if not blob_path.exists():
                # Drift — prune and miss.
                del entries[clip_id]
                self._write_manifest(entries)
                self.misses += 1
                return False

            dest.parent.mkdir(parents=True, exist_ok=True)
            # Remove any existing file at dest first so the hard link
            # can be created cleanly. Harmless if dest didn't exist.
            if dest.exists() or dest.is_symlink():
                try:
                    dest.unlink()
                except OSError:
                    pass

            if not _link_or_copy(blob_path, dest):
                # Link and copy both failed — treat as miss so the
                # caller redownloads. Leave the cache entry alone;
                # the blob is still valid, we just can't reach dest.
                self.misses += 1
                return False

            entry.last_access_at = time.time()
            entries[clip_id] = entry
            self._write_manifest(entries)
            self.hits += 1
            return True

    def ingest(
        self,
        clip_id: str,
        source_path: Path,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Copy/link a freshly downloaded clip file into the cache.

        ``source_path`` is the file as it already sits in the caller's
        project directory after a successful download. We do NOT move
        or mutate it — the caller keeps the file for its own pipeline
        and the cache holds a second reference via hard link (or copy
        on cross-drive).

        Returns ``True`` if the clip was added (or was already present
        and had its access time bumped), ``False`` if ingest failed
        (missing source, empty file, lock timeout, or link/copy fail).
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

        metadata = dict(metadata or {})

        with self._locked():
            entries = self._read_manifest()

            # Already cached → just bump last_access and return.
            if clip_id in entries and (
                self.cache_dir / entries[clip_id].file_name
            ).exists():
                entries[clip_id].last_access_at = time.time()
                self._write_manifest(entries)
                return True

            # Make room.
            self._evict_to_fit_locked(entries, size_bytes)

            # Name the blob ``{clip_id}{ext}``. Stable and collision-free
            # as long as clip_ids are unique (they are — {source}_{source_id}).
            ext = source_path.suffix or ""
            blob_name = f"{clip_id}{ext}"
            blob_path = self.cache_dir / blob_name

            # Clean any stale blob at the same path (drift or interrupted
            # ingest from a previous run).
            if blob_path.exists():
                try:
                    blob_path.unlink()
                except OSError:
                    return False

            if not _link_or_copy(source_path, blob_path):
                return False

            now = time.time()
            entries[clip_id] = CacheEntry(
                clip_id=clip_id,
                file_name=blob_name,
                size_bytes=size_bytes,
                added_at=now,
                last_access_at=now,
                source=str(metadata.get("source", "") or ""),
                source_id=str(metadata.get("source_id", "") or ""),
                source_url=str(metadata.get("source_url", "") or ""),
                license=str(metadata.get("license", "") or ""),
                creator=str(metadata.get("creator", "") or ""),
                source_tags=str(metadata.get("source_tags", "") or ""),
            )
            self._write_manifest(entries)
            return True

    def stats(self) -> dict[str, Any]:
        """Return a snapshot of cache state plus session counters.

        The persistent fields (``entry_count``, ``total_bytes``) reflect
        what's on disk right now. The ``*_this_session`` fields reflect
        only what this ``ClipCache`` instance has observed — they
        reset when the process exits.
        """
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
            "evictions_this_session": self.evictions_count,
            "bytes_evicted_this_session": self.bytes_evicted,
            "filelock_backend": "filelock" if _HAVE_FILELOCK else "o_excl_fallback",
        }

    # ------------------------------------------------------------------
    # LRU eviction (caller holds the lock)
    # ------------------------------------------------------------------

    def _evict_to_fit_locked(
        self, entries: dict[str, CacheEntry], needed_bytes: int
    ) -> None:
        """Evict least-recently-accessed entries until ``needed_bytes`` fits.

        Mutates ``entries`` in place. Silently skips victims whose
        blob file has already vanished (drift) so eviction is
        best-effort and does not block the ingest path.
        """
        if needed_bytes <= 0:
            return
        current_bytes = sum(e.size_bytes for e in entries.values())
        if current_bytes + needed_bytes <= self.max_total_bytes:
            return

        # Oldest first.
        sorted_victims = sorted(
            entries.values(), key=lambda e: e.last_access_at
        )
        for victim in sorted_victims:
            if current_bytes + needed_bytes <= self.max_total_bytes:
                break
            blob_path = self.cache_dir / victim.file_name
            unlinked = False
            try:
                if blob_path.exists():
                    blob_path.unlink()
                unlinked = True
            except OSError:
                # Could not delete the blob (in-use on Windows, for
                # instance). Leave the entry in place and try the next.
                continue
            if not unlinked:
                continue
            current_bytes -= victim.size_bytes
            del entries[victim.clip_id]
            self.evictions_count += 1
            self.bytes_evicted += victim.size_bytes


# ----------------------------------------------------------------------
# Module-level helpers
# ----------------------------------------------------------------------


def _link_or_copy(src: Path, dst: Path) -> bool:
    """Hard-link ``src`` to ``dst``; on failure, fall back to ``shutil.copy2``.

    Hard linking is instant and uses zero extra disk on the same
    filesystem. Cross-drive (Windows C:→D:) and cross-filesystem
    situations raise ``OSError`` on ``os.link`` and we transparently
    copy the bytes instead. Returns ``True`` on success, ``False`` if
    both link and copy failed.
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


_DEFAULT_CACHE: Optional[ClipCache] = None


def get_default_cache() -> ClipCache:
    """Return a process-level default ``ClipCache`` at the default path.

    Lazily constructed on first call. Tests that want a pristine cache
    should instantiate ``ClipCache(cache_dir=tmp_path)`` directly
    rather than going through this accessor.
    """
    global _DEFAULT_CACHE
    if _DEFAULT_CACHE is None:
        _DEFAULT_CACHE = ClipCache()
    return _DEFAULT_CACHE


def reset_default_cache() -> None:
    """Drop the cached singleton so a subsequent ``get_default_cache()``
    re-reads env vars. Useful for tests that mutate ``OPENMONTAGE_CACHE_DIR``.
    """
    global _DEFAULT_CACHE
    _DEFAULT_CACHE = None
