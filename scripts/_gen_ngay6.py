"""Seven clips for 'Dưới tán hoa — Ngày 6: Bông hoa đầu tiên', anime, 9:16, 64s.

    python scripts/_gen_ngay6.py check      # the standard's checklist, spends nothing
    python scripts/_gen_ngay6.py videos     # resumes: only missing clips are made

No images are generated. The seven opening frames are the user's artworks, one
per beat, so STYLE, CAST and STAGE cannot drift between shots — the frames carry
them. What still has to be said in words is everything that must stay put while
the camera moves, because Flow regenerates from the frame instead of playing it.

Three problems here that the earlier episodes did not have.

**The headcount changes shot to shot.** Ngày 7 could state "exactly two people"
once and reuse it. Here it is one woman for five shots, two for the sixth, and
one again — a different one — for the last. A single shared block would license
a second figure into the greenhouse, which is the exact failure Ngày 8 recorded:
an empty room grew a woman at 1.5s. So `HEADCOUNT` is written per shot and
`check()` refuses a shot that does not carry one.

**Three separate pieces of Vietnamese handwriting.** The bench sign, the
visitor's note in shot 4, and the card in shot 7 — and the note and the card are
the whole point of their scenes, so the old trick of describing a blank surface
and stamping text afterwards cannot apply. Ngày 8 established what actually
preserves lettering, and it was not locking the camera: the sentence "the
lettering does not move, warp or alter" is what does the work. Each shot names
the words it must keep, verbatim.

**The story leaves the greenhouse.** Shots 6 and 7 are a public park, so `STAGE`
is per shot rather than global, and the two locations never borrow each other's
furniture.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PROJECT = Path("projects/duoi-tan-hoa-ngay-6")
FRAMES = PROJECT / "assets" / "frames"
VIDEO = PROJECT / "assets" / "video"

PROJECT_URL = "https://flow.google.com/project/1bf5b712-b98d-4c38-a7d3-ffbd4aa377b2"
LOCK = Path.home() / ".openmontage" / "flow_video.lock"

STYLE = ("Soft anime illustration in the style of a painted storybook: warm sunlit palette, "
         "clean linework, gentle watercolour shading, no photorealism and no 3D render. ")

# Both women, always described together, and always saying which is which in the
# same breath as what she is wearing. Ngày 7 proved that with two figures the
# failure is not drift in one costume, it is the pair swapping attributes.
CAST = ("THE GARDENER is a young woman with very long dark brown wavy hair falling past her waist, "
        "a cream ribbon bow tied at the side of her head, and a long ivory-cream cotton dress with "
        "puffed sleeves and deep white lace cuffs. THE WOMAN ON THE BENCH is older, around forty, "
        "with dark hair pinned in a low loose bun and no ribbon, and wears a sage-green button "
        "shirt with the sleeves rolled to the elbow and a long cream linen skirt. The gardener is "
        "never in green and the woman on the bench is never in cream lace, and they never exchange "
        "hair, clothes or hair ornaments. ")

GREENHOUSE = ("A weathered wooden potting bench inside a white-framed glasshouse, with a speckled "
              "terracotta pot of dark crumbled soil, a small wooden sign on a stake beside it, a "
              "floral cloth runner, dry golden foliage hanging from the frames, and through the "
              "tall window a summer garden with a rose-covered iron arch and a pale stone house "
              "under a blue sky. ")

PARK = ("A public park on a bright summer afternoon: a dark iron-and-wood bench under a broad "
        "leafy tree, a black lamp post, a paved path of pale stone slabs, flowering shrubs and "
        "more benches further off under green trees. ")

MOTION = ("The camera moves slowly and continuously for the entire shot at one constant speed, "
          "with no stop, no acceleration and no cut anywhere in the clip. The movement is small: "
          "the framing at the end is only a little different from the framing at the start. ")

SIGN = ("The small wooden sign keeps its handwritten Vietnamese words “Dưới Tán Hoa” exactly as "
        "written; the lettering does not move, warp or alter. ")

HOLD = ("Nothing in the setting changes: every object stays exactly as it is and in the same "
        "place, and nothing is added — no new plant, no extra pot, no vase, no furniture, no "
        "ornament and no object of any kind appears or grows into the frame, and the background "
        "never dissolves, fades out or changes into another place. ")

FLOWER = ("There is exactly one pale pink flower with a golden centre, and it stays one flower of "
          "the same size and colour: no second bloom and no new bud appears anywhere. ")

MEDIUM_TAIL = "The whole shot stays a soft painted anime illustration, never a photograph. "

AUDIO_TAIL = ("ambient: still warm air, faint birdsong, the rustle of paper or leaves close by. "
              "no dialogue, no music, no voices.")

ONE_GARDENER = ("There is exactly one person anywhere in the shot — the gardener — and no one "
                "else appears at any moment: no second person, no child, no passer-by walks into "
                "frame or stands in the garden beyond the glass. ")
TWO_IN_PARK = ("There are exactly two people anywhere in the shot — the gardener and the woman on "
               "the bench — and no one else appears at any moment: nobody walks along the path, "
               "sits on the further benches or passes behind the tree. ")
ONE_ON_BENCH = ("There is exactly one person anywhere in the shot — the woman on the bench — and "
                "no one else appears at any moment; the gardener has gone and does not come back "
                "into frame. ")
NOBODY = ("There are no people anywhere in the shot at any moment: no person, no hand, no arm, no "
          "face and no figure appears in the glasshouse or in the garden beyond the glass, and "
          "nobody walks into frame at any point. ")

# (name, frame, seconds, headcount, stage, action)
SHOTS = [
    ("01_hoa_no", "a_hoa_no.jpg", "8", NOBODY, GREENHOUSE,
     "The camera drifts slowly in toward the flower. The single pale pink flower is already fully "
     "open on its tall stem, and over the shot its petals ease open a little wider and settle, "
     "while the clear dew beaded on the petals and along the serrated leaf edges catches the light "
     "and one drop slides slowly to the tip of a leaf. Nobody touches the plant. " + SIGN),

    ("02_ngam_hoa", "b_ngam_hoa.jpg", "10", ONE_GARDENER, GREENHOUSE,
     "The camera drifts slowly in past the gardener toward the flower. She stays where she is with "
     "her chin resting on both hands, watching the flower, and only breathes and blinks; she does "
     "not stand up, reach out or turn away. Sunlight moves slowly across the petals so that they "
     "glow from behind, and the shadows of the leaves shift a little on the bench. " + SIGN),

    ("03_dinh_hai", "c_dinh_hai.jpg", "8", ONE_GARDENER, GREENHOUSE,
     "The camera holds close on the gardener's hand and the flower and drifts in very slightly. "
     "Her hand reaches toward the bloom, the fingers almost touching a petal — and then stops, "
     "hesitates, and draws slowly back without picking the flower or breaking the stem. The flower "
     "stays whole and on its stem for the entire shot. " + SIGN),

    ("04_manh_giay", "d_manh_giay.jpg", "8", ONE_GARDENER, GREENHOUSE,
     "The camera drifts slowly down and in toward the sheet of paper lying on the bench. The "
     "gardener leans over it and reads, her eyes moving across the lines; her hand rests beside "
     "the paper and does not lift it or turn it over. The handwritten Vietnamese words on the "
     "paper read “Nếu một ngày nơi này có hoa, hãy dành một bông cho người đang buồn.” and they stay "
     "exactly as written for the whole shot; the lettering does not move, warp or alter. " + SIGN),

    ("05_goi_hoa", "e_goi_hoa.jpg", "10", ONE_GARDENER, GREENHOUSE,
     "The camera drifts slowly in on the gardener's hands. She finishes wrapping the single pink "
     "flower in cream paper and draws the dusty-pink ribbon into a small bow, her fingers pulling "
     "the loops gently tight. The paper creases and settles as she works. She stays leaning over "
     "the bench and does not stand up or lift the bouquet away. " + SIGN),

    ("06_dat_hoa", "f_dat_hoa.jpg", "10", TWO_IN_PARK, PARK,
     "The camera drifts slowly in toward the bench. The gardener leans over the back of the bench "
     "and sets the wrapped bouquet down on the seat beside the older woman, lets go, and "
     "straightens up to leave. The woman keeps her face buried in both hands and her shoulders "
     "shake softly; she does not look up, does not see the gardener and does not speak. "),

    ("07_cam_thiep", "g_cam_thiep.jpg", "10", ONE_ON_BENCH, PARK,
     # Reworded after Flow refused the original twice with "Chúng tôi nhận thấy
     # có hoạt động bất thường" — its automation warning, not a content notice.
     # It fired on this one prompt out of seven and on a run that made a single
     # call, which is not how an account-level block behaves; the only thing this
     # shot described that no other did was a woman crying. The beat is the same
     # without naming the tears: she has been crying, and the shot is her reading
     # the card and softening.
     "The camera holds close and drifts in very slightly. The woman is holding the wrapped bouquet "
     "against her lap in one hand and the small card in the other, reading it; she reads to the end "
     "and a small quiet smile comes to her face. The handwritten Vietnamese words on "
     "the card read “Đừng khóc nhé, hoa đẹp và bạn cũng vậy.” and they stay exactly as written for "
     "the whole shot; the lettering does not move, warp or alter. "),
]

DURATIONS = {"4", "6", "8", "10"}
TARGET_SECONDS = 64


def prompt_for(shot) -> str:
    """Assemble one shot's prompt.

    `CAST` is left out of a shot with nobody in it. Carrying it there is not
    merely redundant — the first cut of shot 1 opened on an artwork with no
    person in it, said "exactly one person, the gardener", and described her in
    full, and Veo duly grew her into the frame: absent at 0s, a ghost at 1s,
    standing behind the pot from 1.5s on. It is the same failure this project
    already recorded once, in Ngày 8's empty room.
    """
    _, _, _, headcount, stage, action = shot
    cast = "" if headcount is NOBODY else CAST
    return (STYLE + stage + cast + action + FLOWER + HOLD + headcount
            + MOTION + MEDIUM_TAIL + AUDIO_TAIL)


def check() -> None:
    supplied = {p.name for p in FRAMES.glob("*.jpg")}
    used = {frame for _, frame, _, _, _, _ in SHOTS}
    assert used <= supplied, f"frames not supplied: {sorted(used - supplied)}"
    assert len(used) == len(SHOTS), "each shot must open on its own artwork"

    total = sum(int(s) for _, _, s, _, _, _ in SHOTS)
    assert total == TARGET_SECONDS, f"clips total {total}s, expected {TARGET_SECONDS}s"
    for name, _, seconds, _, _, _ in SHOTS:
        assert seconds in DURATIONS, f"{name}: Flow does not offer {seconds}s"

    heads = (ONE_GARDENER, TWO_IN_PARK, ONE_ON_BENCH, NOBODY)
    for shot in SHOTS:
        name, _, _, headcount, stage, _ = shot
        text = prompt_for(shot)
        assert headcount in heads, f"{name}: headcount is not one of the three written blocks"
        # Per shot, never shared: the cast changes twice in this episode and a
        # blanket "two people" would put a stranger in the greenhouse.
        assert headcount in text, f"{name}: missing HEADCOUNT"
        for block, label in ((MOTION, "MOTION"), (HOLD, "HOLD"), (FLOWER, "FLOWER")):
            assert block in text, f"{name}: missing {label}"
        # A shot with people must name them; a shot with none must not, or the
        # description alone conjures one.
        assert (CAST in text) == (headcount is not NOBODY),             f"{name}: CAST must appear if and only if someone is in the shot"
        assert "ambient:" in text and "no dialogue" in text, f"{name}: missing the audio tail"
        assert "locked-off" not in text, f"{name}: 'locked-off' is retired from this series"
        assert (GREENHOUSE in text) != (PARK in text), f"{name}: must be in exactly one location"

    # Every piece of handwriting is quoted, and every shot that shows one says
    # the sentence that keeps it intact.
    quoted = {
        "01_hoa_no": "Dưới Tán Hoa", "02_ngam_hoa": "Dưới Tán Hoa",
        "03_dinh_hai": "Dưới Tán Hoa", "05_goi_hoa": "Dưới Tán Hoa",
        "04_manh_giay": "hãy dành một bông cho người đang buồn",
        "07_cam_thiep": "hoa đẹp và bạn cũng vậy",
    }
    for shot in SHOTS:
        name = shot[0]
        text = prompt_for(shot)
        if name in quoted:
            assert quoted[name] in text, f"{name}: the handwriting is not quoted"
            assert "does not move, warp or alter" in text, \
                f"{name}: handwriting shown but not pinned"

    # The flower is picked in no shot: shot 3 is the hand stopping, and by shot 5
    # it is already wrapped in the artwork. A prompt that lets it be plucked
    # would contradict the frame it opens on.
    for shot in SHOTS:
        assert "picks the flower" not in prompt_for(shot), f"{shot[0]}: the flower is never picked"

    print(f"check ok — {len(SHOTS)} clips, {total}s, {len(used)} supplied frames, "
          f"no image generation")


def run_videos() -> int:
    from tools.video.flow_video import FlowVideo

    os.environ.setdefault("FLOW_PROJECT_URL", PROJECT_URL)
    LOCK.unlink(missing_ok=True)
    VIDEO.mkdir(parents=True, exist_ok=True)
    tool, results = FlowVideo(), []

    for name, frame, seconds, _, _, _ in SHOTS:
        out = VIDEO / f"{name}.mp4"
        if out.is_file() and out.stat().st_size > 200_000:
            print(f"skip {name}", flush=True)
            continue

        began = time.time()
        result = tool.execute({
            "prompt": prompt_for((name, frame, seconds, *_shot_tail(name))),
            "operation": "image_to_video",
            "reference_image_path": str(FRAMES / frame),
            "model_variant": "Omni",
            "duration": seconds,
            "aspect_ratio": "9:16",
            "resolution": "720p",
            "output_path": str(out),
            "timeout_seconds": 900,
        })
        took = round(time.time() - began, 1)

        row = {"name": name, "frame": frame, "ok": result.success, "seconds": took}
        if result.success:
            row["credits"] = result.data.get("flow_credits")
            row["duration"] = result.data.get("duration_seconds")
        else:
            row["error"] = result.error
            # The tool writes the file before it checks the duration, and this
            # script resumes by skipping any output that exists — so a rejected
            # clip would be skipped forever and shipped as if it had passed.
            out.unlink(missing_ok=True)
        results.append(row)
        print(f"{name}: {'ok' if result.success else 'FAILED'} ({took}s)", flush=True)
        if not result.success:
            print(f"   {result.error}", flush=True)

    ledger = PROJECT / "ngay6_videos_result.json"
    previous = json.loads(ledger.read_text(encoding="utf-8")) if ledger.is_file() else []
    merged = {row["name"]: row for row in previous}
    merged.update({row["name"]: row for row in results})
    ledger.write_text(json.dumps([merged[k] for k in sorted(merged)], indent=1,
                                 ensure_ascii=False), encoding="utf-8")

    failed = [row["name"] for row in results if not row["ok"]]
    print(f"\ndone: {len(results) - len(failed)}/{len(results)}")
    if failed:
        print("failed:", ", ".join(failed))
    return 1 if failed else 0


def _shot_tail(name: str):
    for shot in SHOTS:
        if shot[0] == name:
            return shot[3], shot[4], shot[5]
    raise KeyError(name)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "check"
    check()
    raise SystemExit(0 if command == "check" else run_videos())
