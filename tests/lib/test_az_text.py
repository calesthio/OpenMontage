from lib import az_text


def test_dotted_and_dotless_i_follow_azerbaijani_rules() -> None:
    assert az_text.az_lower("IĞDIR İLHAM") == "ığdır ilham"
    assert az_text.az_upper("ığdır ilham") == "IĞDIR İLHAM"


def test_az_lower_keeps_length_unlike_str_lower() -> None:
    # "İ".lower() is two code points ("i" + U+0307) and shifts offsets.
    assert len("İ".lower()) == 2
    assert az_text.az_lower("İtalyan") == "italyan"


def test_all_special_letters_round_trip() -> None:
    lower = "əğıöüşç"
    assert az_text.az_lower(az_text.az_upper(lower)) == lower
    assert az_text.az_upper(lower) == "ƏĞIÖÜŞÇ"


def test_normalize_repairs_schwa_lookalikes_and_spacing() -> None:
    cyrillic = "әziz  dostlar ,salam !"
    assert az_text.normalize(cyrillic) == "əziz dostlar,salam!"


def test_normalize_composes_decomposed_letters() -> None:
    decomposed = "ş"  # s + combining cedilla
    assert az_text.normalize(decomposed) == "ş"


def test_match_key_ignores_case_and_punctuation() -> None:
    assert az_text.match_key("«İnstaqram»,") == az_text.match_key("instaqram")


def test_match_key_folds_dotted_and_dotless_i() -> None:
    assert az_text.match_key("INSTAQRAM") == az_text.match_key("instaqram")
    assert az_text.match_key("Instagram") == az_text.match_key("instagram")
    assert az_text.match_key("IĞDIR") == az_text.match_key("ığdır")


def test_apply_case_like_uses_azerbaijani_rules_for_ordinary_words() -> None:
    assert az_text.apply_case_like("SMM", "smm") == "SMM"
    assert az_text.apply_case_like("smm", "SMM") == "SMM"
    assert az_text.apply_case_like("İLHAM", "ilham") == "İLHAM"
    assert az_text.apply_case_like("İnsan", "insan") == "İnsan"


def test_protected_terms_keep_their_exact_spelling() -> None:
    for source in ("instaqram", "Instaqram", "INSTAQRAM", "İnstaqram"):
        assert az_text.apply_case_like(source, "Instagram", protected=True) == "Instagram"


def test_upper_token_uses_latin_casing_for_protected_brands() -> None:
    protected = {"Instagram", "TikTok", "WhatsApp"}
    assert az_text.upper_token("Instagram,", protected) == "INSTAGRAM,"
    assert az_text.upper_token("WhatsApp", protected) == "WHATSAPP"
    # Ordinary Azerbaijani words keep the dotted capital İ.
    assert az_text.upper_token("istifadə", protected) == "İSTİFADƏ"
    assert az_text.upper_token("ığdır", protected) == "IĞDIR"
