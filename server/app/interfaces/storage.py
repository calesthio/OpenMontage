"""Storage backend seam.

The default LocalStorage writes under projects/ and serves via the /media mount.
A future S3Storage/OSSStorage implements the same interface and returns signed
URLs — no call-site changes needed (see interfaces/__init__.get_storage).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

# server/app/interfaces/storage.py -> repo root is three parents up from app/.
_OM_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class StorageBackend(ABC):
    """Abstract project-asset storage."""

    name: str = "abstract"

    @abstractmethod
    def project_dir(self, project: str) -> Path:
        """Local working directory for a project (tools write here)."""

    @abstractmethod
    def exists(self, project: str, rel_path: str) -> bool:
        ...

    @abstractmethod
    def url_for(self, project: str, rel_path: str) -> str:
        """Return a client-fetchable URL for a stored asset."""


class LocalStorage(StorageBackend):
    """Filesystem storage under projects/, served by the FastAPI /media mount."""

    name = "local"

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or (_OM_ROOT / "projects")).resolve()

    def project_dir(self, project: str) -> Path:
        return self.root / project

    def exists(self, project: str, rel_path: str) -> bool:
        return (self.project_dir(project) / rel_path).is_file()

    def url_for(self, project: str, rel_path: str) -> str:
        rel = str(rel_path).replace("\\", "/").lstrip("/")
        return f"/media/{project}/{rel}"
