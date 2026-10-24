"""Repeat-Reveal ad for the AOP Christmas sweater (2 SKUs) — 4 clips, trimmed to 9.5s.

    python scripts/_gen_podsweater_ad.py check     # the skill's checklist, spends nothing
    python scripts/_gen_podsweater_ad.py sample    # shot 1 only — approve before the rest
    python scripts/_gen_podsweater_ad.py videos    # resumes: only missing clips are made
    python scripts/_gen_podsweater_ad.py cut       # trim to the beat sheet + stitch

Built from `skills/creative/shopee-product-ad.md` (Repeat-Reveal), against the
measured DNA in `projects/_analysis/fb_dropship_ref/`: one reveal repeated in
several settings, accelerating cuts, every shot ending on a bystander reaction,
no narration, no on-screen text.

**The repeated element is the ACTION, not the SKU.** The skill forbids "four
shots, four different things" — that is a spec sheet. But this product line has
two SKUs that both need screen time. The compromise, stated openly rather than
smuggled in: the *gag mechanic* is identical in all four shots — coat comes off,
printed body is revealed, someone reacts — and only the setting and the SKU
change. The repetition the format needs lives in the action.

**The known weak point.** Holding one specific garment print identical across
four independently generated clips is the hardest thing being asked here.
`SKU_ELF` and `SKU_SANTA` are written as exhaustively as the series' character
blocks and pasted verbatim; print drift is still the first thing to check on
review, before anything else.

Flow's floor is 4s, so every clip is generated at 4s and `cut` trims to the beat.
Flow's VN watermark was accepted by the user; no text is burned in by us.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path("projects/podsweater-ad")
VIDEO = PROJECT / "assets" / "video"
CUT = PROJECT / "renders"

PROJECT_URL = "https://flow.google.com/project/0ebed0ec-2661-4413-851f-9fa34078c90f?hl=vi"
LOCK = Path.home() / ".openmontage" / "flow_video.lock"

GEN_SECONDS = "4"

# ---------------------------------------------------------------- locked blocks

SKU_ELF = ("The sweatshirt is a dark forest-green crewneck with black ribbed "
           "collar, cuffs and hem. Printed flat onto the front — it is a printed "
           "picture on fabric, not real clothing and not real skin — is a "
           "trompe-l'oeil elf costume: an open red jacket edge with white fur "
           "trim, a red-and-white candy-striped border running down both sides of "
           "the opening, three round gold buttons down the centre, and a red "
           "fur-trimmed costume bodice printed between the edges. The whole "
           "garment stays one continuous piece of fabric with no real opening "
           "anywhere. ")

SKU_SANTA = ("The sweater is a bright red crewneck with black ribbed collar, "
             "cuffs and hem. Printed flat onto the front — it is a printed "
             "picture on fabric, not real clothing and not real skin — is a "
             "trompe-l'oeil Santa costume: an open red coat edge with thick white "
             "fur trim, a printed muscular bare male chest and six-pack stomach "
             "between the edges, a string of small round multicoloured Christmas "
             "lights draped across the chest, and a wide black belt with a square "
             "gold buckle printed across the waist. The whole garment stays one "
             "continuous piece of fabric with no real opening anywhere. ")

WEARER_F = ("THE WEARER is a young woman in her twenties with shoulder-length "
            "dark hair worn loose and small silver earrings, in dark jeans. ")

WEARER_M = ("THE WEARER is a man in his thirties with short dark hair and a "
            "trimmed beard, in dark jeans. ")

REVEAL = ("At the start he or she is wearing a plain dark winter coat, fully "
          "closed, with the sweater completely hidden underneath. The coat is "
          "pulled open and off the shoulders, revealing the printed sweater "
          "underneath. ")

# The fix the pig-mask sample forced: the product must stay visible *during* the
# reaction, not only before it. Without this the reacting person gets the camera
# and the garment ends up behind someone's back.
FRAMING = ("The camera films from the side or front of the group, at an angle "
           "where BOTH the printed front of the sweater AND the reacting "
           "person's face are visible in the frame at the same time for the whole "
           "clip. The printed front of the garment faces the camera and is never "
           "turned away, never covered by an arm, and never leaves the frame. ")

MOTION = ("Handheld phone footage, filmed by a friend standing a few steps away. "
          "The camera moves slightly and continuously the way a hand-held phone "
          "does, with no stop and no cut anywhere in the clip. ")

SPEED = ("Everything runs at normal real-time speed, 1x, not slow motion. ")

CLEAN = ("There is no text anywhere in the frame: no caption, no subtitle, no "
         "title card, no sticker, no logo, no watermark and no graphic overlay of "
         "any kind. No writing appears on any wall, screen or surface in shot. ")

MEDIUM_TAIL = ("Realistic candid smartphone video, natural indoor party light, "
               "slightly imperfect framing, not a studio advert and not an "
               "illustration. Vertical 9:16. ")

AUDIO_TAIL = ("ambient: party room noise and a short burst of genuine laughter "
              "from the other people. no dialogue, no music, no voice-over.")

# (name, trim_seconds, sku, wearer, setting, beat)
SHOTS = [
    ("01_office", 4.0, SKU_ELF, WEARER_F,
     "An office Christmas party: a meeting room with a small decorated tree, "
     "paper cups on the table and two colleagues sitting at the table. ",
     "She shrugs the coat off her shoulders. The two colleagues look up, see the "
     "printed elf-bikini front, and both burst out laughing, one clapping a hand "
     "over their mouth. That is the only action — she does not speak and does not "
     "put the coat back on. "),

    ("02_livingroom", 2.0, SKU_SANTA, WEARER_M,
     "A family living room at Christmas: a lit tree, a sofa, an older woman "
     "sitting with a mug. ",
     "He pulls the coat open and off. The older woman looks up, sees the printed "
     "muscular Santa chest, and throws her head back laughing. That is the only "
     "action — nobody speaks and the coat stays off. "),

    ("03_kitchen", 2.0, SKU_ELF, WEARER_F,
     "A kitchen at a house party: a counter with snacks and drinks, two friends "
     "leaning against it. ",
     "She drops the coat off her shoulders. Both friends turn, see the printed "
     "elf-bikini front, and double over laughing, one pointing. That is the only "
     "action — she does not walk out of frame. "),

    ("04_doorway", 1.5, SKU_SANTA, WEARER_M,
     "The front doorway of a house, guests arriving, coats and a wreath visible. ",
     "He swings the coat open in the doorway. Three people in the hallway see the "
     "printed Santa chest at once and all burst out laughing together. That is "
     "the only action — the moment ends on their laugh. "),
]

TARGET_TOTAL = 9.5


def prompt_for(shot) -> str:
    _, _, sku, wearer, setting, beat = shot
    return (MEDIUM_TAIL + setting + wearer + sku + REVEAL + beat + FRAMING
            + MOTION + SPEED + CLEAN + AUDIO_TAIL)


def check() -> None:
    assert len(SHOTS) == 4, "Repeat-Reveal wants 3-4 settings; this is built for 4"

    trims = [t for _, t, _, _, _, _ in SHOTS]
    for earlier, later in zip(trims, trims[1:]):
        assert later <= earlier, f"shot lengths must never grow: {trims}"
    assert trims[0] >= 2 * trims[-1], f"shot 1 should be ~2x the last: {trims}"
    total = sum(trims)
    assert total == TARGET_TOTAL, f"beats total {total}s, expected {TARGET_TOTAL}s"
    assert 9.0 <= total <= 12.0, f"format lives at 10-12s, got {total}s"
    for name, trim, *_ in SHOTS:
        assert trim <= float(GEN_SECONDS), f"{name}: cannot trim {trim}s from {GEN_SECONDS}s"

    settings = [s for _, _, _, _, s, _ in SHOTS]
    assert len(set(settings)) == len(settings), "every shot needs its own setting"

    # Both SKUs get screen time, and each shot commits to exactly one of them —
    # a frame showing both prints at once would read as a costume, not a product.
    skus = [sku for _, _, sku, _, _, _ in SHOTS]
    assert set(skus) == {SKU_ELF, SKU_SANTA}, "both SKUs must appear"
    for shot in SHOTS:
        name = shot[0]
        text = prompt_for(shot)
        assert (SKU_ELF in text) != (SKU_SANTA in text), f"{name}: exactly one SKU per shot"
        assert (WEARER_F in text) != (WEARER_M in text), f"{name}: exactly one wearer per shot"
        # The illusion only works if the model knows it is a print, not a body.
        assert "printed picture on fabric, not real clothing and not real skin" in text, \
            f"{name}: the print must be pinned as a print or it renders as a bare torso"
        assert REVEAL in text, f"{name}: missing the coat-off reveal — that is the repeated action"
        assert FRAMING in text, f"{name}: missing FRAMING — the print will vanish during the payoff"
        assert MOTION in text and SPEED in text, f"{name}: missing MOTION/SPEED"
        assert CLEAN in text, f"{name}: missing the no-on-screen-text clause"
        assert any(w in text for w in ("laugh", "laughing")), \
            f"{name}: no bystander reaction — the reaction IS the proof"
        assert "only action" in text, f"{name}: doesn't pin a single beat"
        assert "no dialogue" in text and "ambient:" in text, f"{name}: missing audio tail"

    print(f"check ok — {len(SHOTS)} shots, 2 SKUs, generate {GEN_SECONDS}s each, "
          f"trim to {trims} = {total}s, no on-screen text")


def _wanted(names: list[str]) -> list[tuple]:
    if not names:
        return SHOTS
    picked = [s for s in SHOTS if s[0].split("_")[0] in names]
    if not picked:
        raise SystemExit(f"no shot matches {names} — ids are "
                         + ", ".join(s[0].split("_")[0] for s in SHOTS))
    return picked


def run_videos(names: list[str] | None = None) -> int:
    from tools.video.flow_video import FlowVideo

    os.environ.setdefault("FLOW_PROJECT_URL", PROJECT_URL)
    LOCK.unlink(missing_ok=True)
    VIDEO.mkdir(parents=True, exist_ok=True)
    tool, results = FlowVideo(), []

    for shot in _wanted(names or []):
        name = shot[0]
        out = VIDEO / f"{name}.mp4"
        if out.is_file() and out.stat().st_size > 200_000:
            print(f"skip {name}", flush=True)
            continue

        began = time.time()
        result = tool.execute({
            "prompt": prompt_for(shot),
            "operation": "text_to_video",
            "model_variant": "Omni",
            "duration": GEN_SECONDS,
            "aspect_ratio": "9:16",
            "resolution": "720p",
            "output_path": str(out),
            "timeout_seconds": 900,
        })
        took = round(time.time() - began, 1)
        row = {"name": name, "ok": result.success, "seconds": took}
        if result.success:
            row["credits"] = result.data.get("flow_credits")
        else:
            row["error"] = result.error
            out.unlink(missing_ok=True)
        results.append(row)
        print(f"{name}: {'ok' if result.success else 'FAILED'} ({took}s)", flush=True)
        if not result.success:
            print(f"   {result.error}", flush=True)

    ledger = PROJECT / "podsweater_videos_result.json"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    previous = json.loads(ledger.read_text(encoding="utf-8")) if ledger.is_file() else []
    merged = {r["name"]: r for r in previous}
    merged.update({r["name"]: r for r in results})
    ledger.write_text(json.dumps([merged[k] for k in sorted(merged)], indent=1,
                                 ensure_ascii=False), encoding="utf-8")

    failed = [r["name"] for r in results if not r["ok"]]
    print(f"\ndone: {len(results) - len(failed)}/{len(results)} clips this run")
    if failed:
        print("failed:", ", ".join(failed))
    return 1 if failed else 0


def run_cut() -> int:
    CUT.mkdir(parents=True, exist_ok=True)
    parts = []
    for name, trim, *_ in SHOTS:
        src = VIDEO / f"{name}.mp4"
        if not src.is_file():
            print(f"missing {src} — run `videos` first")
            return 1
        dst = CUT / f"_trim_{name}.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src),
                        "-t", str(trim), "-c:v", "libx264", "-preset", "slow",
                        "-crf", "18", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "160k", str(dst)], check=True)
        parts.append(dst)

    listing = CUT / "_concat.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    out = CUT / "podsweater_ad_9x16.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", str(listing), "-c:v", "libx264", "-preset", "slow",
                    "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac",
                    "-b:a", "160k", "-movflags", "+faststart", str(out)], check=True)
    listing.unlink()
    for p in parts:
        p.unlink()

    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "format=duration", "-of", "csv=p=0", str(out)],
                         capture_output=True, text=True, check=True).stdout.strip()
    print(f"{out}  {float(dur):.2f}s")
    return 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    check()
    if mode == "check":
        raise SystemExit(0)
    if mode == "sample":
        raise SystemExit(run_videos(["01"]))
    if mode == "videos":
        raise SystemExit(run_videos(sys.argv[2:]))
    if mode == "cut":
        raise SystemExit(run_cut())
    raise SystemExit(f"usage: {sys.argv[0]} [check | sample | videos | cut] [shot-id ...]")
