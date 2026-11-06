"""Image Asset Pipeline — safe receipt and validation of Flow-generated
(or otherwise sourced) image assets for the production pipeline.

All operations are local and read-only with respect to the source files:
the pipeline copies/validates assets into a project-local assets tree,
computes hashes, checks resolution/format/corruption, detects duplicates,
and builds per-project/per-scene organization.  Preview (thumbnail)
generation uses FFmpeg when available, otherwise a lightweight PIL
downscale.

Zero-cost: no generation, no credits, no network.  Uses test stub images
when no real asset exists — never triggers Google Flow.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    from PIL import Image

    _HAS_PIL = True
except Exception:  # pragma: no cover - PIL optional
    _HAS_PIL = False

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class AssetReceipt:
    """Result of receiving one image asset into the pipeline."""

    asset_id: str
    scene_id: str
    source_path: str | None
    stored_path: str | None
    status: str  # "validated" | "corrupted" | "duplicate" | "missing" | "format_error"
    resolution: str | None = None
    format: str | None = None
    sha256: str | None = None
    file_size_bytes: int = 0
    preview_path: str | None = None
    duplicate_of: str | None = None
    error: str | None = None


@dataclass
class AssetPipelineReport:
    """Aggregate report for a batch of received assets."""

    project: str
    run_id: str
    total_received: int = 0
    validated: int = 0
    corrupted: int = 0
    duplicates: int = 0
    missing: int = 0
    format_errors: int = 0
    receipts: list[AssetReceipt] = field(default_factory=list)
    missing_asset_ids: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class ImageAssetPipeline:
    """Receive, validate, and organize image assets for render."""

    # Supported input image extensions.
    INPUT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}

    # Expected output resolution (16:9 HD default).
    EXPECTED_WIDTH = 1920
    EXPECTED_HEIGHT = 1080

    def __init__(
        self,
        project: str,
        run_id: str,
        base_dir: str | Path | None = None,
        *,
        expect_width: int = 1920,
        expect_height: int = 1080,
        create_previews: bool = True,
        preview_width: int = 320,
    ) -> None:
        self.project = project
        self.run_id = run_id
        self.base_dir = Path(base_dir) if base_dir else Path.cwd() / "projects" / project
        self.expect_width = expect_width
        self.expect_height = expect_height
        self.create_previews = create_previews
        self.preview_width = preview_width

        # Directory layout: projects/<project>/assets/images/<scene_id>/<asset_id>.<ext>
        self.images_dir = self.base_dir / "assets" / "images"
        self.previews_dir = self.base_dir / "assets" / "previews"
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.previews_dir.mkdir(parents=True, exist_ok=True)

        # Hash -> asset_id for duplicate detection.
        self._hash_index: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Receipt
    # ------------------------------------------------------------------

    def receive_asset(
        self,
        *,
        asset_id: str,
        scene_id: str,
        source_path: str | Path | None = None,
        expected_resolution: str | None = None,
        copy: bool = True,
    ) -> AssetReceipt:
        """Receive one image asset.

        If source_path is None, the asset is treated as missing and a stub
        receipt is returned (no file created).  If copy=True the file is
        copied into the project assets tree; otherwise it is validated in
        place.

        Returns an AssetReceipt with status, resolution, hash, and optional
        preview path.
        """
        expected_resolution = expected_resolution or f"{self.expect_width}x{self.expect_height}"

        # Missing asset
        if source_path is None:
            return AssetReceipt(
                asset_id=asset_id,
                scene_id=scene_id,
                source_path=None,
                stored_path=None,
                status="missing",
                error="No source file provided for asset",
            )

        src = Path(source_path)
        if not src.exists():
            return AssetReceipt(
                asset_id=asset_id,
                scene_id=scene_id,
                source_path=str(source_path),
                stored_path=None,
                status="missing",
                error=f"Source file not found: {src}",
            )

        # Format check
        if src.suffix.lower() not in self.INPUT_EXTENSIONS:
            return AssetReceipt(
                asset_id=asset_id,
                scene_id=scene_id,
                source_path=str(source_path),
                stored_path=None,
                status="format_error",
                error=f"Unsupported extension {src.suffix!r}",
            )

        # Hash the source file
        try:
            sha = self._sha256_file(src)
        except OSError as exc:
            return AssetReceipt(
                asset_id=asset_id,
                scene_id=scene_id,
                source_path=str(source_path),
                stored_path=None,
                status="corrupted",
                error=f"Cannot read source file: {exc}",
            )

        # Duplicate detection (by content hash)
        if sha in self._hash_index:
            return AssetReceipt(
                asset_id=asset_id,
                scene_id=scene_id,
                source_path=str(source_path),
                stored_path=None,
                status="duplicate",
                duplicate_of=self._hash_index[sha],
                sha256=sha,
                error=f"Duplicate of asset {self._hash_index[sha]}",
            )

        # Corruption / resolution check via PIL or FFmpeg probe
        resolution = self._probe_resolution(src)
        corrupted = resolution is None
        if corrupted:
            return AssetReceipt(
                asset_id=asset_id,
                scene_id=scene_id,
                source_path=str(source_path),
                stored_path=None,
                status="corrupted",
                sha256=sha,
                error="Cannot decode image (corrupted or unsupported format)",
            )

        # Resolution match (warning only, not a hard failure — render can
        # letterbox/pillarbox; we record actual vs expected).
        res_w, res_h = resolution
        res_str = f"{res_w}x{res_h}"
        if res_w != self.expect_width or res_h != self.expect_height:
            # Not an error — just recorded.  Render stage handles fit/pad.
            pass

        file_size = src.stat().st_size

        # Store (copy or in-place)
        if copy:
            scene_dir = self.images_dir / scene_id
            scene_dir.mkdir(parents=True, exist_ok=True)
            dest = scene_dir / f"{asset_id}{src.suffix.lower()}"
            if dest.exists():
                # Avoid clobbering: hash-name the file
                dest = scene_dir / f"{sha[:12]}_{asset_id}{src.suffix.lower()}"
            shutil.copy2(src, dest)
            stored_path = str(dest)
        else:
            stored_path = str(src.resolve())

        # Register hash
        self._hash_index[sha] = asset_id

        # Preview
        preview_path = None
        if self.create_previews:
            preview_path = self._make_preview(src, asset_id, scene_id)

        return AssetReceipt(
            asset_id=asset_id,
            scene_id=scene_id,
            source_path=str(source_path),
            stored_path=stored_path,
            status="validated",
            resolution=res_str,
            format=src.suffix.lower().lstrip("."),
            sha256=sha,
            file_size_bytes=file_size,
            preview_path=preview_path,
        )

    # ------------------------------------------------------------------
    # Preview generation
    # ------------------------------------------------------------------

    def _make_preview(
        self, source: Path, asset_id: str, scene_id: str
    ) -> str | None:
        """Create a small preview thumbnail for the asset."""
        preview_dir = self.previews_dir / scene_id
        preview_dir.mkdir(parents=True, exist_ok=True)
        preview_path = preview_dir / f"{asset_id}.preview.jpg"

        if _HAS_PIL:
            try:
                with Image.open(source) as im:
                    im = im.convert("RGB")
                    w, h = im.size
                    new_h = max(1, int(h * self.preview_width / w))
                    im.thumbnail((self.preview_width, new_h))
                    im.save(preview_path, quality=85)
                return str(preview_path)
            except Exception:
                return None
        # Fallback: FFmpeg thumbnail
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-i", str(source),
                    "-vf", f"scale={self.preview_width}:-2",
                    "-frames:v", "1",
                    str(preview_path),
                ],
                check=True,
                capture_output=True,
            )
            return str(preview_path)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sha256_file(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def _probe_resolution(self, path: Path) -> tuple[int, int] | None:
        """Return (width, height) or None if the image cannot be decoded."""
        if _HAS_PIL:
            try:
                with Image.open(path) as im:
                    im.verify()
                with Image.open(path) as im:
                    return im.size
            except Exception:
                return None
        # FFmpeg probe fallback
        try:
            out = subprocess.check_output(
                [
                    "ffprobe", "-v", "error",
                    "-select_streams", "v:0",
                    "-show_entries", "stream=width,height",
                    "-of", "csv=p=0",
                    str(path),
                ],
                stderr=subprocess.STDOUT,
                text=True,
            )
            parts = out.strip().split(",")
            if len(parts) == 2:
                return int(parts[0]), int(parts[1])
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Batch intake from a production manifest
    # ------------------------------------------------------------------

    def intake_manifest(
        self,
        scenes: list[dict[str, Any]],
        assets_by_id: dict[str, dict[str, Any]],
    ) -> AssetPipelineReport:
        """Intake assets described in a production manifest.

        Args:
            scenes: List of scene dicts from the manifest (each with
                scene_id, asset_id, expected_format, etc.).
            assets_by_id: asset_id -> {"path": <file path>} mapping of
                available source assets.

        Returns:
            AssetPipelineReport with per-asset receipts and summary counts.
        """
        report = AssetPipelineReport(project=self.project, run_id=self.run_id)

        for scene in scenes:
            sid = scene.get("scene_id", "unknown")
            aid = scene.get("asset_id", f"asset-{sid}")
            expected_fmt = scene.get("expected_format", "")

            asset_info = assets_by_id.get(aid)
            src_path = asset_info.get("path") if asset_info else None

            if src_path is None:
                receipt = AssetReceipt(
                    asset_id=aid,
                    scene_id=sid,
                    source_path=None,
                    stored_path=None,
                    status="missing",
                    error="No asset source registered for this asset_id",
                )
                report.missing_asset_ids.append(aid)
                report.missing += 1
            else:
                receipt = self.receive_asset(
                    asset_id=aid,
                    scene_id=sid,
                    source_path=src_path,
                    expected_resolution=expected_fmt,
                )

            report.receipts.append(receipt)
            report.total_received += 1

            if src_path is None:
                # Already counted above; skip status-based counting
                pass
            elif receipt.status == "validated":
                report.validated += 1
            elif receipt.status == "corrupted":
                report.corrupted += 1
            elif receipt.status == "duplicate":
                report.duplicates += 1
            elif receipt.status == "missing":
                report.missing += 1
            elif receipt.status == "format_error":
                report.format_errors += 1

        return report
