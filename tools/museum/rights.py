#!/usr/bin/env python3
"""tools/museum/rights.py — rights gating for museum adapters (M4).

Accepts ONLY explicit CC0 / public-domain. Rejects third-party credit and any
non-CC0/non-PD license. Fail-closed: unknown/missing license => not usable.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

CC0_TERMS = {"cc0", "cc0 1.0", "cc0-1.0", "creative commons zero", "creativecommons.org/publicdomain/zero/1.0"}
PD_TERMS = {"public domain", "pd", "pdm", "public-domain", "pdm 1.0"}


def _norm(s: str) -> str:
    return " ".join(str(s or "").lower().split())


def check_rights(license_info: Any) -> Tuple[bool, str]:
    """Return (usable, reason).

    usable=True only when license is explicit CC0 or public domain AND there is
    no third-party credit requirement. Everything else is rejected.
    """
    if license_info is None:
        return False, "no license info"
    if isinstance(license_info, dict):
        license_str = license_info.get("license") or license_info.get("rights") or ""
        license_url = license_info.get("license_url") or license_info.get("url") or ""
        third_party = bool(license_info.get("third_party_credit"))
        credit_required = bool(license_info.get("credit_required"))
    elif isinstance(license_info, str):
        license_str = license_info
        license_url = ""
        third_party = False
        credit_required = False
    else:
        return False, "unrecognized license info"

    l = _norm(license_str)
    lu = _norm(license_url)

    if third_party or credit_required:
        return False, "third-party credit required"
    if l in CC0_TERMS or "creativecommons.org/publicdomain/zero/1.0" in lu:
        return True, "cc0"
    if l in PD_TERMS or "public domain" in l or "publicdomain" in lu:
        return True, "public_domain"
    return False, f"license not CC0/PD: {license_str!r}"


def rights_basis(usable: bool, reason: str) -> str:
    if not usable:
        return "rejected_license"
    if reason == "cc0":
        return "explicit_cc0_public_domain"
    if reason == "public_domain":
        return "explicit_public_domain"
    return "rejected_license"
