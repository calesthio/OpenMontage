#!/usr/bin/env python3
"""scripts/fw_subtitles.py — word timestamps + sentence cues via faster-whisper.

Why this exists: `scripts/z3_subtitles.py` needs stable-ts, whose torchaudio
dependency does not import on this image (ABI mismatch with torch 2.x). This
helper transcribes the finished narration with CTranslate2 (no torch) and
emits the same two artifacts the pipeline expects:

    python fw_subtitles.py <wav> <words.json> <subtitles.srt> [model]

Cues are built from word timings: max 2 lines, <=42 chars per line, a break
on sentence punctuation or a >=0.6 s pause, and no cue longer than 6 s.
Offline after the first model download (HF cache); no paid routes.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

DEFAULT_MODEL = "base.en"
MAX_LINE_CHARS = 42
MAX_CUE_CHARS = 84
MAX_CUE_S = 6.0
PAUSE_S = 0.6
SENTENCE_END = ".!?…"


def hmsms(seconds: float) -> str:
    ms = max(0, round(float(seconds) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def cues_from_words(words: list[dict]) -> list[tuple[float, float, str]]:
    """Group word timings into subtitle cues (no cue > MAX_CUE_S, <=2 lines)."""
    cues: list[tuple[float, float, str]] = []
    current: list[dict] = []
    text_len = 0

    def flush() -> None:
        nonlocal current, text_len
        if not current:
            return
        text = " ".join(str(w["word"]).strip() for w in current).strip()
        if text:
            cues.append((float(current[0]["start"]), float(current[-1]["end"]), text))
        current = []
        text_len = 0

    for word in words:
        token = str(word.get("word", "")).strip()
        if not token:
            continue
        if current:
            gap = float(word["start"]) - float(current[-1]["end"])
            dur = float(word["end"]) - float(current[0]["start"])
            line_chars = len(token) + 1
            if (gap >= PAUSE_S or dur > MAX_CUE_S
                    or text_len + line_chars > MAX_CUE_CHARS):
                flush()
        current.append(word)
        text_len += len(token) + 1
        if token and token[-1] in SENTENCE_END:
            flush()
    flush()
    return cues


def wrap_two_lines(text: str, max_chars: int = MAX_LINE_CHARS) -> str:
    """Wrap a cue into at most two lines, balanced around the middle."""
    if len(text) <= max_chars:
        return text
    words = text.split()
    best = 1
    for i in range(1, len(words)):
        first = " ".join(words[:i])
        second = " ".join(words[i:])
        if len(first) <= max_chars and len(second) <= max_chars:
            best = i
            if len(first) >= len(second):
                break
    return " ".join(words[:best]) + "\n" + " ".join(words[best:])


def srt_text(cues: list[tuple[float, float, str]]) -> str:
    blocks = []
    for i, (start, end, text) in enumerate(cues, 1):
        blocks.append(f"{i}\n{hmsms(start)} --> {hmsms(end)}\n"
                      f"{wrap_two_lines(text)}\n")
    return "\n".join(blocks)


def decode_16k_mono(wav: str) -> "object":
    """Decode with ffmpeg (PyAV cannot load on this image) into float32 mono.

    faster-whisper accepts a numpy array, which also keeps the model call
    independent of the container/demuxer stack.
    """
    import numpy as np

    res = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(wav), "-f", "s16le",
         "-acodec", "pcm_s16le", "-ac", "1", "-ar", "16000", "pipe:1"],
        capture_output=True, check=True)
    if not res.stdout:
        raise RuntimeError(f"ffmpeg decoded no audio from {wav}")
    return np.frombuffer(res.stdout, dtype=np.int16).astype("float32") / 32768.0


def transcribe(wav: str, model_name: str = DEFAULT_MODEL) -> list[dict]:
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(
        decode_16k_mono(wav), language="en", word_timestamps=True,
        vad_filter=True, beam_size=5, condition_on_previous_text=False)
    words: list[dict] = []
    for seg in segments:
        for w in (seg.words or []):
            token = str(w.word).strip()
            if token:
                words.append({"word": token,
                              "start": round(float(w.start), 3),
                              "end": round(float(w.end), 3)})
    return words


def main() -> int:
    if len(sys.argv) < 4:
        print("usage: fw_subtitles.py <wav> <words.json> <subtitles.srt> [model]")
        return 2
    wav, words_out, srt_out = sys.argv[1:4]
    model_name = sys.argv[4] if len(sys.argv) > 4 else DEFAULT_MODEL
    words = transcribe(wav, model_name)
    if not words:
        print(json.dumps({"error": "no words transcribed"}))
        return 3
    cues = cues_from_words(words)
    Path(words_out).parent.mkdir(parents=True, exist_ok=True)
    Path(words_out).write_text(json.dumps({
        "audio": wav,
        "model": f"faster-whisper {model_name} (ctranslate2 int8)",
        "engine": "faster-whisper 1.2.1",
        "word_count": len(words),
        "words": words,
    }, indent=2), encoding="utf-8")
    Path(srt_out).write_text(srt_text(cues), encoding="utf-8")
    print(json.dumps({"words": len(words), "cues": len(cues),
                      "last_word_s": words[-1]["end"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
