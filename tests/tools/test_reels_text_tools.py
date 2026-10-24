"""transcript_corrector, speech_cutter planning and reels_captions (no media needed)."""

from pathlib import Path

from tools.subtitle.reels_captions import ReelsCaptions, build_cues, hex_to_ass, split_lines
from tools.subtitle.transcript_corrector import TranscriptCorrector
from tools.video.speech_cutter import SpeechCutter


def _words(text: str, start: float = 0.0, step: float = 0.4, prob: float = 0.95) -> list[dict]:
    out = []
    for i, w in enumerate(text.split()):
        s = start + i * step
        out.append({"word": " " + w, "start": round(s, 3), "end": round(s + 0.3, 3), "probability": prob})
    return out


# --- transcript_corrector -------------------------------------------------

def test_corrector_applies_lexicon_and_keeps_timings() -> None:
    words = _words("bu gün instaqram rils və smm haqqında")
    result = TranscriptCorrector().execute({
        "segments": [{"id": 0, "words": words}],
        "client_id": "neutral_test",
    })
    assert result.success, result.error
    seg = result.data["segments"][0]
    assert seg["text"] == "bu gün Instagram Reels və SMM haqqında"
    assert [w["start"] for w in seg["words"]] == [w["start"] for w in words]
    assert {c["to"] for c in result.data["changes"]} == {"Instagram", "Reels", "SMM"}
    assert result.data["verified"] is False


def test_corrector_merges_multiword_phrase_and_keeps_punctuation() -> None:
    words = _words("insta qram, tik tok!")
    result = TranscriptCorrector().execute({"segments": [{"id": 0, "words": words}]})
    seg = result.data["segments"][0]
    assert seg["text"] == "Instagram, TikTok!"
    assert seg["words"][0]["start"] == words[0]["start"]
    assert seg["words"][0]["end"] == words[1]["end"]


def test_corrector_keeps_brand_spelling_from_all_caps_source() -> None:
    words = _words("INSTAQRAM və WHATSAPP")
    result = TranscriptCorrector().execute({"segments": [{"id": 0, "words": words}]})
    assert result.data["segments"][0]["text"] == "Instagram və WhatsApp"


def test_corrector_flags_low_confidence_words_for_review() -> None:
    words = _words("salam əziz dostlar")
    words[1]["probability"] = 0.3
    result = TranscriptCorrector().execute({"segments": [{"id": 0, "words": words}]})
    review = result.data["review_items"]
    assert [r["word"] for r in review if r["reason"] == "low_confidence"] == ["əziz"]


def test_corrector_repairs_cyrillic_schwa() -> None:
    words = _words("әziz dostlar")
    result = TranscriptCorrector().execute({"segments": [{"id": 0, "words": words}]})
    assert result.data["segments"][0]["text"] == "əziz dostlar"


def test_corrector_rejects_unsafe_client_id() -> None:
    result = TranscriptCorrector().execute({"segments": [], "client_id": "../x"})
    assert not result.success


# --- speech_cutter planning -----------------------------------------------

def test_plan_removes_pauses_and_fillers_and_remaps_words() -> None:
    words = _words("salam dostlar", start=1.0) + _words("əəə", start=2.0) + _words("bu gün", start=5.0)
    plan = SpeechCutter.plan_cuts(words, 7.0, min_silence_s=0.5, keep_pause_s=0.2)
    assert [r["reason"] for r in plan["removed"] if r["reason"] == "filler"] == ["filler"]
    assert [w["word"].strip() for w in plan["words"]] == ["salam", "dostlar", "bu", "gün"]
    assert len(plan["keep_segments"]) == 2
    # The first kept word starts after the 0.1 s lead-in; remapped words are monotonic.
    assert plan["words"][0]["start"] == 0.1
    starts = [w["start"] for w in plan["words"]]
    assert starts == sorted(starts)
    assert plan["output_duration"] < 7.0
    # Every remapped word lies inside the new timeline.
    assert plan["words"][-1]["end"] <= plan["output_duration"] + 1e-6


def test_plan_keeps_discourse_words() -> None:
    words = _words("yəni bax necə")
    plan = SpeechCutter.plan_cuts(words, 2.0)
    assert len(plan["words"]) == 3


def test_plan_extra_fillers_are_case_insensitive() -> None:
    words = _words("Yəni salam")
    plan = SpeechCutter.plan_cuts(words, 2.0, extra_fillers=["yəni"])
    assert [w["word"].strip() for w in plan["words"]] == ["salam"]


# --- reels_captions --------------------------------------------------------

def test_hex_to_ass_is_bgr_with_alpha() -> None:
    assert hex_to_ass("#112233") == "&H00332211"
    assert hex_to_ass("#112233", alpha=1.0) == "&HFF332211"


def test_cues_respect_line_budget_and_sentence_end() -> None:
    words = _words("bir iki üç. dörd beş altı yeddi səkkiz doqquz on on bir")
    cues = build_cues(words, max_chars_per_line=10, max_lines=2)
    assert cues[0][-1]["word"] == "üç."
    assert all(len(" ".join(w["word"] for w in c)) <= 20 for c in cues)


def test_split_lines_balances_two_lines() -> None:
    lines = split_lines(["salam", "əziz", "dostlar", "bu", "gün"], 16, 2)
    assert len(lines) == 2


def test_ass_is_pixel_exact_in_safe_zone_with_az_uppercase(tmp_path: Path) -> None:
    out = tmp_path / "c.ass"
    result = ReelsCaptions().execute({
        "words": _words("ığdır şəhərindən salam"),
        "output_path": str(out),
        "client_id": "neutral_test",
        "style": {"uppercase": True, "mode": "phrase"},
    })
    assert result.success, result.error
    text = out.read_text(encoding="utf-8")
    assert "PlayResX: 1080" in text and "PlayResY: 1920" in text
    assert "IĞDIR ŞƏHƏRİNDƏN" in text
    style_line = next(ln for ln in text.splitlines() if ln.startswith("Style: Reels"))
    fields = style_line.split(",")
    assert fields[-4:-1] == ["90", "160", "480"]  # MarginL, MarginR, MarginV (organic zone)


def test_word_highlight_emits_one_event_per_word(tmp_path: Path) -> None:
    out = tmp_path / "c.ass"
    result = ReelsCaptions().execute({
        "words": _words("salam əziz dostlar"),
        "output_path": str(out),
        "style": {"mode": "word_highlight"},
    })
    assert result.data["event_count"] == 3
    assert out.read_text(encoding="utf-8").count("\\c&H00D4FF&") == 3


def test_short_gaps_are_bridged_without_overlap(tmp_path: Path) -> None:
    out = tmp_path / "c.ass"
    words = _words("bir.", start=0.0) + _words("iki.", start=0.6) + _words("üç.", start=3.0)
    ReelsCaptions().execute({"words": words, "output_path": str(out), "style": {"mode": "phrase"}})
    events = [ln.split(",")[1:3] for ln in out.read_text().splitlines() if ln.startswith("Dialogue")]
    assert events[0][1] == events[1][0]  # 0.3 s gap bridged
    assert events[1][1] == "0:00:01.10"  # long gap: held 0.2 s only


def test_uppercase_captions_keep_brands_latin_and_words_azerbaijani(tmp_path: Path) -> None:
    out = tmp_path / "c.ass"
    result = ReelsCaptions().execute({
        "words": _words("instagram üçün istifadə qaydaları"),
        "output_path": str(out),
        "client_id": "neutral_test",
        "style": {"uppercase": True, "mode": "phrase", "max_chars_per_line": 40},
    })
    assert result.success, result.error
    text = out.read_text(encoding="utf-8")
    # "instagram" is lower-case in the transcript, so it is not a protected
    # spelling yet and follows Azerbaijani rules; the corrector fixes it first.
    assert "İNSTAGRAM" in text
    corrected = TranscriptCorrector().execute({
        "segments": [{"id": 0, "words": _words("instagram üçün istifadə qaydaları")}],
    }).data["segments"][0]["words"]
    ReelsCaptions().execute({
        "words": corrected,
        "output_path": str(out),
        "client_id": "neutral_test",
        "style": {"uppercase": True, "mode": "phrase", "max_chars_per_line": 40},
    })
    text = out.read_text(encoding="utf-8")
    assert "INSTAGRAM ÜÇÜN İSTİFADƏ QAYDALARI" in text
    assert "İNSTAGRAM" not in text
