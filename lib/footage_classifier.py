"""Footage rights classifier.

Classifies a footage clip's rights basis per docs/openmontage/RIGHTS_MODEL.md:

* third-party credit present  => rights_basis "unknown", usable False (REJECT)
* explicit_license / source_policy_us_gov => usable True
* anything else / missing     => rights_basis "unknown", usable False

Pure function, no network, no model downloads. Intended for unit testing
(E5) and for reuse by QC/reporting stages.
"""

from __future__ import annotations

from typing import Any

VALID_RIGHTS = ("explicit_license", "source_policy_us_gov")


def classify_footage(metadata: dict[str, Any]) -> dict[str, Any]:
    """Classify a footage clip's rights basis.

    Returns a dict with keys: rights_basis, usable, reason.
    """
    md = dict(metadata or {})
    third_party = bool(md.get("third_party_credit"))
    rights_basis = md.get("rights_basis")

    if third_party:
        return {
            "rights_basis": "unknown",
            "usable": False,
            "reason": "third-party credit present -> REJECT per RIGHTS_MODEL.md",
        }
    if rights_basis in VALID_RIGHTS:
        return {
            "rights_basis": rights_basis,
            "usable": True,
            "reason": f"valid rights_basis {rights_basis}",
        }
    return {
        "rights_basis": "unknown",
        "usable": False,
        "reason": f"invalid or missing rights_basis {rights_basis!r}",
    }
