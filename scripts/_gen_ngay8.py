"""Eight clips for 'Dưới tán hoa — Ngày 8: Chồi non đầu tiên', anime, 9:16, 60s.

Written to `.agents/skills/flow-video/references/shot-sequence-prompts.md`.

**This episode generates no images.** The eight opening frames are six artworks
the user supplied, in `assets/frames/`, two of them used twice. That removes the
whole class of failure the standard was written for — STYLE, CHARACTER and STAGE
cannot drift between shots when every shot starts from a picture that already
exists. The blocks below are gone for that reason, not by oversight.

What survives is section 5 of the standard, and it survives because it is the
half that image-to-video does *not* solve: Flow **regenerates** from the opening
frame rather than playing it, so anything that must stay put has to be said, in
words, in every clip. That is what `HOLD` is.

Two frames are reused. A reused frame with the same camera move is just a repeat
on screen, so `check()` refuses to let two clips off the same frame share a move:

    c_macro_choi  shot 3 slow macro push-in  shot 5 slow descent under the soil
    b_chau_bien   shot 2 slow push-in       shot 8 slow rise up the sign

No logo stamping this episode — the board carries the lettering that is already
painted into the supplied frames. Its wording is not identical across those six
artworks (one board is blank, one pot has no board at all), which is why the
running order puts the blank board early and holds the readable one only in the
last shot.

Clips 01, 02 and 04 were generated before MOTION existed and measured 1.91, 3.10
and 2.27 — inside the reference band of 1.87 to 8.65 — so they were left alone
and the credits not spent again. Their prompts below carry MOTION anyway: the
table is the instruction for the next episode, not a log of what produced the
files already on disk. Delete a clip to make this script rebuild it.

    python scripts/_gen_ngay8.py check      # the standard's checklist, spends nothing
    python scripts/_gen_ngay8.py videos     # resumes: only missing clips are made
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path("projects/duoi-tan-hoa-ngay-8/assets")
FRAMES, VIDEO = ROOT / "frames", ROOT / "video"

# ---------------------------------------------------------------- locked blocks

# Pasted verbatim into every clip. Flow regenerates the frame instead of playing
# it, so every constant in the picture has to be restated as a constant in words
# or Veo is free to redecorate it over ten seconds. This is Ngày 9's STAGE block
# doing its job from the other side: there it stopped the model *inventing* a
# room, here it stops the model *editing* one.
HOLD = (
    "Nothing in the room changes: the glasshouse, the shelves of dry golden grasses, the round "
    "table and its flowered cloth, the cream ceramic pot with its painted roses and the small "
    "wooden marker sign all stay exactly as they are, in the same places, and the writing on "
    "the sign does not move, warp or alter. Exactly one tiny seedling stands in the soil and it "
    "stays one seedling — it does not grow taller, multiply, or flower. The woman's black hair, "
    "white ribbon bow and long ivory-cream dress stay exactly as they are. "
)

# Measured off the published episode the user sent as the motion reference, with
# scripts/clip_motion.py. Every shot in that reference carries a slow continuous
# move: mean per-frame change ran 1.87 to 8.65, and the only near-still frame in
# it (0.46) was the closing text card on black, not footage. The first pass here
# came back at 0.50, 1.20 and 1.21 on three shots because their prompts opened
# with "Locked-off" — which is correct English for what I asked and wrong for
# this series. So the move is a pasted block now, like STAGE, and "locked-off"
# is not in the vocabulary any more.
MOTION = (
    "The camera moves slowly and continuously for the entire shot at one constant speed, with "
    "no stop, no acceleration and no cut anywhere in the clip. The movement is small: the "
    "framing at the end is only a little different from the framing at the start. "
)

AUDIO_TAIL = " no dialogue, no music, no voices."

# ---------------------------------------------------------------------- the shots
# (name, frame, seconds, move, prompt)
SHOTS = [
    ("01_chay_vao", "a_chay_vao.jpg", "6", "slow drift, subject crosses frame",
     "A wide shot with the camera drifting very slightly. " + MOTION + "Seen from behind, the "
     "woman takes two more light steps across the pale wooden floor toward the table and slows "
     "as she reaches it, her skirt and long hair settling behind her. She does not sit down and "
     "does not touch the pot. Her face is never seen. " + HOLD +
     "ambient: light quick footsteps on a wooden floor, a door swinging on its hinge, faint "
     "birdsong beyond the glass." + AUDIO_TAIL),

    ("02_chau_bien", "b_chau_bien.jpg", "6", "slow push-in",
     "A very slow push-in toward the pot standing on the table. " + MOTION + "Dust motes "
     "drift through the window light and the dry hanging foliage stirs once at the edge of the "
     "frame, then settles. No one enters the frame and no hands appear. " + HOLD +
     "ambient: very faint wind against glass, distant birdsong." + AUDIO_TAIL),

    ("03_macro_choi", "c_macro_choi.jpg", "8", "slow macro push-in",
     "A very slow continuous push-in on the seedling, closing in only a little on its two "
     "leaves across the whole shot — a short move that never becomes a close-up. " + MOTION +
     "The background behind the seedling stays exactly what it is in the opening frame and is "
     "never replaced: the pale rim of the cream ceramic pot, the small wooden marker sign on "
     "its stake, and beyond them the white window frames with the golden sunrise and the "
     "flowering garden outside, all softly out of focus. That background must not dissolve, "
     "fade out, wash to white or change into any other room, and no table, chair, cups, "
     "shelves or glass roof ever appear in it. "
     "As the camera closes in the leaves tremble in a faint draught and the round drop of dew "
     "quivers on the upper leaf without falling; the seedling stays the same size and does not "
     "grow. Nothing enters the frame — no hands, no people. "
     "The whole shot stays a soft cel-shaded painterly anime drawing with delicate linework, "
     "exactly like the frame it starts from. " + HOLD +
     "ambient: a very faint indoor draught, distant birdsong." + AUDIO_TAIL),

    ("04_ngoi_canh", "d_ngoi_canh.jpg", "10", "slow drift in",
     "The camera drifts in very slowly. " + MOTION + "Seated at the round table, the woman "
     "leans a fraction closer to the pot and her faint smile settles as she looks down at the "
     "seedling; her hair "
     "and the hanging foliage move slightly in the draught from the window. She stays seated on "
     "the chair, does not stand, and does not reach out or touch the pot. " + HOLD +
     "ambient: cloth shifting, a very faint draught, distant birdsong." + AUDIO_TAIL),

    # The one beat with no artwork of its own. Rather than invent an underground
    # frame in a different hand, the macro frame is reused and the camera does the
    # work: it sinks past the seedling into the soil, which reads as the script's
    # "xuống lòng đất" and stays inside the supplied art.
    # The beat with no artwork of its own. The first pass built a seventh opening
    # frame by grabbing the last frame of an earlier Veo render — which put a
    # machine's drawing in a set of hand-made ones, the exact "second hand in the
    # picture" failure the standard exists to prevent. Only the six supplied
    # artworks are opening frames. So this shot starts at the surface on the macro
    # artwork and the camera does the travelling, descending into the soil.
    #
    # Descending is not a free choice — from a frame shot at the surface it is the
    # only direction that reaches the roots. The first attempt failed on speed, not
    # direction: 17.52 mean against a reference band topping out at 8.7. MOTION is
    # what fixes that, and it measured 0.50 -> 3.29 on shot 3.
    ("05_duoi_long_dat", "c_macro_choi.jpg", "10", "slow sink, soil line held in frame",
     "The camera sinks slowly and continuously downward into the dark soil beside the "
     "seedling's stem, travelling among pale roots that come into view in the earth. " + MOTION +
     "The travel is short and gentle across the whole ten seconds — it never rushes and never "
     "plunges. "
     "Throughout the entire shot the surface of the soil stays visible as a clear horizontal "
     "line across the TOP of the frame, and the seedling stays standing in the open air above "
     "that line with its two leaves fully uncovered — the camera never descends far enough to "
     "lose the surface, the seedling is never covered by earth, and no soil ever passes in "
     "front of its leaves. Below the line the fine roots creep and spread a little further "
     "through the dark soil as the camera moves, because the line over this shot is \"dưới lớp "
     "đất kia, nó vẫn đang âm thầm lớn lên\". "
     "The whole shot stays a soft cel-shaded painterly anime drawing with delicate linework and "
     "flat painted colour, exactly like the frame it starts from — it never becomes a "
     "photograph, and the soil never takes on photographic texture or camera bokeh. "
     "No hands, no people, and no text of any kind enter the frame. "
     "ambient: a deep soft low hum, water soaking through soil, tiny grains settling."
     + AUDIO_TAIL),

    ("06_cam_ruy_bang", "e_cam_ruy_bang.jpg", "6", "slow drift toward the table",
     "The camera drifts slowly and continuously in toward the table. " + MOTION + "As it moves, "
     "the woman draws the pink ribbon once through her fingers and keeps looking at the pot, "
     "smiling faintly. She stays seated on the chair, does not stand, and does not tie the "
     "ribbon to anything. " + HOLD +
     "ambient: ribbon sliding through fingers, a faint draught, distant birdsong." + AUDIO_TAIL),

    ("07_chap_tay", "f_chap_tay.jpg", "6", "slow push-in past her shoulder",
     "A slow continuous push-in past her shoulder toward the pot, closing in only a little. "
     + MOTION + "The whole clip is one single unbroken shot from one camera position — the "
     "framing never jumps, widens or changes angle at any point. "
     "The room behind and around her stays exactly what it is in the opening frame and nothing "
     "is added to it: the white window frames with the golden sunrise and the flowering garden "
     "beyond, the shelves at the left, and the pot with its wooden sign. No new plant, no spray "
     "of dry grass, no vase, no ornament and no object of any kind appears or grows into the "
     "frame at any moment, and nothing ever materialises in front of her face or her hands. "
     "Seated at the table with her hands clasped near her chin, the woman keeps looking at the "
     "seedling and breathes once, her smile softening. She stays seated on the chair, does not "
     "stand, and does not unclasp her hands or reach for the pot. " + HOLD +
     "ambient: a very faint draught, cloth shifting, distant birdsong." + AUDIO_TAIL),

    ("08_bien_ten", "b_chau_bien.jpg", "8", "slow rise up the sign",
     "The camera rises slowly and continuously, tilting up a little from the pot toward the "
     "wooden sign and the window light behind it. " + MOTION + "As it rises the sunlight "
     "brightens and spreads across the frame and the dry hanging foliage stirs at the edge. The "
     "room stays completely empty of people for the whole eight seconds — no person, no figure "
     "and no hand appears at any edge of the frame at any moment. The sign stays still and "
     "unchanged: the lettering and the sprig painted on its face do not move, warp or alter. "
     + HOLD +
     "ambient: wind against glass dropping away to silence." + AUDIO_TAIL),
]


def check() -> None:
    """Run the standard's checklist over the prompt table before anything is spent.

    Every assertion is a failure this series has already paid for once.
    """
    for name, frame, _, _, _ in SHOTS:
        assert (FRAMES / frame).is_file(), f"{name}: opening frame {frame} is missing"

    # Flow only offers these four lengths. Naming any other fails in the UI after
    # the tab has already been driven, which wastes the run but not the credit.
    for name, _, seconds, _, _ in SHOTS:
        assert seconds in {"4", "6", "8", "10"}, f"{name}: Flow does not offer {seconds}s"

    total = sum(int(seconds) for _, _, seconds, _, _ in SHOTS)
    assert total == 60, f"shot list adds up to {total}s, not the 60s the .srt is cut to"

    # A frame used twice with the same camera move is a repeat on screen. The
    # reuse is only defensible because the moves diverge inside two seconds.
    moves: dict[str, set[str]] = {}
    for name, frame, _, move, _ in SHOTS:
        assert move not in moves.get(frame, set()), \
            f"{name}: reuses {frame} with a move already used on it — that reads as a repeat"
        moves.setdefault(frame, set()).add(move)

    for name, _, _, _, prompt in SHOTS:
        for phrase in ("the patch", "the spot", "that area"):
            assert phrase not in prompt.lower(), \
                f"{name}: '{phrase}' points at something the model has never seen"
        assert "ambient:" in prompt, f"{name}: no ambient line — Veo invents muttering without one"
        assert "no dialogue" in prompt, f"{name}: does not suppress dialogue"

        # Ngày 9 spent eight shots insisting the bed was empty and this episode is
        # written by copying it. A denial surviving the copy would sit beside HOLD's
        # "exactly one tiny seedling" and ask for one sprout and no sprouts at once.
        for phrase in ("no sprout", "no seedling", "nothing is growing",
                       "the bed is bare", "no green shoot"):
            assert phrase not in prompt.lower(), \
                f"{name}: '{phrase}' is Ngày 9's denial — this episode has a sprout"

    # Measured against the reference the user supplied: nothing in it sits still,
    # and the three shots that came back dead here all opened with "locked-off".
    for name, _, _, move, prompt in SHOTS:
        assert MOTION in prompt, f"{name}: no MOTION block — this series has no still shots"
        for text in (move, prompt):
            assert "locked-off" not in text.lower(),                 f"{name}: 'locked-off' is retired — it produced 0.50 and 1.20 mean motion"

    # HOLD is what replaces the image-prompt blocks. Shot 5 is the sole exemption:
    # it leaves the room on purpose, so restating that the room is unchanged would
    # be the self-contradiction the standard warns about.
    for name, _, _, _, prompt in SHOTS:
        if name != "05_duoi_long_dat":
            assert HOLD in prompt, f"{name}: no HOLD block — nothing pins the room across the clip"

    # The six artworks the user supplied, by name. A frame outside this set is a
    # picture drawn by something else, and mixing hands is the one thing a
    # supplied-frame episode is supposed to make impossible.
    supplied = {"a_chay_vao.jpg", "b_chau_bien.jpg", "c_macro_choi.jpg",
                "d_ngoi_canh.jpg", "e_cam_ruy_bang.jpg", "f_chap_tay.jpg"}
    used = {frame for _, frame, _, _, _ in SHOTS}
    assert used <= supplied,         f"not a supplied artwork: {sorted(used - supplied)} — only the six may open a shot"
    assert used == supplied, f"supplied but unused: {sorted(supplied - used)}"

    print(f"check ok — {len(SHOTS)} clips, {total}s, {len(used)} supplied frames, no image generation")


def run_videos() -> int:
    from tools.video.flow_video import FlowVideo

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
        results.append(row)

    # Merge rather than overwrite. This script resumes by skipping finished
    # clips, so a rerun that fixes one failure used to replace the whole file
    # with that single row — and the credit spend for the other seven, which is
    # the only record of what a Flow episode actually costs, was gone.
    ledger = Path("ngay8_videos_result.json")
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
