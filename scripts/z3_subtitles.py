#!/usr/bin/env python3
"""scripts/z3_subtitles.py — stable-ts word alignment + sentence subtitles."""
import json
import sys
from pathlib import Path

import stable_whisper


def hmsms(seconds):
    ms = round(seconds * 1000)
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    wav, text, words_out, srt_out = sys.argv[1:5]
    model = stable_whisper.load_model("tiny")
    result = model.align(wav, text, language="en")
    words = [{"word": w.word, "start": round(w.start, 3), "end": round(w.end, 3)}
             for seg in result.segments for w in seg.words]
    Path(words_out).parent.mkdir(parents=True, exist_ok=True)
    Path(words_out).write_text(json.dumps(
        {"audio": wav, "model": "whisper-tiny (stable-ts alignment)",
         "engine": "stable_whisper 2.19.1", "word_count": len(words), "words": words},
        indent=2), encoding="utf-8")
    cues = [(i + 1, round(seg.start, 3), round(seg.end, 3), seg.text.strip())
            for i, seg in enumerate(result.segments) if seg.text.strip()]
    lines = []
    for n, st, en, txt in cues:
        lines.append(f"{n}\n{hmsms(st)} --> {hmsms(en)}\n{txt}\n")
    Path(srt_out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"words": len(words), "cues": len(cues), "words_out": words_out, "srt_out": srt_out}))


if __name__ == "__main__":
    main()
