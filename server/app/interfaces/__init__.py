"""Evolution seams — swappable backends selected by env var.

Each capability that is expected to change as the platform scales is behind an
interface with a v1 default implementation. Swapping to queue/object-storage/
OAuth is adding an adapter class + flipping an env var, NOT rewriting call
sites. Selection is centralized here so the rest of the app stays impl-agnostic.

    OM_STORAGE_BACKEND=local            (future: s3, oss)
    OM_JOB_QUEUE=asyncio                (future: redis, celery)
    OM_AUTH_PROVIDER=passphrase         (future: oauth, sso)
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from app.interfaces.auth import AuthProvider, PassphraseAuth
from app.interfaces.queue import AsyncioJobQueue, JobQueue
from app.interfaces.storage import LocalStorage, StorageBackend

logger = logging.getLogger(__name__)

# Registries — extend by adding an adapter class here.
_STORAGE = {"local": LocalStorage}
_QUEUES = {"asyncio": AsyncioJobQueue}
_AUTH = {"passphrase": PassphraseAuth}

_STORAGE_ROADMAP = ["s3", "oss"]
_QUEUE_ROADMAP = ["redis", "celery"]
_AUTH_ROADMAP = ["oauth", "sso"]


@lru_cache(maxsize=1)
def get_storage() -> StorageBackend:
    key = os.environ.get("OM_STORAGE_BACKEND", "local").lower()
    if key not in _STORAGE:
        logger.warning("Unknown OM_STORAGE_BACKEND=%r; falling back to 'local'", key)
    return _STORAGE.get(key, LocalStorage)()


@lru_cache(maxsize=1)
def get_job_queue() -> JobQueue:
    key = os.environ.get("OM_JOB_QUEUE", "asyncio").lower()
    if key not in _QUEUES:
        logger.warning("Unknown OM_JOB_QUEUE=%r; falling back to 'asyncio'", key)
    return _QUEUES.get(key, AsyncioJobQueue)()


@lru_cache(maxsize=1)
def get_auth_provider() -> AuthProvider:
    key = os.environ.get("OM_AUTH_PROVIDER", "passphrase").lower()
    if key not in _AUTH:
        logger.warning("Unknown OM_AUTH_PROVIDER=%r; falling back to 'passphrase'", key)
    return _AUTH.get(key, PassphraseAuth)()


def active_backends() -> dict:
    """Live view of which adapter each seam is running, for the settings page."""
    return {
        "storage": {
            "active": get_storage().name,
            "available": sorted(_STORAGE),
            "planned": _STORAGE_ROADMAP,
        },
        "queue": {
            "active": get_job_queue().name,
            "available": sorted(_QUEUES),
            "planned": _QUEUE_ROADMAP,
        },
        "auth": {
            "active": get_auth_provider().name,
            "available": sorted(_AUTH),
            "planned": _AUTH_ROADMAP,
            # Unlike storage/queue (genuinely used for every operation),
            # nothing in server/app actually calls AuthProvider.verify() —
            # no route has a Depends() checking it. Reporting "active" the
            # same way as the other two seams read as "requests are
            # authenticated," which was false. This is a deliberate choice
            # for a local single-user tool, not an oversight to silently
            # paper over — surface it honestly instead.
            "enforced": False,
        },
    }
