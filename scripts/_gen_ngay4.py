"""Six clips for 'Dưới tán hoa — Ngày 4: Khu vườn bắt đầu có màu sắc', anime, 9:16, 50s.

    python scripts/_gen_ngay4.py check      # the standard's checklist, spends nothing
    python scripts/_gen_ngay4.py videos     # resumes: only missing clips are made

No images are generated. The six opening frames are the user's artworks, one per
beat (CẢNH 1-6 of the script), so STYLE, CAST and the glasshouse cannot drift —
the frames carry them. Follows the same discipline as
`.agents/skills/flow-video/references/shot-sequence-prompts.md`: STYLE / CAST /
GREENHOUSE pasted verbatim, STAGE per shot (terrain, camera, feet), one action
per clip, absences stated positively.

**The seventh frame is not generated.** The script's closing beat (CẢNH CUỐI,
51-60s) is a comment-bait CTA: title banner "BẠN SẼ CHỌN MÀU NÀO?" and four
colour-option chips (HỒNG / ĐỎ / KEM / TÍM) baked into the image. Flow's Veo
regenerates the whole frame from a text+image prompt, and dense Vietnamese UI
text is exactly what the series' style-lock notes warp under regeneration
(`.agents/skills/flow-video/SKILL.md`, continuity table). There is also nothing
for a camera move to do on a finished end card — the series' own measured
range treats a text-bearing card as near-static (mean 0.5, see
`references/shot-sequence-prompts.md` §7). The frame is kept at
`assets/frames/g_loi_moi_END_CARD_do_not_generate.jpg` and goes straight into
the compose stage as a held static image for the last ~10s, not through Flow.

Six clips at Flow's nearest offered durations sum to 50s (script called for
51s across the same six beats — 11s is not one of Flow's four duration
options, so shot 6 rounds down to 10s). Compose then holds the CTA frame for
the remaining ~10s to land close to the scripted 60s runtime.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Windows' console defaults to cp1252, which can't encode Vietnamese text
# (e.g. "giây", "ỳ") — a plain print() of an error message containing it
# crashes the whole run instead of just garbling one line. Confirmed
# 2026-09-10: killed the script mid-batch on a fully-succeeded shot's own
# summary print, with nothing wrong with the shot itself.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path("projects/duoi-tan-hoa-ngay-4")
FRAMES = PROJECT / "assets" / "frames"
VIDEO = PROJECT / "assets" / "video"

# Pinned rather than left to "whichever Flow tab is open": without this, the
# driver picks any project tab it finds, and one stray navigation (a stuck
# hover state, a "Trang chủ" click, anything) can land it on a *different*
# project — which also silently drops the `?hl=vi` locale, switching Flow's
# whole UI to English under selectors this driver writes in Vietnamese.
# Confirmed 2026-09-10: exactly this happened mid-session.
PROJECT_URL = "https://flow.google.com/project/0ebed0ec-2661-4413-851f-9fa34078c90f?hl=vi"
LOCK = Path.home() / ".openmontage" / "flow_video.lock"

STYLE = ("Detailed anime-style digital illustration, softly painterly with delicate "
         "linework and warm cinematic sunlight; glossy, semi-realistic rendering, not "
         "flat cel-shaded and not a photograph, no 3D render. ")

# One character in every shot (or her hand alone in shot 2) — no second person is ever
# introduced, so there is no headcount block to switch per shot the way Ngày 6 needed.
CAST = ("THE FLORIST is a young woman with very long dark brown wavy hair falling past "
        "her waist, a cream satin ribbon bow tied at the side of her head, and a long "
        "ivory-cream dress with a tied waist sash, puffed sleeves and wide lace cuffs. "
        "No other person is anywhere in the shot. ")

HAND_ONLY = ("Only THE FLORIST's hand and forearm are in shot, entering from the left "
             "edge of frame, wearing the ivory-cream lace sleeve cuff of her dress; no "
             "face, no other body part and no other person is visible anywhere. ")

# Shared architecture, pasted verbatim into every prompt — this is what makes six
# independently-generated shots read as one glasshouse and not six different rooms.
GREENHOUSE = ("Inside the old glasshouse of flower shop “Dưới Tán "
              "Hoa”: tall white wood-framed glass walls and a peaked glass roof, "
              "climbing white star-shaped jasmine flowers and green vines twining up "
              "the white frames, a black iron hanging lantern near the roof peak, and "
              "through the glass a clear blue sky with a few white clouds and dark "
              "green pine trees in the distance. The floor is pale worn stone paving. ")

MOTION = ("The camera moves slowly and continuously for the entire shot at one constant "
          "speed, with no stop, no acceleration and no cut anywhere in the clip. The "
          "movement is small: the framing at the end is only a little different from "
          "the framing at the start. ")

SIGN = ("The small wooden sign keeps its handwritten Vietnamese words “Dưới "
        "Tán Hoa” exactly as written; the lettering does not move, warp or "
        "alter. ")

MEDIUM_TAIL = "The whole shot stays a detailed anime illustration, never a photograph. "

AUDIO_TAIL = ("ambient: still warm greenhouse air, faint birdsong, a soft rustle of "
              "leaves and fabric. no dialogue, no music, no voices.")

# (name, frame, seconds, stage, action)
SHOTS = [
    ("01_thuc_giac", "a_thuc_giac.jpg", "8",
     GREENHOUSE +
     "A stone-paved aisle runs down the middle of the glasshouse: to the left a wooden "
     "shelving unit crowded with potted pink roses and a wooden ladder leaning against "
     "it; to the right a long wooden table holding stacked books, a galvanized watering "
     "can, terracotta pots, a wooden lavender crate and the small wooden sign; ahead, "
     "open white-framed glass double doors lead further into the glasshouse and garden "
     "beyond. The camera is behind THE FLORIST at chest height, looking past her down "
     "the aisle toward the open doors. Both her feet stay on the pale stone paving. ",
     CAST +
     "She walks a few slow steps down the aisle and eases to a stop near the middle of "
     "the frame, her shoulders settling. Sunlight through the glass roof shifts gently "
     "across the stone floor and the flowers stir a little in a light breeze. That is "
     "the only action — she does not run, does not turn around and does not step off "
     "the paved aisle. The shelving, the ladder, the table and its sign, and the open "
     "doors ahead all stay exactly as they are in the opening frame, and no new "
     "furniture, pot or person appears anywhere. " + SIGN + MEDIUM_TAIL + AUDIO_TAIL),

    ("02_be_hong", "b_be_hong.jpg", "8",
     GREENHOUSE +
     "In the foreground, a terracotta pot of pink garden roses beaded with dew stands "
     "on a low wooden bench; behind it, out of focus, purple and white flowers, a "
     "small wooden crate carrying the sign, and a galvanized watering can. The camera "
     "holds close on the roses and THE FLORIST's hand. ",
     HAND_ONLY +
     "Her hand drifts slowly toward one open pink rose, fingertips coming to rest "
     "just beside a petal without picking it or breaking the stem. A single drop of "
     "dew slides slowly down one petal. That is the only action — the hand does not "
     "grip the stem and does not pull the flower toward camera. The rose bush, the "
     "pot, the bench and the blurred sign and watering can behind all stay exactly as "
     "they are in the opening frame, and no second flower or hand ever appears. "
     + SIGN + MEDIUM_TAIL + AUDIO_TAIL),

    ("03_be_do", "c_be_do.jpg", "8",
     GREENHOUSE +
     "A cluster of deep red garden roses grows from a terracotta pot on a weathered "
     "wooden bench, loose red petals scattered across the bench top, the small wooden "
     "sign visible on a crate just behind the roses, lavender softly out of focus at "
     "the lower right. The camera frames THE FLORIST in profile from the waist up, "
     "standing beside the rose bush. Both her feet stay on the stone floor; she does "
     "not step onto the bench or the pot. ",
     CAST +
     # Reworded 2026-09-10 after 5+ identical-text attempts on this one shot
     # all failed at the download step while every other shot succeeded —
     # the same pattern Ngày 7 traced to Flow's automation warning firing on
     # repeated byte-identical prompts, not a driver bug. Same beat, new words.
     "Her hand lifts slowly toward a red rose, fingertips coming to rest just short "
     "of a petal, her eyes staying fixed on the bloom. That is the only action — she "
     "never plucks the flower and never looks away. The rose bush, the scattered "
     "petals, the bench, the sign and the lavender behind stay exactly as they are "
     "in the opening frame, with no bloom appearing or disappearing. "
     + SIGN + MEDIUM_TAIL + AUDIO_TAIL),

    ("04_be_kem", "d_be_kem.jpg", "8",
     GREENHOUSE +
     "THE FLORIST sits on a low wooden chair at a rustic wooden table beside the tall "
     "window. On the table stands a white ceramic pitcher of white roses and small "
     "white star flowers, the small wooden sign propped beside it, a floral-patterned "
     "saucer and a short stack of small wooden boxes; a sheer white curtain hangs at "
     "the window's edge. The camera holds close at table height, side-on, framing her "
     "from the shoulders up. She stays seated on the chair for the whole shot. ",
     CAST +
     # Reworded alongside 03_be_do — this shot hit the same repeated-attempt
     # download stall, so the same mitigation applies pre-emptively.
     "She raises the teacup in both hands to her lips and takes a slow, quiet sip, "
     "her gaze resting on the garden beyond the glass. That is the only action — the "
     "cup never leaves her hands and she never rises from the chair. The pitcher of "
     "roses, the sign, the saucer, the boxes and the curtain stay exactly as they are "
     "in the opening frame, with nothing new added to the table. "
     + SIGN + MEDIUM_TAIL + AUDIO_TAIL),

    ("05_be_tim", "e_be_tim.jpg", "8",
     GREENHOUSE +
     "Rows of potted purple lavender spikes, pale lilac campanula blooms and a blush "
     "hydrangea head stand on a low wooden bench, loose petals drifting in the air. "
     "The camera frames THE FLORIST from the front, medium-close, as she bends forward "
     "at the waist over the lavender. Both her feet stay on the stone floor; she does "
     "not climb onto the bench. ",
     CAST +
     # Reworded alongside 03_be_do / 04_be_kem for the same reason.
     "She dips her head toward the lavender and draws in its scent, her eyes drifting "
     "shut, while loose petals sail slowly past her on the air. That is the only "
     "action — she never reaches out to pick a stem and never straightens back up. "
     "The lavender, the campanula, the hydrangea and the bench stay exactly as they "
     "are in the opening frame, with no new bloom appearing. "
     + MEDIUM_TAIL + AUDIO_TAIL),

    ("06_ban_bo", "f_ban_bo.jpg", "10",
     GREENHOUSE +
     "THE FLORIST stands behind a long wooden table on which four finished bouquets "
     "stand side by side, wrapped in cream paper: from camera-left to camera-right, "
     "pink roses tied with a pink ribbon, deep red roses tied with a dark maroon "
     "ribbon, white roses and daisies tied with a champagne ribbon, and purple "
     "lavender and roses tied with a lilac ribbon. The small wooden sign sits centred "
     "on the table in front of the bouquets. The camera frames her from the waist up, "
     "front-on at table height. She stands behind the table for the whole shot; she "
     "does not walk around it or pick up a bouquet. ",
     CAST +
     # Reworded alongside the shots above for the same reason.
     "Her eyes travel slowly across the four bouquets, from the pink one on the left "
     "to the purple one on the right, as though weighing which belongs to whom. That "
     "is the only action — her hands stay resting on the table edge and she never "
     "lifts or touches a bouquet. All four bouquets, their ribbons, the sign and the "
     "shelving behind stay exactly as they are in the opening frame, with no fifth "
     "bouquet or new object ever appearing. "
     + SIGN + MEDIUM_TAIL + AUDIO_TAIL),
]

DURATIONS = {"4", "6", "8", "10"}
TARGET_SECONDS = 50


def prompt_for(shot) -> str:
    """Assemble one shot's video prompt exactly as sent to Flow."""
    _, _, _, stage, action = shot
    return MOTION + stage + action


def check() -> None:
    supplied = {p.name for p in FRAMES.glob("*.jpg") if "END_CARD" not in p.name}
    used = {frame for _, frame, _, _, _ in SHOTS}
    assert used <= supplied, f"frames not supplied: {sorted(used - supplied)}"
    assert len(used) == len(SHOTS), "each shot must open on its own artwork"

    end_card = FRAMES / "g_loi_moi_END_CARD_do_not_generate.jpg"
    assert end_card.is_file(), "the CTA end-card frame is missing from assets/frames"

    total = sum(int(s) for _, _, s, _, _ in SHOTS)
    assert total == TARGET_SECONDS, f"clips total {total}s, expected {TARGET_SECONDS}s"
    for name, _, seconds, _, _ in SHOTS:
        assert seconds in DURATIONS, f"{name}: Flow does not offer {seconds}s"

    for shot in SHOTS:
        name = shot[0]
        text = prompt_for(shot)
        assert GREENHOUSE in text, f"{name}: missing GREENHOUSE"
        assert MOTION in text, f"{name}: missing MOTION — it will come back locked-off"
        for phrase in ("the patch", "the spot", "that area"):
            assert phrase not in text.lower(), f"{name}: '{phrase}' points at nothing"
        assert "ambient:" in text and "no dialogue" in text, f"{name}: missing audio tail"
        assert "locked-off" not in text, f"{name}: 'locked-off' is retired from this series"
        # Every shot has exactly one of the two cast blocks, never both, never neither.
        assert (CAST in text) != (HAND_ONLY in text), f"{name}: expected exactly one of CAST/HAND_ONLY"
        assert "only action" in text, f"{name}: doesn't pin a single beat"

    print(f"check ok — {len(SHOTS)} clips, {total}s, {len(used)} supplied frames, "
          f"no image generation, end card held separately")


def run_videos() -> int:
    from tools.video.flow_video import FlowVideo

    os.environ.setdefault("FLOW_PROJECT_URL", PROJECT_URL)
    LOCK.unlink(missing_ok=True)
    VIDEO.mkdir(parents=True, exist_ok=True)
    tool, results = FlowVideo(), []

    for name, frame, seconds, stage, action in SHOTS:
        out = VIDEO / f"{name}.mp4"
        if out.is_file() and out.stat().st_size > 200_000:
            print(f"skip {name}", flush=True)
            continue

        began = time.time()
        result = tool.execute({
            "prompt": MOTION + stage + action,
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
            out.unlink(missing_ok=True)
        results.append(row)
        print(f"{name}: {'ok' if result.success else 'FAILED'} ({took}s)", flush=True)
        if not result.success:
            print(f"   {result.error}", flush=True)

    ledger = PROJECT / "ngay4_videos_result.json"
    previous = json.loads(ledger.read_text(encoding="utf-8")) if ledger.is_file() else []
    merged = {row["name"]: row for row in previous}
    merged.update({row["name"]: row for row in results})
    ledger.write_text(json.dumps([merged[k] for k in sorted(merged)], indent=1,
                                 ensure_ascii=False), encoding="utf-8")

    failed = [row["name"] for row in results if not row["ok"]]
    spent = sum(r.get("credits") or 0 for r in merged.values())
    print(f"\ndone: {len(results) - len(failed)}/{len(results)} clips this run, "
          f"{spent} credits total")
    if failed:
        print("failed:", ", ".join(failed))
    print(f"\nNext: python scripts/clip_motion.py {VIDEO} --cuts")
    print(f"      python scripts/flow_continuity_check.py {VIDEO}")
    return 1 if failed else 0


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "check"
    check()
    raise SystemExit(0 if command == "check" else run_videos())
