"""Image Uniqueness — near-duplicate detection for generated images.

Computes an average hash (aHash) of each image and flags near-duplicates via
Hamming distance.  When a duplicate is detected the caller can trigger a
re-roll with a revised prompt via :mod:`lib.prompt_engineer`.

All work is local and zero-cost: no model calls, no generation, no credits.
Requires Pillow (already a project dependency).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

# Hamming-distance threshold above which two images are considered near-duplicates.
# 0 = identical; larger = more permissive.  5/64 is a conservative starting point.
DUPLICATE_THRESHOLD = 5

HASH_SIZE = 8  # aHash grid (HASH_SIZE x HASH_SIZE)


@dataclass
class ImageHash:
    """Per-image fingerprint and metadata."""

    image_path: str
    sha256: str
    ahash: str  # hex string of HASH_SIZE*HASH_SIZE bits
    size: tuple[int, int]  # (width, height)
    duplicate_of: str | None = None  # path of the image it duplicates, if any
    hamming_distance: int | None = None


@dataclass
class UniquenessReport:
    """Result of checking a batch of images for duplicates."""

    total: int = 0
    unique: int = 0
    duplicates: int = 0
    hashes: dict[str, ImageHash] = field(default_factory=dict)  # path -> ImageHash
    duplicate_groups: list[list[str]] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    @property
    def duplicate_rate(self) -> float:
        return self.duplicates / self.total if self.total else 0.0


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_ahash(image_path: str, hash_size: int = HASH_SIZE) -> str:
    """Average hash of an image as a hex string.

    Resizes to ``hash_size x hash_size`` grayscale, thresholds at the mean,
    returns one bit per cell (1 = above mean).
    """
    with Image.open(image_path) as img:
        small = img.convert("L").resize((hash_size, hash_size))
        pixels = list(small.tobytes())
    mean = sum(pixels) / len(pixels)
    bits = 0
    for i, p in enumerate(pixels):
        if p > mean:
            bits |= 1 << (len(pixels) - 1 - i)
    return format(bits, f"0{hash_size * hash_size}x")


def _hamming(a_hash: str, b_hash: str) -> int:
    """Hamming distance between two equal-length hex hash strings."""
    xa = int(a_hash, 16)
    xb = int(b_hash, 16)
    return bin(xa ^ xb).count("1")


def check_uniqueness(image_paths: list[str], *, threshold: int = DUPLICATE_THRESHOLD) -> UniquenessReport:
    """Check a list of images for near-duplicates.

    Returns an :class:`UniquenessReport`.  Images whose aHash is within
    ``threshold`` Hamming distance of an earlier image are flagged as
    duplicates (the first occurrence wins).
    """
    report = UniquenessReport()
    report.total = len(image_paths)
    accepted: list[ImageHash] = []

    for path in image_paths:
        p = Path(path)
        if not p.exists():
            report.issues.append(f"unreadable image: {path}")
            continue
        try:
            sha = _sha256_file(path)
            ahash = compute_ahash(path)
        except Exception as exc:  # noqa: BLE001
            report.issues.append(f"hash failed for {path}: {exc}")
            continue

        info = ImageHash(image_path=path, sha256=sha, ahash=ahash, size=_size(path))
        report.hashes[path] = info

        dup_of: str | None = None
        dist: int | None = None
        for prev in accepted:
            d = _hamming(info.ahash, prev.ahash)
            if d <= threshold:
                dup_of = prev.image_path
                dist = d
                break
        if dup_of is not None:
            info.duplicate_of = dup_of
            info.hamming_distance = dist
            report.duplicates += 1
            # Group duplicates under the original.
            placed = False
            for group in report.duplicate_groups:
                if dup_of in group:
                    group.append(path)
                    placed = True
                    break
            if not placed:
                report.duplicate_groups.append([dup_of, path])
        else:
            report.unique += 1
            accepted.append(info)

    return report


def _size(path: str) -> tuple[int, int]:
    with Image.open(path) as img:
        return img.size


def build_revision_prompt(original_prompt: str, duplicate_of: str) -> str:
    """Build a revised prompt that nudges the generator away from a duplicate.

    Appends a uniqueness instruction without altering the original subject.
    """
    suffix = (
        "; unique composition, different camera angle and lighting, "
        "no repetition of the previous frame."
    )
    if original_prompt.rstrip().endswith("."):
        return original_prompt.rstrip()[:-1] + suffix + "."
    return original_prompt.rstrip() + suffix
