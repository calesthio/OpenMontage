"""Seven clips for 'Dưới tán hoa — Ngày 1: Khu vườn sắp mở cửa', anime, 9:16, 58s.

    python scripts/_gen_ngay1.py check      # the standard's checklist, spends nothing
    python scripts/_gen_ngay1.py upload     # sends every frame to Flow's library first, 0 credits
    python scripts/_gen_ngay1.py videos     # resumes: only missing clips are made; uses any
                                             # frame already uploaded instead of re-uploading it

No images are generated. The seven opening frames are the user's artworks, one
per beat of the script. Follows
`.agents/skills/flow-video/references/shot-sequence-prompts.md`.

**02_hoi_uc is not a real space.** The reference frame is already a vertical
collage of four separate memory panels (a seed, a sprout, two people at the
table, a woman crying on a bench) stacked with soft cloud dividers — the
artist's own recap graphic, not one continuous room. Asking Flow to animate
it as a single physical scene would blend four disconnected pieces of art
into one, which is exactly the kind of thing this model invents badly. The
shot is prompted as a camera drifting down over a fixed illustration instead
— nothing within any panel moves, only the framing does.

**06_bon_bo is the one shot with three people.** The florist inside, plus a
girl and a woman outside the door — named and described so the shot doesn't
drift toward the "empty frame grows a person" failure this series has hit
before (Ngày 8), and so it doesn't merge into "two people" either.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Windows' console defaults to cp1252, which can't encode Vietnamese text.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path("projects/duoi-tan-hoa-ngay-1")
FRAMES = PROJECT / "assets" / "frames"
VIDEO = PROJECT / "assets" / "video"

# Same shared Flow project as Ngày 3/4 — see _gen_ngay3.py for why reusing it
# is safe now that lib/flow_driver.py identifies tiles by position, not caption.
PROJECT_URL = "https://flow.google.com/project/0ebed0ec-2661-4413-851f-9fa34078c90f?hl=vi"
LOCK = Path.home() / ".openmontage" / "flow_video.lock"
UPLOADS = PROJECT / "ngay1_uploaded_frames.json"

STYLE = ("Detailed anime-style digital illustration, softly painterly with delicate "
         "linework and warm cinematic sunlight; glossy, semi-realistic rendering, not "
         "flat cel-shaded and not a photograph, no 3D render. ")

CAST = ("THE FLORIST is a young woman with very long dark brown wavy hair falling past "
        "her waist, a cream satin ribbon bow tied at the side of her head, and a long "
        "ivory-cream lace dress with puffed sleeves and a tied waist sash. No other "
        "person is anywhere in the shot. ")

HANDS_AND_CHIN = ("Only THE FLORIST's hands, forearms and the lower curve of her chin "
                  "and lips are in shot — her eyes and the rest of her face stay out of "
                  "frame above the top edge — and no other person is visible anywhere. ")

HAND_ONLY = ("Only THE FLORIST's hand and forearm are in shot, entering from the left "
             "edge of frame, wearing the ivory-cream lace sleeve cuff of her dress; no "
             "face, no other body part and no other person is visible anywhere. ")

# The two returning characters from earlier episodes, named and pinned exactly
# as hard as THE FLORIST — Ngày 8's rule: an unnamed body in frame gets invented.
RETURNING_GUESTS = ("Outside the open door, two more women stand together in the garden "
                    "path beyond: THE YOUNGER GUEST has dark hair tied back in a high "
                    "ponytail with a burgundy ribbon and wears a pale blue puff-sleeved "
                    "dress with a woven straw bag on her shoulder; THE OLDER GUEST has "
                    "shoulder-length dark hair loose and wears a mauve button-front "
                    "dress with a small bag across her body. Both are smiling toward THE "
                    "FLORIST. There are exactly three people anywhere in the shot — THE "
                    "FLORIST and these two — and no one else appears at any moment. ")

SIGN = ('The wooden sign keeps its handwritten Vietnamese words “Dưới Tán Hoa” and the '
        "small painted flower sprig beneath them exactly as they are; the lettering and "
        "the sprig do not move, warp or alter. ")

MOTION = ("The camera moves slowly and continuously for the entire shot at one constant "
          "speed, with no stop, no acceleration and no cut anywhere in the clip. The "
          "movement is small: the framing at the end is only a little different from "
          "the framing at the start. ")

MEDIUM_TAIL = "The whole shot stays a detailed anime illustration, never a photograph. "

AUDIO_TAIL = ("ambient: still warm greenhouse air, faint birdsong, a soft rustle of "
              "leaves, paper and fabric. no dialogue, no music, no voices.")


def lettering(text: str) -> str:
    return (f'The handwritten Vietnamese words on the card read “{text}” '
            f"and they stay exactly as written for the whole shot; the lettering does "
            f"not move, warp or alter. ")


# (name, frame, seconds, stage, action)
SHOTS = [
    ("01_don_dep", "a_don_dep.jpg", "8",
     "Inside the glasshouse workroom, a hanging iron lantern above a wooden table "
     "against the tall window, holding stacked kraft gift boxes tied with dusty-pink "
     "ribbon, bundles of cream cards tied with twine, rolled sheets of patterned "
     "wrapping paper, a spool of ribbon and a galvanized jug of pink roses; the small "
     "wooden sign sits on the table. A sheer white curtain hangs at the window. "
     "Wooden shelves of potted flowers stand to the left. The camera frames THE "
     "FLORIST from behind and to the side, at chest height. Both her feet stay on the "
     "floor; she does not walk away from the table. ",
     CAST +
     "She draws the curtain back with one hand, letting more morning light into the "
     "room, while her other hand rests on the stack of cards. That is the only action "
     "— she does not pick up any box or card and does not sit down. The table, the "
     "boxes, the cards, the paper rolls, the ribbon, the jug of roses and the sign all "
     "stay exactly as they are in the opening frame. " + SIGN + MEDIUM_TAIL + AUDIO_TAIL),

    ("02_hoi_uc", "b_hoi_uc.jpg", "8",
     "The frame is a still hand-painted memory board, not a real room: from top to "
     "bottom it shows four separate illustrated panels divided by soft cloud-like "
     "borders — a hand planting one seed into dark soil in a rose-patterned pot; the "
     "same pot with a small green sprout beaded with dew; THE FLORIST leaning on a "
     "table watching the sprout while a girl with a red-ribboned ponytail, a plaid "
     "pinafore dress and a brown satchel bag hands her a small note; and, in the "
     "lowest panel, a middle-aged woman sitting on a garden bench, her eyes soft and "
     "a little bright, smiling gently while she holds a small wrapped pink flower "
     "close to her chest. The camera holds on the "
     "whole board and drifts slowly straight downward, from the seed panel toward "
     "the bench panel. ",
     "That is the only action — the camera glides down past the panels. Nothing "
     "within any panel moves: the seed stays a seed, the sprout stays as it is, the "
     "two figures at the table stay exactly as posed, and the woman on the bench "
     "does not shift. No panel gains or loses a figure, and no new panel appears. "
     "This stays a flat painted illustration being looked at, not a real space the "
     "camera travels through. " + MEDIUM_TAIL + AUDIO_TAIL),

    ("03_hoa_sap", "c_hoa_sap.jpg", "8",
     "In the foreground, an open floral-patterned box divided into compartments, "
     "each holding one preserved wax rose or a small cluster of wax daisies: deep "
     "red, pink, cream, and pale lilac roses, with white wax daisies in the front "
     "compartments. The wooden lid, printed with the small wooden \"Dưới Tán Hoa\" "
     "sign lettering, leans open behind the box. Kraft gift boxes and ribbon rolls "
     "sit to the left, a metal jug of pink roses and lavender to the right, a stack "
     "of cards tied with twine at the bottom edge. The camera holds close on the box "
     "and THE FLORIST's hand, which holds one loose pink wax rose above it. ",
     HAND_ONLY +
     "Her fingers turn the wax rose slowly, catching the light on its petals, then "
     "lower it back toward the compartment it came from without yet placing it down. "
     "That is the only action — no other rose is touched and the box's arrangement "
     "does not change. The box, its compartments, the gift boxes, the jug and the "
     "cards all stay exactly as they are in the opening frame, and no new flower "
     "appears in any compartment. " + SIGN + MEDIUM_TAIL + AUDIO_TAIL),

    ("04_ket_bo", "d_ket_bo.jpg", "10",
     "THE FLORIST leans over the same wooden table, tying a dusty-pink ribbon into a "
     "bow around a gathered bouquet of wax roses — pink, deep red, cream and pale "
     "lilac — wrapped in floral-patterned paper with small white wax daisies among "
     "the blooms. The open floral box of remaining wax roses sits to her right on "
     "the table, the small wooden sign visible behind it, scissors and loose cards "
     "with twine lying at the front edge. The camera holds close at table height, "
     "side-on, framing her from the chest up. She stays leaning over the table for "
     "the whole shot. ",
     CAST +
     "Her hands pull the ribbon tight and shape one loop of the bow with quick, "
     "practised fingers. That is the only action — the bouquet is not lifted from "
     "the table and not carried. The bouquet, the open box of roses, the sign, the "
     "scissors and the cards all stay exactly as they are in the opening frame, and "
     "no new bloom is added to the bouquet. Everything runs at normal real-time "
     "speed: her hands move at a florist's brisk, practised working pace, quick and "
     "unhesitating — this is real-time footage at 1x, not slow motion. "
     + MEDIUM_TAIL + AUDIO_TAIL),

    ("05_cai_thiep", "e_cai_thiep.jpg", "8",
     "Close on the finished wax-flower bouquet — pink, cream, deep red and pale "
     "lilac roses with small white wax daisies, wrapped in cream paper and tied with "
     "a dusty-pink ribbon bow — standing upright on its own wrapped base. Behind it, "
     "a small wooden plant marker reading \"Dưới Tán Hoa\" stands in a potted plant, "
     "and white daisies grow beyond the glass wall. Two hands hold a small cream "
     "card against the front of the bouquet. The camera holds close at chest height, "
     "static but carrying the series' small continuous drift. ",
     HANDS_AND_CHIN +
     "Her fingers settle the card fully into place against the wrapping and hold it "
     "there, steady. That is the only action — the bouquet is not lifted from the "
     "table and no other part of the wrap is touched. The bouquet stands on its own "
     "wrapped base the whole time; it is never held up in mid-air. The plant marker "
     "and the daisies behind stay exactly as they are in the opening frame. "
     + lettering("Có những điều khó nói, hãy để hoa nói giúp bạn.")
     + MEDIUM_TAIL + AUDIO_TAIL),

    ("06_bon_bo", "f_bon_bo.jpg", "8",
     "THE FLORIST stands just inside the open glasshouse door, the small wooden "
     "sign hanging beside the doorframe. In the foreground on the table, four "
     "finished wax-flower bouquets stand side by side, each wrapped in cream paper: "
     "pink roses tied with a pink ribbon, deep red roses tied with a burgundy "
     "ribbon, cream roses tied with a champagne ribbon, and pale lilac roses tied "
     "with a lilac ribbon. Beyond the door, a garden path lined with flowers leads "
     "to a small iron gate. The camera frames her from the waist up, front-on, "
     "looking toward the doorway. She stays standing in place for the whole shot. ",
     CAST + RETURNING_GUESTS +
     "THE FLORIST's face brightens into a smile as she looks toward the doorway; "
     "THE YOUNGER GUEST and THE OLDER GUEST stand together and smile back, neither "
     "one stepping through the door. That is the only action — nobody crosses the "
     "threshold and no one else appears on the path. The four bouquets, the sign, "
     "the doorway and the garden path all stay exactly as they are in the opening "
     "frame. " + SIGN + MEDIUM_TAIL + AUDIO_TAIL),

    ("07_treo_bang", "g_treo_bang.jpg", "8",
     "THE FLORIST stands just outside the glasshouse's open door, reaching up with "
     "both hands to hang the oval wooden \"Dưới Tán Hoa\" sign on its rope from an "
     "iron bracket beside the doorframe. Through the open door behind her, wrapped "
     "bouquets in red, pink, cream and lilac stand on the table beside scissors and "
     "ribbon spools. A stone path scattered with petals leads away under a clear "
     "blue sky. The camera frames her from behind and to the side, at chest height, "
     "looking up past her toward the sign. Both her feet stay on the stone path; "
     "she does not walk. ",
     CAST +
     "She settles the sign's rope onto the hook and lets go, the sign swaying very "
     "slightly before it settles, while she watches it with a quiet smile. That is "
     "the only action — she does not take the sign back down and does not turn "
     "away. The doorway, the bouquets and table behind her, and the path all stay "
     "exactly as they are in the opening frame. " + SIGN + MEDIUM_TAIL + AUDIO_TAIL),
]

DURATIONS = {"4", "6", "8", "10"}
TARGET_SECONDS = 58


def prompt_for(shot) -> str:
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
        if name != "02_hoi_uc":
            assert "only action" in text, f"{name}: doesn't pin a single beat"

    # Each shot carries exactly the right cast block for its headcount.
    cast_map = {
        "01_don_dep": [CAST], "03_hoa_sap": [HAND_ONLY], "04_ket_bo": [CAST],
        "05_cai_thiep": [HANDS_AND_CHIN], "06_bon_bo": [CAST, RETURNING_GUESTS],
        "07_treo_bang": [CAST],
    }
    all_blocks = [CAST, HAND_ONLY, HANDS_AND_CHIN, RETURNING_GUESTS]
    for shot in SHOTS:
        name = shot[0]
        if name == "02_hoi_uc":
            continue
        text = prompt_for(shot)
        expected = cast_map[name]
        for block in all_blocks:
            assert (block in text) == (block in expected), f"{name}: wrong cast block set"

    # The florist-craft SUPPORT rule for the one two-handed-wrap shot.
    ket_bo = next(s for s in SHOTS if s[0] == "04_ket_bo")
    ket_bo_text = prompt_for(ket_bo)
    assert "florist's brisk" in ket_bo_text, "04_ket_bo: no SPEED block — it will come back slow-motion"

    # Every card/sign whose text is legible in the reference artwork is quoted
    # and pinned (Ngày 6/8's fix for warped lettering).
    quoted = {"05_cai_thiep": ["Có những điều khó nói, hãy để hoa nói giúp bạn."]}
    sign_shots = {"01_don_dep", "03_hoa_sap", "06_bon_bo", "07_treo_bang"}
    for shot in SHOTS:
        name = shot[0]
        text = prompt_for(shot)
        for phrase in quoted.get(name, []):
            assert phrase in text, f"{name}: the card's handwriting is not quoted"
            assert "does not move, warp or alter" in text, f"{name}: handwriting shown but not pinned"
        if name in sign_shots:
            assert SIGN in text, f"{name}: the wooden sign is visible but not pinned"

    # 02_hoi_uc must never claim to be a real, continuous space.
    hoi_uc_text = prompt_for(next(s for s in SHOTS if s[0] == "02_hoi_uc"))
    assert "not a real space" in hoi_uc_text or "flat painted illustration" in hoi_uc_text, "02_hoi_uc: doesn't say this is a static memory board, not a real room"

    print(f"check ok — {len(SHOTS)} clips, {total}s, {len(used)} supplied frames, "
          f"no image generation")


def run_uploads() -> int:
    """Upload every shot's frame to the Flow project's library up front.

    Resumable: shots already in `UPLOADS` are skipped, so re-running after a
    partial upload only sends the ones still missing. `videos` picks these up
    automatically and skips re-uploading a frame it already has a library
    name for.
    """
    from lib.flow_driver import FlowDriver, FlowError

    os.environ.setdefault("FLOW_PROJECT_URL", PROJECT_URL)
    mapping = json.loads(UPLOADS.read_text(encoding="utf-8")) if UPLOADS.is_file() else {}

    pending = [(name, frame) for name, frame, *_ in SHOTS
               if not (VIDEO / f"{name}.mp4").is_file() and name not in mapping]
    if not pending:
        print("all frames already uploaded")
        return 0

    ok = 0
    with FlowDriver(project_url=os.environ["FLOW_PROJECT_URL"]) as driver:
        driver.ensure_project()
        for name, frame in pending:
            try:
                uploaded = driver.upload_only(FRAMES / frame)
                mapping[name] = uploaded
                ok += 1
                print(f"uploaded {name} -> {uploaded}", flush=True)
            except FlowError as exc:
                print(f"{name}: FAILED\n   {exc}", flush=True)
            UPLOADS.write_text(json.dumps(mapping, indent=1, ensure_ascii=False),
                               encoding="utf-8")

    print(f"\ndone: {ok}/{len(pending)} frames uploaded this run")
    return 0 if ok == len(pending) else 1


def run_videos() -> int:
    from tools.video.flow_video import FlowVideo

    os.environ.setdefault("FLOW_PROJECT_URL", PROJECT_URL)
    uploaded = json.loads(UPLOADS.read_text(encoding="utf-8")) if UPLOADS.is_file() else {}
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
            "asset_uploaded_name": uploaded.get(name),
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

    ledger = PROJECT / "ngay1_videos_result.json"
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
    if command == "check":
        raise SystemExit(0)
    if command == "upload":
        raise SystemExit(run_uploads())
    raise SystemExit(run_videos())
