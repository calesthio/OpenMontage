"""Five chained clips, 46s, one seedling growing into one flower.

    python scripts/_gen_timelapse.py check     # the checklist, spends nothing
    python scripts/_gen_timelapse.py videos    # resumes: only missing clips are made

Two artworks were supplied and nothing else: a two-leaf seedling on a
greenhouse bench, and the same pot with a single pink flower open on a tall
stem. Everything between them has to be invented, and it has to arrive exactly
on the second artwork — so the chain is:

    clip 1   start = the seedling artwork
    clip 2   start = last frame of clip 1
    ...
    clip 5   start = last frame of clip 4

Only the opening frame is ever pinned. Flow's closing-frame slot does land the
last clip exactly on the artwork — it was tried and it worked — but it buys that
by making the clip race: pinned, it measured 5.69 mean motion against 1.71 to
2.96 for the four unpinned ones, which in a timelapse reads as a morph rather
than a flower opening. The closing artwork is carried by `FLOWER` in words
instead.

The frame handed forward is taken from the *cleaned* clip, never the raw one.
A raw Flow frame carries the sparkle in its corner, and feeding that to the
next clip bakes a watermark into footage the watermark was already removed
from — and then removes it again from a place where it is now part of the
picture.

Two things this piece needs that the episodes did not.

**Nobody.** Ngày 8 proved Veo puts a person into a frame with room for one:
there, an empty room grew a woman at 1.5s. This is 46 seconds of an empty
greenhouse, which is 46 seconds of room. `NOBODY` says so in every prompt.

**Monotonic growth.** Every other prompt in this series forbids growth. Here
growth is the subject, so instead each clip names the stage it starts from and
the stage it reaches, and `check()` refuses a prompt that lets the plant shrink
back or skip ahead — a chained sequence has no way to recover from one clip
that flowers early.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PROJECT = Path("projects/duoi-tan-hoa-timelapse")
FRAMES = PROJECT / "assets" / "frames"
VIDEO = PROJECT / "assets" / "video"
CLEAN = PROJECT / "assets" / "video_clean"
LINKS = PROJECT / "assets" / "chain"          # last frames handed forward

START_ART = FRAMES / "start_mam_non.jpg"
END_ART = FRAMES / "end_hoa_no.jpg"

PROJECT_URL = "https://flow.google.com/project/1bf5b712-b98d-4c38-a7d3-ffbd4aa377b2"
LOCK = Path.home() / ".openmontage" / "flow_video.lock"

STYLE = ("Soft anime illustration in the style of a painted storybook: warm sunlit palette, "
         "clean linework, gentle watercolour shading, no photorealism and no 3D render. ")

STAGE = ("A single terracotta pot of dark crumbled soil stands on a weathered wooden potting "
         "bench inside a white-framed glasshouse. A small wooden sign on a stake leans beside "
         "the pot. Dry golden foliage hangs from the frames on both sides, an enamel watering "
         "can with a painted leaf pattern sits to the right, and through the tall window behind "
         "the bench a summer garden shows a rose-covered iron arch, a gravel path and a pale "
         "stone house under a blue sky with soft clouds. ")

MOTION = ("The camera moves slowly and continuously for the entire shot at one constant speed, "
          "with no stop, no acceleration and no cut anywhere in the clip. The movement is small: "
          "the framing at the end is only a little different from the framing at the start. ")

SIGN = ("The small wooden sign keeps its handwritten Vietnamese words exactly as written; "
        "the lettering does not move, warp or alter. ")

HOLD = ("Nothing except the plant changes. The terracotta pot, the dark crumbled soil, the "
        "wooden bench and its boards, the wooden sign and its handwriting, the white window "
        "frames, the dry hanging foliage, the enamel watering can, and the garden beyond the "
        "glass with its rose arch, gravel path and stone house all stay exactly as they are and "
        "in the same places. Nothing is added to the scene either — no new pot, no second plant, "
        "no tool, no vase, no ornament and no object of any kind appears or grows into the "
        "frame, and the background never dissolves, fades out or changes into another place. ")

NOBODY = ("There are no people anywhere in the shot at any moment: no person, no hand, no arm, "
          "no face and no figure appears in the glasshouse or in the garden beyond the glass, "
          "and nobody walks into frame at any point. ")

MEDIUM_TAIL = ("The whole shot stays a soft painted anime illustration, never a photograph. ")

# Repeated at the very end of the last clip's prompt, and only there. Without a
# closing frame to hold the set, the first attempt drifted right off it: the
# flower opened well but the terracotta pot and the wooden sign left the frame
# entirely, the camera pulled back instead of in, and the warm afternoon light
# went cold and pale. HOLD already said all of this — it just said it in the
# middle, where the long flower description buried it. Ngày 8's lesson again:
# the sentence that must survive goes last.
FRAMING_TAIL = ("Throughout the shot the terracotta pot stays in frame with its rim across the "
                "bottom, the small wooden sign stays visible near the right edge, and the light "
                "stays warm afternoon sun falling from behind the glass. The camera only ever "
                "moves closer, never further away. ")

AUDIO_TAIL = ("ambient: still greenhouse air, faint birdsong in the garden beyond the glass, "
              "the occasional creak of old wood. no dialogue, no music, no voices.")

# The closing artwork, carried in words instead of pinned to Flow's end-frame
# slot. Pinning it worked — the last frame came back almost identical to the
# painting — but it costs the thing a timelapse is made of: that clip measured
# 5.69 mean motion against 1.71 to 2.96 for the four unpinned ones, because a
# fixed destination makes the model race to arrive rather than open at the pace
# of the shot. Described instead, the bloom has to be specific enough to land in
# the same place on its own, which is what all this detail is for.
FLOWER = ("The open flower is a single wide shallow cup of about nine broad rounded petals in two "
          "loose layers, pale blush pink, each petal a little paler toward its slightly ruffled "
          "edge and marked with fine deeper-pink veins running from its base outward. At the "
          "centre sits a dense round cluster of thread-fine golden-yellow stamens. Small green "
          "sepals stay visible where the petals meet the stem. The bloom faces up and tilts "
          "slightly toward the camera, high in the frame. Clear dew beads the petals and stands "
          "in droplets along the veins and serrated edges of the broad dark-green leaves below, "
          "and one large clear drop hangs from the base of the flower.")

# (name, seconds, camera, action). The action names where the plant starts and
# where it gets to, so the chain has no gap and no overlap.
SHOTS = [
    ("01_hai_la", "10",
     "The camera drifts very slowly in toward the pot, closing a little of the distance.",
     "The seedling begins as a short green stem carrying one pair of small smooth leaves. "
     "Over the shot the stem lengthens steadily and a second pair of leaves unfolds above the "
     "first, so the plant ends roughly twice its starting height with four leaves in all. "
     "The growth is smooth and continuous and never stops or reverses."),

    ("02_bon_la", "10",
     "The camera continues drifting slowly in, the pot growing a little larger in frame.",
     "The plant begins as a slim stem with two pairs of leaves. Over the shot the stem thickens, "
     "a third pair of leaves opens above the others, and every leaf broadens and deepens in "
     "colour. It ends as a sturdier young plant with six leaves, still with no bud of any kind. "
     "The growth is smooth and continuous and never stops or reverses."),

    ("03_nu_hinh_thanh", "10",
     "The camera keeps drifting in and begins to rise slightly toward the top of the plant.",
     "The plant begins as a sturdy young stem with six broad leaves. Over the shot it grows "
     "taller still, and at the very tip a single small green bud forms and begins to swell — one "
     "bud only, tightly closed, showing no colour yet. The growth is smooth and continuous and "
     "never stops or reverses."),

    ("04_nu_hong", "10",
     "The camera drifts in closer and rises a little more, the tip of the plant near the middle "
     "of the frame.",
     # Written against the frame this clip actually starts from, not against the
     # plan. Clip 03 delivered a bud already blushed pink, a stage early; telling
     # clip 04 it begins with a closed green bud would ask the model to undo the
     # picture it was handed.
     "The plant begins as a tall stem with broad leaves and one small closed bud at its tip, "
     "already blushed pale pink. Over the shot that bud swells steadily and its pink deepens "
     "and spreads down the petals, but it stays closed and there is still only one bud on the "
     "whole plant. The growth is smooth and continuous and never stops or reverses."),

    ("05_no_hoa", "6",
     "The camera drifts in the last of the way, ending close on the flower with the pot rim low "
     "in the frame.",
     "The plant begins as a tall stem with one swollen pink-tipped bud. Over the shot that single "
     "bud opens into one fully open pale pink flower. " + FLOWER +
     " Exactly one flower opens and no second bud or flower appears anywhere. The opening is "
     "smooth and continuous and never stops or reverses."),
]

DURATIONS = {"4", "6", "8", "10"}
TARGET_SECONDS = 46


def prompt_for(shot) -> str:
    name, _, camera, action = shot
    tail = FRAMING_TAIL if name == SHOTS[-1][0] else ""
    return (STYLE + STAGE + camera + " " + MOTION + action + " "
            + SIGN + HOLD + NOBODY + tail + MEDIUM_TAIL + AUDIO_TAIL)


def check() -> None:
    assert START_ART.is_file(), f"missing the opening artwork at {START_ART}"
    # END_ART is no longer fed to Flow; it is kept as the thing FLOWER describes,
    # and as what the finished clip gets compared against by eye.
    assert END_ART.is_file(), f"missing the closing artwork at {END_ART}"

    total = sum(int(seconds) for _, seconds, _, _ in SHOTS)
    assert total == TARGET_SECONDS, f"clips total {total}s, expected {TARGET_SECONDS}s"
    for name, seconds, _, _ in SHOTS:
        assert seconds in DURATIONS, f"{name}: Flow does not offer {seconds}s"

    for shot in SHOTS:
        name = shot[0]
        text = prompt_for(shot)
        for block, label in ((MOTION, "MOTION"), (SIGN, "SIGN"), (HOLD, "HOLD"),
                             (NOBODY, "NOBODY")):
            assert block in text, f"{name}: missing {label}"
        assert "ambient:" in text and "no dialogue" in text, f"{name}: missing the audio tail"
        assert "locked-off" not in text, f"{name}: 'locked-off' is retired from this series"
        # A chained sequence cannot recover from one clip that runs backwards.
        assert "never stops or reverses" in text, f"{name}: growth is not pinned as monotonic"

    # The flower may only exist in the last clip. One early bloom and every
    # later clip inherits it from the frame handed forward.
    for shot in SHOTS[:-1]:
        text = prompt_for(shot).lower()
        assert "opens into" not in text, f"{shot[0]}: only the last clip may open the flower"
    assert "fully open pale pink flower" in prompt_for(SHOTS[-1]), \
        "the last clip must actually reach the flower"

    print(f"check ok — {len(SHOTS)} clips, {total}s, chained on opening frames only; "
          f"the ending is described, not pinned")


def last_frame(clip: Path, dst: Path) -> Path:
    """The final rendered frame of a clip, as a still.

    `-sseof -0.1` rather than a computed timestamp: a seek to the reported
    duration lands past the last frame and writes nothing at all, silently
    leaving the previous chain image in place for the next clip to reuse.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-sseof", "-0.1", "-i", str(clip),
                    "-update", "1", "-frames:v", "1", "-q:v", "2", str(dst)], check=True)
    if not dst.is_file() or dst.stat().st_size < 10_000:
        raise SystemExit(f"could not read a last frame out of {clip}")
    return dst


def clean(src: Path, dst: Path) -> Path:
    """Take the Flow sparkle off, so it is never handed to the next clip."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src),
                    "-vf", "removelogo=projects/_brand/flow-watermark-mask.png",
                    "-c:v", "libx264", "-crf", "17", "-preset", "slow",
                    "-pix_fmt", "yuv420p", "-c:a", "copy", str(dst)], check=True)
    return dst


def run_videos() -> int:
    from tools.video.flow_video import FlowVideo

    os.environ.setdefault("FLOW_PROJECT_URL", PROJECT_URL)
    LOCK.unlink(missing_ok=True)
    for folder in (VIDEO, CLEAN, LINKS):
        folder.mkdir(parents=True, exist_ok=True)

    tool, results = FlowVideo(), []
    start = START_ART

    for index, shot in enumerate(SHOTS):
        name, seconds, _, _ = shot
        raw, done = VIDEO / f"{name}.mp4", CLEAN / f"{name}.mp4"
        link = LINKS / f"after_{name}.jpg"
        last = index == len(SHOTS) - 1

        if done.is_file() and done.stat().st_size > 200_000:
            print(f"skip {name}", flush=True)
            start = link if link.is_file() else last_frame(done, link)
            continue

        # Only the opening frame is pinned, on every clip including the last.
        # The closing artwork is carried by `FLOWER` instead: see its comment
        # for why. The opening frame stays because it *is* the chain — drop it
        # and the final clip no longer continues the one before it, and the cut
        # that was invisible becomes the loudest thing in the piece.
        job = {
            "prompt": prompt_for(shot),
            "operation": "image_to_video",
            "reference_image_path": str(start),
            "model_variant": "Omni",
            "duration": seconds,
            "aspect_ratio": "9:16",
            "resolution": "720p",
            "output_path": str(raw),
            "timeout_seconds": 900,
        }

        began = time.time()
        result = tool.execute(job)
        took = round(time.time() - began, 1)

        row = {"name": name, "ok": result.success, "seconds": took,
               "from": start.name, "described_target": last}
        if result.success:
            row["credits"] = result.data.get("flow_credits")
            row["duration"] = result.data.get("duration_seconds")
        else:
            row["error"] = result.error
            raw.unlink(missing_ok=True)
        results.append(row)
        print(f"{name}: {'ok' if result.success else 'FAILED'} ({took}s)", flush=True)
        if not result.success:
            # Stop rather than carry on. Every later clip starts from this one's
            # last frame, so continuing past a failure builds the rest of the
            # sequence on the wrong picture.
            print(f"   {result.error}", flush=True)
            break

        clean(raw, done)
        start = last_frame(done, link)

    ledger = PROJECT / "timelapse_result.json"
    previous = json.loads(ledger.read_text(encoding="utf-8")) if ledger.is_file() else []
    merged = {row["name"]: row for row in previous}
    merged.update({row["name"]: row for row in results})
    ledger.write_text(json.dumps([merged[k] for k in sorted(merged)], indent=1,
                                 ensure_ascii=False), encoding="utf-8")

    failed = [row["name"] for row in results if not row["ok"]]
    print(f"\ndone: {len(results) - len(failed)}/{len(results)}")
    return 1 if failed else 0


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "check"
    check()
    raise SystemExit(0 if command == "check" else run_videos())
