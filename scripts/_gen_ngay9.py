"""Eight shots for 'Dưới tán hoa — Ngày 9: Ngày chưa thấy gì', anime, 9:16.

Written to `.agents/skills/flow-video/references/shot-sequence-prompts.md`.

Images and clips live in one file on purpose. The standard's whole point is that
STAGE appears **word for word** in every outdoor prompt; splitting the episode
across two scripts creates a second copy of STAGE, and a second copy is where the
location starts to drift. Ngày 10 was split that way and cost three regenerations.

    python scripts/_gen_ngay9.py check      # the standard's checklist, spends nothing
    python scripts/_gen_ngay9.py images
    python scripts/_gen_ngay9.py videos
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path("projects/duoi-tan-hoa-ngay-9/assets")
IMAGES, VIDEO = ROOT / "images", ROOT / "video"

# ---------------------------------------------------------------- locked blocks
# Pasted verbatim into every prompt. Never reworded per shot — rewording is how
# the drift starts.

STYLE = (
    "Anime illustration, Studio Ghibli inspired: soft cel shading, delicate linework, "
    "painterly watercolour foliage, warm golden sunlight with gentle bloom, high-key "
    "pastel palette of cream, soft gold and pale green. Vertical 9:16 composition. "
)

# Unchanged from Ngày 10, to the letter. Measurable attributes only — no
# "graceful", no "gentle"; those do not reproduce.
CHARACTER = (
    "A young woman of about twenty-five with long dark-brown wavy hair falling past her "
    "shoulders, fair skin and large dark eyes, wearing a long ivory-cream linen dress "
    "with three-quarter sleeves and a tiered skirt, and pale canvas shoes. "
)

# The one block that changes per episode. The marker sign is new: planted at the
# end of Ngày 10, it is what tells the viewer this is still yesterday's garden.
# Its face is described BLANK because gpt-image and Veo both mangle lettering —
# the logo is printed in afterwards with scripts/stamp_logo_on_sign.py.
STAGE = (
    "The place is a wide rectangular raised bed of bare dark tilled soil, edged with a low "
    "weathered red-brick wall, with an old white-framed glasshouse standing directly behind "
    "it and dry pale-gold grass all around. A small pale wooden marker sign stands upright "
    "in the near half of the bed on a single stake; its rounded board is COMPLETELY BLANK "
    "smooth pale wood with no writing or carving of any kind. Sparse leggy bare shrubs and "
    "a few bare young trees stand around the bed. The garden is dry and wilted — pale gold, "
    "no lush green growth — but the light is bright and hopeful, never bleak. Pale cool "
    "early-morning light, thin mist lying low over the soil. "
)

# The close-ups cannot carry the whole STAGE — naming the glasshouse in a shot of
# two hands drags it into frame. But dropping the block entirely leaves the model
# with no palette or ground to anchor to, and it invents one: the first pass put
# shot 4 in warm orange light against glossy new brick, and shot 7 against a green
# flowering hedge. So the close shots get the ground and the light, minus the
# geography.
CLOSE_STAGE = (
    "The ground here is the bare dark tilled soil of a raised bed edged with a low "
    "weathered red-brick wall — dusty matt muted brick, not glossy or orange. Pale cool "
    "early-morning light, high-key palette of cream, soft gold and pale green; no warm "
    "orange, no golden-hour or sunset tones. The garden around is dry and wilted, pale "
    "gold, with no lush green growth and no flowers in bloom. "
)

# The episode's one recurring contradiction: nine days out, nothing has come up.
# Every model wants to reward a planted bed with a sprout, so it is denied by name.
BARE = ("The bed is bare — nothing is growing in it. No sprout, no seedling, no green "
        "shoot of any kind anywhere in the soil. ")

AUDIO_TAIL = " no dialogue, no music, no voices."

# ---------------------------------------------------------------------- the shots
# (name, seconds, image prompt, video prompt)
SHOTS = [
    ("01_sang_som", "6",
     STYLE + STAGE + "No people. A tall vertical view across the bed toward the glasshouse, "
     "the marker sign standing alone in the middle of the bare soil, mist and drifting motes "
     "in the low light. " + BARE,
     "The camera drifts in very slowly across the bed toward the glasshouse; mist stirs over "
     "the soil and dry grass moves at the edges of frame. Nothing else moves — the marker "
     "sign stays still and the soil stays bare. "
     "ambient: early birdsong, very light wind." + AUDIO_TAIL),

    ("02_ngoi_xuong", "6",
     STYLE + CHARACTER + STAGE + "Seen from behind, she lowers herself into a crouch on the "
     "dry grass just outside the low brick edge, facing the bed and the marker sign. Both "
     "feet stay on the grass; she does not step or kneel on the soil. Her face is turned "
     "away. " + BARE,
     "Seen from behind, she takes the last two steps on the grass and settles into a crouch "
     "at the brick edge, her dress and hair moving as she lowers. She stays outside the brick "
     "edge and never steps onto the soil. Her face is never seen. "
     "ambient: footsteps on dry grass, cloth, soft wind." + AUDIO_TAIL),

    ("03_gat_dat", "6",
     STYLE + CHARACTER + CLOSE_STAGE + "Close vertical view of her hands only, fingertips "
     "brushing aside the top crumbs of dark damp soil as if looking for something underneath. "
     "Only hands and soil fill the frame. There is nothing under her fingers — no sprout, no "
     "shoot, no green — only dark earth. ",
     "Her fingertips brush the top crumbs of soil aside, part them, and pause. Nothing is "
     "revealed underneath — only more dark soil. Only hands and soil in frame. "
     "ambient: fingers in loose soil, faint wind." + AUDIO_TAIL),

    ("04_chi_co_dat", "8",
     STYLE + CLOSE_STAGE + "Very close low vertical view of bare dark damp tilled soil, with "
     "the low weathered red-brick edge running along one side of the frame. No hands, no "
     "people. Nothing is growing — no sprout, no seedling, no green of any kind. Only damp "
     "earth. ",
     "A locked-off close shot of the bare soil. Almost nothing happens: a crumb of earth "
     "settles, the light shifts a fraction, a thread of mist passes. Nothing grows and "
     "nothing enters the frame. "
     "ambient: very light wind, distant birds." + AUDIO_TAIL),

    ("05_ngoi_yen", "8",
     STYLE + CHARACTER + STAGE + "Seen from behind, she has settled back on her heels on the "
     "dry grass outside the brick edge, hands resting in her lap, looking at the bed and the "
     "marker sign. She is not touching the soil and both feet stay on the grass. Her face is "
     "turned away. " + BARE,
     "Locked-off shot from behind. She sits back on her heels and stays still; only her hair "
     "and the hem of her dress move in the breeze. She does not stand, does not reach out and "
     "does not touch the soil. Her face is never seen. "
     "ambient: wind through dry grass." + AUDIO_TAIL),

    ("06_van_tuoi", "10",
     STYLE + CHARACTER + STAGE + "Seen from behind, she kneels on the dry grass just outside "
     "the brick edge and tips a small metal watering can so that water falls onto one spot of "
     "the bare soil. Both knees stay on the grass, outside the brick edge. Her face is turned "
     "away. " + BARE,
     "Seen from behind, she tips the watering can and a fine stream falls onto the bare soil; "
     "the earth darkens where it lands. She stays in one place — she does not walk and does "
     "not move onto the soil. The bed stays empty; nothing grows while she waters. "
     "ambient: pouring water, water soaking into soil." + AUDIO_TAIL),

    ("07_lau_bang", "8",
     STYLE + CLOSE_STAGE + "Close vertical view of ONE HAND ONLY. No face, no head, no "
     "shoulders, no body — only a hand and a bare forearm entering low from the bottom edge "
     "of the frame. The hand has just finished wiping dust from a small wooden marker board "
     "and is dropping away: its thumb rests against the very bottom rim of the board, below "
     "the face, and the entire flat face of the board above it is clear and unobstructed — "
     "the hand does not cross or cover any part of it. The board is a rounded rectangle on a "
     "single stake and is COMPLETELY BLANK — smooth pale wood, no writing, no carving, no "
     "marks. Its face is turned almost square-on to the camera and fully visible. Behind the "
     "board is the bare soil of the bed and the low weathered brick edge — no hedge, no "
     "bushes, no flowers, nothing green. ",
     "The hand drops away from the bottom rim of the board and withdraws out of the bottom of "
     "the frame, a faint haze of dust drifting off the wood behind it. The hand never crosses "
     "the face of the board. The camera is locked off and the board itself stays perfectly "
     "still and unchanged — the printed flower and lettering on its face do not move, warp or "
     "alter. "
     "ambient: a thumb on dry wood, faint wind." + AUDIO_TAIL),

    ("08_con_lai", "6",
     STYLE + STAGE + "No people, no hands. Seen from slightly above and close, the marker sign "
     "stands alone in the bare bed, its blank face turned almost square-on to the camera and "
     "fully visible. The same pale cool morning light as the rest of the sequence — not warm, "
     "not golden, no sunset or evening tones. " + BARE,
     "Locked-off camera. The sign stands alone; a thread of mist drifts past and the dry grass "
     "at the edge of frame stirs once, then settles. The sign does not move and nothing on its "
     "face changes. No one enters the frame. "
     "ambient: wind dropping away to silence." + AUDIO_TAIL),
]

# EVERY shot the board appears in, with the ROI its face sits in. The first pass
# stamped only the two close-ups, on the theory that a 140px board reads the same
# blank or printed. It does not: against a bare bed the eye goes straight to the
# one man-made object, and a sign blank in four shots and branded in two is a
# continuity break like any other. If a branded object is in STAGE, it carries the
# brand in every frame it appears in.
STAMP = {
    "01_sang_som":   "400,790,620,930",
    "02_ngoi_xuong": "590,660,800,810",
    "05_ngoi_yen":   "610,590,800,730",
    "06_van_tuoi":   "730,710,920,860",
    "07_lau_bang":   "150,250,850,870",
    "08_con_lai":    "260,790,660,1055",
}
LOGO = "projects/_brand/duoi-tan-hoa-logo.png"


def check() -> None:
    """Run the standard's checklist over the prompt table before anything is spent.

    Each assertion is one of the Ngày 10 failures, caught here instead of after
    the credits are gone.
    """
    outdoor = [name for name, _, image, _ in SHOTS if STAGE in image]
    assert len(outdoor) >= 4, "STAGE must appear verbatim in every outdoor shot"

    # The first pass asserted only that STAGE appeared *somewhere*, so the three
    # close-ups slipped through with no palette or ground anchor at all. Two of
    # them came back in the wrong light against the wrong brick. Every shot now
    # has to carry one block or the other.
    for name, _, image, _ in SHOTS:
        assert STAGE in image or CLOSE_STAGE in image,             f"{name}: neither STAGE nor CLOSE_STAGE — nothing pins the ground or the light"

    for name, _, image, video in SHOTS:
        for label, text in (("image", image), ("video", video)):
            for phrase in ("the patch", "the spot", "that area"):
                assert phrase not in text.lower(), \
                    f"{name} {label}: '{phrase}' points at something the model has never seen"
        assert "ambient:" in video, f"{name}: video prompt has no ambient line"
        assert "no dialogue" in video, f"{name}: video prompt does not suppress dialogue"

    # Shot 7 broke on Ngày 10 because the prompt said what she looked at and never
    # said where she stood. Any shot with her body in it has to answer that.
    for name, _, image, _ in SHOTS:
        if CHARACTER in image and "hands only" not in image and "one hand only" not in image:
            assert "feet stay on the grass" in image or "knees stay on the grass" in image, \
                f"{name}: the woman is in shot but the prompt never says where her feet are"

    total = sum(int(seconds) for _, seconds, _, _ in SHOTS)
    assert total == 58, f"shot list adds up to {total}s, not the scripted 58s"
    print(f"check ok — {len(SHOTS)} shots, {total}s, STAGE verbatim in {len(outdoor)} outdoor shots")


def run_images() -> int:
    from tools.graphics.codex_image import CodexImage

    IMAGES.mkdir(parents=True, exist_ok=True)
    tool, results = CodexImage(), []

    for name, _, prompt, _ in SHOTS:
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
            print(f"  {name} attempt {attempt + 1} failed", flush=True)
            time.sleep(40)

        took = round(time.time() - started, 1)
        print(f"{name}: {'ok' if result.success else 'FAILED'} ({took}s)", flush=True)
        if not result.success:
            print(f"   {result.error}", flush=True)
        results.append({"name": name, "ok": result.success, "seconds": took})

    Path("ngay9_images_result.json").write_text(
        json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    failed = [row["name"] for row in results if not row["ok"]]
    print(f"\ndone: {len(results) - len(failed)}/{len(results)}")
    if failed:
        print("failed:", ", ".join(failed))

    # Stamp from a pristine copy, never in place: the tool reads and writes whole
    # frames, so running it twice on one file prints the logo on top of itself.
    print("\nNext — print the logo onto every shot the board appears in:")
    for name, roi in STAMP.items():
        print(f"  python scripts/stamp_logo_on_sign.py <blank>/{name}.png "
              f"{LOGO} {IMAGES / name}.png --roi {roi}")
    return 1 if failed else 0


def run_videos() -> int:
    from tools.video.flow_video import FlowVideo

    VIDEO.mkdir(parents=True, exist_ok=True)
    tool, results = FlowVideo(), []

    for name, duration, _, prompt in SHOTS:
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

        Path("ngay9_videos_result.json").write_text(
            json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")

    failed = [row["name"] for row in results if not row["ok"]]
    spent = sum(row.get("credits") or 0 for row in results)
    print(f"\ndone: {len(results) - len(failed)}/{len(results)} clips, {spent} credits")
    if failed:
        print("failed:", ", ".join(failed))
    print(f"\nNext: python scripts/flow_continuity_check.py {VIDEO}")
    return 1 if failed else 0


MODES = {"check": lambda: (check(), 0)[1], "images": run_images, "videos": run_videos}

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    if mode not in MODES:
        raise SystemExit(f"usage: {sys.argv[0]} [{' | '.join(MODES)}]")
    sys.exit(MODES[mode]())
