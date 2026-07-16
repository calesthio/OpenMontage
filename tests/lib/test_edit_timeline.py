"""lib/edit_timeline.validate_edit_timeline (audit 2026-07-16, Wave 2 item 13).

Manifests promised "no timeline gaps or overlaps" and playbooks declared
pacing_rules with zero enforcement — this is the enforcement point's spec.
"""

from lib.edit_timeline import validate_edit_timeline


def _cut(cid, start, end, layer=None):
    c = {"id": cid, "source": "x.mp4", "in_seconds": start, "out_seconds": end}
    if layer is not None:
        c["layer"] = layer
    return c


def test_clean_timeline_is_valid():
    result = validate_edit_timeline({"cuts": [_cut("a", 0, 4), _cut("b", 4, 8)]})
    assert result["valid"] is True
    assert result["issues"] == []
    assert result["warnings"] == []
    assert result["stats"]["timeline_end_seconds"] == 8


def test_gap_warns_but_does_not_invalidate():
    result = validate_edit_timeline({"cuts": [_cut("a", 0, 4), _cut("b", 5.0, 8)]})
    assert result["valid"] is True
    assert any("gap" in w for w in result["warnings"])


def test_same_layer_overlap_is_an_issue():
    result = validate_edit_timeline({"cuts": [_cut("a", 0, 5), _cut("b", 4.0, 8)]})
    assert result["valid"] is False
    assert any("overlap" in i for i in result["issues"])


def test_overlay_layer_may_overlap_base():
    result = validate_edit_timeline(
        {"cuts": [_cut("a", 0, 8), _cut("logo", 2, 6, layer=1)]}
    )
    assert result["valid"] is True


def test_inverted_cut_is_an_issue():
    result = validate_edit_timeline({"cuts": [_cut("a", 5, 5)]})
    assert result["valid"] is False


def test_playbook_pacing_rules_enforced():
    playbook = {"motion": {"pacing_rules": {
        "min_scene_hold_seconds": 3, "max_scene_hold_seconds": 7,
    }}}
    result = validate_edit_timeline(
        {"cuts": [_cut("fast", 0, 1.5), _cut("slow", 1.5, 12)]}, playbook
    )
    assert result["valid"] is True  # pacing is advisory
    assert any("under the playbook minimum" in w for w in result["warnings"])
    assert any("exceeds the playbook maximum" in w for w in result["warnings"])


def test_sub_frame_jitter_tolerated():
    result = validate_edit_timeline(
        {"cuts": [_cut("a", 0, 4.0), _cut("b", 4.03, 8)]}
    )
    assert result["valid"] is True
    assert result["warnings"] == []
