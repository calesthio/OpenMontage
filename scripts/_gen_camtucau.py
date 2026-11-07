"""Eight shots for 'Tiệm hoa — bó cẩm tú cầu xanh tím', photoreal POV, 9:16, 60s.

Same-place sequence, so it follows
`.agents/skills/flow-video/references/shot-sequence-prompts.md`: STYLE / HANDS /
STAGE / MOTION pasted verbatim into every prompt, one beat per clip, and a
per-shot NOTHING block naming the contradiction that shot can invent.

Reference: TikTok @vnretro322 white-peony bouquet, 4:28. We keep its seven
beats and its POV grammar; the flower, the palette and the wrap are ours, and
none of its burnt-in branding is reproduced.

    python scripts/_gen_camtucau.py check     # the standard's checklist, spends nothing
    python scripts/_gen_camtucau.py images    # codex_image gpt-image-2
    python scripts/_gen_camtucau.py videos    # flow_video Omni, ~10 credits/clip
    python scripts/_gen_camtucau.py videos 01 04    # sample: just these shots
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path("projects/tiem-hoa-cam-tu-cau/assets")
IMAGES, VIDEO = ROOT / "images", ROOT / "video"

# ---------------------------------------------------------------- locked blocks
# Pasted verbatim into every prompt. Never reworded per shot — rewording is how
# the drift starts.

STYLE = (
    "Photoreal vertical 9:16 smartphone video, first-person POV looking down at a "
    "florist's work counter. Natural daylight from a shopfront window, soft and "
    "slightly cool, no studio lighting and no colour grading. Shallow natural phone "
    "depth of field. Palette of cream, dove grey, soft blue and lilac. It is real "
    "footage, not an illustration and not a render. "
)

# Measurable attributes only. The hands carry ~80% of the piece, so they are
# pinned exactly as hard as a character would be.
HANDS = (
    "Only a young woman's two hands and forearms are in shot: fair skin, short "
    "unpainted nails, a thin plain gold ring on the right ring finger, and the "
    "sleeves of a soft dove-grey knit sweater pushed up to mid-forearm. No other "
    "person is visible. "
)

# The block that does the work. Measurable props, and the blue tape dispenser and
# gold-handled scissors are the continuity anchors — they sit in the same corner
# of the counter in every shot, which is what tells the viewer it is one bench
# and one afternoon.
STAGE = (
    "The place is a florist's shop counter: a cream melamine work surface with a "
    "rounded front edge, a stainless-steel sink recessed into it on the left, and a "
    "wall rack of ribbon spools on the back wall behind. A bright blue plastic tape "
    "dispenser and a pair of gold-handled scissors lie on the right-hand side of the "
    "counter in every shot. Beyond the counter is a full-height black-framed glass "
    "shopfront looking onto a bright daylight street. Every surface in the shop is "
    "blank: there are no chalkboards, no signs, no posters, no price cards, no "
    "packaging labels and no lettering of any kind anywhere in the frame. "
)

# No shot is locked-off — a still shot reads as a photograph the moment it sits
# next to a moving one. Measured with scripts/clip_motion.py, target mean 2-9.
MOTION = (
    "The camera is handheld and drifts slowly and continuously for the whole shot "
    "with a small steady amplitude — it never stops and never speeds up, and the "
    "last frame differs only a little from the first. "
)

# The flower. Named botanically because "hydrangea" alone drifts to a garden bush.
FLOWER = (
    "The flowers are mophead hydrangeas (Hydrangea macrophylla): large rounded heads "
    "the size of a grapefruit, each made of many small four-petalled florets, in soft "
    "sky blue and pale lilac with a few heads shading to cream. Thick pale-green stems "
    "and broad serrated leaves. "
)

# The bouquet's answer to "where are the feet". A florist gets both hands free
# only because the bench is carrying the bouquet: it stands on its cut stems,
# base down, and the hands work around it. Left out of the first pass, and the
# clip came back with the bouquet hanging in mid-air under two working hands —
# the one thing in the shot a viewer knows is impossible.
SUPPORT = (
    "The bouquet stands upright on the counter, its cut stem ends resting on the "
    "surface and taking its own weight. It is never held up in mid-air and never "
    "floats: whenever both hands are working on the wrapping, the counter is what "
    "holds the bouquet. "
)

# Veo renders a "slow, careful" description as slow motion. The action's tempo has
# to be stated separately from the camera's, or a florist working at normal speed
# comes back at half rate.
SPEED = (
    "Everything runs at normal real-time speed: the hands move at a florist's "
    "brisk, practised working pace, quick and unhesitating. This is real-time "
    "footage at 1x, not slow motion and not a slowed-down clip. "
)

AUDIO_TAIL = " no dialogue, no music, no voices."

# ---------------------------------------------------------------------- the shots
# (name, seconds, image prompt, video prompt)
SHOTS = [
    ("01_tuot_la", "8",
     STYLE + HANDS + STAGE + FLOWER +
     "Loose hydrangea stems lie across the counter. The hands strip the lower leaves "
     "off one stem, a small pile of stripped leaves beside them. "
     "Nothing is assembled: there is no bouquet, no wrapping paper and no ribbon "
     "anywhere on the counter, and the flowers are loose and separate. ",
     MOTION + SPEED +
     "The hands strip leaves down one hydrangea stem and drop them on the counter. "
     "That is the only action — the hands do not lift the stem away and do not begin "
     "gathering. The counter, the sink, the ribbon rack behind, the blue tape "
     "dispenser and the gold scissors all stay exactly as they are in the opening "
     "frame, and no new tool, vase, paper or ribbon ever appears. "
     "ambient: soft rustle of leaves, a faint street hum through glass." + AUDIO_TAIL),

    ("02_gom_bo", "8",
     STYLE + HANDS + STAGE + FLOWER +
     "The left hand holds a gathered spiral bunch of about nine hydrangea heads at the "
     "binding point, loosely between thumb and forefinger, forming one rounded dome; "
     "every stem lies at the same angle and spirals in the same direction. The right "
     "hand adds a further stem. The bunch is bare stems only — it is not tied yet, and "
     "there is no twine, no paper, no fabric and no ribbon on it. ",
     MOTION + SPEED +
     "The left hand turns the gathered dome of hydrangeas a little while the right "
     "hand tucks one more stem into it. That is the only action — the bunch is not "
     "wrapped and is not set down. The counter, the ribbon rack, the blue tape "
     "dispenser and the gold scissors stay exactly as they are in the opening frame, "
     "and no paper or ribbon appears. "
     "ambient: stems shifting against each other, a faint street hum." + AUDIO_TAIL),

    ("03_buoc_diem", "6",
     STYLE + HANDS + STAGE + FLOWER +
     "Close over the counter: the left hand holds the gathered spiral bunch at the "
     "binding point, about a third of the way down from the heads, while the right "
     "hand winds a length of natural jute twine around that point. The bunch is bare "
     "stems below the twine — no paper, no fabric and no ribbon on it. ",
     MOTION + SPEED +
     "The right hand winds the twine around the binding point and pulls it tight. That "
     "is the only action — the stems are not cut and nothing is wrapped. The counter, "
     "the sink, the blue tape dispenser and the gold scissors stay exactly as they are "
     "in the opening frame. "
     "ambient: twine drawn tight around stems, a faint street hum." + AUDIO_TAIL),

    ("04_cat_goc", "6",
     STYLE + HANDS + STAGE + FLOWER +
     "Close over the counter: the left hand holds the bunch, already tied with jute "
     "twine wound three times around the binding point, while the right hand closes a "
     "pair of florist's shears on the stem ends, short offcuts lying on the counter "
     "below. The bunch is tied but unwrapped — no paper and no ribbon on it. ",
     MOTION + SPEED +
     "The shears close once through the stem ends and the offcuts drop onto the "
     "counter. That is the only action — the hands do not carry the bunch away and do "
     "not begin wrapping. The counter, the sink, the blue tape dispenser and the gold "
     "scissors stay exactly as they are in the opening frame. "
     "ambient: one crisp snip of shears, stems falling on a hard counter." + AUDIO_TAIL),

    ("05_lot_trang", "8",
     STYLE + HANDS + STAGE + FLOWER + SUPPORT +
     "The gathered bouquet stands on the counter and the hands draw a sheet of soft "
     "white non-woven fabric up around the outside of the hydrangea dome, forming a "
     "shallow white collar that cups the heads like a bowl. Only this white inner "
     "layer is on the bouquet — no grey paper and no ribbon are on it yet. ",
     MOTION + SPEED +
     "The hands lift the white fabric collar up around the flower heads and press the "
     "fold in place, working quickly. The bouquet stays standing on the counter on its "
     "own stems for the whole shot — it is never lifted into the air. That is the only "
     "action — no paper is added and nothing is tied. "
     "The counter, the ribbon rack behind, the blue tape dispenser and the gold "
     "scissors stay exactly as they are in the opening frame, and the background does "
     "not dissolve or change into any other room. "
     "ambient: soft crinkle of non-woven fabric, a faint street hum." + AUDIO_TAIL),

    ("06_quan_ngoai", "8",
     STYLE + HANDS + STAGE + FLOWER + SUPPORT +
     "The bouquet stands on the counter in its white collar and the hands fold the "
     "dove-grey handmade paper around the outside of it, closing it into a wide cone "
     "with two raised corners standing above the hydrangea heads. No ribbon and no "
     "bow are on the bouquet yet. ",
     MOTION + SPEED +
     "The hands bring one side of the grey paper across the front of the bouquet and "
     "press the fold closed with one quick practised movement. The bouquet stays "
     "standing on the counter on its own stems for the whole shot and is never held "
     "up in the air. That is the only action — nothing is tied and no bow "
     "appears. The counter, the ribbon rack, the blue tape dispenser and the gold "
     "scissors stay exactly as they are in the opening frame, and the background does "
     "not change into any other room. "
     "ambient: thick paper creasing and crinkling, a faint street hum." + AUDIO_TAIL),

    ("07_that_no", "8",
     STYLE + HANDS + STAGE + FLOWER + SUPPORT +
     "Close on the waist of the wrapped bouquet, which stands upright on the counter "
     "on its own stems: the hands pull a wide ivory satin ribbon tight around the "
     "narrow point of the grey paper cone and shape the first loop of a bow, the long "
     "tails hanging down. The hydrangea heads sit above in their white collar and "
     "grey paper. ",
     MOTION + SPEED +
     "The hands draw the ivory ribbon tight and shape one loop of the bow with quick "
     "practised fingers. The bouquet stays standing on the counter on its own stems "
     "for the whole shot and is never held up in the air. That is the only action — "
     "the bouquet is not lifted and not carried. The counter, the blue "
     "tape dispenser and the gold scissors stay exactly as they are in the opening "
     "frame. "
     "ambient: satin ribbon sliding against paper, one soft pull." + AUDIO_TAIL),

    ("08_ra_nang", "8",
     STYLE + FLOWER +
     "A young woman with long dark-brown hair, in the same soft dove-grey knit sweater "
     "and straight light-blue jeans, stands on the grey pavement just outside a "
     "black-framed glass shopfront, holding the finished bouquet across her body: "
     "hydrangea heads in a white fabric collar inside a dove-grey handmade-paper cone, "
     "tied at the waist with a wide ivory satin bow whose tails hang down. Framed from "
     "the chest down, her face not in shot. Both feet stay on the pavement; she does "
     "not step into the road. Bright natural daylight. There is no lettering of any "
     "kind anywhere in the frame: no shop sign, no board, no poster, no label. ",
     MOTION + SPEED +
     "She turns the bouquet slightly toward the camera as she stands. That is the only "
     "action — she does not walk and does not hand the bouquet over. The bouquet stays "
     "exactly as it is: the same grey paper cone, the same white collar and the same "
     "ivory bow, and no new flower, wrapper or ribbon appears on it. The shopfront "
     "behind her stays what it is in the opening frame and does not change into any "
     "other street. "
     "ambient: quiet street, a light breeze, distant traffic." + AUDIO_TAIL),
]

STAMP: dict[str, str] = {}  # no branded prop in frame — nothing to stamp


# --------------------------------------------------------------------- the check
def check() -> None:
    """The standard's checklist. Spends nothing; run it before the first clip."""
    counter = [s for s in SHOTS if STAGE in s[2]]
    assert len(counter) == 7, f"{len(counter)} shots carry STAGE verbatim, expected 7"

    for name, _, image, video in SHOTS:
        assert STYLE in image, f"{name}: STYLE missing — the render will drift"
        assert MOTION in video, f"{name}: no MOTION block — it will come back locked-off"
        for label, text in (("image", image), ("video", video)):
            for phrase in ("the patch", "the spot", "that area"):
                assert phrase not in text.lower(), \
                    f"{name} {label}: '{phrase}' points at something the model has never seen"
        assert "ambient:" in video, f"{name}: video prompt has no ambient line"
        assert "no dialogue" in video, f"{name}: video prompt does not suppress dialogue"
        assert " only action" in video, f"{name}: video prompt does not pin one beat"
        # Veo reads "slow and careful" as slow motion unless the action's tempo is
        # stated on its own. Every clip says it, or the piece plays at half rate.
        assert SPEED in video, f"{name}: no SPEED block — it will come back slow-motion"
        # Signage is furniture that differs shot to shot and that Veo warps on every
        # re-render. One chalkboard invented in shot 6 is a continuity break in the
        # other seven, so the whole set is kept blank.
        assert "no lettering of any kind" in image,             f"{name}: nothing forbids invented signage in the frame"

    # A florist frees both hands only because the bench is holding the bouquet.
    # Any shot where two hands work the wrapping must say what carries its weight,
    # or the bouquet comes back floating — which is what happened on the first pass.
    for name, _, image, video in SHOTS:
        two_handed_wrap = any(w in image for w in ("white collar", "grey handmade paper "
                                                   "around", "ivory satin ribbon"))
        if two_handed_wrap and "out of frame" not in image:
            assert SUPPORT in image, f"{name}: two hands on the wrap, nothing says what holds the bouquet"
            assert "standing on the counter" in video, \
                f"{name}: video prompt never pins the bouquet to the counter"

    # Every shot has to say what stage of assembly the bouquet is at, or the model
    # rewraps it between cuts — the wrap either goes on or it does not exist yet.
    WRAP_STATE = ("no ribbon", "no bow", "ivory satin bow", "loop of a bow",
                  "bouquet is out of frame")
    for name, _, image, _ in SHOTS:
        assert any(w in image for w in WRAP_STATE), \
            f"{name}: the image prompt never says how far the wrap has got"

    # The one shot with a body in it must say where her feet are (Ngày 10, shot 7).
    body = SHOTS[-1][2]
    assert "feet stay on the pavement" in body, "08: never says where her feet are"

    # Trade order, from skills/styles/florist-bouquet-craft.md §3. Cutting an
    # untied bunch makes it fall apart, and the wrap layers only go on in one
    # order. The first pass cut the stems with nothing holding the bunch at all.
    order = [n for n, _, _, _ in SHOTS]
    def at(fragment: str) -> int:
        return next(i for i, n in enumerate(order) if fragment in n)
    assert at("buoc_diem") < at("cat_goc"), "stems are cut before the bunch is tied"
    assert at("cat_goc") < at("lot_trang"), "wrapping starts before the stems are cut"
    assert at("lot_trang") < at("quan_ngoai"), "outer paper goes on before the inner collar"
    assert at("quan_ngoai") < at("that_no"), "the bow is tied before the paper is closed"

    total = sum(int(seconds) for _, seconds, _, _ in SHOTS)
    assert total == 60, f"shot list adds up to {total}s, not the scripted 60s"
    print(f"check ok — {len(SHOTS)} shots, {total}s, STAGE verbatim in {len(counter)} shots")


def _wanted(names: list[str]) -> list[tuple]:
    if not names:
        return SHOTS
    picked = [s for s in SHOTS if s[0].split("_")[0] in names]
    if not picked:
        raise SystemExit(f"no shot matches {names} — ids are "
                         + ", ".join(s[0].split("_")[0] for s in SHOTS))
    return picked


def run_images(names: list[str] | None = None) -> int:
    """Opening frames through codex_image (gpt-image-2).

    Flow's Nano Banana drew these for free until Flow's abuse detection flagged
    the account mid-run and started refusing every generation ("Chúng tôi nhận
    thấy có hoạt động bất thường"). Codex is the fallback the user approved; one
    provider for all eight frames either way, because STAGE only holds still if
    the same model renders every shot.
    """
    from tools.graphics.codex_image import CodexImage

    IMAGES.mkdir(parents=True, exist_ok=True)
    tool, results = CodexImage(), []

    for name, _, prompt, _ in _wanted(names or []):
        target = IMAGES / f"{name}.png"
        if target.is_file() and target.stat().st_size > 50_000:
            print(f"skip {name}", flush=True)
            continue

        started = time.time()
        for attempt in range(4):
            # Codex answers "Selected model is at capacity" under load; it clears.
            result = tool.execute({"prompt": prompt, "size": "1024x1536",
                                   "output_path": str(target)})
            if result.success:
                break
            print(f"  {name} attempt {attempt + 1}: {result.error}"[:300], flush=True)
            time.sleep(40)
        took = round(time.time() - started, 1)
        print(f"{name}: {'ok' if result.success else 'FAILED'} ({took}s)", flush=True)
        if not result.success:
            print(f"   {result.error}", flush=True)
        results.append({"name": name, "ok": result.success, "seconds": took})

    failed = [r["name"] for r in results if not r["ok"]]
    print(f"\ndone: {len(results) - len(failed)}/{len(results)}")
    if failed:
        print("failed:", ", ".join(failed))
    return 1 if failed else 0


def run_videos(names: list[str] | None = None) -> int:
    from tools.video.flow_video import FlowVideo

    VIDEO.mkdir(parents=True, exist_ok=True)
    tool, results = FlowVideo(), []

    for name, duration, _, prompt in _wanted(names or []):
        out = VIDEO / f"{name}.mp4"
        if out.is_file() and out.stat().st_size > 200_000:
            print(f"skip {name}", flush=True)
            continue
        frame = IMAGES / f"{name}.png"
        if not frame.is_file():
            print(f"{name}: no opening frame — run `images` first", flush=True)
            return 1

        started = time.time()
        result = tool.execute({
            "prompt": prompt,
            "operation": "image_to_video",
            "reference_image_path": str(frame),
            "model_variant": "Omni",
            "duration": duration,
            "aspect_ratio": "9:16",
            "resolution": "720p",
            "output_path": str(out),
            "timeout_seconds": 900,
        })
        took = round(time.time() - started, 1)

        row = {"name": name, "ok": result.success, "seconds": took}
        if result.success:
            row["credits"] = result.data.get("flow_credits")
            row["duration"] = result.data.get("duration_seconds")
            print(f"{name}: ok ({took}s) — {row['duration']}s, "
                  f"{row['credits']} credits", flush=True)
        else:
            row["error"] = result.error
            print(f"{name}: FAILED ({took}s)\n   {result.error}", flush=True)
        results.append(row)

        Path("camtucau_videos_result.json").write_text(
            json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")

    failed = [r["name"] for r in results if not r["ok"]]
    spent = sum(r.get("credits") or 0 for r in results)
    print(f"\ndone: {len(results) - len(failed)}/{len(results)} clips, {spent} credits")
    if failed:
        print("failed:", ", ".join(failed))
    print(f"\nNext: python scripts/clip_motion.py {VIDEO} --cuts")
    print(f"      python scripts/flow_continuity_check.py {VIDEO}")
    return 1 if failed else 0


MODES = {"check": lambda _: (check(), 0)[1], "images": run_images, "videos": run_videos}

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    if mode not in MODES:
        raise SystemExit(f"usage: {sys.argv[0]} [{' | '.join(MODES)}] [shot-id ...]")
    sys.exit(MODES[mode](sys.argv[2:]))
