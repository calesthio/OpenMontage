"""E5 footage-classifier tests.

Verifies the footage rights classifier (lib/footage_classifier.py):
third-party credit => rights_basis "unknown", usable False (REJECT per
RIGHTS_MODEL.md); valid rights_basis => usable True.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.footage_classifier import classify_footage  # noqa: E402


def test_third_party_credit_rejected():
    """A clip with third-party credit is unknown/not usable (REJECT)."""
    result = classify_footage(
        {"rights_basis": "source_policy_us_gov", "third_party_credit": True}
    )
    assert result["rights_basis"] == "unknown"
    assert result["usable"] is False
    assert "third-party" in result["reason"].lower()


def test_valid_rights_basis_usable():
    """A clip with explicit_license or source_policy_us_gov is usable."""
    for basis in ("explicit_license", "source_policy_us_gov"):
        result = classify_footage({"rights_basis": basis})
        assert result["rights_basis"] == basis
        assert result["usable"] is True


def test_missing_rights_basis_rejected():
    """A clip without a rights_basis is unknown/not usable."""
    result = classify_footage({})
    assert result["rights_basis"] == "unknown"
    assert result["usable"] is False


def test_unknown_rights_basis_rejected():
    """A clip with rights_basis 'unknown' is not usable."""
    result = classify_footage({"rights_basis": "unknown"})
    assert result["rights_basis"] == "unknown"
    assert result["usable"] is False


def test_third_party_credit_blocks_valid_rights_basis():
    """Third-party credit overrides an otherwise-valid rights_basis."""
    result = classify_footage(
        {"rights_basis": "explicit_license", "third_party_credit": "yes"}
    )
    assert result["rights_basis"] == "unknown"
    assert result["usable"] is False
