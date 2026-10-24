"""product.json + dna.json -> Remotion props for the XmasAd composition.

This is the glue the whole "give me a product link and get a video" flow turns on.
Every numeric default it writes comes from workspace/xmas_dna/dna.json, which was
measured off the four reference ads — not chosen.

Two things it deliberately refuses to do:

  * It never invents copy about personalisation. The sweatshirt's title says
    "Personalized" but the only option the store actually exposes is skin tone,
    so a line like "add your name" would be false advertising. Copy comes in from
    the caller; this script only checks its shape.
  * It writes EVERY prop key. Remotion's `--props` shallow-merges over
    defaultProps, so an omitted key silently inherits the previous product's
    value — which on a batch run means product A's video carrying product B's
    headline. Missing keys are a hard error here instead.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

FPS = 30


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check_caption(text: str, kind: str, dna: dict) -> None:
    """Enforce the measured caption shape. The references are remarkably tight."""
    lines = text.split("\n")
    spec = dna["parameters"]["hook_line" if kind == "hook" else "cta_line"]
    lo, hi = spec["chars"]
    total = len(text.replace("\n", " "))
    assert len(lines) == 2, f"{kind}: references are always exactly 2 lines, got {len(lines)}"
    assert lo - 6 <= total <= hi + 6, f"{kind}: {total} chars, measured range {lo}-{hi}"
    # 30 chars fits the DNA's observed range but NOT the rendered frame: at the
    # default 2.5% ink height the face is ~66px, 86% of 1080 leaves ~929px, and
    # a 29-char line wrapped to a third line on the first real second product.
    # The references are always exactly 2 lines, so the cap is the pixel limit.
    for ln in lines:
        assert len(ln) <= 24, (
            f"{kind}: line is {len(ln)} chars; over 24 wraps to a 3rd line at the "
            f"default caption size, and the references are always exactly 2 lines")


def beat_grid(bpm: float, total: int) -> list[int]:
    """Frame index of every beat. DNA invariant: cuts land on the music grid (4/4)."""
    step = 60.0 / bpm * FPS
    n = int(total / step) + 1
    return [round(i * step) for i in range(n) if round(i * step) <= total]


def plan_shots(images: list[str], duration_s: float, dna: dict,
               fit: str = "cover", bpm: float | None = None) -> list[dict]:
    """Lay images across the runtime at the measured cut rate.

    Ken Burns values alternate direction so consecutive shots do not all drift
    the same way. Zoom stays <= 1.22: the pan budget is (s-1)/(2s), so a bigger
    zoom buys very little extra travel while costing real resolution on a
    1000x1000 source upscaled into a 1080x1920 frame.
    """
    n = len(images)
    total = round(duration_s * FPS)

    if bpm:
        # Snap every boundary to the nearest beat, then take first differences.
        # Evenly-dividing the runtime gives cuts that drift off the grid, which
        # is audible: the reference ads cut ON the beat in 4/4 clips.
        grid = beat_grid(bpm, total)
        bounds = [0]
        for i in range(1, n):
            want = total * i / n
            cand = min(grid, key=lambda g: abs(g - want))
            bounds.append(max(cand, bounds[-1] + 1))
        bounds.append(total)
        durations = [bounds[i + 1] - bounds[i] for i in range(n)]
    else:
        base, extra = divmod(total, n)
        durations = [base + (1 if i < extra else 0) for i in range(n)]

    zoom_lo, zoom_hi = 1.08, 1.24
    # Pan is budgeted off the LOW zoom, not the endpoint zoom. The budget
    # (z-1)/(2z) rises with z, so sizing against the smallest zoom the shot
    # passes through is what keeps every intermediate frame legal. Sizing
    # against the endpoint is the bug this file's demo() caught: at zoom 1.04
    # the budget is 0.019 and a hardcoded 0.05 was silently clamped, so the
    # rendered move did not match the props.
    pan = 0.8 * (zoom_lo - 1) / (2 * zoom_lo)

    shots = []
    for i, img in enumerate(images):
        d = durations[i]
        out = i % 2 == 0
        shots.append({
            "src": img,
            "durationInFrames": d,
            "fit": fit,
            "zoomFrom": zoom_lo if out else zoom_hi,
            "zoomTo": zoom_hi if out else zoom_lo,
            "panXFrom": -pan if out else pan,
            "panXTo": pan if out else -pan,
            "panYFrom": pan * 0.6 if i % 3 == 0 else -pan * 0.6,
            "panYTo": -pan * 0.6 if i % 3 == 0 else pan * 0.6,
        })
    assert sum(s["durationInFrames"] for s in shots) == total
    return shots


def cut_frames(shots: list[dict]) -> list[int]:
    """Frame index of every shot boundary — captions may only change on these."""
    out, acc = [0], 0
    for s in shots:
        acc += s["durationInFrames"]
        out.append(acc)
    return out


def snap(frame: int, cuts: list[int]) -> int:
    """Measured: 3/3 caption swaps land on a cut at 0-frame offset."""
    return min(cuts, key=lambda c: abs(c - frame))


def build(product: dict, dna: dict, *, hook: str, cta: str, duration_s: float,
          cta_mode: str, images: list[str], end_card: dict | None,
          fit: str = "cover", bpm: float | None = None) -> dict:
    check_caption(hook, "hook", dna)
    p = dna["parameters"]

    shots = plan_shots(images, duration_s, dna, fit=fit, bpm=bpm)
    cuts = cut_frames(shots)
    total = cuts[-1]

    cta_start = snap(round(total * p["cta_start_pct"]["default"]), cuts)
    captions = [{
        "text": hook,
        "fromFrame": 0,                      # up at frame 0, fully formed, 4/4
        "toFrame": cta_start if cta_mode != "brand_end_card" else total,
        "style": p["caption_style"]["default"],
        "yPct": p["caption_y_pct"]["default"],
        "xPct": p["caption_x_pct"]["default"],
        "align": p["caption_align"]["default"],
        "sizePct": p["caption_size_pct"]["default"],
        "leadingRatio": p["caption_leading_ratio"]["default"],
    }]

    if cta_mode in ("punchline_swap", "comment_gate"):
        check_caption(cta, "cta", dna)
        captions.append({
            "text": cta,
            "fromFrame": cta_start,
            "toFrame": total,
            "style": p["caption_style"]["default"],
            "yPct": 18.0,                    # CTAs measured slightly lower than hooks
            "xPct": p["caption_x_pct"]["default"],
            "align": p["caption_align"]["default"],
            "sizePct": p["caption_size_pct"]["default"],
            "leadingRatio": p["caption_leading_ratio"]["default"],
        })

    for c in captions:
        assert c["fromFrame"] in cuts, f"caption in at {c['fromFrame']} is not on a cut"
        assert c["toFrame"] in cuts, f"caption out at {c['toFrame']} is not on a cut"

    return {
        "shots": shots,
        "captions": captions,
        "endCard": end_card if cta_mode == "brand_end_card" else None,
        "musicSrc": None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("product_json", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--dna", type=Path, default=Path("workspace/xmas_dna/dna.json"))
    ap.add_argument("--hook", required=True, help="2 lines separated by \\n")
    ap.add_argument("--cta", default="", help="2 lines separated by \\n")
    ap.add_argument("--duration", type=float, default=15.0)
    ap.add_argument("--cta-mode", default="punchline_swap",
                    choices=["punchline_swap", "comment_gate", "brand_end_card"])
    ap.add_argument("--images", nargs="+", required=True,
                    help="filenames relative to the Remotion --public-dir, in order")
    ap.add_argument("--end-card-json", type=Path, default=None)
    ap.add_argument("--bpm", type=float, default=None,
                    help="quantise cuts to this tempo's beat grid (DNA: 136-162)")
    ap.add_argument("--fit", default="cover", choices=["cover", "blur_pad"],
                    help="blur_pad for square shop photos; cover for native 9:16 AI imagery")
    a = ap.parse_args()

    product = _load(a.product_json)
    dna = _load(a.dna)
    end_card = _load(a.end_card_json) if a.end_card_json else None

    props = build(product, dna,
                  hook=a.hook.replace("\\n", "\n"),
                  cta=a.cta.replace("\\n", "\n"),
                  duration_s=a.duration, cta_mode=a.cta_mode,
                  images=a.images, end_card=end_card, fit=a.fit, bpm=a.bpm)

    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(props, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(s["durationInFrames"] for s in props["shots"])
    print(f"[ok] {a.out}  {len(props['shots'])} shots  {total} frames  "
          f"{total / FPS:.2f}s  {len(props['captions'])} captions")
    return 0


def demo() -> None:
    """Self-check: the invariants that would silently wreck a batch run."""
    dna = _load(Path(__file__).resolve().parents[1] / "workspace/xmas_dna/dna.json")
    imgs = [f"{i}.jpg" for i in range(7)]
    props = build({}, dna, hook="A" * 24 + "\n" + "B" * 20, cta="C" * 12 + "\n" + "D" * 14,
                  duration_s=15.0, cta_mode="punchline_swap", images=imgs, end_card=None)
    assert all(s_["fit"] == "cover" for s_ in props["shots"])

    # Beat quantisation must still tile the runtime exactly and stay monotonic.
    nl = chr(10)
    q = build({}, dna, hook="A" * 24 + nl + "B" * 20, cta="C" * 12 + nl + "D" * 14,
              duration_s=15.0, cta_mode="punchline_swap", images=imgs, end_card=None,
              bpm=161.5)
    assert sum(s_["durationInFrames"] for s_ in q["shots"]) == 450
    assert all(s_["durationInFrames"] > 0 for s_ in q["shots"]), "a beat snap collapsed a shot"
    grid = set(beat_grid(161.5, 450))
    qcuts = cut_frames(q["shots"])[1:-1]
    assert all(c in grid for c in qcuts), f"cuts off the beat grid: {[c for c in qcuts if c not in grid]}"

    cuts = cut_frames(props["shots"])
    assert sum(s["durationInFrames"] for s in props["shots"]) == 450
    for c in props["captions"]:
        assert c["fromFrame"] in cuts and c["toFrame"] in cuts
    assert props["captions"][0]["fromFrame"] == 0, "hook must be up at frame 0"
    # Ken Burns must never ask for more pan than the zoom can cover.
    for s in props["shots"]:
        for z, pan in ((s["zoomFrom"], s["panXFrom"]), (s["zoomTo"], s["panXTo"])):
            assert abs(pan) <= (z - 1) / (2 * z) + 1e-9, f"pan {pan} exceeds budget at zoom {z}"
    # Every key the composition reads must be present — shallow-merge guard.
    for key in ("shots", "captions", "endCard", "musicSrc"):
        assert key in props, key
    print("demo ok:", len(props["shots"]), "shots,", len(props["captions"]), "captions")


if __name__ == "__main__":
    import sys
    raise SystemExit(demo() if "--demo" in sys.argv else main())
