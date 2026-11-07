"""Nine clips for 'Dưới tán hoa — Ngày 3: Những lời chưa kịp nói', anime, 9:16, 58s.

    python scripts/_gen_ngay3.py check      # the standard's checklist, spends nothing
    python scripts/_gen_ngay3.py videos     # resumes: only missing clips are made

No images are generated. The nine opening frames are the user's artworks, one
per beat of the script, so STYLE, CAST and the greenhouse cannot drift — the
frames carry them. Follows
`.agents/skills/flow-video/references/shot-sequence-prompts.md` and, for the
one shot with two hands finishing a bouquet, `skills/styles/florist-bouquet-craft.md`.

**The four cards carry real handwritten text in the supplied artwork**, even
though the script's own note says to leave cards blank and caption them in
CapCut — the artist already rendered the message onto the card, so the job
here is to keep Flow from warping it during regeneration, not to withhold it.
Follows the series' proven fix for this (Ngày 6/8's wooden sign): quote the
exact text and say the lettering does not move, warp or alter.

Durations are rounded to what Flow's Omni model actually offers (4/6/8/10s).
The script's own beats are 7/3/3/3/4/11/12/11/6 = 60s; the four short card
inserts (3s, 3s, 3s, 4s) are below Flow's 4s floor and round up to 4s each,
landing the shot list at 58s total.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Windows' console defaults to cp1252, which can't encode Vietnamese text.
# See scripts/_gen_ngay4.py — confirmed 2026-09-10 it can crash mid-batch.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path("projects/duoi-tan-hoa-ngay-3")
FRAMES = PROJECT / "assets" / "frames"
VIDEO = PROJECT / "assets" / "video"

# Same project as Ngày 4 — reused rather than created fresh. The grid-clutter
# problems that day traced to caption collisions and a download-path bug, both
# fixed in lib/flow_driver.py now (position-based tile lookup, role-based
# download selectors), so a shared project no longer needs to be avoided.
PROJECT_URL = "https://flow.google.com/project/0ebed0ec-2661-4413-851f-9fa34078c90f?hl=vi"
LOCK = Path.home() / ".openmontage" / "flow_video.lock"

STYLE = ("Detailed anime-style digital illustration, softly painterly with delicate "
         "linework and warm cinematic sunlight; glossy, semi-realistic rendering, not "
         "flat cel-shaded and not a photograph, no 3D render. ")

CAST = ("THE FLORIST is a young woman with very long dark brown wavy hair falling past "
        "her waist, a cream satin ribbon bow tied at the side of her head, and a long "
        "ivory-cream dress with a tied waist sash, puffed sleeves and wide lace cuffs. "
        "No other person is anywhere in the shot. ")

HAND_ONLY = ("Only THE FLORIST's hand and forearm are in shot, entering from the bottom "
             "edge of frame, wearing the ivory-cream lace sleeve cuff of her dress; no "
             "face, no other body part and no other person is visible anywhere. ")

# The wooden card-trellis is this episode's version of Ngày 4's glasshouse
# architecture block — pasted verbatim into every shot that is under it.
TRELLIS = ("A rough wooden trellis crosses the glasshouse ceiling, twined with green "
           "vines and small white star-shaped jasmine flowers, and small rectangular "
           "cream cardstock tags hang from it on thin ribbons and cords, swaying gently "
           "in the air. Beyond the glass roof and walls, a clear blue sky with a few "
           "white clouds and dark green pine trees in the distance. ")

MOTION = ("The camera moves slowly and continuously for the entire shot at one constant "
          "speed, with no stop, no acceleration and no cut anywhere in the clip. The "
          "movement is small: the framing at the end is only a little different from "
          "the framing at the start. ")

# The florist-bouquet-craft rule (skills/styles/florist-bouquet-craft.md §2): two
# hands are only free to work because something else is carrying the bouquet's weight.
BOUQUET_SUPPORT = ("The bouquet stands upright on the table, its wrapped base resting on "
                   "the surface and taking its own weight. It is never held up in "
                   "mid-air and never floats: while both hands tie the ribbon, the table "
                   "is what holds the bouquet. ")

MEDIUM_TAIL = "The whole shot stays a detailed anime illustration, never a photograph. "

AUDIO_TAIL = ("ambient: still warm greenhouse air, faint birdsong, a soft rustle of "
              "leaves, paper and fabric. no dialogue, no music, no voices.")


def lettering(text: str) -> str:
    """Quote one card's exact words and pin them against warping (Ngày 6/8's fix)."""
    return (f'The handwritten Vietnamese words on the card read “{text}” '
            f"and they stay exactly as written for the whole shot; the lettering does "
            f"not move, warp or alter. ")


# (name, frame, seconds, stage, action)
SHOTS = [
    ("01_the_treo", "a_the_treo.jpg", "6",
     TRELLIS +
     "Below the trellis, potted roses in cream, deep red and pale purple stand along "
     "a wooden shelf and a low bench to left and right, and a long wooden table sits "
     "against the glass wall on the right carrying the small wooden sign, some stacked "
     "books and a galvanized watering can. The cards hanging directly above THE "
     "FLORIST are plain cream card, no writing visible on any of them yet. The camera "
     "frames her from behind and slightly to the side, at chest height, looking up "
     "past her toward the cards. Both her feet stay on the stone floor; she does not "
     "walk. ",
     CAST +
     "She tilts her head back and reaches one hand up toward the hanging cards, "
     "fingertips almost touching the nearest one, her face lit with quiet surprise. "
     "That is the only action — she does not pull a card down and does not turn away. "
     "The trellis, the hanging cards, the potted roses, the table and the sign all "
     "stay exactly as they are in the opening frame, and no new card appears among "
     "them. " + MEDIUM_TAIL + AUDIO_TAIL),

    ("02a_xin_loi", "b_xin_loi.jpg", "4",
     TRELLIS +
     "In the foreground, one small cream card hangs from the trellis on a champagne "
     "satin ribbon tied in a bow around the wooden beam, surrounded closely by cream "
     "and white garden roses and small white jasmine blooms. The camera holds close on "
     "the card, filling most of the frame. ",
     "Sunlight shifts slowly across the card's surface and the ribbon stirs very "
     "slightly in the air. That is the only action — nothing touches the card and it "
     "does not swing or turn. The card, its ribbon and the roses around it all stay "
     "exactly as they are in the opening frame. " + lettering("Con xin lỗi mẹ.")
     + MEDIUM_TAIL + AUDIO_TAIL),

    ("02b_cam_on", "c_cam_on.jpg", "4",
     TRELLIS +
     "In the foreground, one small cream card hangs from the trellis on a dusty-pink "
     "satin ribbon tied in a bow around the wooden beam, surrounded closely by pale "
     "pink garden roses. The camera holds close on the card, filling most of the "
     "frame. ",
     "Sunlight shifts slowly across the card's surface and the ribbon stirs very "
     "slightly in the air. That is the only action — nothing touches the card and it "
     "does not swing or turn. The card, its ribbon and the roses around it all stay "
     "exactly as they are in the opening frame. " + lettering("Cảm ơn vì đã ở lại.")
     + MEDIUM_TAIL + AUDIO_TAIL),

    ("02c_nho_em", "d_nho_em.jpg", "4",
     TRELLIS +
     "In the foreground, one small cream card hangs from the trellis on a deep "
     "burgundy satin ribbon tied in a bow around the wooden beam, surrounded closely "
     "by dark red garden roses. The camera holds close on the card, filling most of "
     "the frame. ",
     "Sunlight shifts slowly across the card's surface and the ribbon stirs very "
     "slightly in the air. That is the only action — nothing touches the card and it "
     "does not swing or turn. The card, its ribbon and the roses around it all stay "
     "exactly as they are in the opening frame. " + lettering("Anh nhớ em.")
     + MEDIUM_TAIL + AUDIO_TAIL),

    ("02d_tu_hao", "e_tu_hao.jpg", "4",
     TRELLIS +
     "In the foreground, one small cream card hangs from the trellis on a pale lilac "
     "satin ribbon tied in a bow around the wooden beam, surrounded closely by purple "
     "lavender spikes and pale purple campanula blooms. The camera holds close on the "
     "card, filling most of the frame. ",
     "Sunlight shifts slowly across the card's surface and the ribbon stirs very "
     "slightly in the air. That is the only action — nothing touches the card and it "
     "does not swing or turn. The card, its ribbon and the lavender around it all "
     "stay exactly as they are in the opening frame. " + lettering("Mình tự hào về bạn.")
     + MEDIUM_TAIL + AUDIO_TAIL),

    ("03_doc_thiep", "f_doc_thiep.jpg", "10",
     "THE FLORIST sits on a low wooden chair at a rustic wooden table beside a tall "
     "window, three small cream cards lying side by side on the table in front of "
     "her — tied respectively with a dusty-pink, a deep burgundy and a pale lilac "
     "ribbon bow — with the small wooden sign, a short stack of books and a "
     "galvanized jug of lavender behind them. She holds a fourth card, tied with a "
     "champagne ribbon, up in both hands, reading it. The camera holds close at table "
     "height, side-on, framing her from the chest up. She stays seated on the chair "
     "for the whole shot. ",
     CAST +
     "She reads the card slowly, her eyes moving down the page, and her gaze softens. "
     "That is the only action — she does not set the card down and does not stand up. "
     "The three cards on the table, the sign, the books and the jug of lavender all "
     "stay exactly as they are in the opening frame, and no lettering on any card "
     "moves, warps or alters. " + MEDIUM_TAIL + AUDIO_TAIL),

    ("04_ghep_hoa", "g_ghep_hoa.jpg", "10",
     "Directly overhead, top-down, a rustic wooden table: the small wooden sign and a "
     "galvanized jug of white jasmine sit at the top of frame, a spool of ribbon and a "
     "pair of scissors lie to the right. Below them, four small clusters of loose-cut "
     "flowers are laid out in a row — cream roses and jasmine, pale pink roses, one "
     "deep red rose, and purple lavender with campanula — each directly above its own "
     "small cream card, which is tied with a matching ribbon bow: champagne, "
     "dusty-pink, burgundy and lilac in that order, left to right. The camera holds "
     "directly overhead, close on the table, static in frame though the shot still "
     "carries the series' small continuous drift. ",
     HAND_ONLY +
     "Her hand reaches down and lays one small white jasmine bloom beside the "
     "leftmost card, fingertips just releasing it onto the wood. That is the only "
     "action — she does not touch any other cluster and does not pick anything back "
     "up. The four clusters, the four cards, the sign, the ribbon spool and the "
     "scissors all stay exactly as they are in the opening frame, and no fifth "
     "cluster or card ever appears. "
     + lettering("Con xin lỗi mẹ.") + lettering("Cảm ơn vì đã ở lại.")
     + lettering("Anh nhớ em.") + lettering("Mình tự hào về bạn.")
     + MEDIUM_TAIL + AUDIO_TAIL),

    ("05_hoan_thien", "h_hoan_thien.jpg", "10",
     "Close overhead on a wrapped bouquet of pale pink and cream roses with small "
     "white filler flowers, wrapped in cream patterned paper, a blank cream card "
     "tucked into the wrap. Two hands are tying a dusty-pink satin ribbon into a bow "
     "at the bouquet's waist. Behind, the small wooden sign sits on the wooden table. "
     + BOUQUET_SUPPORT,
     "The hands pull the ribbon tight and shape one loop of the bow with quick, "
     "practised fingers. That is the only action — the bouquet is not lifted and not "
     "carried. The roses, the wrapping paper, the blank card and the sign all stay "
     "exactly as they are in the opening frame, and no lettering appears on the "
     "blank card. Everything runs at normal real-time speed: the hands move at a "
     "florist's brisk, practised working pace, quick and unhesitating — this is "
     "real-time footage at 1x, not slow motion. "
     + MEDIUM_TAIL + AUDIO_TAIL),

    ("06_trao_hoa", "i_trao_hoa.jpg", "6",
     "THE FLORIST stands among the greenhouse's roses and hanging cards, holding a "
     "finished bouquet of pink and cream roses wrapped in cream paper with a dusty-"
     "pink ribbon bow, a blank cream card tucked into the wrap, lifted toward the "
     "camera in both hands. The camera holds close at chest height, framing her from "
     "the waist up, front-on. She stays standing in place for the whole shot; she "
     "does not step toward the camera or look away. ",
     CAST +
     "She lifts the bouquet very slightly higher toward the camera and her expression "
     "softens into a gentle smile. That is the only action — she does not hand the "
     "bouquet off and does not turn away. The bouquet, its wrapping, its ribbon and "
     "the hanging cards behind her all stay exactly as they are in the opening frame, "
     "and no lettering appears on the blank card tucked into the wrap. "
     + MEDIUM_TAIL + AUDIO_TAIL),
]

DURATIONS = {"4", "6", "8", "10"}
TARGET_SECONDS = 58


def prompt_for(shot) -> str:
    """Assemble one shot's video prompt exactly as sent to Flow."""
    _, _, _, stage, action = shot
    return MOTION + stage + action


def check() -> None:
    supplied = {p.name for p in FRAMES.glob("*.jpg")}
    used = {frame for _, frame, _, _, _ in SHOTS}
    assert used <= supplied, f"frames not supplied: {sorted(used - supplied)}"
    assert len(used) == len(SHOTS), "each shot must open on its own artwork"

    total = sum(int(s) for _, _, s, _, _ in SHOTS)
    assert total == TARGET_SECONDS, f"clips total {total}s, expected {TARGET_SECONDS}s"
    for name, _, seconds, _, _ in SHOTS:
        assert seconds in DURATIONS, f"{name}: Flow does not offer {seconds}s"

    for shot in SHOTS:
        name = shot[0]
        text = prompt_for(shot)
        assert MOTION in text, f"{name}: missing MOTION — it will come back locked-off"
        for phrase in ("the patch", "the spot", "that area"):
            assert phrase not in text.lower(), f"{name}: '{phrase}' points at nothing"
        assert "ambient:" in text and "no dialogue" in text, f"{name}: missing audio tail"
        assert "locked-off" not in text, f"{name}: 'locked-off' is retired from this series"
        assert "only action" in text, f"{name}: doesn't pin a single beat"

    # Every shot with a visible person carries the CAST or HAND_ONLY block, and
    # never both — Ngày 6's rule: a body left undescribed still gets one invented.
    people_shots = {"01_the_treo", "03_doc_thiep", "06_trao_hoa"}
    hand_shots = {"04_ghep_hoa"}
    for shot in SHOTS:
        name = shot[0]
        text = prompt_for(shot)
        if name in people_shots:
            assert CAST in text and HAND_ONLY not in text, f"{name}: expected CAST only"
        elif name in hand_shots:
            assert HAND_ONLY in text and CAST not in text, f"{name}: expected HAND_ONLY only"
        else:
            assert CAST not in text and HAND_ONLY not in text, f"{name}: card close-up must show neither CAST nor HAND_ONLY"

    # Every card whose text is legible in the reference artwork is quoted and
    # pinned in the shot that shows it (Ngày 6/8's fix for warped lettering).
    quoted = {
        "02a_xin_loi": ["Con xin lỗi mẹ."],
        "02b_cam_on": ["Cảm ơn vì đã ở lại."],
        "02c_nho_em": ["Anh nhớ em."],
        "02d_tu_hao": ["Mình tự hào về bạn."],
        "04_ghep_hoa": ["Con xin lỗi mẹ.", "Cảm ơn vì đã ở lại.", "Anh nhớ em.",
                        "Mình tự hào về bạn."],
    }
    for shot in SHOTS:
        name = shot[0]
        text = prompt_for(shot)
        for phrase in quoted.get(name, []):
            assert phrase in text, f"{name}: the card's handwriting is not quoted"
            assert "does not move, warp or alter" in text, f"{name}: handwriting shown but not pinned"

    # florist-bouquet-craft.md §2: two hands on a wrap must say what holds the
    # bouquet's weight, or it comes back floating.
    support_shot = next(s for s in SHOTS if s[0] == "05_hoan_thien")
    support_text = prompt_for(support_shot)
    assert BOUQUET_SUPPORT in support_text, "05_hoan_thien: nothing says what holds the bouquet"
    assert "florist's brisk" in support_text, "05_hoan_thien: no SPEED block — it will come back slow-motion"

    print(f"check ok — {len(SHOTS)} clips, {total}s, {len(used)} supplied frames, "
          f"no image generation")


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

    ledger = PROJECT / "ngay3_videos_result.json"
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
