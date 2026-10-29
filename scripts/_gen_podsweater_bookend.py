"""POD sweater ad built from two stills per shot instead of one prompt.

    python scripts/_gen_podsweater_bookend.py check    # checklist, spends nothing
    python scripts/_gen_podsweater_bookend.py end      # the payoff stills (0 credits)
    python scripts/_gen_podsweater_bookend.py start    # the coats-on stills (0 credits)
    python scripts/_gen_podsweater_bookend.py videos   # start+end -> video (7 credits each)
    python scripts/_gen_podsweater_bookend.py cut      # trim to the beat sheet + stitch

Why this shape. Text-to-video made the garment print a lottery: the elf SKU came
back as a full red vest with a belt, which is a different product, and each retry
cost credits. Flow images cost nothing, so the print is settled in a still first,
reviewed, regenerated for free until it matches `ref_products.jpg` — and only
then does the video get made, with that still pinned as the **end** frame and its
coats-on twin as the **start** frame. The video no longer has to invent the
product; it only has to move between two frames that already show it.

Order matters: the END still is generated first because it is the one carrying
the product, and the START still is then generated *from* it so the same two
people stand in the same room wearing coats.

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
FRAMES = PROJECT / "assets" / "frames"
BOOK = PROJECT / "assets" / "bookend"
VIDEO = PROJECT / "assets" / "video_bookend"
CUT = PROJECT / "renders"

PROJECT_URL = "https://flow.google.com/project/0ebed0ec-2661-4413-851f-9fa34078c90f?hl=vi"
LOCK = Path.home() / ".openmontage" / "flow_video.lock"

# 8s, not Flow's 4s floor: at 4s the pair had to get their coats off and the room
# had to react inside four seconds, and the motion came out rushed. The beats are
# still short — the extra seconds are headroom to cut the best part out of, not
# length to keep.
GEN_SECONDS = "8"

# The two approved single-SKU stills, and nothing else. Four earlier attempts
# spelled the prints out in prose instead; all four failed, and the failures are
# worth keeping written down because the prose looked so reasonable each time:
#   - cast stills as refs in video elements mode -> portraits of the cast
#     printed onto the green sweatshirt;
#   - long garment description, text only -> the elf became a closed red vest
#     with a belt, which is a different product;
#   - long description + the product photo as a ref -> a knitted novelty jumper;
#   - same, with the surface pinned as a flat print -> flat cartoon vector art,
#     and one refusal from Flow's content filter along the way.
# Pointing at the stills and saying almost nothing else is what finally matched
# `ref_products.jpg`. This print is not describable in prose at this fidelity.
CAST_REFS = [FRAMES / "char_elf.jpg", FRAMES / "char_santa.jpg"]

# ---------------------------------------------------------------- locked blocks

CAST = ("THE WOMAN is the woman from the first reference photo and THE MAN is "
        "the man from the second reference photo. Keep both faces exactly as "
        "they are there. They stand side by side, the woman on the left of frame "
        "and the man on the right. ")

# Deliberately says nothing about what either print depicts. Every attempt that
# did describe it drifted or was refused; this one matched the product photo.
GARMENTS = (
    "Each of them wears exactly the same printed sweatshirt they wear in their "
    "own reference photo, with the printed design identical in every detail, in "
    "the same colours, at the same size and in the same position on the chest: "
    "hers the dark green one, his the red one. The printed designs are "
    "photographic all-over prints on smooth sweatshirt fleece, not knitted, not "
    "embroidered and not cartoon drawings. Nothing from a reference photo is "
    "reprinted onto a garment as a portrait — the sweatshirt designs are only "
    "the costume designs already on them. ")

FRAMING = ("Both people are shown from the knees up, facing the camera square on, "
           "far enough back that both printed sweater fronts are fully visible "
           "and unobstructed, with nothing crossing in front of either chest. ")

CLEAN = ("There is no text anywhere in the frame: no caption, no subtitle, no "
         "title card, no sticker, no logo, no watermark and no graphic overlay of "
         "any kind. No writing appears on any wall, screen or surface in shot. ")

MEDIUM = ("Realistic candid smartphone photo, natural indoor party light, "
          "slightly imperfect framing, not a studio advert and not an "
          "illustration. Vertical 9:16. ")

COATS_ON = ("Both of them are wearing plain dark winter coats, fully closed and "
            "buttoned to the neck, so the sweaters underneath are completely "
            "hidden and no part of either print is visible. ")

# The reveal is made in the edit, not by the model.
#
# Flow refuses to animate the coats coming off. Measured, not guessed: the same
# two stills generate fine under a neutral prompt, so the frames are accepted —
# it is the described act of taking clothing off, next to a print depicting a
# bikini and a midriff, that the classifier reads as a strip. Two wordings were
# refused, including the plainest one. No third wording was tried: searching for
# phrasing that slips past a content filter is evading it.
#
# So neither clip contains the action. One clip holds on the closed coats, the
# other holds on the sweaters already showing, and the hard cut between them is
# the reveal. This is how the measured reference ad does it anyway — in
# `projects/_analysis/fb_dropship_ref/` the cut lands on the reaction, and no
# shot in it animates a garment coming off.
MOTION_BEFORE = (
    "The two of them stand still in their closed winter coats while the people "
    "behind them talk and laugh among themselves. Nothing else happens: they "
    "stay dressed exactly as in the first frame for the whole clip and their "
    "coats stay closed. Handheld phone footage that moves slightly and "
    "continuously, one continuous take with no cut. Everything runs at normal "
    "real-time speed, 1x, not slow motion. ")

MOTION_AFTER = (
    "The two of them stand facing the camera with their coats already off and "
    "held down at their sides, dressed exactly as in the first frame for the "
    "whole clip. The people behind them catch sight of the sweatshirts and burst "
    "out laughing. Handheld phone footage that moves slightly and continuously, "
    "one continuous take with no cut. Everything runs at normal real-time speed, "
    "1x, not slow motion. ")

AUDIO_TAIL = ("ambient: party room noise and a short burst of genuine laughter "
              "from the other people. no dialogue, no music, no voice-over.")

# (name, (before_seconds, after_seconds), setting, reaction). The pair always
# accelerates the same way: the coats-on beat is the short one, because the
# audience is waiting for the cut, and the payoff beat holds on the reaction.
SHOTS = [
    ("01_doorway", (1.5, 2.5),
     "The front doorway of a house at Christmas, a wreath on the door, coats on "
     "hooks and three guests standing in the hallway behind them. ",
     "The three guests in the hallway are laughing, one with a hand over her "
     "mouth. "),

    ("02_livingroom", (1.0, 2.0),
     "A family living room: a lit Christmas tree behind them, a sofa, an older "
     "woman sitting with a mug and a teenager beside her. ",
     "The older woman has her head back laughing and the teenager is doubled "
     "over. "),

    ("03_kitchen", (0.7, 1.3),
     "A kitchen at a house party: a counter with snacks and drinks behind them, "
     "two friends leaning against it. ",
     "Both friends are cracking up, one pointing at the sweaters. "),
]

TARGET_TOTAL = 9.0


def end_prompt(shot) -> str:
    _, _, setting, reaction = shot
    return (MEDIUM + setting + CAST + GARMENTS
            + "Their coats are off and hanging from their hands at their sides, "
              "so both printed sweaters are fully on show. " + reaction
            + FRAMING + CLEAN)


def start_prompt(shot) -> str:
    _, _, setting, _ = shot
    return (MEDIUM + setting
            + "The same two people as in the reference image, standing in the "
              "same place in the same room, with the same people behind them. "
            + COATS_ON
            + "Nobody is laughing yet — the people behind them are just talking. "
            + FRAMING + CLEAN)


def video_prompt(shot, half: str) -> str:
    _, _, setting, _ = shot
    # No garment description at all: the still it starts from carries the
    # product, and every sentence about the print is a sentence Flow can drift
    # on or refuse.
    motion = MOTION_BEFORE if half == "before" else MOTION_AFTER
    return (MEDIUM + setting + motion + CLEAN + AUDIO_TAIL)


def _still(name: str, kind: str) -> Path:
    return BOOK / f"{name}_{kind}.jpg"


def check() -> None:
    assert len(SHOTS) == 3, "Repeat-Reveal wants 3-4 settings"
    for ref in CAST_REFS:
        assert ref.is_file(), f"missing reference image: {ref}"

    pairs = [t for _, t, _, _ in SHOTS]
    lengths = [before + after for before, after in pairs]
    for earlier, later in zip(lengths, lengths[1:]):
        assert later <= earlier, f"shot lengths must never grow: {lengths}"
    assert lengths[0] >= 2 * lengths[-1], f"shot 1 should be ~2x the last: {lengths}"
    total = sum(lengths)
    assert total == TARGET_TOTAL, f"beats total {total}s, expected {TARGET_TOTAL}s"
    assert 9.0 <= total <= 12.0, f"format lives at 9-12s, got {total}s"
    for (name, (before, after), *_) in SHOTS:
        # The cut is the reveal, so the payoff half must outlast the setup half:
        # an audience that has already guessed the gag will not sit through a
        # long look at two closed coats.
        assert after > before, f"{name}: payoff beat {after}s must beat setup {before}s"
        for half, trim in (("before", before), ("after", after)):
            assert trim <= float(GEN_SECONDS), \
                f"{name}/{half}: cannot trim {trim}s from {GEN_SECONDS}s"

    settings = [s for _, _, s, _ in SHOTS]
    assert len(set(settings)) == len(settings), "every shot needs its own setting"

    for shot in SHOTS:
        name = shot[0]
        end, start = end_prompt(shot), start_prompt(shot)
        before, after = video_prompt(shot, "before"), video_prompt(shot, "after")

        # The end still is the only frame that has to get the product right, and
        # it gets it by pointing at the approved stills, never by describing it.
        assert GARMENTS in end, f"{name}: end still needs the point-at-the-refs block"
        assert "not knitted, not embroidered and not cartoon drawings" in end, \
            f"{name}: without this the print renders as a knit or as vector art"
        assert "reprinted onto a garment as a portrait" in end, \
            f"{name}: without this the cast refs get printed onto the sweater"
        assert "Keep both faces exactly as they are" in end, \
            f"{name}: the cast chips alone did not hold the woman's face"
        for banned in ("candy-striped", "jingle-bell", "muscular", "fur trim"):
            assert banned not in end, (
                f"{name}: {banned!r} describes the print — four attempts proved "
                f"prose drifts or gets refused; let the reference stills carry it")
        assert any(w in end for w in ("laughing", "cracking up", "doubled")), \
            f"{name}: the end still is the payoff — it needs the reaction"

        # The start still must hide the product, or there is nothing to reveal.
        assert COATS_ON in start, f"{name}: start still must have the coats closed"
        assert GARMENTS not in start, \
            f"{name}: describing the print in the start still defeats the reveal"
        assert "reference image" in start, \
            f"{name}: the start still must be built from the end still or the cast drifts"

        for label, text in (("end", end), ("start", start),
                            ("before", before), ("after", after)):
            assert CLEAN in text, f"{name}/{label}: missing the no-on-screen-text clause"
        for label, text in (("before", before), ("after", after)):
            assert "no dialogue" in text and "ambient:" in text, \
                f"{name}/{label}: missing audio tail"
            assert "one continuous take with no cut" in text, \
                f"{name}/{label}: each half must be one take"
            assert "dressed exactly as in the first frame" in text, \
                f"{name}/{label}: without this the model animates the change of clothes"
            # The refused action must not reappear in either half by accident.
            for banned in ("take their coats off", "pull their coats",
                           "revealing", "reveal"):
                assert banned not in text, (
                    f"{name}/{label}: {banned!r} is the action Flow refuses — "
                    f"the reveal belongs to the cut, not to the model")

    print(f"check ok — {len(SHOTS)} shots x 2 halves; stills settle the print "
          f"for free, video generates {GEN_SECONDS}s each, trim to {pairs} "
          f"= {total}s, the cut is the reveal, no on-screen text")


def _wanted(names: list[str]) -> list[tuple]:
    if not names:
        return SHOTS
    picked = [s for s in SHOTS if s[0].split("_")[0] in names]
    if not picked:
        raise SystemExit(f"no shot matches {names} — ids are "
                         + ", ".join(s[0].split("_")[0] for s in SHOTS))
    return picked


def _run_stills(kind: str, names: list[str] | None = None) -> int:
    from tools.graphics.flow_image import FlowImage

    os.environ.setdefault("FLOW_PROJECT_URL", PROJECT_URL)
    LOCK.unlink(missing_ok=True)
    BOOK.mkdir(parents=True, exist_ok=True)
    tool, failed = FlowImage(), []

    for shot in _wanted(names or []):
        name = shot[0]
        out = _still(name, kind)
        if out.is_file() and out.stat().st_size > 50_000:
            print(f"skip {name}_{kind}", flush=True)
            continue

        if kind == "end":
            prompt, refs = end_prompt(shot), list(CAST_REFS)
        else:
            end_still = _still(name, "end")
            if not end_still.is_file():
                print(f"{name}: no end still yet — run `end` first", flush=True)
                failed.append(name)
                continue
            prompt, refs = start_prompt(shot), [end_still]

        result = tool.execute({
            "prompt": prompt,
            "model_variant": "Pro",
            "aspect_ratio": "9:16",
            "n": 1,
            "reference_images": [str(r) for r in refs],
            "output_path": str(out),
            "timeout_seconds": 600,
        })
        print(f"{name}_{kind}: {'ok' if result.success else 'FAILED'}", flush=True)
        if not result.success:
            print(f"   {result.error}", flush=True)
            failed.append(name)

    if failed:
        print("failed:", ", ".join(failed))
    return 1 if failed else 0


def run_videos(names: list[str] | None = None) -> int:
    from tools.video.flow_video import FlowVideo

    os.environ.setdefault("FLOW_PROJECT_URL", PROJECT_URL)
    LOCK.unlink(missing_ok=True)
    VIDEO.mkdir(parents=True, exist_ok=True)
    tool, results = FlowVideo(), []

    for shot in _wanted(names or []):
        # Each half is its own generation, starting from its own still and never
        # crossing between them — no end frame is passed, because a start and an
        # end frame that differ is precisely how you ask for the change of
        # clothes Flow refuses.
        for half, kind in (("before", "start"), ("after", "end")):
            name = shot[0]
            tag = f"{name}_{half}"
            out = VIDEO / f"{tag}.mp4"
            if out.is_file() and out.stat().st_size > 200_000:
                print(f"skip {tag}", flush=True)
                continue

            still = _still(name, kind)
            if not still.is_file():
                print(f"{tag}: missing {still} — run `end` then `start`", flush=True)
                results.append({"name": tag, "ok": False, "error": f"missing {still}"})
                continue

            began = time.time()
            result = tool.execute({
                "prompt": video_prompt(shot, half),
                "operation": "image_to_video",
                "reference_image_path": str(still),
                "model_variant": "Omni",
                "duration": GEN_SECONDS,
                "aspect_ratio": "9:16",
                "resolution": "720p",
                "output_path": str(out),
                "timeout_seconds": 900,
            })
            took = round(time.time() - began, 1)
            row = {"name": tag, "ok": result.success, "seconds": took}
            if result.success:
                row["credits"] = result.data.get("flow_credits")
                row["model"] = result.data.get("flow_model")
            else:
                row["error"] = result.error
                out.unlink(missing_ok=True)
            results.append(row)
            print(f"{tag}: {'ok' if result.success else 'FAILED'} ({took}s)", flush=True)
            if not result.success:
                print(f"   {result.error}", flush=True)

    ledger = PROJECT / "podsweater_bookend_result.json"
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
    for name, (before, after), *_ in SHOTS:
        for half, trim in (("before", before), ("after", after)):
            src = VIDEO / f"{name}_{half}.mp4"
            if not src.is_file():
                print(f"missing {src} — run `videos` first")
                return 1
            dst = CUT / f"_booktrim_{name}_{half}.mp4"
            # The payoff half is taken from the END of its clip, where the
            # laughter has actually landed; the setup half from the start, so
            # the cut falls while the coats are still closed.
            seek = ["-ss", f"{float(GEN_SECONDS) - trim:.2f}"] if half == "after" else []
            subprocess.run(["ffmpeg", "-y", "-v", "error", *seek, "-i", str(src),
                            "-t", str(trim), "-c:v", "libx264", "-preset", "slow",
                            "-crf", "18", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "160k", str(dst)], check=True)
            parts.append(dst)

    listing = CUT / "_bookconcat.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    out = CUT / "podsweater_bookend_9x16.mp4"
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
    if mode == "end":
        raise SystemExit(_run_stills("end", sys.argv[2:]))
    if mode == "start":
        raise SystemExit(_run_stills("start", sys.argv[2:]))
    if mode == "videos":
        raise SystemExit(run_videos(sys.argv[2:]))
    if mode == "cut":
        raise SystemExit(run_cut())
    raise SystemExit(f"usage: {sys.argv[0]} [check | end | start | videos | cut] [shot-id ...]")
