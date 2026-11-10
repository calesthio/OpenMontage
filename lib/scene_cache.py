"""Scene-level content hashing and caching utility for OpenMontage.

Enables incremental re-renders where modifying a single scene in a script
or scene plan only re-synthesizes and re-renders that specific scene clip,
leaving all other scene assets untouched.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any, Callable, Optional


def compute_scene_hash(
    scene_id: str,
    narration_text: str,
    scene_props: dict[str, Any],
    style_name: str = "",
    duration_s: float = 0.0,
) -> str:
    """Compute deterministic SHA-256 hash for a scene's specification."""
    spec = {
        "scene_id": scene_id,
        "narration": narration_text.strip(),
        "props": scene_props,
        "style": style_name,
        "duration": round(duration_s, 2),
    }
    dumped = json.dumps(spec, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()[:16]


class SceneCacheManager:
    """Manages scene-level caching of audio and video clips for a project."""

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir).resolve()
        self.cache_dir = self.project_dir / ".cache" / "scenes"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.cache_dir / "cache_manifest.json"
        self._manifest = self._load_manifest()

    def _load_manifest(self) -> dict[str, Any]:
        if self.manifest_path.is_file():
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_manifest(self) -> None:
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(self._manifest, f, indent=2, ensure_ascii=False)

    def get_cached_audio(self, scene_id: str, scene_hash: str) -> Optional[Path]:
        """Return path to cached audio if valid, else None."""
        entry = self.get_cached_audio_entry(scene_id, scene_hash)
        if entry:
            return Path(entry["path"])
        return None

    def get_cached_audio_entry(self, scene_id: str, scene_hash: str) -> Optional[dict[str, Any]]:
        """Return cached audio entry including metadata if valid, else None."""
        entry = self._manifest.get(f"{scene_id}:audio")
        if entry and entry.get("hash") == scene_hash:
            target = Path(entry.get("path", ""))
            if target.is_file():
                return entry
        return None

    def put_cached_audio(
        self,
        scene_id: str,
        scene_hash: str,
        audio_path: Path,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Record generated audio into scene cache."""
        self._manifest[f"{scene_id}:audio"] = {
            "hash": scene_hash,
            "path": str(audio_path),
            "metadata": metadata or {},
            "cached_at": time.time(),
        }
        self._save_manifest()

    def get_cached_clip(self, scene_id: str, scene_hash: str) -> Optional[Path]:
        """Return path to cached video clip if valid, else None."""
        entry = self._manifest.get(f"{scene_id}:clip")
        if entry and entry.get("hash") == scene_hash:
            target = Path(entry.get("path", ""))
            if target.is_file():
                return target
        return None

    def put_cached_clip(self, scene_id: str, scene_hash: str, clip_path: Path) -> None:
        """Record rendered video clip into scene cache."""
        self._manifest[f"{scene_id}:clip"] = {
            "hash": scene_hash,
            "path": str(clip_path),
            "cached_at": time.time(),
        }
        self._save_manifest()
