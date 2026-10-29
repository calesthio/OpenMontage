"""Wrappiness "dad belly" AOP sweatshirt — design-showcase / UGC-reaction ad.

    python scripts/_gen_wrappiness_ad.py check    # checklist, spends nothing
    python scripts/_gen_wrappiness_ad.py hero     # the model-wearing-it still (0 credits)
    python scripts/_gen_wrappiness_ad.py stills   # one still per beat (0 credits)
    python scripts/_gen_wrappiness_ad.py videos   # one clip per beat (12 credits each at 8s)
    python scripts/_gen_wrappiness_ad.py cut      # trim to the beat sheet + stitch

Product: https://wrappiness.co/products/funny-christmas-personalized-all-over-print-sweatshirt
A skin-tone crewneck printed with a photographic hairy belly, red suspenders in a
deep V, a string of Christmas lights across the chest and a plush snowman sitting
at the navel. Product shots in `assets/product/`.

Format. Keeps the measured pacing of `projects/_analysis/fb_dropship_ref/` —
4 beats at [4.2, 2.1, 2.2, 1.5] = 10.0s, accelerating, at most one word spoken,
no on-screen text — but drops its mechanic. The brief asks for design showcase
plus UGC reaction, so the gag is the double-take and the snowman, and nobody
takes anything off. That also sidesteps the refusal in `FINDINGS.md` §2 by
construction rather than by wording, which is the only legitimate way to.

Cast. The product mockups use a heavyset bearded man in his fifties. The brief
asks for a different model, so this uses a slim young woman — the printed dad
belly reads instantly as a print on her, which is what makes it both a clearer
showcase and a better joke.

Read `projects/wrappiness-ad/FINDINGS.md` before editing any prompt here.
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

PROJECT = Path("projects/wrappiness-ad")
PRODUCT = PROJECT / "assets" / "product"
STILL = PROJECT / "assets" / "stills"
VIDEO = PROJECT / "assets" / "video"
CUT = PROJECT / "renders"

PROJECT_URL = "https://flow.google.com/project/0ebed0ec-2661-4413-851f-9fa34078c90f?hl=vi"
LOCK = Path.home() / ".openmontage" / "flow_video.lock"

GEN_SECONDS = "8"

# The flat lay and one worn mockup. FINDINGS.md §1: the print is carried by the
# reference, never by prose, and the flat lay alone lost the drape.
PRODUCT_REFS = [PRODUCT / "flat.jpg", PRODUCT / "mk-1.jpg"]
HERO = STILL / "hero.jpg"

# ---------------------------------------------------------------- locked blocks

MODEL = ("THE MODEL is a slim woman in her twenties with long straight black "
         "hair, no make-up beyond a little lip colour, in plain blue jeans and "
         "white trainers. ")

# FINDINGS.md §1. Says what the garment IS and how it is printed, and nothing
# whatsoever about what the design depicts.
GARMENT_FROM_PRODUCT = (
    "She wears the sweatshirt from the reference photos, with the printed design "
    "identical in every detail — same artwork, same colours, same size, same "
    "position on the body — and the garment cut and sleeves identical too. It is "
    "a photographic all-over print on smooth sweatshirt fleece, not knitted, not "
    "embroidered and not a cartoon drawing. The printed design is a picture on "
    "fabric, worn over her own clothes; she is fully dressed and stays fully "
    "dressed. Nothing from a reference photo is reprinted onto the garment as a "
    "portrait. ")

GARMENT_FROM_HERO = (
    "She wears exactly the sweatshirt she wears in the reference photo, with the "
    "printed design identical in every detail, and her face identical to the "
    "reference photo. It is a photographic all-over print on smooth sweatshirt "
    "fleece, not knitted, not embroidered and not a cartoon drawing. She is fully "
    "dressed and stays fully dressed. ")

CLEAN = ("There is no text anywhere in the frame: no caption, no subtitle, no "
         "title card, no sticker, no logo, no watermark and no graphic overlay of "
         "any kind. No writing appears on any wall, screen or surface in shot. "
         # Caught in the group beat: the other people's own jumpers came back
         # carrying half-legible slogan text. It is set dressing rather than an
         # overlay, but it still puts broken words on screen.
         "Nobody else in shot wears clothing with any writing, slogan or lettering "
         "on it — their tops are plain or patterned only. ")

MEDIUM = ("Realistic candid smartphone photo, natural indoor party light, "
          "slightly imperfect framing, not a studio advert and not an "
          "illustration. Vertical 9:16. ")

HOLD = ("Everything in the clip stays dressed exactly as in the first frame for "
        "the whole clip; no clothing is put on, taken off or changed. Handheld "
        "phone footage that moves slightly and continuously, one continuous take "
        "with no cut. Everything runs at normal real-time speed, 1x, not slow "
        "motion. ")

AUDIO_TAIL = ("ambient: party room noise and a short burst of genuine laughter. "
              "no dialogue, no music, no voice-over.")

# The hero still is the one image the whole ad is pinned to, so it is framed to
# show the print whole: the lights at the collar down to the snowman at the hem.
HERO_PROMPT = (
    MEDIUM
    + "A living room at Christmas, a lit tree and a sofa behind her. "
    + MODEL + GARMENT_FROM_PRODUCT
    + "She stands facing the camera square on, shown from the knees up, arms "
      "relaxed at her sides, smiling straight down the lens. The whole printed "
      "front is visible from the collar to the hem, unobstructed, with nothing "
      "crossing in front of it. "
    + CLEAN)

# (name, trim_seconds, still_prompt_tail, motion)
# Pacing lifted from the measured reference: 4.2 / 2.1 / 2.2 / 1.5, accelerating.
BEATS = [
    ("01_doubletake", 4.2,
     "A kitchen at a house party, a counter with drinks and three friends "
     "standing at it with their backs half turned. She is walking past them "
     "towards the camera, the printed front fully visible. One friend has just "
     "started to turn her head towards her. ",
     "She walks slowly past the group towards the camera. One friend glances "
     "up, looks away, then snaps her head back for a second look and stares. "
     "That is the only action. "),

    ("02_showcase", 2.1,
     "The same kitchen, softly out of focus behind her. The camera is close in "
     "on the printed front of the sweatshirt, filling most of the frame from the "
     "string of lights at the collar down to the snowman at the hem, with her "
     "chin just visible at the top of frame. ",
     "The camera pushes slowly in on the printed front and holds. She stands "
     "still. That is the only action. "),

    ("03_touch", 2.2,
     "The same kitchen. A friend is standing beside her, leaning in with one "
     "hand reaching towards the small plush snowman at the bottom of the print. "
     "Both of them are in frame, the printed front facing the camera. ",
     "The friend reaches out, taps the little snowman on the front of the "
     "sweatshirt with one finger, and bursts out laughing. She laughs too. That "
     "is the only action. "),

    ("04_group", 1.5,
     "The same kitchen, four friends now crowded around her for a photo, all of "
     "them laughing, her in the middle with the printed front facing the camera "
     "and unobstructed. ",
     "The group crowds in around her laughing and one of them points at the "
     "print. That is the only action. "),
]

TARGET_TOTAL = 10.0


def still_prompt(beat) -> str:
    _, _, setting, _ = beat
    return (MEDIUM + setting + MODEL + GARMENT_FROM_HERO
            + "The printed front of the sweatshirt faces the camera and is never "
              "turned away, never covered by an arm and never leaves the frame. "
            + CLEAN)


def video_prompt(beat) -> str:
    _, _, _, motion = beat
    return (MEDIUM + motion + HOLD + CLEAN + AUDIO_TAIL)


def check() -> None:
    assert len(BEATS) == 4, "the reference ad is four beats"
    for ref in PRODUCT_REFS:
        assert ref.is_file(), f"missing product image: {ref}"

    trims = [t for _, t, _, _ in BEATS]
    for earlier, later in zip(trims, trims[1:]):
        assert later <= earlier + 0.1, f"beats must not grow: {trims}"
    assert trims[0] >= 2 * trims[-1], f"beat 1 should be ~2x the last: {trims}"
    total = round(sum(trims), 2)
    assert total == TARGET_TOTAL, f"beats total {total}s, expected {TARGET_TOTAL}s"
    for name, trim, *_ in BEATS:
        assert trim <= float(GEN_SECONDS), f"{name}: cannot trim {trim}s from {GEN_SECONDS}s"

    settings = [s for _, _, s, _ in BEATS]
    assert len(set(settings)) == len(settings), "every beat needs its own framing"

    # FINDINGS.md §1: the print is never described, only pointed at.
    for label, text in [("hero", HERO_PROMPT)] + [
            (b[0], still_prompt(b)) for b in BEATS]:
        for banned in ("suspender", "belly", "torso", "snowman print", "hairy",
                       "chest hair", "navel", "Christmas lights print"):
            assert banned not in text, (
                f"{label}: {banned!r} describes the print — four prose attempts "
                f"failed; let the reference photo carry it (FINDINGS.md §1)")
        assert "identical in every detail" in text, \
            f"{label}: must pin the print to the reference photo"
        assert "not knitted, not embroidered and not a cartoon drawing" in text, \
            f"{label}: without this the print renders as a knit or as vector art"
        assert CLEAN in text, f"{label}: missing the no-on-screen-text clause"
        assert "fully dressed" in text, \
            f"{label}: this print reads as a bare torso — say she is dressed"

    # FINDINGS.md §2/§3: no clip may describe clothing coming off or changing.
    for beat in BEATS:
        name, text = beat[0], video_prompt(beat)
        assert HOLD in text, f"{name}: missing the stays-dressed hold"
        for banned in ("take off", "takes off", "pull open", "pulls open",
                       "revealing", "reveal", "lifts her", "undress"):
            assert banned not in text, (
                f"{name}: {banned!r} is the wording Flow refuses next to this "
                f"kind of print (FINDINGS.md §2) — the ad has no undressing beat")
        assert "only action" in text, f"{name}: doesn't pin a single beat"
        assert "no dialogue" in text and "ambient:" in text, f"{name}: missing audio tail"

    # Showcase and reaction both have to be in the cut, or it is not the brief.
    assert any("pushes slowly in on the printed front" in video_prompt(b) for b in BEATS), \
        "no showcase beat — the brief asks the design to get its own screen time"
    reacting = sum(1 for b in BEATS
                   if any(w in video_prompt(b) for w in ("stares", "laughing", "laughs")))
    assert reacting >= 3, f"only {reacting} beats end on a reaction — this is a UGC reaction ad"

    print(f"check ok — {len(BEATS)} beats at {trims} = {total}s, showcase + "
          f"reaction, no undressing beat, no on-screen text")


def _wanted(names: list[str]) -> list[tuple]:
    if not names:
        return BEATS
    picked = [b for b in BEATS if b[0].split("_")[0] in names]
    if not picked:
        raise SystemExit(f"no beat matches {names} — ids are "
                         + ", ".join(b[0].split("_")[0] for b in BEATS))
    return picked


def _image(prompt: str, refs: list[Path], out: Path) -> tuple[bool, str]:
    from tools.graphics.flow_image import FlowImage

    os.environ.setdefault("FLOW_PROJECT_URL", PROJECT_URL)
    LOCK.unlink(missing_ok=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    result = FlowImage().execute({
        "prompt": prompt,
        "model_variant": "Pro",
        "aspect_ratio": "9:16",
        "n": 1,
        "reference_images": [str(r) for r in refs],
        "output_path": str(out),
        "timeout_seconds": 600,
    })
    return result.success, result.error or ""


def run_hero() -> int:
    if HERO.is_file() and HERO.stat().st_size > 50_000:
        print(f"skip hero — {HERO} exists")
        return 0
    ok, err = _image(HERO_PROMPT, PRODUCT_REFS, HERO)
    print(f"hero: {'ok' if ok else 'FAILED'}")
    if not ok:
        print(f"   {err}")
    return 0 if ok else 1


def run_stills(names: list[str] | None = None) -> int:
    if not HERO.is_file():
        print("no hero still yet — run `hero` first")
        return 1
    failed = []
    for beat in _wanted(names or []):
        name = beat[0]
        out = STILL / f"{name}.jpg"
        if out.is_file() and out.stat().st_size > 50_000:
            print(f"skip {name}", flush=True)
            continue
        ok, err = _image(still_prompt(beat), [HERO], out)
        print(f"{name}: {'ok' if ok else 'FAILED'}", flush=True)
        if not ok:
            print(f"   {err}", flush=True)
            failed.append(name)
    if failed:
        print("failed:", ", ".join(failed))
    return 1 if failed else 0


def run_videos(names: list[str] | None = None) -> int:
    from tools.video.flow_video import FlowVideo

    os.environ.setdefault("FLOW_PROJECT_URL", PROJECT_URL)
    LOCK.unlink(missing_ok=True)
    VIDEO.mkdir(parents=True, exist_ok=True)
    tool, results = FlowVideo(), []

    for beat in _wanted(names or []):
        name = beat[0]
        out = VIDEO / f"{name}.mp4"
        if out.is_file() and out.stat().st_size > 200_000:
            print(f"skip {name}", flush=True)
            continue
        still = STILL / f"{name}.jpg"
        if not still.is_file():
            print(f"{name}: missing {still} — run `stills` first", flush=True)
            results.append({"name": name, "ok": False, "error": f"missing {still}"})
            continue

        began = time.time()
        result = tool.execute({
            "prompt": video_prompt(beat),
            "operation": "image_to_video",
            "reference_image_path": str(still),
            "model_variant": "Omni",
            "duration": GEN_SECONDS,
            "aspect_ratio": "9:16",
            "resolution": "720p",
            "output_path": str(out),
            "timeout_seconds": 900,
        })
        took = round(time.time() - began, 1)
        row = {"name": name, "ok": result.success, "seconds": took}
        if result.success:
            row["credits"] = result.data.get("flow_credits")
            row["model"] = result.data.get("flow_model")
        else:
            row["error"] = result.error
            out.unlink(missing_ok=True)
        results.append(row)
        print(f"{name}: {'ok' if result.success else 'FAILED'} ({took}s)", flush=True)
        if not result.success:
            print(f"   {result.error}", flush=True)

    ledger = PROJECT / "wrappiness_videos_result.json"
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
    for name, trim, *_ in BEATS:
        src = VIDEO / f"{name}.mp4"
        if not src.is_file():
            print(f"missing {src} — run `videos` first")
            return 1
        dst = CUT / f"_trim_{name}.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src),
                        "-t", str(trim), "-c:v", "libx264", "-preset", "slow",
                        "-crf", "18", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "160k", str(dst)], check=True)
        parts.append(dst)

    listing = CUT / "_concat.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    out = CUT / "wrappiness_ad_9x16.mp4"
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
    if mode == "hero":
        raise SystemExit(run_hero())
    if mode == "stills":
        raise SystemExit(run_stills(sys.argv[2:]))
    if mode == "videos":
        raise SystemExit(run_videos(sys.argv[2:]))
    if mode == "cut":
        raise SystemExit(run_cut())
    raise SystemExit(f"usage: {sys.argv[0]} [check | hero | stills | videos | cut] [beat-id ...]")
