"""Azerbaijani-aware text helpers for transcripts and captions.

Python's str.lower()/upper() follow the Unicode default mapping, which is
wrong for Azerbaijani (and Turkish): "I" must lower to dotless "ı" and "i"
must upper to dotted "İ". "İ".lower() even yields two code points
("i" + U+0307), which silently shifts string offsets. These helpers apply the
Azerbaijani casing rules and repair the look-alike characters that ASR output
and copy-pasted scripts commonly carry.
"""

from __future__ import annotations

import re
import unicodedata

AZ_ALPHABET = "AaBbCcÇçDdEeƏəFfGgĞğHhXxIıİiJjKkQqLlMmNnOoÖöPpRrSsŞşTtUuÜüVvYyZz"
AZ_SPECIAL_CHARS = "ƏəĞğıİÖöŞşÇçÜü"

# Look-alikes that render almost identically but break search, spell-check
# and font fallback: Cyrillic schwa (U+04D9/U+04D8) and the Latin
# "turned e" (U+01DD) are often typed or recognised instead of ə/Ə.
_LOOKALIKES = {
    "ә": "ə",  # Cyrillic small schwa
    "Ә": "Ə",  # Cyrillic capital schwa
    "ǝ": "ə",  # Latin small turned e
    "Ǝ": "Ə",  # Latin capital reversed E
}

_PUNCT = ".,!?;:…\"'«»“”()[]—–-"
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([.,!?;:…»”)])")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")


def az_lower(text: str) -> str:
    return text.replace("I", "ı").replace("İ", "i").lower()


def az_upper(text: str) -> str:
    return text.replace("i", "İ").replace("ı", "I").upper()


def az_capitalize(text: str) -> str:
    """Upper-case the first letter only, leaving the rest untouched."""
    for idx, ch in enumerate(text):
        if ch.isalpha():
            return text[:idx] + az_upper(ch) + text[idx + 1:]
    return text


def normalize(text: str) -> str:
    """NFC-compose, replace look-alike glyphs and tidy whitespace/punctuation."""
    text = unicodedata.normalize("NFC", text)
    for bad, good in _LOOKALIKES.items():
        text = text.replace(bad, good)
    text = _SPACE_BEFORE_PUNCT.sub(r"\1", text)
    text = _MULTI_SPACE.sub(" ", text)
    return text.strip()


def strip_punct(token: str) -> tuple[str, str, str]:
    """Split a token into (leading punctuation, core, trailing punctuation)."""
    start = 0
    end = len(token)
    while start < end and token[start] in _PUNCT:
        start += 1
    while end > start and token[end - 1] in _PUNCT:
        end -= 1
    return token[:start], token[start:end], token[end:]


def match_key(token: str) -> str:
    """Case- and punctuation-insensitive lookup key for a single token.

    Dotted and dotless i are folded together: a Latin brand typed in capitals
    ("INSTAQRAM" -> "ınstaqram") must still match the lexicon key
    "instaqram", and ASR confuses ı/i often enough that the distinction would
    only cause missed corrections. The key is for lookup only; text is never
    rewritten with it.
    """
    return az_lower(normalize(strip_punct(token.strip())[1])).replace("ı", "i")


def apply_case_like(source: str, replacement: str, protected: bool = False) -> str:
    """Carry the casing pattern of ``source`` onto ``replacement``.

    ALL-CAPS stays all-caps and a capitalised word stays capitalised; any
    other pattern keeps the replacement exactly as written in the lexicon, so
    proper nouns and acronyms ("SMM", "McDonald's") survive. A ``protected``
    replacement (a brand or name from ``protected_terms``) is returned exactly
    as written: "INSTAQRAM" -> "Instagram", never "İNSTAGRAM".
    """
    if protected:
        return replacement
    letters = [c for c in source if c.isalpha()]
    if len(letters) > 1 and all(c.isupper() for c in letters):
        return az_upper(replacement)
    if letters and letters[0].isupper() and not replacement[:1].isupper():
        return az_capitalize(replacement)
    return replacement


def has_az_special(text: str) -> bool:
    return any(ch in AZ_SPECIAL_CHARS for ch in text)


def upper_token(token: str, protected: set[str] | frozenset[str] = frozenset()) -> str:
    """Upper-case one caption token.

    Protected brand/name spellings use Latin casing ("Instagram" ->
    "INSTAGRAM"); every other word uses Azerbaijani casing ("ilham" -> "İLHAM").
    """
    lead, core, trail = strip_punct(token)
    if core in protected:
        return lead + core.upper() + trail
    return az_upper(token)
