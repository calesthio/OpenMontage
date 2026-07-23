"""Media normalization and download helpers for Kling official providers."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from urllib.parse import urlparse


def strip_data_uri_prefix(value: str | None) -> str | None:
    """Return raw base64/content by removing a data URI prefix if present."""

    if value is None:
        return None
    marker = ";base64,"
    if value.startswith("data:") and marker in value:
        return value.split(marker, 1)[1]
    return value


def image_file_to_raw_base64(path: str | Path) -> str:
    """Read a local image file and return raw base64 without data URI prefix."""

    image_path = Path(path)
    if not image_path.is_file():
        raise FileNotFoundError(f"Image not found: {image_path}")
    return base64.b64encode(image_path.read_bytes()).decode("ascii")


def file_to_raw_base64(path: str | Path, *, label: str = "File") -> str:
    """Read a local media file and return raw base64 without a data URI prefix."""

    media_path = Path(path)
    if not media_path.is_file():
        raise FileNotFoundError(f"{label} not found: {media_path}")
    return base64.b64encode(media_path.read_bytes()).decode("ascii")


def normalize_image_input(url: str | None = None, path: str | Path | None = None) -> str | None:
    """Normalize a Kling image input to either URL or raw base64."""

    if url:
        return strip_data_uri_prefix(url)
    if path:
        return image_file_to_raw_base64(path)
    return None


def normalize_media_input(
    url: str | None = None,
    path: str | Path | None = None,
    value: str | None = None,
    *,
    label: str = "Media file",
) -> str | None:
    """Normalize a generic Kling media input to URL, raw base64, or raw provided value."""

    if value:
        return strip_data_uri_prefix(value)
    if url:
        return strip_data_uri_prefix(url)
    if path:
        return file_to_raw_base64(path, label=label)
    return None


def extension_from_url(url: str | None, default: str = ".png") -> str:
    """Infer a file extension from a URL path."""

    if not url:
        return default
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".gif",
        ".mp4",
        ".mov",
        ".m4v",
        ".mp3",
        ".wav",
        ".m4a",
        ".aac",
        ".ogg",
        ".opus",
    }:
        return suffix
    return default


def extension_from_content_type(content_type: str | None, default: str = ".png") -> str:
    if not content_type:
        return default
    ext = mimetypes.guess_extension(content_type.split(";", 1)[0].strip())
    return ext or default


def output_path_with_suffix(path: str | Path, suffix: str) -> Path:
    output_path = Path(path)
    if output_path.suffix:
        return output_path
    return output_path.with_suffix(suffix)


def numbered_output_path(first_path: Path, index: int, suffix: str) -> Path:
    if index == 0:
        return output_path_with_suffix(first_path, suffix)
    return first_path.with_name(f"{first_path.stem}_{index + 1}{suffix}")
