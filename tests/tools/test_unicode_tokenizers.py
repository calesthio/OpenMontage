"""Tokenizers must keep non-ASCII (e.g. Hebrew) words and leave ASCII behaviour unchanged."""

from __future__ import annotations

import random
import re
import string

from lib.scoring import _tokenize_text
from tools.video.video_compose import VideoCompose

_OLD_COMPOSE_RE = re.compile(r"[^A-Za-z0-9\-' ]+")
_OLD_SCORING_RE = re.compile(r"[a-z0-9](?:[a-z0-9+._-]*[a-z0-9])?")


def _old_compose_tokenize(text: str) -> list[str]:
    cleaned = _OLD_COMPOSE_RE.sub(" ", text.lower())
    return [t for t in cleaned.split() if t and t != "-"]


def _random_ascii(rng: random.Random) -> str:
    return "".join(rng.choice(string.printable) for _ in range(rng.randint(0, 60)))


def test_compose_tokenize_keeps_hebrew():
    assert VideoCompose._tokenize("שלום עולם, זה מבחן!") == ["שלום", "עולם", "זה", "מבחן"]


def test_compose_tokenize_pointed_matches_unpointed():
    pointed = "בְּרֵאשִׁית בָּרָא אֱלֹהִים"
    assert VideoCompose._tokenize(pointed) == VideoCompose._tokenize("בראשית ברא אלהים")


def test_compose_tokenize_hebrew_punctuation():
    # Maqaf acts as a hyphen, geresh as an apostrophe, underscore splits.
    assert VideoCompose._tokenize("בית־ספר") == ["בית-ספר"]
    assert VideoCompose._tokenize("ג׳ירפה") == VideoCompose._tokenize("ג'ירפה")
    assert VideoCompose._tokenize("foo_bar") == ["foo", "bar"]


def test_compose_tokenize_ascii_unchanged():
    assert VideoCompose._tokenize("The many-worlds view... isn't - new!") == [
        "the", "many-worlds", "view", "isn't", "new",
    ]
    rng = random.Random(0)
    for _ in range(5000):
        text = _random_ascii(rng)
        assert VideoCompose._tokenize(text) == _old_compose_tokenize(text), text


def test_compose_transcript_check_runs_on_hebrew(tmp_path):
    transcript = tmp_path / "t.json"
    words = ["שלום", "לכולם", "וברוכים", "הבאים"]
    transcript.write_text(
        '{"word_timestamps": [' + ",".join(f'{{"word": "{w}"}}' for w in words) + "]}",
        encoding="utf-8",
    )
    result = VideoCompose._compare_transcript_to_script(
        transcript, "שָׁלוֹם לְכוּלָּם, וּבְרוּכִים הַבָּאִים."
    )
    assert result["issues"] == []
    assert result["word_accuracy"] == 1.0
    assert result["transcript_matches_script"] is True


def test_scoring_tokenize_keeps_hebrew():
    assert _tokenize_text("סרטון קולנועי של נוף") == ["סרטון", "קולנועי", "של", "נוף"]
    assert _tokenize_text("קוֹלְנוֹעִי") == ["קולנועי"]


def test_scoring_tokenize_ascii_unchanged():
    assert _tokenize_text("Cinematic 4K b-roll, v2.1 + Text_To_Video") == [
        "cinematic", "4k", "b-roll", "v2.1", "text_to_video",
    ]
    rng = random.Random(1)
    for _ in range(5000):
        text = _random_ascii(rng)
        assert _tokenize_text(text) == _OLD_SCORING_RE.findall(text.lower()), text
