#!/usr/bin/env python3
"""Parse script.md → shot_list.json with bits of 12-18s per section.

Uses real per-section audio durations to allocate bit timing proportionally
to word count. Outputs shot_list.json with id, section, start/end, bit text,
Klein-style prompt, host_in_frame.
"""

import json
import re
from pathlib import Path

ROOT = Path("/workspaces/OpenMontage")
SCRIPT = ROOT / "docs/openmontage/pilot/script.md"
AUDIO_DIR = ROOT / "tools/kaggle_bridge/jobs/pilot-render/audio"
OUT = ROOT / "tools/kaggle_bridge/jobs/pilot-render/shot_list.json"

# Real per-section audio durations (seconds), measured by ffprobe
SECTION_DURS = {
    1: 83.025, 2: 129.400, 3: 148.600, 4: 135.500, 5: 132.875,
    6: 137.750, 7: 99.875, 8: 101.375, 9: 83.575, 10: 47.800,
}

MIN_BIT, MAX_BIT, TARGET_BIT = 12, 18, 15  # seconds
WPS = 2.7  # words per second (3090 words / 1099.8s ≈ 2.8; use 2.7 conservative)

SENTENCE_RE = re.compile(r"^(S\d{3})\s+\[([^\]]+)\]\s+(.*)$")
SECTION_RE = re.compile(r"^## (\d+)\. (.+)$")
PROMPT_RE = re.compile(r"^\s+PROMPT:\s*(.*)$")


def parse_script(text):
    """Return list of sections: {num, title, sentences:[{id, tag, text, words, prompt}]}"""
    sections = []
    cur = None
    cur_sent = None
    for line in text.splitlines():
        m = SECTION_RE.match(line)
        if m:
            if cur is not None:
                if cur_sent:
                    cur["sentences"].append(cur_sent)
                sections.append(cur)
            cur = {"num": int(m.group(1)), "title": m.group(2).strip(), "sentences": []}
            cur_sent = None
            continue
        if cur is None:
            continue
        sm = SENTENCE_RE.match(line)
        if sm:
            if cur_sent:
                cur["sentences"].append(cur_sent)
            cur_sent = {
                "id": sm.group(1), "tag": sm.group(2), "text": sm.group(3),
                "words": len(sm.group(3).split()), "prompt": "",
            }
            continue
        pm = PROMPT_RE.match(line)
        if pm and cur_sent is not None:
            cur_sent["prompt"] = pm.group(1).strip()
    if cur is not None:
        if cur_sent:
            cur["sentences"].append(cur_sent)
        sections.append(cur)
    return sections


def split_into_bits(section, section_dur):
    """Split section sentences into bits of 12-18s, proportional to word count."""
    sents = section["sentences"]
    if not sents:
        return []
    total_words = sum(s["words"] for s in sents)
    if total_words == 0:
        return []
    # Cumulative word boundaries -> time boundaries
    cum_words = [0]
    for s in sents:
        cum_words.append(cum_words[-1] + s["words"])

    bits = []
    bit_id = 1
    i = 0  # sentence index
    bit_start_t = 0.0
    while i < len(sents):
        # accumulate sentences until we hit TARGET_BIT (within MIN..MAX)
        acc_words = 0
        j = i
        while j < len(sents):
            cand_words = acc_words + sents[j]["words"]
            cand_t = cand_words / total_words * section_dur
            # if adding this sentence exceeds MAX_BIT, stop (unless we have < MIN_BIT)
            if cand_t > MAX_BIT and acc_words > 0:
                break
            acc_words = cand_words
            j += 1
            # stop if we've reached TARGET_BIT and have at least MIN_BIT worth
            if acc_words > 0 and (acc_words / total_words * section_dur) >= TARGET_BIT:
                break
        if j == i:  # single sentence longer than MAX_BIT — force it
            j = i + 1
        bit_sents = sents[i:j]
        bit_words = sum(s["words"] for s in bit_sents)
        bit_dur = bit_words / total_words * section_dur
        # clamp
        bit_dur = max(MIN_BIT, min(MAX_BIT, bit_dur))
        bit_text = " ".join(s["text"] for s in bit_sents)
        bit_ids = [s["id"] for s in bit_sents]
        # prompts: combine, tag with host
        combined_prompt = " | ".join(s["prompt"] for s in bit_sents if s["prompt"])
        bits.append({
            "bit_id": f"B{bit_id:03d}",
            "section": section["num"],
            "sentence_ids": bit_ids,
            "start": round(bit_start_t, 2),
            "end": round(bit_start_t + bit_dur, 2),
            "duration": round(bit_dur, 2),
            "text": bit_text,
            "words": bit_words,
            "prompt": combined_prompt,
            "host_in_frame": False,  # no host in this script; set True manually if needed
        })
        bit_start_t += bit_dur
        bit_id += 1
        i = j
    return bits


def klein_prompt(bit, section_title):
    """Build a Klein 4B prompt from bit text + style technique."""
    tech = (
        "thick crisp black outer contours, controlled interior linework, "
        "large flat matte color fills, clean two-tone cel shading, "
        "restrained palette, no gradients, graphic-novel ink illustration"
    )
    scene_desc = bit["prompt"] or bit["text"][:160]
    return (
        f"{scene_desc}. {tech}. "
        f"Section: {section_title}. 1280x720, flat graphic style."
    )


def main():
    text = SCRIPT.read_text(encoding="utf-8")
    sections = parse_script(text)
    print(f"Parsed {len(sections)} sections, "
          f"{sum(len(s['sentences']) for s in sections)} sentences")

    shot_list = []
    total_frames = 0
    for sec in sections:
        bits = split_into_bits(sec, SECTION_DURS[sec["num"]])
        total_frames += len(bits)
        print(f"  §{sec['num']} {sec['title']}: {SECTION_DURS[sec['num']]:.1f}s -> {len(bits)} bits")
        for b in bits:
            b["prompt_klein"] = klein_prompt(b, sec["title"])
            shot_list.append(b)

    print(f"\nTotal frames: {total_frames}")
    # Time estimate: ~90s per frame (from K1) + ~80s load per kernel
    gen_seconds = total_frames * 90
    print(f"Estimated generation: {gen_seconds}s = {gen_seconds/60:.1f} min "
          f"(~{total_frames*90/3600:.2f} h GPU)")

    data = {
        "generated_utc": "2026-10-28T00:00:00Z",
        "model": "black-forest-labs/FLUX.2-klein-4B",
        "resolution": "1280x720",
        "steps": 4,
        "guidance_scale": 1.0,
        "total_audio_s": round(sum(SECTION_DURS.values()), 3),
        "total_frames": total_frames,
        "est_gen_seconds_per_frame": 90,
        "est_gen_total_s": gen_seconds,
        "est_gen_min": round(gen_seconds / 60, 1),
        "sections": sections,
        "shots": shot_list,
    }
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"\nSaved {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
