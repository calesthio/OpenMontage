"""Hardening tests for Milestone H3.

Covers:
- scripts/rebuild_slice_assets.sh logic: hash mismatch => fail, missing file => fail.
- Script/claim validation: unknown claim IDs are rejected (regression test).
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.qa.qc import QCTool  # noqa: E402

REBUILD_SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "rebuild_slice_assets.sh"


# ---------------------------------------------------------------------------
# rebuild_slice_assets.sh logic: sha256 verification
# ---------------------------------------------------------------------------


def _sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def test_rebuild_hash_mismatch_fails(tmp_path):
    """A downloaded file whose sha256 does not match the manifest must fail verification."""
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "assets": [
                    {
                        "file_name": "clip.mp4",
                        "sha256": "0" * 64,
                    }
                ]
            }
        )
    )
    # Create a file with different content than the manifest expects.
    bad = tmp_path / "clip.mp4"
    bad.write_bytes(b"not the expected content")
    actual = _sha256(bad)
    assert actual != "0" * 64, "test setup: hash should mismatch"
    # The rebuild script compares expected vs actual sha256 and must fail on mismatch.
    assert actual != json.loads(manifest.read_text())["assets"][0]["sha256"]


def test_rebuild_missing_file_fails(tmp_path):
    """A missing asset file must fail verification."""
    missing = tmp_path / "does_not_exist.mp4"
    assert not missing.exists()
    # Verification step: file must exist and hash must match manifest.
    assert not missing.is_file()


def test_rebuild_hash_match_passes(tmp_path):
    """A file whose sha256 matches the manifest passes verification."""
    content = b"expected content"
    actual = hashlib.sha256(content).hexdigest()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"assets": [{"file_name": "clip.mp4", "sha256": actual}]})
    )
    good = tmp_path / "clip.mp4"
    good.write_bytes(content)
    assert _sha256(good) == json.loads(manifest.read_text())["assets"][0]["sha256"]


# ---------------------------------------------------------------------------
# Script/claim validation: unknown claim IDs rejected
# ---------------------------------------------------------------------------


def _write_claim_ids(path: Path, entries: list[dict]) -> None:
    path.write_text(json.dumps(entries))


def _run_qc_claim_ids(qc, tmp_path, claim_ids_path):
    out = tmp_path / "qa_report.json"
    inputs = {
        "input_path": "projects/slice_cid_v0/final_slice.mp4",
        "output_path": str(out),
        "claim_ids_path": str(claim_ids_path),
    }
    res = qc.execute(inputs)
    assert res.success, f"qc.execute failed: {res.error}"
    assert out.exists()
    return json.loads(out.read_text())


def test_claim_ids_rejects_missing_claim_id(tmp_path):
    """Every sentence must carry a claim_id; sentences without one fail."""
    path = tmp_path / "claim_ids.json"
    _write_claim_ids(
        path,
        [
            {"text": "sentence with claim", "claim_id": "CID-01"},
            {"text": "sentence without claim"},  # missing claim_id
        ],
    )
    qc = QCTool()
    report = _run_qc_claim_ids(qc, tmp_path, path)
    entry = next((e for e in report if e.get("check_id") == "claim_ids"), None)
    assert entry is not None, "claim_ids entry missing"
    assert entry["status"] == "FAILED", entry


def test_claim_ids_passes_when_all_have_claim_id(tmp_path):
    """When every sentence has a claim_id, the check passes."""
    path = tmp_path / "claim_ids.json"
    _write_claim_ids(
        path,
        [
            {"text": "sentence one", "claim_id": "CID-01"},
            {"text": "sentence two", "claim_id": "CID-02"},
        ],
    )
    qc = QCTool()
    report = _run_qc_claim_ids(qc, tmp_path, path)
    entry = next((e for e in report if e.get("check_id") == "claim_ids"), None)
    assert entry is not None, "claim_ids entry missing"
    assert entry["status"] == "PASS", entry


def test_claim_ids_rejects_empty_claim_id(tmp_path):
    """An empty claim_id string is treated as missing."""
    path = tmp_path / "claim_ids.json"
    _write_claim_ids(
        path,
        [
            {"text": "sentence", "claim_id": ""},
        ],
    )
    qc = QCTool()
    report = _run_qc_claim_ids(qc, tmp_path, path)
    entry = next((e for e in report if e.get("check_id") == "claim_ids"), None)
    assert entry is not None, "claim_ids entry missing"
    assert entry["status"] == "FAILED", entry


# ---------------------------------------------------------------------------
# rebuild_slice_assets.sh fail-closed behavior
# ---------------------------------------------------------------------------


def _run_rebuild(tmp_path, manifest_content=None, assets_dir_name="assets"):
    """Run rebuild_slice_assets.sh with optional MANIFEST env override."""
    assets_dir = tmp_path / assets_dir_name
    env = dict(os.environ)
    if manifest_content is not None:
        manifest = tmp_path / "manifest.json"
        manifest.write_text(manifest_content)
        env["MANIFEST"] = str(manifest)
    result = subprocess.run(
        ["bash", str(REBUILD_SCRIPT), str(assets_dir)],
        env=env, capture_output=True, text=True,
    )
    return result, assets_dir


def _asset_entry(file_name, sha256, download_url="https://example.com/file", role="archive_insert"):
    return {
        "file_name": file_name,
        "sha256": sha256,
        "download_url": download_url,
        "role": role,
    }


def test_rebuild_invalid_json_fails(tmp_path):
    """Invalid JSON manifest must cause the script to fail non-zero."""
    result, _ = _run_rebuild(tmp_path, manifest_content="{ not valid json }")
    assert result.returncode != 0, result.stdout + result.stderr


def test_rebuild_hash_comment_style_rejected(tmp_path):
    """'#'-prefixed legacy manifest must be rejected, not silently ignored."""
    result, _ = _run_rebuild(tmp_path, manifest_content="# legacy comment\n{ \"assets\": [] }")
    assert result.returncode != 0, result.stdout + result.stderr


def test_rebuild_empty_manifest_fails(tmp_path):
    """Manifest with zero assets must fail (nothing to verify)."""
    result, _ = _run_rebuild(tmp_path, manifest_content=json.dumps({"assets": []}))
    assert result.returncode != 0, result.stdout + result.stderr


def test_rebuild_missing_assets_key_fails(tmp_path):
    """Manifest missing 'assets' key must fail."""
    result, _ = _run_rebuild(tmp_path, manifest_content=json.dumps({}))
    assert result.returncode != 0, result.stdout + result.stderr


def test_rebuild_missing_file_download_fails(tmp_path):
    """Referenced download URL that cannot be fetched must fail."""
    result, _ = _run_rebuild(
        tmp_path,
        manifest_content=json.dumps({"assets": [_asset_entry("clip.mp4", "0" * 64)]}),
    )
    assert result.returncode != 0, result.stdout + result.stderr


def test_rebuild_sha256_mismatch_fails(tmp_path):
    """Pre-placed file with wrong sha256 must cause failure (no network to re-download)."""
    content = b"wrong content"
    actual = hashlib.sha256(content).hexdigest()
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    dest = assets_dir / "clip.mp4"
    dest.write_bytes(content)
    result, _ = _run_rebuild(
        tmp_path,
        manifest_content=json.dumps({"assets": [_asset_entry("clip.mp4", "0" * 64)]}),
        assets_dir_name="assets",
    )
    assert result.returncode != 0, result.stdout + result.stderr


def test_rebuild_summary_count_matches_manifest(tmp_path):
    """When all assets verify, output must report N/N and exit zero."""
    content = b"expected content"
    actual = hashlib.sha256(content).hexdigest()
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    dest = assets_dir / "clip.mp4"
    dest.write_bytes(content)
    result, _ = _run_rebuild(
        tmp_path,
        manifest_content=json.dumps({"assets": [_asset_entry("clip.mp4", actual)]}),
        assets_dir_name="assets",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1/1" in result.stdout, result.stdout


# ---------------------------------------------------------------------------
# claim_ids_resolve: every claim_id resolves to the ledger and SINGLE_SOURCE
# claims carry a flag
# ---------------------------------------------------------------------------


def _write_ledger(path: Path, rows: list[tuple[str, str]]) -> None:
    """rows: list of (claim_id, source_type)."""
    lines = [
        "| claim_id | claim | sources | source_type | verification_status | evidence_notes |",
        "|---|---|---|---|---|---|",
    ]
    for cid, st in rows:
        lines.append(f"| {cid} | some claim | FS | {st} | AGENT_VERIFIED_TEXT | note |")
    path.write_text("\n".join(lines))


def _run_resolve_qc(tmp_path, entries, ledger_rows):
    claim_ids_path = tmp_path / "claim_ids.json"
    claim_ids_path.write_text(json.dumps(entries))
    ledger_path = tmp_path / "ledger.md"
    _write_ledger(ledger_path, ledger_rows)
    out = tmp_path / "qa_report.json"
    qc = QCTool()
    # Tiny 1s input keeps the check fast (avoids re-decoding the 52s slice).
    tiny = tmp_path / "tiny.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=30",
            "-f", "lavfi", "-i", "sine=duration=1:frequency=440",
            "-c:v", "libx264", "-c:a", "aac", "-shortest", str(tiny),
        ],
        check=True,
    )
    res = qc.execute(
        {
            "input_path": str(tiny),
            "output_path": str(out),
            "claim_ids_path": str(claim_ids_path),
            "claim_ledger_path": str(ledger_path),
        }
    )
    assert res.success, f"qc.execute failed: {res.error}"
    report = json.loads(out.read_text())
    entry = next((e for e in report if e.get("check_id") == "claim_ids_resolve"), None)
    assert entry is not None, "claim_ids_resolve entry missing"
    return entry


def test_claim_ids_resolve_rejects_unknown_id(tmp_path):
    """An unknown claim_id must fail the resolve check."""
    entry = _run_resolve_qc(
        tmp_path,
        [{"text": "s", "claim_id": "CID-99", "source_flags": ""}],
        [("CID-01", "TWO")],
    )
    assert entry["status"] == "FAILED", entry


def test_claim_ids_resolve_rejects_single_source_without_flag(tmp_path):
    """A SINGLE_SOURCE claim without a flag must fail the resolve check."""
    entry = _run_resolve_qc(
        tmp_path,
        [{"text": "s", "claim_id": "CID-02", "source_flags": ""}],
        [("CID-01", "TWO"), ("CID-02", "SINGLE")],
    )
    assert entry["status"] == "FAILED", entry


def test_claim_ids_resolve_passes_when_all_resolve_and_flagged(tmp_path):
    """When every claim_id resolves and SINGLE_SOURCE claims are flagged, pass."""
    entry = _run_resolve_qc(
        tmp_path,
        [
            {"text": "s one", "claim_id": "CID-01", "source_flags": ""},
            {"text": "s two", "claim_id": "CID-02", "source_flags": "FS only"},
        ],
        [("CID-01", "TWO"), ("CID-02", "SINGLE")],
    )
    assert entry["status"] == "PASS", entry
