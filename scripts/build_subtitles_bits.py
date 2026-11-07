#!/usr/bin/env python3
"""Build per-bit subtitles (SRT) from shot_list.json.

- Split each bit's text into blocks of 2-5s, 1-2 lines, ≤42 chars/line.
- No per-phrase wavs → time allocated proportional to char count within the bit.
- Absolute timing = bit start + relative offset.
- Output: tools/kaggle_bridge/jobs/pilot-render/audio/subtitles_bits.srt
"""

import json
import re
from pathlib import Path

ROOT = Path("/workspaces/OpenMontage")
SL = ROOT / "tools/kaggle_bridge/jobs/pilot-render/shot_list.json"
OUT = ROOT / "tools/kaggle_bridge/jobs/pilot-render/audio/subtitles_bits.srt"

MIN_SUB, MAX_SUB, TARGET_SUB = 2.0, 5.0, 3.5
MAX_CHARS_LINE = 42
MAX_LINES = 2


def srt_time(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int((t - int(t)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def wrap_lines(text, max_chars=MAX_CHARS_LINE, max_lines=MAX_LINES):
    words = text.split()
    if not words:
        return [""]
    lines = []
    cur = ""
    for w in words:
        trial = (cur + " " + w).strip()
        if len(trial) <= max_chars:
            cur = trial
        else:
            lines.append(cur)
            cur = w
        if len(lines) >= max_lines:
            break
    if cur:
        if len(lines) < max_lines:
            lines.append(cur)
        else:
            lines[-1] = (lines[-1] + " " + cur).strip()
    return lines[:max_lines]


def split_bit_into_subs(text, bit_start, bit_dur):
    """Split bit text into subtitle blocks, each 2-5s, absolute timing."""
    text = re.sub(r"\s+", " ", text).strip()
    total_chars = len(text)
    if total_chars == 0 or bit_dur <= 0:
        return []

    # Number of blocks: each within [MIN_SUB, MAX_SUB]
    n = max(1, round(bit_dur / TARGET_SUB))
    while bit_dur / n < MIN_SUB and n > 1:
        n -= 1
    while bit_dur / n > MAX_SUB:
        n += 1
    block_dur = bit_dur / n

    words = text.split()
    total_w = len(words)
    blocks = []
    idx = 0
    for b in range(n):
        if b == n - 1:
            block_words = words[idx:]
        else:
            target_w = max(1, int(round(total_w * (b + 1) / n)) - idx)
            block_words = words[idx:idx + target_w]
        idx += len(block_words)
        blocks.append(" ".join(block_words))

    subs = []
    t = 0.0
    for block in blocks:
        lines = wrap_lines(block)
        subs.append({
            "start": bit_start + t,
            "end": bit_start + t + block_dur,
            "lines": lines,
        })
        t += block_dur
    # ensure last block ends exactly at bit end
    if subs:
        subs[-1]["end"] = bit_start + bit_dur
    return subs


def main():
    data = json.loads(SL.read_text())
    shots = data["shots"]
    sent_text = {}
    for sec in data["sections"]:
        for s in sec["sentences"]:
            sent_text[s["id"]] = s["text"]

    all_subs = []
    index = 1
    for shot in shots:
        bit_text = " ".join(sent_text[sid] for sid in shot["sentence_ids"])
        bit_text = re.sub(r"\s+", " ", bit_text).strip()
        bit_dur = shot["end"] - shot["start"]
        subs = split_bit_into_subs(bit_text, shot["start"], bit_dur)
        for sub in subs:
            if sub["end"] <= sub["start"]:
                continue
            all_subs.append({
                "index": index,
                "start": sub["start"],
                "end": sub["end"],
                "lines": sub["lines"],
            })
            index += 1

    with open(OUT, "w", encoding="utf-8") as f:
        for i, sub in enumerate(all_subs, start=1):
            f.write(f"{i}\n")
            f.write(f"{srt_time(sub['start'])} --> {srt_time(sub['end'])}\n")
            for line in sub["lines"]:
                f.write(f"{line}\n")
            f.write("\n")

    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes), {len(all_subs)} subtitle blocks")
    durs = [sb["end"] - sb["start"] for sb in all_subs]
    print(f"Subtitle duration range: {min(durs):.2f}s - {max(durs):.2f}s")
    bad_chars = [sb for sb in all_subs if any(len(l) > MAX_CHARS_LINE for l in sb["lines"])]
    print(f"Blocks exceeding {MAX_CHARS_LINE} chars/line: {len(bad_chars)}")
    short = [sb for sb in all_subs if sb["end"] - sb["start"] < MIN_SUB]
    print(f"Blocks under {MIN_SUB}s: {len(short)}")


if __name__ == "__main__":
    main()
