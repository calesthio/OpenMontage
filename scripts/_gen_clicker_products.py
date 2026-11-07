"""Hero product shots for the "clicker charm" line — one image per charm design.

    python scripts/_gen_clicker_products.py check    # spends nothing
    python scripts/_gen_clicker_products.py images   # flow_image, 0 credits

Each charm is a separate product, shot on its own, so the set can be used as a
catalogue / carousel / thumbnail pool rather than one group photo.

**Grounded in what a PLA FDM printer actually does.** The reference creator's
real workflow is: print opaque PLA → hand-paint with acrylics → clear-coat or
resin-dip for gloss → add a metal keyring loop. So every prompt below says
opaque printed plastic with hand-painted colour and a *surface* gloss coat —
never "translucent plastic lit from within", which is an SLA/resin look PLA
cannot do at these wall thicknesses. A faint layer-line texture on the
unpainted underside is authentic and is called for on purpose.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

OUT = Path("projects/_analysis/clicker_products")

# Pasted verbatim into every prompt so the whole line reads as one product
# family shot in one sitting, not six unrelated stock photos.
STYLE = ("Realistic macro product photo, cosy craft-studio style. Soft natural "
         "window light from the left, shallow depth of field, warm and tactile. "
         "Shot on a pale weathered wood tabletop. Background is a blurred "
         "sage-green pegboard wall, softly out of focus. Vertical 9:16 phone "
         "framing. No text, no watermark, no logo, no packaging. ")

# The craft truth: opaque printed PLA, hand-painted, glossed on the surface.
MAKE = ("The charm is a small 3D-printed object in opaque PLA plastic, "
        "hand-painted with acrylic paint — tiny visible brush texture in the "
        "details — then finished with a thick glassy clear top-coat that pools "
        "slightly at the edges and catches a bright specular highlight. A small "
        "gold jump ring and keyring loop is fitted through a printed hole at the "
        "top. Faint 3D-printing layer lines are just visible on the unpainted "
        "underside. It sits about 4cm tall, held between fingertips or resting "
        "on the wood. ")

PROPS = ("A few tiny acrylic paint pots, a fine detail brush and a couple of "
         "loose gold jump rings sit blurred in the background. ")

# (name, subject)
PRODUCTS = [
    ("01_cupcake",
     "A cupcake charm: a dark chocolate-brown printed base in a pale teal "
     "fluted paper-cup shape, topped with a tall swirl of cream and pink "
     "frosting, a single glossy red cherry on top, and scattered painted "
     "sprinkle dots down the swirl."),

    ("02_donut",
     "A ring donut charm: pale biscuit-coloured dough with a thick pink "
     "strawberry icing lid that drips slightly over the edge, and multicoloured "
     "painted sprinkles scattered across the icing."),

    ("03_macaron",
     "A macaron charm: two mint-green domed shells with the characteristic "
     "ruffled 'foot' edge printed into the sides, sandwiching a thin pale cream "
     "filling that squeezes out very slightly."),

    ("04_icecream",
     "An ice cream cone charm: a printed waffle cone with a crisp cross-hatch "
     "texture, topped with a soft-serve swirl in pale mint green, with tiny "
     "painted chocolate-chip flecks."),

    ("05_lollipop",
     "A swirl lollipop charm: a flat round disc printed with a raised spiral "
     "groove, hand-painted in a rainbow pastel swirl of pink, lilac, mint and "
     "cream, on a short white stick."),

    ("06_gummybear",
     "A gummy bear charm: a chunky bear silhouette printed in translucent-red "
     "tinted plastic, hand-glossed so it reads like real jelly candy, with a "
     "faint dusting of painted sugar crystals on its shoulders."),
]


def prompt_for(subject: str) -> str:
    return STYLE + subject + " " + MAKE + PROPS


def check() -> None:
    assert len(PRODUCTS) == len({n for n, _ in PRODUCTS}), "duplicate product name"
    for name, subject in PRODUCTS:
        text = prompt_for(subject)
        assert STYLE in text, f"{name}: missing shared STYLE block"
        assert MAKE in text, f"{name}: missing the PLA/hand-paint/gloss craft block"
        # The one claim PLA cannot back up. Gummy bear is the single exception:
        # translucent filament is real and common, but it is still surface-lit,
        # never glowing from inside.
        for banned in ("lit from within", "glowing from inside", "backlit through"):
            assert banned not in text.lower(), f"{name}: {banned!r} is not a PLA look"
        low = text.lower()
        assert "no text" in low and "no watermark" in low, f"{name}: missing clean-frame clause"
    print(f"check ok — {len(PRODUCTS)} products, shared STYLE + MAKE blocks, "
          f"no impossible material claims")


def run_images(only: list[str] | None = None) -> int:
    from tools.graphics.flow_image import FlowImage

    OUT.mkdir(parents=True, exist_ok=True)
    tool, failed = FlowImage(), []
    wanted = [p for p in PRODUCTS if not only or p[0].split("_")[0] in only]

    for name, subject in wanted:
        target = OUT / f"{name}.jpg"
        if target.is_file() and target.stat().st_size > 50_000:
            print(f"skip {name}", flush=True)
            continue

        began = time.time()
        result = tool.execute({
            "prompt": prompt_for(subject),
            "model_variant": "2",
            "aspect_ratio": "9:16",
            "n": 1,
            "output_path": str(target),
        })
        took = round(time.time() - began, 1)
        print(f"{name}: {'ok' if result.success else 'FAILED'} ({took}s)", flush=True)
        if not result.success:
            print(f"   {result.error}", flush=True)
            failed.append(name)

    print(f"\ndone: {len(wanted) - len(failed)}/{len(wanted)} products")
    if failed:
        print("failed:", ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "check"
    check()
    if command == "check":
        raise SystemExit(0)
    raise SystemExit(run_images(sys.argv[2:]))
