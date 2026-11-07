"""Claim ledger + asset provenance / rights QC (V8 §8.8, §8.10).

Every used asset — image, video, audio, music, font — must have a row in
the asset ledger with source URL, creator, license, license URL, retrieval
date, local file hash, intended commercial use flag, modification flag, and
attribution text.  Archive.org / "free download" is NOT proof of license.

Claims (scientific statements) are linked to scene manifests via claim_ids.
Conflicting claims are flagged for human review.

Zero-cost: pure Python, no network, no API calls.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ClaimRecord:
    """One scientific/factual claim — linked to scenes via claim_id."""

    claim_id: str
    text: str
    source: str  # e.g. "NASA NTRS document ID", "peer-reviewed paper DOI"
    source_url: str | None = None
    confidence: float = 1.0  # 0.0-1.0
    requires_human_review: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AssetRecord:
    """One used asset with full rights/provenance record."""

    asset_id: str
    local_path: str
    local_hash: str  # sha256 of local file
    source_url: str
    creator: str
    license: str  # e.g. "Public Domain", "CC-BY-4.0", "NASA imagery policy"
    license_url: str | None = None
    retrieval_date: str = field(
        default_factory=lambda: datetime.now(timezone.utc).date().isoformat()
    )
    intended_commercial_use: bool = True  # YouTube is commercial
    modifications: str | None = None  # e.g. "cropped, color-graded"
    attribution_text: str | None = None
    rights_verified: bool = False  # set True after human/programmatic check
    quarantined: bool = False  # True if license unclear -> human review
    quarantine_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not self.source_url:
            problems.append(f"{self.asset_id}: missing source_url")
        if not self.creator:
            problems.append(f"{self.asset_id}: missing creator")
        if not self.license:
            problems.append(f"{self.asset_id}: missing license")
        if not self.local_hash:
            problems.append(f"{self.asset_id}: missing local_hash")
        if self.intended_commercial_use and not self.rights_verified:
            problems.append(
                f"{self.asset_id}: commercial use but rights_verified=False"
            )
        if self.quarantined and not self.quarantine_reason:
            problems.append(
                f"{self.asset_id}: quarantined without quarantine_reason"
            )
        return problems


@dataclass
class ClaimLedger:
    """In-memory ledger of claims and assets for one episode."""

    episode_id: str
    claims: dict[str, ClaimRecord] = field(default_factory=dict)
    assets: dict[str, AssetRecord] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # ------------------------------------------------------------------
    # Claims
    # ------------------------------------------------------------------

    def add_claim(self, claim: ClaimRecord) -> None:
        self.claims[claim.claim_id] = claim

    def get_claim(self, claim_id: str) -> ClaimRecord | None:
        return self.claims.get(claim_id)

    # ------------------------------------------------------------------
    # Assets
    # ------------------------------------------------------------------

    def add_asset(self, asset: AssetRecord) -> None:
        self.assets[asset.asset_id] = asset

    def get_asset(self, asset_id: str) -> AssetRecord | None:
        return self.assets.get(asset_id)

    def asset_for_path(self, local_path: str) -> AssetRecord | None:
        for a in self.assets.values():
            if a.local_path == local_path:
                return a
        return None

    # ------------------------------------------------------------------
    # Rights QC
    # ------------------------------------------------------------------

    def rights_qc(self) -> dict[str, Any]:
        """QC all assets: return problems and unverified/quarantined lists."""
        problems: list[str] = []
        unverified: list[str] = []
        quarantined: list[str] = []

        for aid, asset in self.assets.items():
            problems.extend(asset.validate())
            if not asset.rights_verified:
                unverified.append(aid)
            if asset.quarantined:
                quarantined.append(aid)

        return {
            "episode_id": self.episode_id,
            "total_assets": len(self.assets),
            "total_claims": len(self.claims),
            "problems": problems,
            "unverified_assets": unverified,
            "quarantined_assets": quarantined,
            "rights_qc_passed": len(problems) == 0 and len(unverified) == 0,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "claims": {cid: c.to_dict() for cid, c in self.claims.items()},
            "assets": {aid: a.to_dict() for aid, a in self.assets.items()},
            "created_at": self.created_at,
        }


def rights_qc_report(ledger: ClaimLedger) -> dict[str, Any]:
    """Module-level convenience: run rights QC on a ledger."""
    return ledger.rights_qc()
