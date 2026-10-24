import shutil
from pathlib import Path

import pytest
import yaml

from lib import reels_profiles as rp

EXPECTED_PROFILES = {
    "expert_editorial",
    "dynamic_business",
    "premium_academy",
    "luxury_editorial",
    "warm_educational",
    "hospitality_coffee",
}


def test_six_editing_profiles_ship_and_load() -> None:
    assert set(rp.list_editing_profiles()) == EXPECTED_PROFILES
    numbers = sorted(rp.load_editing_profile(p)["number"] for p in EXPECTED_PROFILES)
    assert numbers == [1, 2, 3, 4, 5, 6]


@pytest.mark.parametrize("profile_id", sorted(EXPECTED_PROFILES))
def test_profiles_target_reels_and_carry_no_brand_colours(profile_id: str) -> None:
    profile = rp.load_editing_profile(profile_id)
    assert profile["export"] == {"width": 1080, "height": 1920, "fps": 30}
    assert not rp._BRAND_ONLY_KEYS & set(profile)
    assert "color" not in profile["captions"]


def test_profile_with_brand_keys_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "bad.yaml").write_text(
        yaml.safe_dump({"profile_id": "bad", "primary_colors": ["#FF0000"]})
    )
    with pytest.raises(rp.ProfileError, match="brand-only"):
        rp.load_editing_profile("bad", root=tmp_path)


def test_neutral_profile_is_valid_and_template_has_every_field() -> None:
    assert rp.load_brand_profile(rp.NEUTRAL_CLIENT_ID)["approved"] is True
    template = yaml.safe_load((rp.BRAND_PROFILES_DIR / "_template" / "brand.yaml").read_text())
    assert rp.validate_brand_profile(template) == []


@pytest.mark.parametrize("bad_id", ["../etc", "a", "UPPER", "x/y", ""])
def test_client_id_rejects_path_traversal(bad_id: str) -> None:
    with pytest.raises(rp.ProfileError):
        rp.validate_client_id(bad_id)


def _client(root: Path, client_id: str, **overrides) -> None:
    shutil.copytree(rp.BRAND_PROFILES_DIR / rp.NEUTRAL_CLIENT_ID, root / rp.NEUTRAL_CLIENT_ID)
    brand = yaml.safe_load((rp.BRAND_PROFILES_DIR / "_template" / "brand.yaml").read_text())
    brand.update(client_id=client_id, brand_name="Client", **overrides)
    (root / client_id).mkdir()
    (root / client_id / "brand.yaml").write_text(yaml.safe_dump(brand, allow_unicode=True))


def test_unapproved_brand_renders_neutral(tmp_path: Path) -> None:
    _client(
        tmp_path, "acme", approved=False,
        primary_colors=["#123456"], subtitle_style={"text_color": "#123456"},
        logo_asset="assets/logo.png",
    )
    style = rp.resolve_style("acme", brand_root=tmp_path)
    assert style["brand_approved"] is False
    assert style["colors"]["primary"] == ["#FFFFFF"]
    assert style["captions"]["text_color"] == "#FFFFFF"
    assert style["logo_asset"] is None
    assert style["warnings"]


def test_approved_brand_colours_override_profile(tmp_path: Path) -> None:
    _client(
        tmp_path, "acme", approved=True, preferred_editing_profile="dynamic_business",
        primary_colors=["#123456"], subtitle_style={"text_color": "#ABCDEF"},
    )
    style = rp.resolve_style("acme", brand_root=tmp_path)
    assert style["profile_id"] == "dynamic_business"
    assert style["captions"]["text_color"] == "#ABCDEF"
    assert style["captions"]["mode"] == "word_highlight"  # from the profile
    assert style["warnings"] == []


def test_invalid_hex_colour_is_reported() -> None:
    problems = rp.validate_brand_profile({"primary_colors": ["red"]})
    assert any("not a #RRGGBB" in p for p in problems)


def test_lexicon_merges_shared_and_client_entries(tmp_path: Path) -> None:
    (tmp_path / "acme").mkdir()
    (tmp_path / "acme" / "corrections.yaml").write_text(
        "protected_terms: [Acme]\nreplacements: {akme: Acme, rils: Reels Pro}\n"
    )
    lex = rp.load_lexicon("acme", brand_root=tmp_path)
    assert lex["replacements"]["instaqram"] == "Instagram"  # shared
    assert lex["replacements"]["akme"] == "Acme"
    assert lex["replacements"]["rils"] == "Reels Pro"  # client wins
    assert lex["initial_prompt"]
