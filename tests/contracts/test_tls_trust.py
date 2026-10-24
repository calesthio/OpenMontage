"""The installed application CA bundle must exclude the eMudhra incident roots."""

import hashlib
import ssl

import certifi


def test_certifi_excludes_emudhra_incident_roots():
    # Published certificate SHA-256 fingerprints (not subject-name matching):
    # https://emudhra.we-have-a-problem.com/roots.json
    incident_roots = {
        "7DD78D5F4F13459A83DFF9ABBBA62EDBAF6F2D102BF257FD712F4D9F2746ED8D",
        "F2EDAAFF3D9B701FB4D14C9F285F8C0BAD90FC3BCC1FA07D47F4718EDABA34A5",
        "D7A7A0FB5D7E2731D771E9484EBCDEF71D5F0C3E0A2948782BC83EE0EA699EF4",
        "86A1ECBA089C4A8D3BBE2734C612BA341D813E043CF9E8A862CD5C57A36BBE6B",
    }
    # Explicit cafile avoids silently falling back to the host's trust store.
    context = ssl.create_default_context(cafile=certifi.where())
    trusted_roots = {
        hashlib.sha256(der).hexdigest().upper()
        for der in context.get_ca_certs(binary_form=True)
    }
    assert trusted_roots, "The application must retain a usable CA bundle"
    assert not incident_roots & trusted_roots, (
        "Upgrade certifi to >=2026.10.19: the bundle still trusts an eMudhra incident root"
    )
