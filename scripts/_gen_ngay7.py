"""Six clips for 'Dưới tán hoa — Ngày 7: Vị khách đầu tiên', anime, 9:16, 54s.

Written to `.agents/skills/flow-video/references/shot-sequence-prompts.md`, and
to the two things Ngày 8 paid for: `MOTION` in every prompt, and a background
that is described rather than left as space for Veo to fill.

No images are generated. The six opening frames are the user's artworks, one per
beat, so STYLE, CAST and STAGE cannot drift between shots — the frames carry
them. What still has to be said in words is everything that must stay put while
the camera moves, because Flow regenerates from the frame instead of playing it.

Two problems here that Ngày 8 never had.

**Two people in frame.** Ngày 8 pinned one woman and that was enough. With two,
the failure is not drift in one costume, it is the pair swapping attributes — the
guest inheriting the owner's ribbon, the owner turning up in pink. So `CAST`
names both by measurable attributes and, more importantly, says which is which
in the same sentence as what they are wearing. `HEADCOUNT` then fixes the number,
because Ngày 8's shot 8 proved Veo adds a person to a frame that has room for
one: there, an empty room grew a woman at 1.5s.

**Vietnamese handwriting is the subject of a shot.** Shot 5 is a note being read.
The standard's old answer — describe the surface blank and stamp the text in
afterwards — cannot apply when the words are the point of the scene. Ngày 8
established what actually preserves lettering, and it was not locking the camera:
shot 8 held its sign perfectly intact through a rising move, on the strength of
the sentence "the lettering does not move, warp or alter". That sentence carries
shot 5 here.

    python scripts/_gen_ngay7.py check      # the standard's checklist, spends nothing
    python scripts/_gen_ngay7.py videos     # resumes: only missing clips are made
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path("projects/duoi-tan-hoa-ngay-7/assets")
FRAMES, VIDEO = ROOT / "frames", ROOT / "video"

# ---------------------------------------------------------------- locked blocks

# Measured off the published episode, in scripts/clip_motion.py: every shot in
# this series carries a slow continuous move, mean per-frame change 1.9 to 8.7.
# The word "locked-off" is not in this series' vocabulary — on Ngày 8 it produced
# three shots that measured 0.50, 1.20 and 1.21 and read as photographs.
MOTION = (
    "The camera moves slowly and continuously for the entire shot at one constant speed, with "
    "no stop, no acceleration and no cut anywhere in the clip. The movement is small: the "
    "framing at the end is only a little different from the framing at the start. "
)

# Both women, in one block, each tied to her own clothes in the same breath. Split
# across two sentences the model is free to reassign them.
CAST = (
    "Two women, and they never exchange clothes, hair or hair ornaments. THE GARDENER has very "
    "long black wavy hair falling past her waist with a cream ribbon bow tied at the back of her "
    "head, and wears a long ivory-cream cotton dress with full puffed sleeves gathered at the "
    "wrist, deep lace cuffs and a lace-trimmed square neckline. THE VISITOR has shoulder-length "
    "soft brown hair gathered in a low loose ponytail with no ribbon and no bow, and wears a long "
    "dusty-pink dress with three-quarter puffed sleeves, a gathered waist and a plain round "
    "neckline. The gardener is never in pink and the visitor is never in cream. "
)

# The room, from the artworks — not carried over from Ngày 8, which was a round
# table under a floral cloth in a different glasshouse.
STAGE = (
    "The place is the inside of an old white-painted wooden-framed glasshouse with a pitched "
    "glass roof. A long rustic wooden potting bench runs along the tall windows, its planks "
    "scattered with dark soil crumbs and covered in part by a cream lace runner embroidered with "
    "small flowers. On the bench stands one weathered terracotta flowerpot holding dark soil, "
    "with a small pale wooden marker sign on a stake bearing the handwritten words \"Dưới Tán "
    "Hoa\" in dark-brown ink. Galvanised buckets, more terracotta pots, a white enamel jug, old "
    "books and hand tools sit along the bench and on the wooden shelves. Dry golden-brown "
    "climbing foliage hangs from the frame and the shelves all around. Through the glass is a "
    "bright summer garden: a black wrought-iron gate, flowering shrubs, and a pale stone house "
    "with a chimney beyond, under a blue sky with soft white clouds. Warm daylight comes through "
    "the glass and lays leaf-shadows across the bench and the stone floor. "
)

# Ngày 8's recurring contradiction was "exactly one sprout". Here it is the
# number of people: the frames all hold two, and an empty-looking corner is an
# invitation. Stated as a count, positively, in every prompt.
HEADCOUNT = (
    "There are exactly two people anywhere in the shot — the gardener and the visitor — and no "
    "one else appears at any moment: no third person, no child, no passer-by walks into frame or "
    "stands in the garden beyond the glass. "
)

# HOLD's gap on Ngày 8 was that it listed what must stay and never forbade what
# might be added — so a push-in dissolved one background into a different room
# and grew a spray of dry grass in front of a face. The second sentence is that
# missing half, and it names the things this set invites.
HOLD = (
    "Nothing in the glasshouse changes: the potting bench, the lace runner, the terracotta pot, "
    "the wooden marker sign and its handwriting, the buckets and jug and books, the hanging dry "
    "foliage, and the garden with its iron gate and stone house beyond the glass all stay exactly "
    "as they are and in the same places. Nothing is added to the room either — no new plant, no "
    "extra pot, no vase, no furniture, no ornament and no object of any kind appears or grows "
    "into the frame, and the background never dissolves, fades out or changes into another room. "
    "The seedling in the pot stays exactly one small green seedling of the same size. "
)

AUDIO_TAIL = " no dialogue, no music, no voices."

# ---------------------------------------------------------------------- the shots
# (name, frame, seconds, move, prompt)
SHOTS = [
    ("01_tuoi_cay", "a_tuoi_cay.jpg", "8", "slow drift toward the bench",
     "The camera drifts slowly and continuously in toward the potting bench. " + MOTION +
     "The gardener keeps pouring a thin stream of water from the galvanised watering can onto "
     "the soil in the terracotta pot, and raises her eyes toward the window as she pours. She "
     "stays where she stands and does not put the can down or turn her body away. Beyond the "
     "glass the visitor stands still by the iron gate and stays outside — she does not walk "
     "closer, does not reach the glasshouse and does not come indoors at any point. " +
     CAST + HEADCOUNT + HOLD +
     "ambient: water falling on soil, a metal watering can shifting, birdsong in the garden."
     + AUDIO_TAIL),

    ("02_khach_ngoai", "b_khach_ngoai.jpg", "10", "very slow push-in past the shoulder",
     "A very slow continuous push-in past the gardener's shoulder toward the window. " + MOTION +
     "Beyond the glass the visitor stands still and keeps looking in at the seedling and the "
     "wooden marker sign; her hands stay clasped in front of her and her dress and hair move a "
     "little in the garden breeze. She does not walk toward the glasshouse, does not raise a "
     "hand, does not knock and does not come indoors. In the near foreground the gardener's "
     "shoulder and hair stay where they are and she does not turn around. " +
     CAST + HEADCOUNT + HOLD +
     "The background beyond the glass stays exactly the garden it is — the iron gate, the "
     "flowering shrubs and the stone house — softly out of focus and never replaced. "
     "ambient: faint wind against glass, distant birdsong, leaves moving outside." + AUDIO_TAIL),

    ("03_mo_cua", "c_mo_cua.jpg", "8", "slow drift in through the doorway",
     "The camera drifts slowly and continuously in toward the open doorway. " + MOTION +
     "The gardener holds the glasshouse door open with one hand and lifts her other hand toward "
     "the bench in a small welcoming gesture; the visitor takes one quiet step in over the "
     "threshold and stops just inside. Neither of them speaks or opens her mouth. The gardener "
     "keeps hold of the door and does not let it swing shut. " +
     CAST + HEADCOUNT + HOLD +
     "ambient: a door on its hinge, quiet footsteps on a stone floor, birdsong outside."
     + AUDIO_TAIL),

    ("04_dat_giay", "d_dat_giay.jpg", "8", "slow push-in toward the bench",
     "A slow continuous push-in toward the bench. " + MOTION +
     "The visitor lays a small folded cream note down flat on the wooden bench beside the "
     "terracotta pot and lifts her fingers away from it. That is the only thing that happens: "
     "she does not turn to leave, does not walk out of frame and does not speak, and the "
     "gardener behind her stays still and watches without moving toward the bench. The note "
     "stays folded and closed, lying flat where it is put. " +
     CAST + HEADCOUNT + HOLD +
     "ambient: paper settling on wood, cloth shifting, faint birdsong." + AUDIO_TAIL),

    # The lettering shot. Ngày 8 proved the sentence below — not a locked camera —
    # is what holds handwriting together through a move, so this one is free to
    # drift like every other shot in the series.
    ("05_doc_giay", "e_doc_giay.jpg", "10", "very slow drift toward the note",
     "A very slow continuous drift in toward the note held open in the gardener's two hands. "
     + MOTION +
     "The handwritten Vietnamese words on the note stay perfectly still and completely "
     "unchanged for the whole shot — the handwriting does not move, warp, ripple, re-form or "
     "alter, no letter changes shape and no new line of writing appears. The paper stays flat "
     "and open between her fingers and is not folded, turned over or lowered. Far beyond it, "
     "through the open door, the visitor keeps walking slowly away down the garden path with her "
     "back turned; she keeps going and never stops, turns around or comes back. " +
     CAST + HEADCOUNT +
     "The background stays exactly what it is in the opening frame and is never replaced: the "
     "open white door, the garden path, the flowering shrubs and the stone house beyond, and at "
     "the right the terracotta pot with its seedling and the wooden marker sign, all softly out "
     "of focus. Nothing new appears in it, and the seedling in the pot stays exactly one small "
     "green seedling of the same size. "
     "The whole shot stays a soft cel-shaded painterly anime drawing with delicate linework and "
     "flat painted colour, exactly like the frame it starts from — it never becomes a "
     "photograph, and the paper and hands never take on photographic texture. "
     "ambient: paper held in two hands, a faint breeze through an open door, distant birdsong."
     + AUDIO_TAIL),

    # The one shot where something is allowed to grow. Everywhere else HOLD freezes
    # the seedling; here the script asks for a leaf to open, so the permission is
    # given by name and the freeze is lifted for this clip only.
    ("06_nhin_theo", "f_nhin_theo.jpg", "10", "slow drift toward the window",
     "The camera drifts slowly and continuously toward the window. " + MOTION +
     "The gardener sits at the bench with her chin resting on her hand, looking out through the "
     "glass, and breathes once as her expression settles; she stays seated and does not stand, "
     "turn around or reach for anything. In the pot beside her ONE new small green leaf unfurls "
     "very slowly and opens — this is the only thing in the whole episode that is allowed to "
     "grow, and nothing else about the seedling changes: it does not get taller, does not "
     "flower and does not sprout a second stem. Far away through the glass the visitor walks on "
     "down the garden path with her back turned and does not stop or return. " +
     CAST + HEADCOUNT +
     "Nothing in the glasshouse changes and nothing is added to it: the bench, the lace runner, "
     "the terracotta pot, the wooden marker sign and its handwriting, the open note lying on the "
     "bench, the buckets and books and hanging dry foliage all stay exactly as they are, and no "
     "new object appears or enters the frame. "
     "ambient: a faint breeze, cloth shifting, birdsong settling into quiet." + AUDIO_TAIL),
]


def check() -> None:
    """Run the standard's checklist over the prompt table before anything is spent.

    Every assertion below is a failure this series has already paid for once.
    """
    supplied = {"a_tuoi_cay.jpg", "b_khach_ngoai.jpg", "c_mo_cua.jpg",
                "d_dat_giay.jpg", "e_doc_giay.jpg", "f_nhin_theo.jpg"}
    used = {frame for _, frame, _, _, _ in SHOTS}
    assert used <= supplied, \
        f"not a supplied artwork: {sorted(used - supplied)} — only the six may open a shot"
    assert used == supplied, f"supplied but unused: {sorted(supplied - used)}"
    for name, frame, _, _, _ in SHOTS:
        assert (FRAMES / frame).is_file(), f"{name}: opening frame {frame} is missing"

    for name, _, seconds, _, _ in SHOTS:
        assert seconds in {"4", "6", "8", "10"}, f"{name}: Flow does not offer {seconds}s"
    total = sum(int(seconds) for _, _, seconds, _, _ in SHOTS)
    assert total == 54, f"shot list adds up to {total}s, not the planned 54s"

    # A frame reused with the same move reads as a repeat. Nothing is reused here,
    # but the guard stays so the next episode cannot quietly introduce one.
    moves: dict[str, set[str]] = {}
    for name, frame, _, move, _ in SHOTS:
        assert move not in moves.get(frame, set()), \
            f"{name}: reuses {frame} with a move already used on it — that reads as a repeat"
        moves.setdefault(frame, set()).add(move)

    for name, _, _, move, prompt in SHOTS:
        for phrase in ("the patch", "the spot", "that area"):
            assert phrase not in prompt.lower(), \
                f"{name}: '{phrase}' points at something the model has never seen"
        assert "ambient:" in prompt, f"{name}: no ambient line — Veo invents muttering without one"
        assert "no dialogue" in prompt, f"{name}: does not suppress dialogue"

        # Retired on Ngày 8, where it measured 0.50 mean and read as a photograph.
        for text in (move, prompt):
            assert "locked-off" not in text.lower(), \
                f"{name}: 'locked-off' is retired — see scripts/clip_motion.py"
        assert MOTION in prompt, f"{name}: no MOTION block — this series has no still shots"

        # Both women named together, and the number of people fixed. Ngày 8's empty
        # room grew a person at 1.5s when nothing said how many there should be.
        assert CAST in prompt, f"{name}: no CAST block — the two of them can swap costumes"
        assert HEADCOUNT in prompt, f"{name}: never says how many people are in the shot"

        # The half HOLD was missing on Ngày 8: naming what stays does not forbid
        # adding. Every prompt has to refuse additions in its own words.
        assert "no new" in prompt.lower() or "nothing new" in prompt.lower(), \
            f"{name}: never forbids new objects appearing — that is how shots 3 and 7 broke"

    # Exactly one shot may show growth, and it is the one the script asks it of.
    growers = [name for name, _, _, _, prompt in SHOTS if "unfurls" in prompt]
    assert growers == ["06_nhin_theo"], f"growth allowed in the wrong shots: {growers}"
    for name, _, _, _, prompt in SHOTS:
        if name != "06_nhin_theo":
            assert "stays exactly one small green seedling" in prompt, \
                f"{name}: does not freeze the seedling"

    print(f"check ok — {len(SHOTS)} clips, {total}s, {len(used)} supplied frames, "
          f"no image generation")


# The Chrome profile that drives Flow routinely has half a dozen project tabs
# open, and without this the driver takes whichever one it finds first — an
# episode's clips land in a stranger's project and the next run cannot resume.
PROJECT_URL = "https://flow.google.com/project/1bf5b712-b98d-4c38-a7d3-ffbd4aa377b2"
LOCK = Path.home() / ".openmontage" / "flow_video.lock"


def run_videos() -> int:
    from tools.video.flow_video import FlowVideo

    os.environ.setdefault("FLOW_PROJECT_URL", PROJECT_URL)
    # A crashed run leaves the serialization lock behind, and the next one dies
    # on a message about a concurrent generation that is not running.
    LOCK.unlink(missing_ok=True)
    VIDEO.mkdir(parents=True, exist_ok=True)
    tool, results = FlowVideo(), []

    for name, frame, duration, _, prompt in SHOTS:
        out = VIDEO / f"{name}.mp4"
        if out.is_file() and out.stat().st_size > 200_000:
            print(f"skip {name}", flush=True)
            continue

        started = time.time()
        result = tool.execute({
            "prompt": prompt,
            "operation": "image_to_video",
            "reference_image_path": str(FRAMES / frame),
            "model_variant": "Omni",
            "duration": duration,
            "aspect_ratio": "9:16",
            "resolution": "720p",
            "output_path": str(out),
            "timeout_seconds": 900,
        })
        took = round(time.time() - started, 1)

        row = {"name": name, "frame": frame, "ok": result.success, "seconds": took}
        if result.success:
            row["credits"] = result.data.get("flow_credits")
            row["duration"] = result.data.get("duration_seconds")
        else:
            row["error"] = result.error
        print(f"{name}: {'ok' if result.success else 'FAILED'} ({took}s)", flush=True)
        if not result.success:
            print(f"   {result.error}", flush=True)
            # Delete what a failed run left behind. The tool writes the file
            # before it checks the duration, and this script resumes by skipping
            # any output that already exists — so a rejected clip would be
            # skipped forever and shipped as if it had passed.
            out.unlink(missing_ok=True)
        results.append(row)

    # Merge rather than overwrite: this script resumes by skipping finished clips,
    # so a rerun that fixes one failure would otherwise erase the credit record
    # for all the others — the only account of what an episode actually cost.
    ledger = Path("ngay7_videos_result.json")
    previous = json.loads(ledger.read_text(encoding="utf-8")) if ledger.is_file() else []
    merged = {row["name"]: row for row in previous}
    merged.update({row["name"]: row for row in results})
    ledger.write_text(
        json.dumps([merged[k] for k in sorted(merged)], indent=1, ensure_ascii=False),
        encoding="utf-8")

    failed = [row["name"] for row in results if not row["ok"]]
    print(f"\ndone: {len(results) - len(failed)}/{len(results)}")
    if failed:
        print("failed:", ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "check"
    check()
    sys.exit(0 if command == "check" else run_videos())
