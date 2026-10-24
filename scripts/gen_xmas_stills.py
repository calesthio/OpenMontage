"""Generate the model stills for the Christmas AOP-sweatshirt ad via Flow.

Reads `skills/creative/printed-apparel-ad.md` as law. The three rules it encodes
are not style preferences — each one is a recorded failure from this project:

  1. NEVER describe the printed design. Four prose attempts produced four wrong
     garments. The reference photo is the only thing allowed to carry the print,
     so the prompt pins it by reference and says nothing about what it depicts.
  2. The hero still is the single pin. Beat stills are generated FROM the hero,
     never from the product photos again, or the model's face drifts per beat.
  3. No undressing beat. Flow refuses to animate a garment coming off when the
     print shows skin, and rewording to slip past a safety control is not an
     option. The format does not need the beat.

Flow images cost 0 credits, so every argument is settled here rather than at the
12-credits-per-clip video stage.

Prerequisite: Chrome must be listening on the CDP port AND signed in to Flow:
    chrome.exe --remote-debugging-port=9222 --user-data-dir="<dedicated dir>"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Running a file in scripts/ puts scripts/ on sys.path, not the repo root, so
# `import tools...` fails unless the root is added explicitly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Words that describe the PRINT rather than the person or the place. Any of them
# in a prompt means the design is being talked about instead of referenced.
BANNED_PRINT = (
    "suspender", "belly", "torso", "hairy", "navel", "chest hair", "abs", "pecs",
    "snowman print", "printed design of", "design shows", "artwork shows",
    "fake body", "muscle", "skin print",
)

# The refused wording from the recorded Flow rejections.
BANNED_ACTION = (
    "take off", "takes off", "taking off", "pull open", "pulls open",
    "revealing", "reveal the", "undress", "remove the sweatshirt", "lift the",
)

PIN = (
    "The person wears exactly the sweatshirt from the reference photo, with the "
    "printed design identical in every detail - same artwork, same colours, same "
    "size, same position on the body. It is a photographic all-over print on smooth "
    "sweatshirt fleece, not knitted, not embroidered and not a cartoon drawing. "
    "Nothing from a reference photo is reprinted onto the garment as a portrait."
)

# The model the brief asked for, described as a PERSON — never as the garment.
CAST = (
    "A cheerful heavyset man in his late forties with noticeably thinning hair and "
    "a short greying beard, warm and goofy, the friend who makes everyone laugh"
)

# "khong duoc do" - the brief's hard note. Stiff catalogue posing is the failure
# mode for generated people, so every prompt names an action already in progress.
PERFORMANCE = (
    "caught mid-movement in a candid unposed moment, natural comedic timing, "
    "relaxed loose body language, genuine open-mouthed laugh with crinkled eyes, "
    "never standing still and never posing straight at the camera"
)

BEATS = {
    "hero": (
        f"{CAST}, standing in a warm living room at a Christmas house party, "
        "string lights and a decorated tree behind him, {perf}, "
        "gesturing down at himself with both hands as if presenting. "
        "Full upper body from the knees up, the whole front of the sweatshirt "
        "visible and unobstructed from collar to hem, arms held wide and clear of "
        "the front of the garment. Vertical 9:16 phone photo, natural indoor light."
    ),
    "party_react": (
        "The same man from the reference, same face, same build, same hair, same "
        "sweatshirt. He is at the Christmas party mid-laugh while two friends beside "
        "him double over laughing and point at him, {perf}. "
        "Vertical 9:16 candid phone snapshot, warm indoor light."
    ),
    # Front-on is not a framing preference, it is a fidelity constraint. The first
    # pass had him turned away pushing a trolley and the generator painted the
    # FRONT design onto his back. All seven product photos are front-facing, so
    # there is no evidence of what the back looks like - inventing one would be a
    # false claim about the garment. Keep every beat facing camera.
    "aisle": (
        "The same man from the reference, same face, same build, same hair, same "
        "sweatshirt, facing the camera front-on in a supermarket Christmas aisle "
        "with a trolley in front of him, grinning straight down the lens, {perf}. "
        "His whole chest and stomach face the camera; his back is never shown. "
        "Shoppers blurred behind him. Vertical 9:16 candid phone snapshot."
    ),
    "office": (
        "The same man from the reference, same face, same build, same hair, same "
        "sweatshirt, at an office Christmas party holding a paper cup, leaning back "
        "laughing while colleagues around him react, {perf}. "
        "Vertical 9:16 candid phone snapshot, string lights and tinsel."
    ),
    "pub_group": (
        "The same man from the reference, same face, same build, same hair, same "
        "sweatshirt, in a busy pub raising a glass with a group of friends who are "
        "all laughing at him, {perf}. "
        "Vertical 9:16 candid phone snapshot, warm pub light."
    ),
    # v3 shot 1 is exactly this: the fitting-room step-out. It is a step THROUGH a
    # curtain, never a change of clothes - the ad has no undressing beat and the
    # guard rejects that wording anyway.
    "fitting_room": (
        "The same man from the reference, same face, same build, same hair, same "
        "sweatshirt, stepping out through a shop fitting-room curtain with both arms "
        "spread wide, grinning at two friends who burst out laughing, {perf}. "
        "His whole chest and stomach face the camera. "
        "Vertical 9:16 candid phone snapshot, bright shop lighting."
    ),
    "street_night": (
        "The same man from the reference, same face, same build, same hair, same "
        "sweatshirt, on a night street outside a house covered in Christmas lights, "
        "a small crowd around him laughing and pointing at him, {perf}. "
        "He faces the camera front-on. "
        "Vertical 9:16 candid phone snapshot, warm festoon light."
    ),
    "mall": (
        "The same man from the reference, same face, same build, same hair, same "
        "sweatshirt, walking toward the camera down a busy shopping-mall concourse "
        "carrying gift bags, a woman beside him covering her face laughing, {perf}. "
        "Vertical 9:16 candid phone snapshot, bright mall light."
    ),
    # DNA: 3 of the 4 references put the SAME product on 3+ different people. One
    # wearer is inside the observed range (v3 has one) but the montage reads richer
    # with a second body. Cast against the mockup's body type, per the skill.
    "second_wearer": (
        "A slim young woman in her twenties with long dark hair, wearing the "
        "sweatshirt from the reference photo, at a Christmas house party holding a "
        "glass and laughing hard while friends around her crack up, {perf}. "
        "Her whole chest and stomach face the camera. "
        "Vertical 9:16 candid phone snapshot, warm indoor light."
    ),
}

# Garment-only beats. These take the GARMENT pin, not the person pin, and their
# references are the product photo rather than the hero - a cast line here is what
# puts a person into the one shot that is supposed to have none.
GARMENT_BEATS = {
    "product_reveal": (
        "The sweatshirt from the reference photo hanging on a wooden hanger on a "
        "clothing rack in a warm Christmas shop, string lights and a decorated tree "
        "behind it, shoppers blurred far in the background, no people near the "
        "garment and nobody wearing it. Vertical 9:16 photo, warm shop light."
    ),
}

GARMENT_PIN = (
    "The printed design is identical in every detail - same artwork, same colours, "
    "same size, same position on the garment. It is a photographic all-over print on "
    "smooth sweatshirt fleece, not knitted, not embroidered and not a cartoon drawing."
)


# Motion, one per beat. These drive image_to_video: the still is the first frame,
# so the prompt only has to say what MOVES. It must still never describe the print
# and must never describe clothing coming off - the same two guards apply.
MOTION = {
    # No push-in on the hero. The first pass asked for one and by the end of the
    # clip the framing had cropped the bottom of the design out of shot - on a
    # product whose whole selling point IS the design. Hold the frame on the beat
    # that has to show the garment; save camera moves for the reaction beats.
    "hero": "He laughs and gestures down at himself with both hands, shoulders shaking, "
            "then looks up at the camera still laughing. The camera holds steady and "
            "keeps his whole upper body in frame the entire time.",
    "party_react": "The friend beside him doubles over laughing and points; he turns "
                   "towards the camera grinning. Handheld, slight sway.",
    "aisle": "He pushes the trolley towards the camera, laughing, shoppers moving behind "
             "him. The camera tracks backwards to keep him framed.",
    "office": "He leans back laughing while colleagues around him react and clap. "
              "Handheld, natural wobble.",
    "pub_group": "He raises his glass and the group around him erupts laughing and "
                 "pointing. The camera drifts slowly right.",
    "fitting_room": "He steps forward through the curtain with his arms spread wide and "
                    "laughs; his two friends double over. The camera holds steady.",
    "street_night": "He laughs and shrugs at the camera while the crowd around him "
                    "cracks up and points. Handheld, slight sway.",
    "mall": "He walks towards the camera laughing and the woman beside him doubles over. "
            "The camera tracks backwards to keep them framed.",
    "second_wearer": "She laughs hard and tips her head back while the friends beside her "
                     "crack up. Handheld, natural wobble.",
    # The garment beat has no actor, so the only motion is the camera. A drift is
    # what v4 shot 1 does around the hanging garment.
    "product_reveal": "Nobody is in shot. The camera drifts slowly sideways past the "
                      "hanging garment, the string lights behind it twinkling.",
}

MOTION_PIN = (
    " The person stays dressed exactly as in the first frame for the whole clip; "
    "no clothing is put on, changed or altered, and the printed design stays "
    "identical in every detail throughout."
)


BANNED_VIEW = ("from behind", "back view", "over his shoulder", "walking away",
               "rear view", "back turned")


def guard_banned(prompt: str, label: str) -> str:
    """The checks that apply to EVERY prompt, still or motion."""
    low = prompt.lower()
    for w in BANNED_PRINT:
        assert w not in low, f"{label}: {w!r} describes the print - let the reference carry it"
    for w in BANNED_ACTION:
        assert w not in low, f"{label}: {w!r} is the refused wording - the ad has no undressing beat"
    # A back view invites the generator to invent a back print. Nothing in the
    # product photos shows the back, so an invented one is an unverifiable claim.
    for w in BANNED_VIEW:
        assert w not in low, f"{label}: {w!r} shows the back, which no product photo evidences"
    return prompt


def guard(prompt: str, label: str) -> str:
    """Still prompts additionally have to carry the two pin clauses."""
    guard_banned(prompt, label)
    assert "identical in every detail" in prompt, f"{label}: missing the pin clause"
    assert "not knitted, not embroidered and not a cartoon drawing" in prompt, f"{label}: missing the texture clause"
    return prompt


def guard_motion(prompt: str, label: str) -> str:
    """Motion prompts pin CONTINUITY instead: the first frame already carries the
    print, so what has to be nailed down is that nothing about it changes."""
    guard_banned(prompt, label)
    if label.removeprefix("motion:") not in GARMENT_BEATS:
        assert "stays dressed exactly as in the first frame" in prompt, f"{label}: missing the continuity clause"
    assert "identical in every detail" in prompt, f"{label}: missing the print-continuity clause"
    return prompt


GARMENT_MOTION_PIN = (
    " Nobody enters the frame and nobody wears the garment at any point; the printed "
    "design stays identical in every detail throughout."
)


def build_prompts() -> dict[str, str]:
    person = {
        name: guard(f"{tpl.format(perf=PERFORMANCE)} {PIN}", name)
        for name, tpl in BEATS.items()
    }
    garment = {
        name: guard(f"{tpl} {GARMENT_PIN}", name)
        for name, tpl in GARMENT_BEATS.items()
    }
    return person | garment


def build_motion_prompts() -> dict[str, str]:
    return {
        k: guard_motion(v + (GARMENT_MOTION_PIN if k in GARMENT_BEATS else MOTION_PIN),
                        f"motion:{k}")
        for k, v in MOTION.items()
    }


def animate(out_dir: Path, beats: list[str], duration: str, model: str) -> int:
    """Turn approved stills into clips. THIS SPENDS FLOW CREDITS - stills do not."""
    from tools.video.flow_video import FlowVideo
    tool = FlowVideo()
    prompts = build_motion_prompts()
    clips = out_dir / "clips"
    clips.mkdir(parents=True, exist_ok=True)

    for name in beats:
        still = out_dir / f"{name}.jpg"
        assert still.is_file(), f"{still} missing - generate and approve the still first"
        out = clips / f"{name}.mp4"
        print(f"[clip] {name}  <- {still.name}  ({duration}s, {model})")
        job = {
            "prompt": prompts[name],
            "operation": "image_to_video",
            "reference_image_path": str(still),
            "aspect_ratio": "9:16",
            "model_variant": model,
            "output_path": str(out),
        }
        # Flow only exposes a duration control for some models; asking for one it
        # is not offering fails the whole run ("Flow does not offer '4 giay'").
        # Empty duration means "take whatever this model gives" and the edit
        # trims to the DNA shot length afterwards anyway.
        if duration:
            job["duration"] = duration
        res = tool.execute(job)
        if not res.success:
            print(f"[fail] {name}: {res.error}")
            return 1
        print(f"[ok] {name} -> {res.data.get('output')}")
    return 0


def to_vertical(src: Path, dst: Path, w: int = 1080, h: int = 1920) -> None:
    """Centre-crop to 9:16 and scale to 1080x1920.

    `openai/gpt-5.4-image-2` on OpenRouter always returns 1024x1024 and ignores
    every instruction to do otherwise - including an explicit "do NOT output a
    square image". Feeding that square straight to Flow produces a 1080x1920
    clip with black bars over ~44% of the frame, which is unusable on TikTok.
    Cropping costs the outer edges of the room but keeps the subject and the
    whole printed design, which is what the shot is actually for.
    """
    import subprocess
    from PIL import Image
    iw, ih = Image.open(src).size
    cw = min(iw, int(round(ih * w / h)))
    ch = min(ih, int(round(cw * h / w)))
    x, y = (iw - cw) // 2, (ih - ch) // 2
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(src), "-vf",
                    f"crop={cw}:{ch}:{x}:{y},scale={w}:{h}:flags=lanczos",
                    "-y", str(dst)], check=True)


def generate_openrouter(out_dir: Path, beats: list[str], flat_lay: Path,
                        model: str) -> int:
    """Same beats, same guards, billed per image instead of free."""
    from tools.graphics.openrouter_image import OpenRouterImage
    tool = OpenRouterImage()
    prompts = build_prompts()
    hero_path = out_dir / "hero.jpg"
    total = 0.0

    for name in beats:
        if name == "hero":
            refs = [str(flat_lay)]
        else:
            assert hero_path.is_file(), "run --beats hero first and approve it"
            refs = [hero_path.as_posix(), str(flat_lay)]

        raw = out_dir / f"{name}_raw.png"
        print(f"[or] {name}  refs={[Path(r).name for r in refs]}")
        res = tool.execute({"prompt": prompts[name], "model": model,
                            "reference_images": refs, "output_path": str(raw)})
        if not res.success:
            print(f"[fail] {name}: {res.error}")
            return 1
        cost = float(res.data.get("usage", {}).get("cost") or 0)
        total += cost
        to_vertical(raw, out_dir / f"{name}.jpg")
        print(f"[ok] {name} -> {name}.jpg  (${cost:.3f})")

    print(f"OpenRouter spend this run: ${total:.2f}")
    return 0


def generate_codex(out_dir: Path, beats: list[str], flat_lay: Path, worn: Path | None,
                   n: int) -> int:
    """Same beats, same guards, billed to the ChatGPT subscription instead of cash.

    gpt-image-2 only offers 1024x1536 (2:3), so every still is centre-cropped to
    9:16 by `to_vertical`. Cropping a 2:3 portrait takes the sides only and keeps
    the full height - unlike the 1:1 that OpenRouter returns, which loses far more.
    """
    from tools.graphics.codex_image import CodexImage
    tool = CodexImage()
    prompts = build_prompts()
    hero_path = out_dir / "hero.jpg"

    # The WORN mockup is the reference, never the flat lay. On a print that is a
    # photograph of a bare torso the flat lay is, on its own, a picture of a bare
    # torso - and gpt-image-2's filter blocked "a man wearing this" as sexual
    # content with it attached. The worn mockup is the same print in apparel
    # context (clothed man, long sleeves) and the identical prompt generates.
    # Measured 2026-09-14: flat-lay refs -> refused; worn ref -> clean hero still.
    garment = worn or flat_lay
    assert garment.is_file(), f"garment reference not found: {garment}"

    # hero pins the cast for every ordinary beat. The garment beats and the
    # second wearer must NOT see it: hero is the reference that carries this man's
    # face, so attaching it to a shot that is meant to have nobody in it, or a
    # different person in it, is what drags him back into frame.
    no_hero = set(GARMENT_BEATS) | {"hero", "second_wearer"}

    for name in beats:
        if name in no_hero:
            refs = [str(garment)]
        else:
            assert hero_path.is_file(), (
                "beat stills must be generated from hero.jpg - run --beats hero first, "
                "review it, and only then generate the rest")
            refs = [hero_path.as_posix(), str(garment)]

        raw = out_dir / f"{name}_raw.png"
        print(f"[codex] {name}  refs={[Path(r).name for r in refs]}  n={n}")
        res = tool.execute({
            "prompt": prompts[name],
            "size": "1024x1536",
            "n": n,
            "reference_images": refs,
            "output_path": str(raw),
        })
        if not res.success:
            print(f"[fail] {name}: {res.error}")
            return 1
        # n>1 writes name_raw_1.png, name_raw_2.png; n==1 writes name_raw.png.
        produced = sorted(out_dir.glob(f"{name}_raw*.png"))
        assert produced, f"{name}: codex reported success but wrote no file"
        for i, src in enumerate(produced, 1):
            dst = out_dir / (f"{name}.jpg" if len(produced) == 1 else f"{name}_{i}.jpg")
            to_vertical(src, dst)
            print(f"[ok] {name} -> {dst.name}")

    print("Review every still before animating. Codex stills cost quota, clips cost credits.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--flat-lay", type=Path, required=True,
                    help="print ground truth: product-on-white, front-on, unoccluded")
    ap.add_argument("--worn", type=Path, default=None, help="optional worn mockup reference")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--beats", nargs="*", default=None, help="subset of beats to generate")
    ap.add_argument("--n", type=int, default=2, help="variants per beat; pick the best by eye")
    ap.add_argument("--dry-run", action="store_true", help="print prompts, generate nothing")
    ap.add_argument("--provider", default="flow", choices=["flow", "openrouter", "codex"],
                    help="flow = free, native 9:16. openrouter = billed, square, auto-cropped. "
                         "codex = ChatGPT-subscription quota, 2:3, auto-cropped.")
    ap.add_argument("--or-model", default="openai/gpt-5.4-image-2")
    ap.add_argument("--animate", action="store_true",
                    help="turn approved stills into CLIPS. Spends Flow credits; stills do not.")
    ap.add_argument("--clip-seconds", default="", choices=["", "4", "6", "8", "10"],
                    help="empty = let the model decide; the edit trims to DNA shot length")
    ap.add_argument("--clip-model", default="Fast", choices=["Lite", "Fast", "Quality", "Omni"])
    a = ap.parse_args()

    prompts = build_prompts()
    wanted = a.beats or list(prompts)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    (a.out_dir / "prompts.json").write_text(
        json.dumps({k: prompts[k] for k in wanted}, ensure_ascii=False, indent=1), encoding="utf-8")

    if a.dry_run:
        for k in wanted:
            print(f"\n=== {k} ===\n{prompts[k]}")
        print(f"\n[dry-run] {len(wanted)} prompts -> {a.out_dir / 'prompts.json'}")
        return 0

    if a.animate:
        return animate(a.out_dir, wanted, a.clip_seconds, a.clip_model)

    if a.provider == "openrouter":
        return generate_openrouter(a.out_dir, wanted, a.flat_lay, a.or_model)

    if a.provider == "codex":
        assert a.flat_lay.is_file(), f"flat-lay not found: {a.flat_lay}"
        return generate_codex(a.out_dir, wanted, a.flat_lay, a.worn, a.n)

    from tools.graphics.flow_image import FlowImage
    tool = FlowImage()

    assert a.flat_lay.is_file(), f"flat-lay not found: {a.flat_lay}"
    hero_path = a.out_dir / "hero.jpg"

    # Rule 2: the hero is generated from the product photos; every other beat is
    # generated from the HERO, so the face stays the same person throughout.
    for name in wanted:
        is_hero = name == "hero"
        if is_hero:
            refs = [str(a.flat_lay)] + ([str(a.worn)] if a.worn else [])
        else:
            assert hero_path.is_file(), (
                "beat stills must be generated from hero.jpg - run --beats hero first, "
                "review it, and only then generate the rest")
            refs = [hero_path.as_posix(), str(a.flat_lay)]

        out = a.out_dir / f"{name}.jpg"
        print(f"[gen] {name}  refs={[Path(r).name for r in refs]}")
        res = tool.execute({
            "prompt": prompts[name],
            "aspect_ratio": "9:16",
            "n": a.n,
            "reference_images": refs,
            "output_path": str(out),
        })
        if not res.success:
            print(f"[fail] {name}: {res.error}")
            return 1
        print(f"[ok] {name} -> {res.data.get('output')}")

    print("\nReview every still before animating. Flow images are free; clips are not.")
    return 0


def demo() -> None:
    """The guards are the point of this file - check they actually bite."""
    prompts = build_prompts()
    assert set(prompts) == set(BEATS) | set(GARMENT_BEATS)
    for name, p in prompts.items():
        assert "9:16" in p, name
        if name in GARMENT_BEATS:
            # The garment beats must carry NO cast line - that is the whole point
            # of keeping them separate. A person pin here puts a model in the shot.
            assert GARMENT_PIN in p, name
            assert "nobody wearing it" in p, f"{name}: nothing keeps people out of frame"
            assert CAST not in p, f"{name}: a cast line invites a person into a product-only shot"
            continue
        assert PIN in p, name
        assert "mid-movement" in p or "mid-laugh" in p, f"{name}: nothing stops a stiff pose"
    for bad, label in ((f"a hairy torso print {PIN}", "print"),
                       (f"he takes off the coat {PIN}", "action")):
        try:
            guard(bad, "t")
        except AssertionError:
            pass
        else:
            raise AssertionError(f"guard failed to catch the {label} case")
    # The hero must not reference itself.
    assert "same man from the reference" not in BEATS["hero"]
    # A second wearer that says "the same man" is not a second wearer.
    assert "same man from the reference" not in BEATS["second_wearer"]
    m = build_motion_prompts()
    assert set(m) == set(BEATS) | set(GARMENT_BEATS), "every beat needs a motion prompt"
    for name, p in m.items():
        if name in GARMENT_BEATS:
            assert "nobody wears the garment" in p, name
            continue
        assert "stays dressed exactly as in the first frame" in p, name
    print(f"demo ok: {len(prompts)} prompts + {len(m)} motion prompts, guards bite")


if __name__ == "__main__":

    raise SystemExit(demo() if "--demo" in sys.argv else main())
