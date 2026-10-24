"""One ad where BOTH sweater SKUs appear — the two character stills drive it as
Flow "Thành phần" reference elements.

    python scripts/_gen_podsweater_duo.py check    # checklist, spends nothing
    python scripts/_gen_podsweater_duo.py sample   # shot 1 only — approve first
    python scripts/_gen_podsweater_duo.py videos   # resumes: only missing clips
    python scripts/_gen_podsweater_duo.py cut      # trim to the beat sheet + stitch

Difference from `_gen_podsweater_ad.py`, which made four solo clips: here the
two wearers are on screen **together** in every shot and open their coats on the
same beat, so one video carries both SKUs. Still Repeat-Reveal
(`skills/creative/shopee-product-ad.md`): identical gag mechanic, changing
setting, accelerating cuts, every shot ending on a bystander reaction, no
narration, no on-screen text.

**The refs do not replace the garment description — measured, not assumed.** The
first sample attached both stills and let the prompt merely *point at* them
("the sweater she wears in the first reference image"). Flow read the elf still
as artwork to print and put photo portraits of two people on the green sweater;
the Santa SKU, which has a far more common print, survived. So both SKUs are
spelled out here in full — the reference chips pin the cast and the room, the
text pins the print — and the elf block carries an explicit "never a photograph
of a person, never a portrait", which is the exact failure it is there to stop.

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
VIDEO = PROJECT / "assets" / "video_duo"
CUT = PROJECT / "renders"

PROJECT_URL = "https://flow.google.com/project/0ebed0ec-2661-4413-851f-9fa34078c90f?hl=vi"
LOCK = Path.home() / ".openmontage" / "flow_video.lock"

GEN_SECONDS = "4"

# Both chips ride on every shot — that is the whole point of this cut.
REFS = [FRAMES / "char_elf.jpg", FRAMES / "char_santa.jpg"]

# ---------------------------------------------------------------- locked blocks

CAST = (
    "THE WOMAN is a young woman in her twenties with shoulder-length dark hair "
    "worn loose and small silver earrings, in dark jeans. She wears a dark "
    "forest-green crewneck with black ribbed collar, cuffs and hem. Printed flat "
    "onto its front — it is a printed picture on fabric, not real clothing and "
    "not real skin, and never a photograph of a person and never a portrait — is "
    "a trompe-l'oeil elf costume, shaped as a single deep narrow V that starts at "
    "the collar and runs down to the waist: a red-and-white candy-striped stripe "
    "edges each side of the V, inside the V is a printed red costume top with a "
    "thick white fur trim across it and printed midriff below it, and three round "
    "gold jingle-bell buttons run down the centre line below the point of the V. "
    "The green fabric covers the shoulders, the whole chest outside the V and the "
    "full sleeves. There is no belt and no buckle on this one. "
    "THE MAN is a man in his thirties with short dark hair and a trimmed beard, "
    "in dark jeans. He wears a bright red crewneck with black ribbed collar, "
    "cuffs and hem. Printed flat onto its front — again a printed picture on "
    "fabric, not real clothing and not real skin — is a trompe-l'oeil Santa "
    "costume: an open red coat edge with thick white fur trim, a printed "
    "muscular bare male chest and six-pack stomach between the edges, a string "
    "of small round multicoloured Christmas lights draped across the chest, and "
    "a wide black belt with a square gold buckle printed across the waist. "
    "Both garments stay one continuous piece of fabric with no real opening "
    "anywhere. ")

REVEAL = ("Both of them start in plain dark winter coats, fully closed, with the "
          "sweaters completely hidden. On the same beat they pull their coats "
          "open and off the shoulders, side by side, revealing both printed "
          "sweaters at once. ")

# From the pig-mask sample: the product must stay visible *during* the reaction.
FRAMING = ("The camera films the pair from the front, wide enough that BOTH "
           "printed sweater fronts AND the reacting people's faces are in frame "
           "at the same time for the whole clip. Both printed fronts face the "
           "camera, are never turned away, never covered by an arm, and never "
           "leave the frame. ")

MOTION = ("Handheld phone footage, filmed by a friend standing a few steps away. "
          "The camera moves slightly and continuously the way a hand-held phone "
          "does, with no stop and no cut anywhere in the clip. ")

SPEED = "Everything runs at normal real-time speed, 1x, not slow motion. "

CLEAN = ("There is no text anywhere in the frame: no caption, no subtitle, no "
         "title card, no sticker, no logo, no watermark and no graphic overlay of "
         "any kind. No writing appears on any wall, screen or surface in shot. ")

MEDIUM_TAIL = ("Realistic candid smartphone video, natural indoor party light, "
               "slightly imperfect framing, not a studio advert and not an "
               "illustration. Vertical 9:16. ")

AUDIO_TAIL = ("ambient: party room noise and a short burst of genuine laughter "
              "from the other people. no dialogue, no music, no voice-over.")

# (name, trim_seconds, setting, beat)
SHOTS = [
    ("01_doorway", 4.0,
     "The front doorway of a house at Christmas, a wreath on the door, coats on "
     "hooks and three guests standing in the hallway inside. ",
     "The two of them shrug their coats off together in the doorway. All three "
     "guests in the hallway look up, see both printed sweaters at once, and burst "
     "out laughing, one clapping a hand over their mouth. That is the only action "
     "— nobody speaks and the coats stay off. "),

    ("02_livingroom", 3.0,
     "A family living room: a lit Christmas tree, a sofa, an older woman sitting "
     "with a mug and a teenager beside her. ",
     "The two of them drop their coats at the same moment in front of the sofa. "
     "The older woman throws her head back laughing and the teenager doubles over. "
     "That is the only action — neither wearer walks out of frame. "),

    ("03_kitchen", 2.0,
     "A kitchen at a house party: a counter with snacks and drinks, two friends "
     "leaning against it. ",
     "The two of them pull their coats open side by side at the counter. Both "
     "friends turn, see both printed sweaters, and crack up, one pointing. That is "
     "the only action — the moment ends on their laugh. "),
]

TARGET_TOTAL = 9.0


def prompt_for(shot) -> str:
    _, _, setting, beat = shot
    return (MEDIUM_TAIL + setting + CAST + REVEAL + beat + FRAMING
            + MOTION + SPEED + CLEAN + AUDIO_TAIL)


def check() -> None:
    assert len(SHOTS) == 3, "Repeat-Reveal wants 3-4 settings"

    for ref in REFS:
        assert ref.is_file(), f"missing reference element: {ref}"
    assert len(REFS) == 2, "one SKU per reference chip — this cut carries both"

    trims = [t for _, t, _, _ in SHOTS]
    for earlier, later in zip(trims, trims[1:]):
        assert later <= earlier, f"shot lengths must never grow: {trims}"
    assert trims[0] >= 2 * trims[-1], f"shot 1 should be ~2x the last: {trims}"
    total = sum(trims)
    assert total == TARGET_TOTAL, f"beats total {total}s, expected {TARGET_TOTAL}s"
    assert 9.0 <= total <= 12.0, f"format lives at 9-12s, got {total}s"
    for name, trim, *_ in SHOTS:
        assert trim <= float(GEN_SECONDS), f"{name}: cannot trim {trim}s from {GEN_SECONDS}s"

    settings = [s for _, _, s, _ in SHOTS]
    assert len(set(settings)) == len(settings), "every shot needs its own setting"

    for shot in SHOTS:
        name = shot[0]
        text = prompt_for(shot)
        # The prompt must say it IS a print — without this the model renders the
        # Santa panel as a bare torso.
        assert "one continuous piece of fabric with no real opening" in text, \
            f"{name}: the print must be pinned as a print"
        assert text.count("not real clothing and not real skin") == 2, \
            f"{name}: both SKUs need the print pin, not just the first"
        # What the first sample actually got wrong: portraits printed on the elf.
        assert "never a photograph of a person and never a portrait" in text, \
            f"{name}: without this the elf ref is used as artwork to print"
        # The second sample rendered the elf as a full red vest with a belt — a
        # different product. The real print is a deep V with striped piping and
        # no belt; both facts have to be in the prompt or it drifts back.
        assert "single deep narrow V" in text and "no belt and no buckle" in text, \
            f"{name}: the elf print drifts into a full vest without the V and the no-belt line"
        assert "elf costume" in text and "Santa costume" in text, \
            f"{name}: both SKUs must be described, not pointed at"
        assert REVEAL in text, f"{name}: missing the coats-off reveal — the repeated action"
        assert "same beat" in text or "same moment" in text or "side by side" in text, \
            f"{name}: the two reveals must land together, not in sequence"
        assert FRAMING in text, f"{name}: missing FRAMING — the prints vanish during the payoff"
        assert MOTION in text and SPEED in text, f"{name}: missing MOTION/SPEED"
        assert CLEAN in text, f"{name}: missing the no-on-screen-text clause"
        assert any(w in text for w in ("laughing", "laugh", "crack up")), \
            f"{name}: no bystander reaction — the reaction IS the proof"
        assert "only action" in text, f"{name}: doesn't pin a single beat"
        assert "no dialogue" in text and "ambient:" in text, f"{name}: missing audio tail"

    print(f"check ok — {len(SHOTS)} shots, both SKUs in every frame via "
          f"{len(REFS)} reference elements, generate {GEN_SECONDS}s each, "
          f"trim to {trims} = {total}s, no on-screen text")


def _readback_problems(data: dict) -> list[str]:
    """What Flow actually did, vs what this cut needs. Empty list = good."""
    problems = []

    refs = data.get("flow_reference_media_id") or ""
    landed = [r for r in refs.split(" + ") if r.strip()]
    if len(landed) != len(REFS):
        problems.append(f"{len(landed)} reference chip(s), expected {len(REFS)}: {refs!r}")

    model = data.get("flow_model") or ""
    if "Omni" not in model:
        problems.append(f"generated on {model!r}, not Omni — the sub-mode switch "
                        f"may have reset the model")

    got = data.get("duration_seconds")
    if got is not None and abs(float(got) - float(GEN_SECONDS)) > 1.0:
        problems.append(f"clip is {float(got):.1f}s, asked for {GEN_SECONDS}s")

    return problems


def _wanted(names: list[str]) -> list[tuple]:
    if not names:
        return SHOTS
    picked = [s for s in SHOTS if s[0].split("_")[0] in names]
    if not picked:
        raise SystemExit(f"no shot matches {names} — ids are "
                         + ", ".join(s[0].split("_")[0] for s in SHOTS))
    return picked


def run_videos(names: list[str] | None = None) -> int:
    from tools.video.flow_video import FlowVideo

    os.environ.setdefault("FLOW_PROJECT_URL", PROJECT_URL)
    LOCK.unlink(missing_ok=True)
    VIDEO.mkdir(parents=True, exist_ok=True)
    tool, results = FlowVideo(), []

    for shot in _wanted(names or []):
        name = shot[0]
        out = VIDEO / f"{name}.mp4"
        if out.is_file() and out.stat().st_size > 200_000:
            print(f"skip {name}", flush=True)
            continue

        began = time.time()
        result = tool.execute({
            "prompt": prompt_for(shot),
            "operation": "text_to_video",
            "model_variant": "Omni",
            "duration": GEN_SECONDS,
            "aspect_ratio": "9:16",
            "resolution": "720p",
            "reference_images": [str(r) for r in REFS],
            "output_path": str(out),
            "timeout_seconds": 900,
        })
        took = round(time.time() - began, 1)
        row = {"name": name, "ok": result.success, "seconds": took}
        if result.success:
            row["credits"] = result.data.get("flow_credits")
            row["refs"] = result.data.get("flow_reference_media_id")
            row["model"] = result.data.get("flow_model")
            # Elements sub-mode had never run before this script. A clip can come
            # back valid, on time and one SKU short: Flow attaches what it can and
            # says nothing. Read back what it actually did before banking the file.
            problems = _readback_problems(result.data)
            if problems:
                row["ok"] = False
                row["error"] = "; ".join(problems)
                print(f"{name}: attached wrong — {row['error']}", flush=True)
                print(f"   kept at {out} for inspection", flush=True)
                results.append(row)
                continue
        else:
            row["error"] = result.error
            out.unlink(missing_ok=True)
        results.append(row)
        print(f"{name}: {'ok' if result.success else 'FAILED'} ({took}s)", flush=True)
        if not result.success:
            print(f"   {result.error}", flush=True)

    ledger = PROJECT / "podsweater_duo_result.json"
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
    for name, trim, *_ in SHOTS:
        src = VIDEO / f"{name}.mp4"
        if not src.is_file():
            print(f"missing {src} — run `videos` first")
            return 1
        dst = CUT / f"_duotrim_{name}.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src),
                        "-t", str(trim), "-c:v", "libx264", "-preset", "slow",
                        "-crf", "18", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "160k", str(dst)], check=True)
        parts.append(dst)

    listing = CUT / "_duoconcat.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    out = CUT / "podsweater_duo_9x16.mp4"
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
    if mode == "sample":
        raise SystemExit(run_videos(["01"]))
    if mode == "videos":
        raise SystemExit(run_videos(sys.argv[2:]))
    if mode == "cut":
        raise SystemExit(run_cut())
    raise SystemExit(f"usage: {sys.argv[0]} [check | sample | videos | cut] [shot-id ...]")
