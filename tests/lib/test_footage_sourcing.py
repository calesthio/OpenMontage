"""Unit tests for lib/footage_sourcing.py (free footage sourcing + provenance).

Local-only checks: hashing and manifest writing. Network searches are not
asserted here (they require external API access).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.footage_sourcing import (  # noqa: E402
    sha256_file, write_manifest,
)


def test_sha256_file_deterministic(tmp_path):
    p = tmp_path / "a.bin"
    p.write_bytes(b"hello world")
    h1 = sha256_file(p)
    h2 = sha256_file(p)
    assert h1 == h2 == hashlib.sha256(b"hello world").hexdigest()


def test_sha256_file_differs_by_content(tmp_path):
    a = tmp_path / "a.bin"; b = tmp_path / "b.bin"
    a.write_bytes(b"aaa"); b.write_bytes(b"bbb")
    assert sha256_file(a) != sha256_file(b)


def test_write_manifest_creates_valid_json(tmp_path):
    entries = [
        {"source": "nasa", "title": "Europa Clipper", "nasa_id": "PIA26445", "license": "Public Domain"},
        {"source": "archive_org", "title": "Ambient drone", "identifier": "x", "license": "CC0"},
    ]
    out = tmp_path / "m" / "manifest.json"
    write_manifest(entries, out)
    assert out.is_file()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data == entries
    assert data[0]["source"] == "nasa"
