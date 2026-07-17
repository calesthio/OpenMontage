"""Cross-process advisory file lock for the cost ledger.

Why this exists
---------------
OpenMontage drives tools through separate `python -c "..."` invocations (see
AGENT_GUIDE.md). Separate processes share no threading.Lock, so an in-process
lock gives no protection at all: two concurrent tool calls would each read the
ledger, each see the same remaining daily budget, and each proceed. This is an
OS-level lock so the read-modify-write of cost_log.json is serialized across
processes.

Deliberately minimal: stdlib only, one context manager, no lock server, no
daemon, no backoff strategy, no abstraction layer. Windows uses msvcrt byte
locking; POSIX uses fcntl.flock. Both are released by the OS when the owning
process exits, so a crash cannot permanently wedge the ledger.
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

try:  # Windows
    import msvcrt
except ImportError:  # POSIX
    msvcrt = None  # type: ignore[assignment]

try:  # POSIX
    import fcntl
except ImportError:  # Windows
    fcntl = None  # type: ignore[assignment]


DEFAULT_TIMEOUT_SECONDS = 5.0
_POLL_SECONDS = 0.05


class LedgerLockError(Exception):
    """Raised when the ledger lock cannot be acquired within the timeout.

    Callers must treat this as fail-closed: without the lock the remaining
    budget cannot be read consistently, so no paid call may proceed.
    """
    pass


def _try_lock(fd: int) -> None:
    """One non-blocking attempt. Raises OSError if already held."""
    if msvcrt is not None:
        # Byte-range lock at offset 0. Must seek there first: msvcrt.locking
        # locks relative to the current file position.
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    elif fcntl is not None:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    else:  # pragma: no cover - no stdlib locking primitive available
        raise LedgerLockError(
            "Neither msvcrt nor fcntl is available; the cost ledger cannot be "
            "locked safely. Refusing to proceed (fail closed)."
        )


def _unlock(fd: int) -> None:
    if msvcrt is not None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    elif fcntl is not None:
        fcntl.flock(fd, fcntl.LOCK_UN)


@contextmanager
def ledger_lock(
    target: Path,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> Iterator[None]:
    """Hold an exclusive cross-process lock for `target`'s read-modify-write.

    The lock is taken on a sibling `<target>.lock` file rather than on the
    ledger itself, so the atomic os.replace() of the ledger cannot disturb it.

    Raises LedgerLockError on timeout. Bounded wait, not indefinite: a caller
    blocked forever on a budget check is its own kind of failure.
    """
    lock_path = target.with_suffix(target.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT)
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                _try_lock(fd)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise LedgerLockError(
                        f"Could not acquire the cost ledger lock at {lock_path} "
                        f"within {timeout:.1f}s. Another OpenMontage process is "
                        f"holding it. Refusing the paid call (fail closed): "
                        f"remaining budget cannot be read consistently."
                    )
                time.sleep(_POLL_SECONDS)
        try:
            yield
        finally:
            _unlock(fd)
    finally:
        # Closing the fd also drops the OS lock; the OS does this for us if the
        # process dies here, which is what makes a crash non-wedging.
        os.close(fd)
