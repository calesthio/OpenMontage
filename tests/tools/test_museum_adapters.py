#!/usr/bin/env python3
"""Red-then-green tests for tools/museum/ (M4).

Offline: recorded fixtures only, no network, no API keys.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.museum.rights import check_rights  # noqa: E402
from tools.museum.asset_record import make_asset_record  # noqa: E402
from tools.museum.adapters import (  # noqa: E402
    met_object, smithsonian_object, rijksmuseum_object, nga_object, wikimedia_file,
    normalize_candidate,
)

FIX = Path(__file__).parent / "fixtures" / "museum"
FIX.mkdir(parents=True, exist_ok=True)


def _write(name, obj):
    import json
    (FIX / name).write_text(json.dumps(obj))


def test_check_rights_accepts_cc0_and_pd():
    assert check_rights({"license": "CC0", "license_url": "https://creativecommons.org/publicdomain/zero/1.0/"})[0] is True
    assert check_rights({"license": "Public Domain", "license_url": "https://example.org/pd"})[0] is True
    assert check_rights({"license": "CC0", "third_party_credit": True})[0] is False  # third-party credit -> reject
    assert check_rights({"license": "CC-BY-NC"})[0] is False  # NC -> reject
    assert check_rights({"license": "Copyright"})[0] is False


def test_make_asset_record_fields():
    rec = make_asset_record(
        url="https://example.org/obj/123",
        credit="The Metropolitan Museum of Art, CC0",
        sha256="abcd1234",
        width=1000, height=1000,
        license_info={"license": "CC0", "license_url": "https://creativecommons.org/publicdomain/zero/1.0/"},
    )
    assert rec["url"] == "https://example.org/obj/123"
    assert rec["credit"] == "The Metropolitan Museum of Art, CC0"
    assert rec["sha256"] == "abcd1234"
    assert rec["rights_basis"] == "explicit_cc0_public_domain"
    assert rec["usable"] is True


def test_normalize_candidate_keeps_required_fields():
    cand = normalize_candidate(
        source="met", object_id="456", title="A Painting",
        url="https://metmuseum.org/art/collection/search/456",
        license_info={"license": "CC0", "license_url": "https://creativecommons.org/publicdomain/zero/1.0/"},
        credit="Met, CC0", width=800, height=600, thumbnail="https://metmuseum.org/img.jpg",
    )
    assert cand["source"] == "met"
    assert cand["rights_basis"] == "explicit_cc0_public_domain"
    assert cand["usable"] is True


def test_adapters_normalize_recorded_fixtures(monkeypatch):
    import json
    # Recorded fixtures (no network).
    met_search = {"objectIDs": [456]}
    met_obj = {"objectID": 456, "title": "Temple of Dendur",
               "artistDisplayName": "Unknown", "objectDate": "15 B.C.",
               "primaryImage": "https://metmuseum.org/temple.jpg",
               "cc0": True, "creditLine": "The Metropolitan Museum of Art, CC0",
               "objectURL": "https://metmuseum.org/art/collection/search/456",
               "width": 800, "height": 600}
    smithsonian = {"response": {"records": [{"uuid": "s1", "title": "S Object",
                        "url": "https://si.edu/s1", "rights": "CC0",
                        "online_media": {"images": [{"url": "https://si.edu/s1.jpg"}]},
                        "credit": "Smithsonian, CC0"}]}}

    def met_get(url):
        if "/search" in url and "objects/" not in url:
            return met_search
        return met_obj

    def si_get(url):
        return smithsonian

    got = met_object("temple", http_get=met_get)
    assert got is not None
    assert got["source"] == "met"
    assert got["rights_basis"] == "explicit_cc0_public_domain"
    assert got["usable"] is True
    assert got["object_id"] == "456"

    got2 = smithsonian_object("thing", http_get=si_get)
    assert got2 is not None
    assert got2["usable"] is True
    assert got2["source"] == "smithsonian"
