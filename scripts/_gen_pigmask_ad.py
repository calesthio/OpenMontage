"""Repeat-Reveal ad for the pig-nose face mask — 4 clips, trimmed to 9.5s.

    python scripts/_gen_pigmask_ad.py check     # the skill's checklist, spends nothing
    python scripts/_gen_pigmask_ad.py sample    # shot 1 only — approve before the rest
    python scripts/_gen_pigmask_ad.py videos    # resumes: only missing clips are made
    python scripts/_gen_pigmask_ad.py cut       # trim to the beat sheet + stitch

Built from `skills/creative/shopee-product-ad.md` (Repeat-Reveal archetype),
against the measured DNA of the @the.fattypack reference in
`projects/_analysis/fb_dropship_ref/`: one reveal repeated in four public
settings, accelerating cuts, every shot ending on a bystander reaction, no
narration.

**Two constraints shape this file.**

*Flow's duration floor is 4s*, but the format needs 4 / 2 / 2 / 1.5s. So every
clip is generated at 4s and `cut` trims it to its beat. Generating short and
padding would not work — the reaction has to land inside the kept window, so
each prompt puts the reaction early and `TRIM` keeps the front of the clip.

*The user accepted Flow's mandatory VN watermark but still wants no on-screen
text.* So `CLEAN` forbids captions, titles and graphics in the generated frame,
and nothing is burned in at the stitch step either. The watermark Flow adds is
outside our control and was accepted knowingly.
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

PROJECT = Path("projects/pigmask-ad")
VIDEO = PROJECT / "assets" / "video"
CUT = PROJECT / "renders"

PROJECT_URL = "https://flow.google.com/project/0ebed0ec-2661-4413-851f-9fa34078c90f?hl=vi"
LOCK = Path.home() / ".openmontage" / "flow_video.lock"

GEN_SECONDS = "4"          # Flow's floor; every clip is generated at this length

# ---------------------------------------------------------------- locked blocks
# Pasted verbatim into every prompt. Four independently generated clips become
# four different women otherwise — the same failure the flow-video shot-sequence
# standard records for this series.

SUBJECT = ("THE WEARER is the same young Vietnamese woman in every shot: early "
           "twenties, shoulder-length straight black hair tucked behind one ear, "
           "no fringe, small gold stud earrings, and a plain oversized cream "
           "cotton shirt with the sleeves pushed to the elbow. Her hair, clothing "
           "and earrings are identical in every shot. ")

PRODUCT = ("She is wearing a novelty fabric face mask printed with a photo-real "
           "pink pig snout: two dark nostrils and a wide pink muzzle covering her "
           "nose and mouth, edges blending softly into the mask fabric, held on by "
           "thin black elastic ear loops. The printed snout sits centred on her "
           "face and keeps exactly the same size, colour and position in every "
           "shot. ")

MOTION = ("Handheld phone footage, filmed by a friend standing a couple of steps "
          "away. The camera moves slightly and continuously, the way a hand-held "
          "phone does, with no stop and no cut anywhere in the clip. ")

# The fix the first sample forced. Shot 01 came back correct to the letter and
# wrong on screen: she turned to face the other person, which turned her *away*
# from camera, so the barista's laugh — the payoff — played over the back of her
# head with the snout out of sight. The product must be visible during the
# reaction, not just before it, so the camera is placed to the side of the pair
# and both faces are pinned into frame together.
FRAMING = ("The camera films the pair from the side, at an angle where BOTH her "
           "masked face in three-quarter profile AND the other person's face are "
           "visible in the frame at the same time, for the whole clip. Her "
           "printed pig snout stays facing partly toward the camera and is never "
           "hidden: the back of her head never turns to the camera and never "
           "fills the frame. ")

SPEED = ("Everything runs at normal real-time speed, 1x, not slow motion. ")

# There is no negative prompt, so the absence is stated positively.
CLEAN = ("There is no text anywhere in the frame: no caption, no subtitle, no "
         "title card, no sticker, no logo, no watermark and no graphic overlay of "
         "any kind. Nothing is written on any surface in shot. ")

MEDIUM_TAIL = ("Realistic candid smartphone video, natural available light, "
               "slightly imperfect framing, not a studio advert and not an "
               "illustration. Vertical 9:16. ")

AUDIO_TAIL = ("ambient: the room's own background noise and a short burst of "
              "genuine laughter from the other person. no dialogue, no music, "
              "no voice-over.")

# (name, trim_seconds, setting, beat)
SHOTS = [
    ("01_cafe", 4.0,
     "Inside a small bright cafe, at the counter. A male barista in a dark apron "
     "stands behind the counter facing her, an espresso machine and a menu board "
     "with no writing on it behind him. ",
     "She is already standing at the counter in profile to the camera when the "
     "barista looks up from the till, sees the pig snout, and his face breaks "
     "into a surprised laugh. That is the only action — she does not turn around, "
     "does not speak, does not remove the mask and does not walk away. "),

    ("02_sieuthi", 2.0,
     "At a supermarket checkout lane. A female cashier in a uniform polo stands "
     "at the till, groceries on the belt between them, shelves blurred behind. ",
     "She leans slightly forward into the cashier's eyeline. The cashier glances "
     "up, sees the pig snout, and laughs, covering her mouth with one hand. That "
     "is the only action — nobody speaks and the mask stays on. "),

    ("03_thangmay", 2.0,
     "Inside a lift, doors just opened. One man in an office shirt stands in the "
     "lift looking at his phone, mirrored lift wall behind him. ",
     "She steps into the doorway. The man looks up from his phone, does a "
     "double-take at the pig snout, and grins. That is the only action — the "
     "doors do not close and the mask stays on. "),

    ("04_vanphong", 1.5,
     "In an open-plan office, beside a desk. Two colleagues sit at the desk with "
     "laptops, a blank whiteboard on the wall behind them. ",
     "She leans into the gap between the two colleagues. Both look up at once, "
     "see the pig snout, and burst out laughing, one throwing their head back. "
     "That is the only action — the moment ends on their laugh. "),
]

TARGET_TOTAL = 9.5


def prompt_for(shot) -> str:
    _, _, setting, beat = shot
    return (MEDIUM_TAIL + setting + SUBJECT + PRODUCT + beat + FRAMING + MOTION
            + SPEED + CLEAN + AUDIO_TAIL)


def check() -> None:
    """The skill's checklist, encoded. Runs before any credit is spent."""
    assert len(SHOTS) == 4, "Repeat-Reveal wants 3-4 settings; this is built for 4"

    # Accelerating cuts — the single rule the reference proves and copies break.
    trims = [t for _, t, _, _ in SHOTS]
    for earlier, later in zip(trims, trims[1:]):
        assert later <= earlier, f"shot lengths must never grow: {trims}"
    assert trims[0] >= 2 * trims[-1], f"shot 1 should be ~2x the last: {trims}"

    total = sum(trims)
    assert total == TARGET_TOTAL, f"beats total {total}s, expected {TARGET_TOTAL}s"
    assert 9.0 <= total <= 12.0, f"format lives at 10-12s, got {total}s"
    for name, trim, _, _ in SHOTS:
        assert trim <= float(GEN_SECONDS), f"{name}: cannot trim {trim}s out of a {GEN_SECONDS}s clip"

    settings = [s for _, _, s, _ in SHOTS]
    assert len(set(settings)) == len(settings), "every shot needs its own setting"

    for shot in SHOTS:
        name = shot[0]
        text = prompt_for(shot)
        # Same person, same product, every shot — verbatim, never reworded.
        assert SUBJECT in text, f"{name}: missing SUBJECT"
        assert PRODUCT in text, f"{name}: missing PRODUCT"
        assert MOTION in text, f"{name}: missing MOTION"
        # Without this the reaction plays over the back of her head — measured,
        # not hypothetical: it is exactly how the first sample of 01_cafe failed.
        assert FRAMING in text, f"{name}: missing FRAMING — the snout will vanish during the payoff"
        assert SPEED in text, f"{name}: missing SPEED — it will come back slow-motion"
        # The user's standing constraint.
        assert CLEAN in text, f"{name}: missing the no-on-screen-text clause"
        # The archetype's load-bearing element: proof is a reaction in frame.
        assert any(w in text for w in ("laugh", "grin", "double-take")), \
            f"{name}: no bystander reaction — the reaction IS the proof"
        assert "only action" in text, f"{name}: doesn't pin a single beat"
        assert "no dialogue" in text and "ambient:" in text, f"{name}: missing audio tail"
        for phrase in ("the patch", "the spot", "that area"):
            assert phrase not in text.lower(), f"{name}: '{phrase}' points at nothing"

    print(f"check ok — {len(SHOTS)} shots, generate {GEN_SECONDS}s each, "
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

    ledger = PROJECT / "pigmask_videos_result.json"
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
    """Trim each clip to its beat and hard-cut them together.

    The front of each clip is kept, not the middle: the prompts put the
    reaction early precisely so the kept window contains it.
    """
    CUT.mkdir(parents=True, exist_ok=True)
    parts = []
    for name, trim, _, _ in SHOTS:
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
    out = CUT / "pigmask_ad_9x16.mp4"
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


MODES = {"check": lambda _: 0, "videos": run_videos, "cut": lambda _: run_cut()}

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    check()
    if mode == "check":
        raise SystemExit(0)
    if mode == "sample":
        raise SystemExit(run_videos(["01"]))
    if mode not in MODES:
        raise SystemExit(f"usage: {sys.argv[0]} [check | sample | videos | cut] [shot-id ...]")
    raise SystemExit(MODES[mode](sys.argv[2:]))
